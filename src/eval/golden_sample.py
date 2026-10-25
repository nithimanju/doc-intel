"""Stratified page sampling for golden-set generation (Step 1 of
docs/golden-set-method.md).

Reads the page catalog built by golden_pages.py and selects a quota of pages
across (source x content-type x position) buckets, biased toward
graphics-heavy pages (tables/diagrams/forms) since that's where naive RAG
fails and therefore where measurement is most valuable. A per-document cap
keeps any single document (AC 43.13-1B alone is 616 of this corpus's 2894
pages) from dominating the sample.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

MAX_PER_DOC = 4
MIN_TOKENS = 40  # skip near-blank pages regardless of bucket


def content_bucket(row: dict) -> str:
    if row["has_figure"] or row["has_table"]:
        return "figure_or_table"
    if row["has_list"]:
        return "list"
    return "prose"


def load_catalog(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
    return rows


def sample(
    rows: list[dict], target_total: int, seed: int
) -> tuple[list[dict], dict[str, int]]:
    rng = random.Random(seed)

    usable = [r for r in rows if r["token_count"] >= MIN_TOKENS and r["position"] != "front_matter"]
    # A small front_matter quota anyway, per the method's own bucket list.
    front_matter = [r for r in rows if r["position"] == "front_matter" and r["token_count"] >= MIN_TOKENS]

    quota = {
        "figure_or_table": round(target_total * 0.35),
        "list": round(target_total * 0.30),
        "prose": round(target_total * 0.30),
    }
    quota_front_matter = max(1, target_total - sum(quota.values()))

    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in usable:
        buckets[content_bucket(r)].append(r)
    for b in buckets.values():
        rng.shuffle(b)
        # Prefer denser pages within each bucket (q3/q4 first).
        b.sort(key=lambda r: {"q4_dense": 0, "q3": 1, "q2": 2, "q1_sparse": 3}.get(r["density_quartile"], 4))

    selected: list[dict] = []
    per_doc_count: dict[str, int] = defaultdict(int)

    def take_from(pool: list[dict], n: int) -> None:
        taken = 0
        for r in pool:
            if taken >= n:
                break
            if per_doc_count[r["doc_id"]] >= MAX_PER_DOC:
                continue
            selected.append(r)
            per_doc_count[r["doc_id"]] += 1
            taken += 1

    for bucket_name, n in quota.items():
        take_from(buckets.get(bucket_name, []), n)

    rng.shuffle(front_matter)
    take_from(front_matter, quota_front_matter)

    # Top up from whatever bucket has the most remaining capacity if short
    # (e.g. too few figure_or_table pages existed to fill that quota).
    shortfall = target_total - len(selected)
    if shortfall > 0:
        remaining = [r for b in buckets.values() for r in b if r not in selected]
        rng.shuffle(remaining)
        take_from(remaining, shortfall)

    counts = {
        "figure_or_table": sum(1 for r in selected if content_bucket(r) == "figure_or_table"),
        "list": sum(1 for r in selected if content_bucket(r) == "list"),
        "prose": sum(1 for r in selected if content_bucket(r) == "prose"),
        "front_matter": sum(1 for r in selected if r["position"] == "front_matter"),
        "nhtsa": sum(1 for r in selected if r["source"] == "nhtsa"),
        "faa": sum(1 for r in selected if r["source"] == "faa"),
        "distinct_docs": len(per_doc_count),
    }
    return selected, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("corpus/.cache/page_catalog.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("corpus/.cache/sampled_pages.jsonl"))
    parser.add_argument("--target-total", type=int, default=85)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--ensure-doc-ids-file",
        type=Path,
        default=None,
        help="optional file of doc_ids to guarantee at least one sampled page each",
    )
    args = parser.parse_args(argv)

    rows = load_catalog(args.catalog)
    selected, counts = sample(rows, args.target_total, args.seed)

    if args.ensure_doc_ids_file is not None:
        wanted = {
            line.strip() for line in args.ensure_doc_ids_file.read_text(encoding="utf-8").splitlines() if line.strip()
        }
        have = {r["doc_id"] for r in selected}
        missing = wanted - have
        by_doc: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_doc[r["doc_id"]].append(r)
        for doc_id in missing:
            pages = [p for p in by_doc.get(doc_id, []) if p["token_count"] >= MIN_TOKENS]
            pages.sort(key=lambda r: (not (r["has_figure"] or r["has_table"]), -r["token_count"]))
            if pages:
                selected.append(pages[0])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in selected:
            fh.write(json.dumps(r) + "\n")

    print(f"sampled {len(selected)} pages -> {args.out}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
