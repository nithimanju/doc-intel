"""Find candidate page-pairs sharing an entity, for deliberate multi-hop
question construction (Step 5 of docs/golden-set-method.md).

This does NOT generate multi-hop questions itself -- the method doc is
explicit that asking an LLM to "write a multi-hop question" produces fake
multi-hop (two facts from one page). It only finds real co-occurrence
candidates (same AC number, same NHTSA campaign number, same part number)
across *different* pages, which a human or a careful follow-up pass then
turns into a question that genuinely needs both pages.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ENTITY_PATTERNS = {
    "nhtsa_campaign": re.compile(r"\b\d{2}[A-Z]-?\d{3}\b"),
    "faa_ac_number": re.compile(r"\bAC\s?\d{2,3}(?:[./-]\d+){1,2}[A-Z]?\b", re.IGNORECASE),
    "part_number": re.compile(r"\b[A-Z]{1,4}-?\d{3,6}(?:-\d+)?\b"),
    "dollar_or_measurement": re.compile(r"\b\d+(?:\.\d+)?\s?(?:in-lb|inch-pounds|psi|lbs|volts?|amperes?)\b", re.IGNORECASE),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("corpus/.cache/page_catalog.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("corpus/.cache/multihop_candidates.json"))
    parser.add_argument("--min-token-count", type=int, default=60)
    args = parser.parse_args(argv)

    entity_to_pages: dict[str, list[dict]] = defaultdict(list)
    with args.catalog.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row["token_count"] < args.min_token_count:
                continue
            text = row["text"]
            for kind, pattern in ENTITY_PATTERNS.items():
                for match in set(pattern.findall(text)):
                    key = f"{kind}:{match.upper()}"
                    entity_to_pages[key].append(
                        {"doc_id": row["doc_id"], "page_num": row["page_num"], "source": row["source"]}
                    )

    pairs = []
    for entity, pages in entity_to_pages.items():
        distinct_docs = {p["doc_id"] for p in pages}
        if len(distinct_docs) < 2:
            continue  # same-page or same-doc co-occurrence isn't genuine multi-hop
        pairs.append({"entity": entity, "pages": pages})

    pairs.sort(key=lambda p: -len({pg["doc_id"] for pg in p["pages"]}))
    args.out.write_text(json.dumps(pairs, indent=2), encoding="utf-8")
    print(f"found {len(pairs)} entities shared across >=2 documents -> {args.out}")
    for p in pairs[:15]:
        docs = sorted({pg["doc_id"] for pg in p["pages"]})
        print(f"  {p['entity']}: {docs[:4]}{'...' if len(docs) > 4 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
