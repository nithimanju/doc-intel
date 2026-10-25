"""Four automated gates from Step 3 of docs/golden-set-method.md.

Gate 2 ("ask a model with no context") is deliberately NOT here -- it needs an
LLM call with zero access to the corpus, which this deterministic script
can't honestly do. Run it as a separate blind pass over survivors of these
four gates (see docs/golden-set-method.md Step 3).

Gates implemented:
  1. Quote fidelity    -- evidence_quote appears verbatim on the cited page
  3. Location leak     -- question doesn't name where the answer lives
  4. Answer leak        -- answer string doesn't already appear in the question
  5. Near-duplicate     -- no true embedding model wired up here, so this uses
                           difflib sequence-similarity on (question + evidence)
                           as a documented approximation of cosine similarity.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

LOCATION_LEAK_RE = re.compile(
    r"\b(table\s*\d|figure\s*\d|section\s*\d|paragraph\s*\d|page\s*\d|"
    r"on this page|according to (?:the|this)|as shown (?:in|on)|"
    r"per this (?:circular|manual|report|ac)|in this (?:circular|manual|document))\b",
    re.IGNORECASE,
)

NEAR_DUPLICATE_THRESHOLD = 0.88


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_page_text_index(catalog_path: Path) -> dict[tuple[str, int], str]:
    index: dict[tuple[str, int], str] = {}
    with catalog_path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            index[(row["doc_id"], row["page_num"])] = row["text"]
    return index


def load_candidates(chunk_dir: Path, pattern: str) -> list[dict]:
    candidates: list[dict] = []
    for path in sorted(chunk_dir.glob(pattern)):
        data = json.loads(path.read_text(encoding="utf-8"))
        for c in data:
            if "question" not in c or "skipped_reason" in c:
                continue  # a fork's note about an unusable page, not a candidate
            c["_origin_file"] = path.name
            candidates.append(c)
    return candidates


def gate_quote_fidelity(candidate: dict, page_text_index: dict[tuple[str, int], str]) -> str | None:
    key = (candidate.get("doc_id"), candidate.get("page"))
    page_text = page_text_index.get(key)
    if page_text is None:
        return f"no page text found for {key}"
    quote = candidate.get("evidence_quote", "")
    if normalize_ws(quote) not in normalize_ws(page_text):
        return "evidence_quote not found verbatim on cited page"
    return None


def gate_location_leak(candidate: dict) -> str | None:
    if LOCATION_LEAK_RE.search(candidate.get("question", "")):
        return "question names a table/section/page/figure location"
    return None


def gate_answer_leak(candidate: dict) -> str | None:
    answer = normalize_ws(candidate.get("answer", "")).lower()
    question = normalize_ws(candidate.get("question", "")).lower()
    if len(answer) >= 4 and answer in question:
        return "answer string appears inside the question"
    return None


def gate_near_duplicate(candidates: list[dict]) -> dict[int, str]:
    """Pairwise check over survivors so far; returns {index: reason} for later dupes."""
    rejected: dict[int, str] = {}
    signatures: list[str] = []
    for i, c in enumerate(candidates):
        sig = normalize_ws(c.get("question", "") + " " + c.get("evidence_quote", "")).lower()
        is_dup = False
        for j, prior_sig in enumerate(signatures):
            if j in rejected:
                continue
            ratio = difflib.SequenceMatcher(None, sig, prior_sig).ratio()
            if ratio >= NEAR_DUPLICATE_THRESHOLD:
                rejected[i] = f"near-duplicate of candidate {j} (similarity {ratio:.2f})"
                is_dup = True
                break
        signatures.append(sig)
        if not is_dup:
            pass
    return rejected


def run_gates(candidates: list[dict], page_text_index: dict[tuple[str, int], str]) -> tuple[list[dict], list[dict]]:
    survivors: list[dict] = []
    rejected: list[dict] = []

    stage_one: list[dict] = []
    for c in candidates:
        reason = gate_quote_fidelity(c, page_text_index) or gate_location_leak(c) or gate_answer_leak(c)
        if reason:
            rejected.append({**c, "rejected_gate": "1/3/4", "rejected_reason": reason})
        else:
            stage_one.append(c)

    dup_map = gate_near_duplicate(stage_one)
    for i, c in enumerate(stage_one):
        if i in dup_map:
            rejected.append({**c, "rejected_gate": "5_near_duplicate", "rejected_reason": dup_map[i]})
        else:
            survivors.append(c)

    return survivors, rejected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path("corpus/.cache"))
    parser.add_argument("--chunk-pattern", type=str, default="candidates_chunk_*.json")
    parser.add_argument("--catalog", type=Path, default=Path("corpus/.cache/page_catalog.jsonl"))
    parser.add_argument("--survivors-out", type=Path, default=Path("corpus/.cache/gate_survivors.json"))
    parser.add_argument("--rejected-out", type=Path, default=Path("corpus/.cache/gate_rejected.json"))
    args = parser.parse_args(argv)

    page_text_index = load_page_text_index(args.catalog)
    candidates = load_candidates(args.cache_dir, args.chunk_pattern)
    survivors, rejected = run_gates(candidates, page_text_index)

    args.survivors_out.write_text(json.dumps(survivors, indent=2), encoding="utf-8")
    args.rejected_out.write_text(json.dumps(rejected, indent=2), encoding="utf-8")

    by_reason: dict[str, int] = {}
    for r in rejected:
        key = r["rejected_gate"]
        by_reason[key] = by_reason.get(key, 0) + 1

    print(f"loaded {len(candidates)} raw candidates")
    print(f"survivors (gates 1,3,4,5): {len(survivors)}")
    print(f"rejected: {len(rejected)}")
    for k, v in sorted(by_reason.items()):
        print(f"  rejected by {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
