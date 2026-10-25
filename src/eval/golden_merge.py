"""Merge the gated single_fact/table_numeric pool with the manually
constructed multi_hop/unanswerable/ambiguous sets into golden/candidates.jsonl,
in the schema review_golden.py expects (source_locations as a list, matching
golden/schema.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize_single(c: dict) -> dict:
    return {
        "question": c["question"],
        "answer": c["answer"],
        "answer_type": c["answer_type"],
        "confidence": c.get("confidence", "medium"),
        "source": c.get("source"),
        "licence": c.get("licence"),
        "source_locations": [
            {"doc_id": c["doc_id"], "page": c["page"], "region": c.get("region_hint", "")}
        ],
        "evidence_quotes": [c.get("evidence_quote", "")],
        "notes": c.get("notes", f"gate2=requires_corpus; origin={c.get('_origin_file', '')}"),
        "pass1_status": "pending",
        "pass2_status": "pending",
    }


def normalize_constructed(c: dict) -> dict:
    quotes = [q for q in (c.get("evidence_quote"), c.get("evidence_quote_2")) if q]
    return {
        "question": c["question"],
        "answer": c["answer"],
        "answer_type": c["answer_type"],
        "confidence": c.get("confidence", "medium"),
        "source": c.get("source"),
        "licence": c.get("licence"),
        "source_locations": c.get("source_locations", []),
        "evidence_quotes": quotes,
        "notes": c.get("notes", ""),
        "pass1_status": "pending",
        "pass2_status": "pending",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-pool", type=Path, default=Path("corpus/.cache/final_pool_single_table.json"))
    parser.add_argument("--multihop", type=Path, default=Path("corpus/.cache/multihop_manual.json"))
    parser.add_argument("--unanswerable", type=Path, default=Path("corpus/.cache/unanswerable_ambiguous_manual.json"))
    parser.add_argument("--out", type=Path, default=Path("golden/candidates.jsonl"))
    args = parser.parse_args(argv)

    single = json.loads(args.single_pool.read_text(encoding="utf-8"))
    multihop = json.loads(args.multihop.read_text(encoding="utf-8"))
    unans = json.loads(args.unanswerable.read_text(encoding="utf-8"))

    merged = [normalize_single(c) for c in single]
    merged += [normalize_constructed(c) for c in multihop]
    merged += [normalize_constructed(c) for c in unans]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in merged:
            fh.write(json.dumps(row) + "\n")

    from collections import Counter

    print(f"wrote {len(merged)} candidates -> {args.out}")
    print(Counter(r["answer_type"] for r in merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
