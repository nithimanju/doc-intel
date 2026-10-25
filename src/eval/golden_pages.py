"""Page-level cataloging and stratified sampling for golden-set construction.

Implements Step 1 of docs/golden-set-method.md: classify every page in the
corpus with cheap heuristics, then sample a quota across buckets (source,
content type, position, density) instead of sampling randomly or taking
first pages.

The full-text page catalog is written under corpus/.cache/ (gitignored) --
it is a reproducible derived cache, not curated eval data, and for the
NHTSA slice of the corpus it would otherwise mean committing full page text
of licence `needs_review` documents to a public repo. Only short, curated
evidence quotes (see golden_generate.py) are meant to reach golden/*.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•]|\(?[0-9]{1,2}[.)]|\(?[a-zA-Z][.)])\s+")
MULTI_SPACE_COLUMNS_RE = re.compile(r"\S+(?: {2,}\S+){2,}")


def classify_table(lines: list[str]) -> bool:
    """Heuristic: several lines with 3+ whitespace-aligned columns => a table."""
    hits = sum(1 for ln in lines if MULTI_SPACE_COLUMNS_RE.search(ln))
    return hits >= 3


def classify_list(lines: list[str]) -> bool:
    hits = sum(1 for ln in lines if LIST_MARKER_RE.match(ln))
    return hits >= 3


def classify_figure(page: "pymupdf.Page") -> bool:
    """A graphics-heavy page (table grid, diagram, form, or figure).

    Raster-image presence turned out not to be a useful signal here: most
    pages in this corpus carry a letterhead/background raster regardless of
    content. Vector-drawing primitive count is the better signal -- a bare
    prose page has ~0, while a table grid, diagram or form has dozens to
    hundreds. Calibrated against a 125-page sample (see decisions.md note
    on golden-set tooling): median page has 0 drawings, so 40 is comfortably
    above incidental rules/underlines but below a fully blank page.
    """
    return len(page.get_drawings()) >= 40


def classify_position(page_num: int, total_pages: int, text: str) -> str:
    if total_pages <= 2:
        return "body"
    if page_num == 1:
        return "front_matter"
    lowered = text.lower()
    if page_num >= total_pages - 1 and (
        "appendix" in lowered or "enclosure" in lowered or "attachment" in lowered
    ):
        return "appendix"
    return "body"


def build_catalog(manifest_path: Path, cache_dir: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    rows: list[dict] = []

    for doc in manifest["documents"]:
        raw_path = Path(doc["raw_path"])
        if not raw_path.exists():
            continue
        try:
            pdf = pymupdf.open(raw_path)
        except Exception as exc:  # malformed PDFs are part of the real problem space
            print(f"skip {doc['doc_id']}: cannot open ({exc})")
            continue

        total_pages = pdf.page_count
        for page_num in range(1, total_pages + 1):
            page = pdf[page_num - 1]
            text = page.get_text("text") or ""
            lines = [ln for ln in text.splitlines() if ln.strip()]
            token_count = len(text.split())
            rows.append(
                {
                    "doc_id": doc["doc_id"],
                    "source": doc["source"],
                    "licence": doc["licence"],
                    "raw_path": doc["raw_path"],
                    "page_num": page_num,
                    "total_pages": total_pages,
                    "token_count": token_count,
                    "has_table": classify_table(lines),
                    "has_list": classify_list(lines),
                    "has_figure": classify_figure(page),
                    "position": classify_position(page_num, total_pages, text),
                    "text": text,
                }
            )
        pdf.close()

    # Density quartiles, computed globally over nonzero-token pages.
    token_counts = sorted(r["token_count"] for r in rows if r["token_count"] > 0)
    if token_counts:
        def quartile_cut(q: float) -> int:
            idx = min(len(token_counts) - 1, int(q * len(token_counts)))
            return token_counts[idx]

        q1, q2, q3 = quartile_cut(0.25), quartile_cut(0.50), quartile_cut(0.75)
    else:
        q1 = q2 = q3 = 0

    for r in rows:
        tc = r["token_count"]
        if tc == 0:
            r["density_quartile"] = "empty"
        elif tc <= q1:
            r["density_quartile"] = "q1_sparse"
        elif tc <= q2:
            r["density_quartile"] = "q2"
        elif tc <= q3:
            r["density_quartile"] = "q3"
        else:
            r["density_quartile"] = "q4_dense"

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / "page_catalog.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    print(f"catalogued {len(rows)} pages across {len(manifest['documents'])} manifest docs")
    print(f"density cuts: q1<={q1} q2<={q2} q3<={q3}")
    by_bucket: dict[str, int] = {}
    for r in rows:
        content = "table" if r["has_table"] else ("list" if r["has_list"] else "prose")
        key = f"{r['source']}/{content}/fig={r['has_figure']}/{r['position']}"
        by_bucket[key] = by_bucket.get(key, 0) + 1
    for key in sorted(by_bucket):
        print(f"  {key}: {by_bucket[key]}")

    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("corpus/manifest.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("corpus/.cache"))
    args = parser.parse_args(argv)
    build_catalog(args.manifest, args.cache_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
