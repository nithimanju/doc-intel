# doc-intel — Project Rules

A public document-intelligence system built to demonstrate production GenAI
engineering: retrieval, agents, evaluation, security, and deployment.

**This file is binding. Follow it over general convenience.**

---

## Project thesis

Evaluation is built **before** the system. Every improvement must carry a
measured delta against a recorded baseline. The deliverable is not "a RAG
system" — it is a sequence of measured improvements with the numbers to prove
them.

## Build order (do not reorder)

| Increment | Content | Gate to pass before moving on |
|---|---|---|
| 0 | Eval harness, golden set, naive baseline, CI | Baseline numbers recorded in README |
| 1 | Hybrid retrieval, reranking, query transforms | Measured delta per technique |
| 2 | Agents: tools, MCP, memory, state, HITL | Task success rate measured |
| 3 | Security, guardrails, red team, cost, observability | Threat model + block rate |
| 4 | React/TS frontend, deploy, CI/CD | Public URL, p95 latency |

---

## The three guards on AI-assisted development

The human owns architecture. AI helps implementation. These are non-negotiable.

### 1. Decision log before code

Every component choice gets an entry in `decisions.md` **before** any code is
written. Required fields:

```
## [date] <decision title>
**Chose:** ...
**Rejected:** ... because ...
**Trade-off accepted:** ...
**How we'd know this was wrong:** ...
```

If asked to implement something that has no decision entry, **stop and ask for
the decision first.** Do not infer it.

### 2. Hand-written evaluation logic

`src/evaluate/` is written by the human, not generated. Metrics (recall@k,
precision@k, MRR, NDCG, hit rate) are implemented from the definitions, then
verified against a library, and any disagreement is reconciled and documented.

Do not generate this module. If asked to, remind the author of this rule.

### 3. No-AI debug drill

Once per increment the author breaks something deliberately and fixes it without
AI help. Record it in `decisions.md` under a `## Debug drill` heading.

---

## Golden set rules

Ground truth lives in `golden/questions.jsonl`. These rules exist because
violating them silently invalidates every number downstream.

1. **Ground truth is a document location, never a chunk id.** Record
   `{doc_id, page, region}`. Chunking changes in Increment 1; ground truth must
   survive it.
2. **Never generate a question and its answer from the same chunk.** That makes
   "correct retrieval = source chunk" true by construction and the eval set then
   measures the chunker against itself. AI may draft candidate questions from
   full pages; answers are verified by the human against the source.
3. **Every question must require the corpus.** Run each candidate against a
   no-context model. If it answers correctly, the question tests nothing — cut
   it or make it more specific.
4. **15% of questions must be unanswerable.** This is the only check on
   hallucination. A system that scores well on answerable questions and invents
   the rest is worse than useless.
5. **Answers must be specific verifiable values**, not summaries or opinions.

Target distribution across ~70 questions:

| Type | Share |
|---|---|
| single_fact | 35% |
| multi_hop | 25% |
| table_numeric | 20% |
| unanswerable | 15% |
| ambiguous | 5% |

Schema:

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

---

## Corpus rules

- Minimum 200 documents. Retrieval problems are invisible below ~100.
- Every document recorded in `corpus/manifest.json` with: `doc_id`,
  `source_url`, `retrieved_at`, `licence`, `page_count`, `sha256`, `description`.
- **Only publicly redistributable documents.** This repo becomes a public demo.
  US federal government works are public domain. Manufacturer documents hosted
  by a government agency are NOT — see `docs/corpus-requirements.md`.
- `corpus/raw/` holds untouched source files. Never edit in place.

---

## Repository layout

```
doc-intel/
  CLAUDE.md
  decisions.md
  docs/
  corpus/
    manifest.json
    raw/
  golden/
    questions.jsonl
    schema.md
  src/
    corpus/          # fetch + corpus tooling
    eval/            # golden-set tooling
    retrieve/
    evaluate/        # human-written metrics harness
  tests/
  .github/workflows/
  README.md
```

---

## README requirements

`README.md` must always carry a results table with dates, so the measured
progression is visible to anyone who opens the repo:

| Date | Config | recall@1 | recall@5 | MRR | NDCG@10 | Notes |
|---|---|---|---|---|---|---|

Never remove a row. The progression is the point.

---

## CI

`.github/workflows/` runs the eval harness on every push and fails on
regression beyond a stated tolerance. The tolerance value must have a
`decisions.md` entry explaining how it was chosen.

---

## Conventions

- Python 3.11+, type hints throughout
- `ruff` for lint, `pytest` for tests
- No secrets in the repo; `.env` for local config, `.env.example` committed
- Commit messages state what changed and why, not just what
