#!/usr/bin/env bash
# Creates the Increment 0 baseline issues in the current repo's GitHub remote.
# Prerequisites: gh CLI authenticated (`gh auth login`), run from the repo root.
#
# Usage:  bash create-increment-0-issues.sh
#
# Safe to inspect first:  bash -n create-increment-0-issues.sh

set -euo pipefail

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

echo "Creating labels..."
gh label create "increment-0"  --color "0E8A16" --description "Eval harness and naive baseline" --force
gh label create "blocking"     --color "B60205" --description "Blocks the increment's definition of done" --force
gh label create "ingestion"    --color "1D76DB" --description "Extraction, chunking, embedding, storage" --force
gh label create "retrieval"    --color "5319E7" --description "Retrieval and scoring" --force
gh label create "infra"        --color "FBCA04" --description "Containers, schema, CI" --force
gh label create "analysis"     --color "006B75" --description "Measurement and error analysis" --force

echo "Creating issues..."

gh issue create --label "increment-0" --title "0.1 Write decisions.md entries before any code" --body "$(cat <<'EOF'
Every component choice needs a decision entry **before** implementation.

Entries required:
- Document extraction (Docling; rejected alternatives and why)
- Chunking baseline (Docling HybridChunker as baseline, own strategy to beat it in Increment 1)
- Embedding model (EmbeddingGemma; note the deliberate choice of a modest baseline embedder to preserve headroom)
- Storage (pgvector now, canonical source separate, Neo4j gated on Increment 2 measurement)
- Vector index type (HNSW vs IVFFlat) and parameters

Each entry states: what was chosen, what was rejected and why, the trade-off accepted, and how I would know the decision was wrong.

**Done when:** five entries committed, each naming a rejected alternative.
EOF
)"

gh issue create --label "increment-0,ingestion" --title "0.2 Docling integration with HybridChunker baseline" --body "$(cat <<'EOF'
Integrate Docling for layout-aware extraction and use its **HybridChunker** as the chunking baseline.

HybridChunker is deliberately the baseline, not the final answer. A custom layout-aware chunker in Increment 1 must beat it on measured numbers — "I wrote my own chunker" is unfalsifiable without this comparison.

Requirements:
- Resumable: key on `source_hash`, skip completed documents
- Per-document parse status recorded (success / partial / failed) with the error
- Chunk output carries page number and region/bbox from Docling, not just text
- Parse failures are recorded, never silently dropped

**Done when:** pipeline parses the pilot set, failures are visible in a status table, and chunks carry page and region.
EOF
)"

gh issue create --label "increment-0,ingestion,blocking" --title "0.3 Design and migrate the chunk metadata schema" --body "$(cat <<'EOF'
The schema is where the golden-set join lives. Getting it wrong means re-ingesting everything.

Required columns on the chunk table:
- `chunk_id`, `doc_id`, `chunk_index`
- `page`, `region` (bbox or structural locator)
- `text`
- `chunk_type` (table / prose / list / heading)
- `section_heading`
- `token_count`
- `source_hash`
- `index_version_id` (FK to the index version table, issue 0.5)

Canonical document table separate from chunks: `doc_id`, `source_url`, `licence`, `page_count`, `sha256`, `retrieved_at`.

Use real migrations, not ad-hoc DDL.

**Done when:** migrations apply cleanly from empty, and the schema supports resolving a chunk back to a page and region.
EOF
)"

gh issue create --label "increment-0,infra" --title "0.4 pgvector infrastructure: docker-compose, volume, extension, migrations" --body "$(cat <<'EOF'
Local Postgres with pgvector, reproducible from scratch.

Requirements:
- docker-compose with a named volume so data survives restarts
- `CREATE EXTENSION vector` in a migration, not manually
- Connection config via `.env`, with `.env.example` committed
- A single command brings the stack up from empty and applies migrations
- **Do not create the vector index yet** — see issue 0.10

**Done when:** `docker compose up` plus the migrate command yields a working empty database on a clean machine.
EOF
)"

gh issue create --label "increment-0,infra,blocking" --title "0.5 Index version and run metadata table" --body "$(cat <<'EOF'
Every eval result must name the index version that produced it, or the results table is untrustworthy.

Index version record:
- `index_version_id`
- `embedding_model` and version
- `chunker` name and version
- `chunking_params` (JSON)
- `created_at`
- `doc_count`, `chunk_count`

Eval run record references `index_version_id`.

**Never mix embeddings from different models in one index** — it produces unpredictable retrieval that is very hard to diagnose.

**Done when:** an eval run cannot be recorded without an index version, and the README results table has an index-version column.
EOF
)"

gh issue create --label "increment-0,ingestion" --title "0.6 Embed chunks with EmbeddingGemma and store" --body "$(cat <<'EOF'

Requirements:
- Batched embedding calls, not one per chunk
- Resumable: skip chunks already embedded for the current `index_version_id`
- Record embedding dimension in the index version row
- Idempotent upsert keyed on `(chunk_id, index_version_id)`
- Handle and log API failures per batch; a failed batch must not abort the run

**Done when:** the pilot set is embedded and stored, and re-running the command is a no-op.
EOF
)"

gh issue create --label "increment-0,retrieval,blocking" --title "0.7 Dense retriever: top-k over pgvector" --body "$(cat <<'EOF'

Scope for the baseline, deliberately minimal:
- Embed the query with the same model as the index
- Cosine top-k over pgvector
- Return chunk ids with scores and all metadata needed by the resolver
- Configurable k
- No hybrid, no reranking, no query transformation — those are Increment 1

**Done when:** a query returns ranked chunks with page and region attached.
EOF
)"

gh issue create --label "increment-0,retrieval,blocking" --title "0.8 Chunk-to-page resolver for scoring" --body "$(cat <<'EOF'

The golden set stores ground truth as `{doc_id, page, region}`. The retriever returns chunk ids. Scoring recall@k requires mapping between them.

Approach:
- Primary: locate the golden question's `evidence_quote` within chunk text by normalised string match. The quote is the portable join key — it survives rechunking.
- Fallback: `(doc_id, page)` overlap when the quote is not found verbatim
- Record which match path was used per question, so quote-match failures are visible rather than silently degrading to page-level matching
- Multi-hop questions: a hit requires **all** required locations retrieved, not any

**Done when:** given a retrieval result and a golden question, the resolver returns a hit/miss decision and the match path used.
EOF
)"

gh issue create --label "increment-0,ingestion" --title "0.9 Pilot run on 25 documents, end to end" --body "$(cat <<'EOF'
Run the complete path — extract, chunk, embed, store, retrieve, score — on **25 documents only**.

Loading all 250 before the pipeline is verified means a bug costs a full reprocess.

Checks on the pilot:
- All 25 documents parsed, or failures understood
- Chunk count per document plausible; no documents yielding 1 chunk or 500
- Spot-check 5 tables: did HybridChunker keep table rows intact?
- Reading order sane on 3 multi-column pages
- Golden questions whose source documents are in the pilot can be scored end to end

**Done when:** the pipeline runs clean on 25 documents and at least a handful of golden questions produce a hit/miss result.
EOF
)"

gh issue create --label "increment-0,ingestion" --title "0.10 Scale to full corpus, then build the HNSW index" --body "$(cat <<'EOF'
Only after the pilot is clean.

Order matters: **bulk load first, create the index afterwards.** Building HNSW on an empty table and inserting into it is substantially slower than inserting then indexing.

Steps:
- Run ingestion over all documents, resumably
- Record final doc and chunk counts on the index version row
- Create the HNSW index with chosen parameters, recorded in decisions.md
- Measure and record index build time and query p95 at this corpus size

**Done when:** full corpus indexed, counts recorded, p95 measured.
EOF
)"

gh issue create --label "increment-0,analysis,blocking" --title "0.11 Run baseline eval and record results" --body "$(cat <<'EOF'
Run the harness over all 74 golden questions against the naive baseline.

Record in the README results table:
- Date, index version, config
- recall@1, recall@5, recall@10
- MRR, NDCG@10
- **Per question type**: single_fact, multi_hop, table_numeric, ambiguous
- **refusal_accuracy** on the 15% unanswerable rows, reported separately and excluded from recall

A single aggregate number is not enough — the per-type breakdown is what makes Increment 1 targeted.

Sanity gate: if recall@5 exceeds 0.90 the golden set is too easy and has no headroom. If it is below 0.30, diagnose before proceeding.

**Done when:** results committed to the README table with the index version named.
EOF
)"

gh issue create --label "increment-0,analysis" --title "0.12 Classify retrieval failures into a taxonomy" --body "$(cat <<'EOF'
Highest-value analysis item. Converts a number into a work plan.

For every failing question, classify the cause:
- Answer not in corpus (golden set error, or genuinely unanswerable)
- Chunk boundary split the answer
- Identifier mismatch (part number embedded poorly)
- Correct chunk retrieved but ranked below k
- Retrieved but generator ignored it
- Multi-hop: one location found, not both
- Query ambiguous

Output a distribution, e.g. "32% failures: 40% chunk-boundary, 30% identifier mismatch, 20% multi-hop, 10% ambiguous".

This distribution decides what Increment 1 prioritises. Without it, Increment 1 is guesswork.

**Done when:** every failing question carries a failure class and the distribution is in the README.
EOF
)"

gh issue create --label "increment-0,infra,blocking" --title "0.13 CI: GitHub Actions eval gate" --body "$(cat <<'EOF'

Workflow requirements:
- Runs on every push and pull request
- Lint and unit tests
- Eval harness over the golden set
- Fails if recall@5 drops more than the agreed tolerance below the recorded baseline
- Tolerance value needs a decisions.md entry explaining how it was chosen (not zero — the system is non-deterministic)

**Done when:** a deliberate regression fails CI, and a clean push passes.
EOF
)"

echo
echo "Done. Review with: gh issue list --label increment-0"
