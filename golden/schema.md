# Golden Question Schema

Ground truth for Increment 0's evaluation harness. See `CLAUDE.md` ("Golden
set rules") and `docs/golden-set-method.md` for the construction method and
rationale; this file states the schema and the rules themselves so they can
be checked against without re-reading either.

## Schema

```json
{
  "id": "q001",
  "question": "...",
  "answer": "...",
  "answer_type": "single_fact|multi_hop|table_numeric|unanswerable|ambiguous",
  "source_locations": [{"doc_id": "...", "page": 14, "region": "table 3, row 2"}],
  "requires_corpus": true,
  "notes": "why this question exists"
}
```

- `source_locations` is a list because `multi_hop` questions require 2+
  locations, one per fact the question combines. Every other `answer_type`
  has exactly one.
- `source_locations` is always a **document location** (`doc_id` + `page` +
  a human-readable `region`), never a chunk ID. Chunking changes in
  Increment 1; this must survive that change. See the `decisions.md` entry
  on ground-truth granularity.
- `unanswerable` questions still carry `source_locations` -- pointing at
  the page/region that makes the question *plausible* (why someone might
  expect an answer there), even though no answer exists in the corpus.
- `requires_corpus` is always `true` by construction (rule 3 below) and is
  kept as an explicit field, not implied, so the harness can assert it.

## The five rules

1. **Ground truth is a document location, never a chunk ID.** Record
   `{doc_id, page, region}`. Chunking changes in Increment 1; ground truth
   must survive it.
2. **Never generate a question and its answer from the same chunk.** AI may
   draft candidate questions from full pages; answers are verified by the
   human against the source. (This is what makes a question merely
   *AI-drafted* rather than *golden* -- see the verification note below.)
3. **Every question must require the corpus.** Run each candidate against a
   no-context model. If it answers correctly, the question tests nothing --
   cut it or make it more specific.
4. **15% of questions must be unanswerable.** This is the only check on
   hallucination. A system that scores well on answerable questions and
   invents the rest is worse than useless.
5. **Answers must be specific verifiable values**, not summaries or
   opinions.

## Target distribution (~70 questions)

| Type | Share |
|---|---|
| single_fact | 35% |
| multi_hop | 25% |
| table_numeric | 20% |
| unanswerable | 15% |
| ambiguous | 5% |

## Verification status is part of the record, not a side note

`golden/candidates.jsonl` holds AI-drafted candidates that have passed the
four automatable gates (quote fidelity, location-leak, answer-leak,
near-duplicate) plus a blind no-context check (gate 2). They are NOT yet
ground truth. Per `docs/golden-set-method.md`'s one hard rule -- *"What may
never be automated: confirming that the answer is actually correct"* -- a
candidate only moves into `golden/questions.jsonl` after a human opens the
source page and confirms the answer (Pass 2 of Step 4). `src/eval/review_golden.py`
is the tool for doing that pass quickly.

## Self-agreement and difficulty calibration

Per Step 6 of `docs/golden-set-method.md`: re-review a random 10% blind a day
later and record agreement (target >90%); and after the first 20 accepted
questions, run the naive baseline once before building the rest (target
recall@5 in the 0.40-0.80 range -- outside that, the set is miscalibrated,
not just incomplete). Record both numbers in `README.md`.
