"""Corpus fetcher for doc-intel.

Pulls documents from three independent public sources and records provenance
in ``corpus/manifest.json``:

- NHTSA recall-communication PDFs (indexed by the ODI flat files)
- DoD issuances (manuals, then instructions) from esd.whs.mil
- FAA Advisory Circulars via the National Transportation Library's ROSA P
  repository (rosap.ntl.bts.gov), which research found to be a plain
  server-rendered Drupal site with no OAI-PMH/REST API -- it still requires a
  listing-page -> record-page -> PDF-link hop, but it is one uniform,
  paginated collection instead of faa.gov's multi-topic-ID crawl, so it
  replaces that source rather than supplementing it.

See docs/corpus-requirements.md for the full research and acceptance checks.

IMPORTANT -- licence note on the NHTSA source:
The flat-file "recall communications" index gives real PDF filenames (owner
notification letters, manufacturer notification letters, quarterly reports,
etc.), served from static.nhtsa.gov. These documents are *manufacturer
authored* but filed with NHTSA under mandatory-disclosure regulation
(49 CFR Part 573) -- structurally the same situation CLAUDE.md flags for
NHTSA Technical Service Bulletins ("hosted by a government agency" is not the
same as "public domain"). This fetcher therefore records their licence as
``needs_review`` rather than assuming public domain, per the acceptance
check "every entry has a non-empty licence field that was actually
determined, not assumed." A human must resolve this before the NHTSA slice
of the corpus is treated as safe to redistribute publicly.

DoD issuances at esd.whs.mil return HTTP 403 to plain HTTP clients (curl and
``requests`` both blocked in testing, with or without browser-style headers)
-- this looks like bot-mitigation that only a real browser passes. The DoD
fetcher is implemented correctly for a client that *can* reach the site, but
in this environment it will fail closed: it logs the block and reports zero
documents rather than crashing, and the shortfall is made up from the
richest source (NHTSA) per the "top up from the richest source if short"
acceptance rule.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import io
import json
import logging
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - exercised via logged degradation
    PdfReader = None

LOG = logging.getLogger("fetch_corpus")

USER_AGENT = (
    "doc-intel-corpus-fetcher/0.1 "
    "(public-interest research corpus; contact: nithinmanjunathml@gmail.com)"
)

LICENCE_GOV_WORK_PUBLIC_DOMAIN = "us_government_work-public_domain"
LICENCE_NEEDS_REVIEW = "needs_review-manufacturer_authored_mandatory_disclosure"

NHTSA_FLAT_FILE_BASE = "https://static.nhtsa.gov/odi/ffdd/rcl/"
NHTSA_DOC_BASE = "https://static.nhtsa.gov/odi/rcl/"
NHTSA_BUCKETS = [
    "RCL_FROM_2025_2026.zip",
    "RCL_FROM_2025_2025.zip",
    "RCL_FROM_2020_2024.zip",
    "RCL_FROM_2015_2019.zip",
    "RCL_FROM_2010_2014.zip",
    "RCL_FROM_2005_2009.zip",
    "RCL_FROM_2000_2004.zip",
]

DOD_INDEXES = {
    "dodm": "https://www.esd.whs.mil/DD/issuances/dodm/",
    "dodi": "https://www.esd.whs.mil/DD/issuances/dodi/",
}
DOD_PDF_LINK_RE = re.compile(
    r'<a[^>]+href="(/Portals/54/Documents/DD/issuances/[^"]+?\.pdf[^"]*)"[^>]*>([^<]*)</a>',
    re.IGNORECASE,
)

ROSAP_BASE = "https://rosap.ntl.bts.gov"
ROSAP_FAA_COLLECTION_ID = "dot:65448"
ROSAP_RECORD_LINK_RE = re.compile(r'href="(/view/dot/\d+)"')
ROSAP_PDF_LINK_RE = re.compile(
    r'href="(https://rosap\.ntl\.bts\.gov/view/dot/\d+/[^"]+?\.pdf)"', re.IGNORECASE
)
ROSAP_TITLE_RE = re.compile(r"<title>([^<]*)</title>")


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip().lower())
    return re.sub(r"-{2,}", "-", text).strip("-")


@dataclasses.dataclass
class SourceStats:
    name: str
    requested: int = 0
    fetched: int = 0
    skipped: int = 0
    failed: int = 0


class PoliteSession:
    """A requests.Session wrapper that rate-limits and identifies itself."""

    def __init__(self, delay: float) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay = delay
        self._last_request = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        self._throttle()
        return self.session.get(url, timeout=30, **kwargs)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()


class Manifest:
    """Loads, resumes against, and saves corpus/manifest.json."""

    def __init__(self, path: Path) -> None:
        self.path = path
        if path.exists() and path.stat().st_size > 0:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            data = {"version": 1, "documents": []}
        self.version: int = data.get("version", 1)
        self.documents: list[dict] = data.get("documents", [])
        self._by_id: dict[str, dict] = {d["doc_id"]: d for d in self.documents}

    def already_has(self, doc_id: str) -> bool:
        """True if doc_id is recorded and its raw file still matches its sha256."""
        entry = self._by_id.get(doc_id)
        if entry is None:
            return False
        raw_path = Path(entry["raw_path"])
        if not raw_path.exists():
            return False
        try:
            return compute_sha256(raw_path.read_bytes()) == entry["sha256"]
        except OSError:
            return False

    def add(self, entry: dict) -> None:
        existing = self._by_id.get(entry["doc_id"])
        if existing is not None:
            self.documents.remove(existing)
        self.documents.append(entry)
        self._by_id[entry["doc_id"]] = entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"version": self.version, "documents": self.documents}, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_page_count(data: bytes) -> tuple[int | None, str | None]:
    if PdfReader is None:
        return None, "pypdf not installed"
    try:
        reader = PdfReader(io.BytesIO(data))
        return len(reader.pages), None
    except Exception as exc:  # pypdf raises assorted exceptions on malformed PDFs
        return None, f"{type(exc).__name__}: {exc}"


def download_and_verify(
    session: PoliteSession, url: str, dest: Path, retries: int = 3
) -> bytes | None:
    """GET url with retries, reject anything that isn't a real PDF, write to dest."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url)
        except requests.RequestException as exc:
            LOG.warning("request error (%d/%d) for %s: %s", attempt, retries, url, exc)
            time.sleep(2**attempt)
            continue

        if resp.status_code == 404:
            LOG.warning("404 for %s", url)
            return None
        if resp.status_code in (403, 429, 500, 502, 503, 504):
            LOG.warning(
                "status %s for %s (attempt %d/%d)", resp.status_code, url, attempt, retries
            )
            if resp.status_code == 403:
                # Bot-mitigation rejections don't improve with retries.
                return None
            time.sleep(2**attempt)
            continue
        if resp.status_code != 200:
            LOG.warning("unexpected status %s for %s", resp.status_code, url)
            return None

        content = resp.content
        if content[:4] != b"%PDF":
            LOG.warning("rejected non-PDF content (likely an HTML error page) at %s", url)
            return None

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return content
    return None


def build_entry(
    *,
    doc_id: str,
    source: str,
    source_url: str,
    raw_path: Path,
    licence: str,
    description: str,
    data: bytes,
    licence_note: str | None = None,
) -> dict:
    page_count, parse_error = compute_page_count(data)
    entry: dict = {
        "doc_id": doc_id,
        "source": source,
        "source_url": source_url,
        "raw_path": raw_path.as_posix(),
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "licence": licence,
        "page_count": page_count,
        "sha256": compute_sha256(data),
        "bytes": len(data),
        "description": description,
    }
    if licence_note:
        entry["licence_note"] = licence_note
    if parse_error:
        entry["parse_error"] = parse_error
    return entry


# --------------------------------------------------------------------------
# NHTSA: recall-communication PDFs, indexed by the ODI flat files
# --------------------------------------------------------------------------


def _nhtsa_pdf_years(nhtsa_id: str) -> list[str]:
    """Candidate four-digit years for an NHTSA ID like '25C004' or '14V123000'."""
    match = re.match(r"(\d{2})", nhtsa_id)
    if not match:
        return []
    yy = int(match.group(1))
    # Recalls flat file covers 1967+; NHTSA IDs are YY-prefixed within century.
    primary = f"20{yy:02d}" if yy <= 69 else f"19{yy:02d}"
    secondary = f"19{yy:02d}" if primary.startswith("20") else f"20{yy:02d}"
    return [primary, secondary]


def _nhtsa_list_candidates(session: PoliteSession) -> dict[str, dict]:
    """document filename -> flat-file row, deduplicated, across all buckets."""
    candidates: dict[str, dict] = {}
    for bucket in NHTSA_BUCKETS:
        url = NHTSA_FLAT_FILE_BASE + bucket
        try:
            resp = session.get(url)
            resp.raise_for_status()
        except requests.RequestException as exc:
            LOG.warning("NHTSA bucket %s unreachable: %s", bucket, exc)
            continue
        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
        except zipfile.BadZipFile:
            LOG.warning("NHTSA bucket %s is not a valid zip", bucket)
            continue
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with zf.open(name) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                for row in csv.DictReader(text):
                    doc_name = (row.get("DOCUMENT NAME") or "").strip()
                    nhtsa_id = (row.get("NHTSA ID") or "").strip()
                    if not doc_name or not nhtsa_id or doc_name in candidates:
                        continue
                    candidates[doc_name] = row
    return candidates


def _diversify_by_make(candidates: dict[str, dict], pool_size: int) -> list[tuple[str, dict]]:
    """Round-robin across manufacturers so one OEM's filings don't dominate."""
    by_make: dict[str, list[tuple[str, dict]]] = {}
    for doc_name, row in candidates.items():
        make = (row.get("MAKE") or "UNKNOWN").strip().upper() or "UNKNOWN"
        by_make.setdefault(make, []).append((doc_name, row))
    makes = sorted(by_make)
    if not makes:
        return []
    selected: list[tuple[str, dict]] = []
    idx = 0
    safety_limit = pool_size * len(makes) + len(makes) + 10
    spins = 0
    while len(selected) < pool_size and spins < safety_limit:
        make = makes[idx % len(makes)]
        bucket = by_make[make]
        if bucket:
            selected.append(bucket.pop(0))
        idx += 1
        spins += 1
    return selected


def fetch_nhtsa(
    session: PoliteSession, manifest: Manifest, out_dir: Path, target_new: int
) -> SourceStats:
    stats = SourceStats("nhtsa")
    if target_new <= 0:
        return stats

    candidates = _nhtsa_list_candidates(session)
    pool = _diversify_by_make(candidates, target_new * 4)

    for doc_name, row in pool:
        if stats.fetched >= target_new:
            break
        stats.requested += 1
        doc_id = f"nhtsa-{slugify(Path(doc_name).stem)}"
        if manifest.already_has(doc_id):
            stats.skipped += 1
            continue

        nhtsa_id = row["NHTSA ID"].strip()
        make = (row.get("MAKE") or "").strip()
        model = (row.get("MODEL") or "").strip()
        model_year = (row.get("MODEL YEAR") or "").strip()
        summary = (row.get("SUMMARY") or "").strip()

        data = None
        chosen_url = ""
        for year in _nhtsa_pdf_years(nhtsa_id):
            candidate_url = f"{NHTSA_DOC_BASE}{year}/{doc_name}"
            dest = out_dir / "nhtsa" / doc_name
            data = download_and_verify(session, candidate_url, dest)
            if data is not None:
                chosen_url = candidate_url
                break

        if data is None:
            stats.failed += 1
            continue

        description = f"{make} {model} ({model_year}) recall communication {nhtsa_id}: {summary}"
        entry = build_entry(
            doc_id=doc_id,
            source="nhtsa",
            source_url=chosen_url,
            raw_path=out_dir / "nhtsa" / doc_name,
            licence=LICENCE_NEEDS_REVIEW,
            description=description.strip()[:500],
            data=data,
            licence_note=(
                "Manufacturer-authored recall communication filed with NHTSA under "
                "49 CFR Part 573 mandatory disclosure. Hosted by a federal agency but "
                "not a government-authored work -- public-domain status is NOT "
                "confirmed. Do not treat as public domain without legal review; see "
                "CLAUDE.md's TSB warning, which applies to the same fact pattern."
            ),
        )
        manifest.add(entry)
        manifest.save()
        stats.fetched += 1

    return stats


# --------------------------------------------------------------------------
# DoD issuances (manuals preferred over instructions)
# --------------------------------------------------------------------------


def fetch_dod(session: PoliteSession, manifest: Manifest, out_dir: Path, limit: int) -> SourceStats:
    stats = SourceStats("dod")
    if limit <= 0:
        return stats

    found: dict[str, str] = {}  # absolute url -> link text
    for kind, index_url in DOD_INDEXES.items():
        try:
            resp = session.get(index_url)
            resp.raise_for_status()
        except requests.RequestException as exc:
            LOG.warning(
                "DoD index %s unreachable (%s). esd.whs.mil returns 403 to plain HTTP "
                "clients in testing (bot-mitigation) -- this source needs a real "
                "browser session to crawl; see docs/corpus-requirements.md. Continuing "
                "without it.",
                index_url,
                exc,
            )
            continue
        for match in DOD_PDF_LINK_RE.finditer(resp.text):
            href, text = match.group(1), match.group(2).strip()
            abs_url = urljoin(index_url, href)
            found.setdefault(abs_url, text or Path(urlsplit(abs_url).path).stem)

    # Manuals (dodm) carry more structure than directives/instructions; since both
    # indexes feed one dict, URLs under /issuances/dodm/ sort before others lexically
    # often enough, but be explicit about preference instead of relying on that.
    ordered = sorted(found.items(), key=lambda kv: ("/issuances/dodm/" not in kv[0], kv[0]))

    for url, link_text in ordered:
        if stats.fetched >= limit:
            break
        stats.requested += 1
        clean_path = urlsplit(url).path
        filename = Path(clean_path).name
        doc_id = f"dod-{slugify(Path(filename).stem)}"
        if manifest.already_has(doc_id):
            stats.skipped += 1
            continue

        dest = out_dir / "dod" / filename
        data = download_and_verify(session, url, dest)
        if data is None:
            stats.failed += 1
            continue

        entry = build_entry(
            doc_id=doc_id,
            source="dod",
            source_url=url,
            raw_path=dest,
            licence=LICENCE_GOV_WORK_PUBLIC_DOMAIN,
            description=link_text[:500],
            data=data,
        )
        manifest.add(entry)
        manifest.save()
        stats.fetched += 1

    return stats


# --------------------------------------------------------------------------
# FAA Advisory Circulars, via the National Transportation Library (rosap)
# --------------------------------------------------------------------------


def _rosap_record_paths(session: PoliteSession, cap: int) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    start = 0
    page_size = 100
    while len(paths) < cap:
        url = (
            f"{ROSAP_BASE}/cbrowse?parentId={ROSAP_FAA_COLLECTION_ID}"
            f"&maxResults={page_size}&start={start}"
        )
        try:
            resp = session.get(url)
            resp.raise_for_status()
        except requests.RequestException as exc:
            LOG.warning("rosap listing page failed at start=%d: %s", start, exc)
            break
        page_paths = ROSAP_RECORD_LINK_RE.findall(resp.text)
        new_paths = [p for p in page_paths if p not in seen]
        if not new_paths:
            break
        for p in new_paths:
            seen.add(p)
            paths.append(p)
        start += page_size
    return paths[:cap]


def _fetch_faa_record(
    session: PoliteSession, manifest: Manifest, out_dir: Path, path: str, stats: SourceStats
) -> None:
    """Fetch one rosap /view/dot/<id> record and add it to the manifest if new."""
    stats.requested += 1
    record_id = path.rsplit("/", 1)[-1]
    doc_id = f"faa-{record_id}"
    if manifest.already_has(doc_id):
        stats.skipped += 1
        return

    record_url = ROSAP_BASE + path
    try:
        resp = session.get(record_url)
        resp.raise_for_status()
    except requests.RequestException as exc:
        LOG.warning("rosap record %s unreachable: %s", record_url, exc)
        stats.failed += 1
        return

    pdf_match = ROSAP_PDF_LINK_RE.search(resp.text)
    if not pdf_match:
        LOG.warning("no PDF link found on rosap record %s", record_url)
        stats.failed += 1
        return
    pdf_url = pdf_match.group(1)

    title_match = ROSAP_TITLE_RE.search(resp.text)
    title = title_match.group(1).strip() if title_match else record_id

    filename = Path(urlsplit(pdf_url).path).name
    dest = out_dir / "faa" / filename
    data = download_and_verify(session, pdf_url, dest)
    if data is None:
        stats.failed += 1
        return

    entry = build_entry(
        doc_id=doc_id,
        source="faa",
        source_url=pdf_url,
        raw_path=dest,
        licence=LICENCE_GOV_WORK_PUBLIC_DOMAIN,
        description=title[:500],
        data=data,
    )
    manifest.add(entry)
    manifest.save()
    stats.fetched += 1


def fetch_faa(session: PoliteSession, manifest: Manifest, out_dir: Path, limit: int) -> SourceStats:
    """Crawl the collection's default (AC-number) ordering for the first `limit` records.

    Note: the collection is ordered by AC number family, not by technical depth,
    so a plain limit-N crawl from start=0 over-represents the earliest AC 00-x
    administrative/checklist circulars. For deliberately technical, table-heavy
    circulars (the stated reason this source was chosen -- see decisions.md),
    use fetch_faa_by_paths() with curated record paths instead.
    """
    stats = SourceStats("faa")
    if limit <= 0:
        return stats

    record_paths = _rosap_record_paths(session, cap=limit * 3)
    for path in record_paths:
        if stats.fetched >= limit:
            break
        _fetch_faa_record(session, manifest, out_dir, path, stats)

    return stats


def fetch_faa_by_paths(
    session: PoliteSession, manifest: Manifest, out_dir: Path, record_paths: list[str]
) -> SourceStats:
    """Fetch a curated, explicit list of rosap /view/dot/<id> record paths."""
    stats = SourceStats("faa")
    for path in record_paths:
        _fetch_faa_record(session, manifest, out_dir, path, stats)
    return stats


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("corpus/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("corpus/manifest.json"))
    parser.add_argument("--target-total", type=int, default=200)
    parser.add_argument("--nhtsa-count", type=int, default=60)
    parser.add_argument("--dod-count", type=int, default=25)
    parser.add_argument("--faa-count", type=int, default=25)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between HTTP requests")
    parser.add_argument(
        "--sources",
        type=str,
        default="nhtsa,dod,faa",
        help="comma-separated subset of: nhtsa,dod,faa",
    )
    parser.add_argument(
        "--faa-paths-file",
        type=Path,
        default=None,
        help=(
            "optional text file of explicit rosap /view/dot/<id> paths (one per "
            "line) to fetch in addition to --faa-count's default crawl -- use "
            "this for curated technical circulars the default AC-number-ordered "
            "crawl would miss (see fetch_faa's docstring)"
        ),
    )
    return parser.parse_args(argv)


def print_summary(all_stats: list[SourceStats]) -> None:
    header = f"{'source':<8} {'requested':>9} {'fetched':>8} {'skipped':>8} {'failed':>7}"
    LOG.info(header)
    LOG.info("-" * len(header))
    for s in all_stats:
        LOG.info(f"{s.name:<8} {s.requested:>9} {s.fetched:>8} {s.skipped:>8} {s.failed:>7}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if PdfReader is None:
        LOG.warning("pypdf is not installed; page_count will be null for every document")

    manifest = Manifest(args.manifest)
    session = PoliteSession(args.delay)
    sources = {s.strip() for s in args.sources.split(",") if s.strip()}

    all_stats: list[SourceStats] = []
    if "nhtsa" in sources:
        all_stats.append(fetch_nhtsa(session, manifest, args.out_dir, args.nhtsa_count))
    if "dod" in sources:
        all_stats.append(fetch_dod(session, manifest, args.out_dir, args.dod_count))
    if "faa" in sources:
        all_stats.append(fetch_faa(session, manifest, args.out_dir, args.faa_count))
        if args.faa_paths_file is not None:
            paths = [
                line.strip()
                for line in args.faa_paths_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            all_stats.append(fetch_faa_by_paths(session, manifest, args.out_dir, paths))

    total = len(manifest.documents)
    if total < args.target_total and "nhtsa" in sources:
        shortfall = args.target_total - total
        LOG.info(
            "corpus below target (%d/%d documents); topping up %d from NHTSA, "
            "the richest source",
            total,
            args.target_total,
            shortfall,
        )
        all_stats.append(fetch_nhtsa(session, manifest, args.out_dir, shortfall))

    manifest.save()
    print_summary(all_stats)
    LOG.info("total documents in manifest: %d", len(manifest.documents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
