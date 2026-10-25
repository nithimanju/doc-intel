"""Export golden/candidates.jsonl + page context text into a single JSON
payload for the mobile/offline-friendly Pass-2 review Artifact.

This lets Pass 2 happen away from the local repo (page images/catalog stay
local, but the text excerpt a human needs to confirm an answer travels with
the export).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def page_excerpt(catalog_index: dict[tuple[str, int], str], doc_id: str | None, page, around: str) -> str:
    if not doc_id or page is None:
        return ""
    text = catalog_index.get((doc_id, page), "")
    if not text:
        return ""
    if not around or around not in text:
        return text[:800]
    idx = text.find(around)
    start = max(0, idx - 300)
    end = min(len(text), idx + len(around) + 300)
    return text[start:end]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=Path("golden/candidates.jsonl"))
    parser.add_argument("--catalog", type=Path, default=Path("corpus/.cache/page_catalog.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("corpus/.cache/review_export.json"))
    args = parser.parse_args(argv)

    catalog_index: dict[tuple[str, int], str] = {}
    if args.catalog.exists():
        with args.catalog.open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                catalog_index[(row["doc_id"], row["page_num"])] = row["text"]

    candidates = []
    with args.candidates.open(encoding="utf-8") as fh:
        for line in fh:
            candidates.append(json.loads(line))

    export = []
    for i, c in enumerate(candidates):
        quotes = c.get("evidence_quotes", [])
        locations = c.get("source_locations", [])
        contexts = []
        for idx, loc in enumerate(locations):
            around = quotes[idx] if idx < len(quotes) else (quotes[0] if quotes else "")
            contexts.append(
                {
                    "doc_id": loc.get("doc_id"),
                    "page": loc.get("page"),
                    "region": loc.get("region", ""),
                    "excerpt": page_excerpt(catalog_index, loc.get("doc_id"), loc.get("page"), around),
                }
            )
        export.append(
            {
                "idx": i,
                "question": c["question"],
                "answer": c["answer"],
                "answer_type": c["answer_type"],
                "confidence": c.get("confidence", ""),
                "source": c.get("source", ""),
                "licence": c.get("licence", ""),
                "evidence_quotes": quotes,
                "notes": c.get("notes", ""),
                "contexts": contexts,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(export), encoding="utf-8")
    print(f"exported {len(export)} candidates -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
