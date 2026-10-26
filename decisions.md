# Decisions Log

Every component choice gets an entry here before any code is written. Each entry names what was rejected and why, and states a falsification
condition so the decision can be revisited honestly later.

---

## [2026-10-22] Corpus choice: NHTSA recall communications + DoD issuances + FAA Advisory Circulars

**Chose:** A three-source public-domain technical corpus —
NHTSA recall-communication documents (manufacturer notification/owner letters,
quarterly reports, indexed via the ODI flat files), publicly releasable DoD
issuances (manuals preferred over instructions/directives), and FAA Advisory
Circulars (via the National Transportation Library's ROSA P repository, which
turned out to be a better crawl target than faa.gov itself — see the Increment 0
note below).

All three sit in the automotive/aerospace/defense technical-documentation space:
dense procedural text, part numbers and component identifiers, affected-item
tables, repair/remedy steps, cross-references, and (for DoD manuals especially)
diagrams — the structural properties that break naive chunk-and-embed RAG and
are therefore worth measuring. FAA Advisory Circulars are specification-dense and
table-heavy, which teaches the system more than policy prose does.

**Rejected:**
- *arXiv papers* — trivially easy to bulk-download and legally unambiguous, but
  prose-shaped. They don't exercise tables, part numbers, procedures, or
  cross-references, which is the entire point of choosing a document-heavy
  domain. A corpus that's easy to retrieve against teaches nothing about
  document intelligence.
- *OEM service manuals* — the most structurally interesting option (exactly the
  kind of procedural, diagram-heavy content the author's automotive-adjacent
  domain knowledge could verify answers against) but copyrighted by the
  manufacturer. This repo ships to a public URL, so anything not legally
  redistributable is disqualified regardless of how good it is for retrieval.
- *NHTSA Technical Service Bulletins* — hosted by NHTSA's Office of Defects
  Investigation, which makes them *look* like government records, but they are
  authored and copyrighted by OEMs. Republishing them in a public repo is a
  copyright risk; TSB content, if wanted at all, is metadata/index records only,
  never the bulletin PDFs. See `docs/corpus-requirements.md`.

**Trade-off accepted:** Format heterogeneity across three agencies and many
manufacturers means more crawler edge cases than a single uniform source would
have (confirmed while building `src/corpus/fetch_corpus.py`: esd.whs.mil
blocks plain HTTP clients with a 403, even with browser-style headers, so the
DoD source degrades to zero documents in this environment and must be made up
from NHTSA). We accept that cost because format heterogeneity is also the
realistic case, and most portfolio RAG projects avoid it by picking one clean
source.

**Open issue carried forward (not yet resolved — flagging rather than
assuming):** researching `src/corpus/fetch_corpus.py` surfaced that the actual
PDF documents available from NHTSA's recall-communications flat files (owner
notification letters, manufacturer notification letters, quarterly Part 573.6
reports) are *manufacturer-authored*, filed under 49 CFR Part 573's
mandatory-disclosure requirement — the same fact pattern flagged above for
TSBs ("hosted by a federal agency" is not "authored by a federal agency, hence
public domain"). The fetcher records these with `licence:
needs_review-manufacturer_authored_mandatory_disclosure` rather than
`public_domain`, and no NHTSA document should be treated as safe to publish
until this is resolved (e.g., by confirming a specific disclosure regulation
grants redistribution rights, or by replacing/supplementing NHTSA with a
higher share of DoD/FAA documents, which are unambiguous US-government works).

**How we'd know this was wrong:** if, once golden questions are drafted against
these documents, verification keeps requiring outside domain knowledge the
author doesn't have (rather than NHTSA/DoD/FAA domain familiarity), or if the
NHTSA licence question above is resolved against redistribution and the corpus
has to be rebuilt around DoD/FAA alone.

---

## [2026-10-22] Ground-truth granularity: document location, not chunk ID

**Chose:** `golden/questions.jsonl` records ground truth as
`{doc_id, page, region}` — a location in the *source document* — never a chunk
ID from any particular chunking strategy.

**Rejected:** Recording ground truth as a chunk ID (e.g., "chunk_0042") from
the Increment-0 naive baseline's fixed-512-token chunker. This was rejected
because Increment 1 explicitly changes chunking (hybrid retrieval, reranking,
query transforms), and a chunk-ID ground truth would silently redefine
"correct" every time the chunker changes. Worse, it makes the eval set
measure the chunker against itself: if a question's answer and its "correct"
chunk were both derived from the same chunking pass, retrieval evaluation
degenerates into checking whether the current chunker agrees with a past run
of itself, not whether it found the right information.

**Trade-off accepted:** Location-based ground truth is more expensive to
score — recall/precision/MRR/NDCG need a page-and-region-to-chunk mapping
step (checking whether a retrieved chunk's span overlaps the recorded
location) instead of a trivial ID-equality check. We accept the extra
scoring-harness complexity because it is a one-time cost paid in
`src/evaluate/`, whereas a chunk-ID ground truth would need to be *regenerated* at every chunking change across all ~70 questions — a recurring cost that compounds across Increment 1's multiple
retrieval techniques.

**How we'd know this was wrong:** if the location-to-chunk overlap scoring
logic turns out to be ambiguous often enough (e.g., a table answer spans a
region no single reasonable chunk boundary fully contains) that the human
author has to adjudicate individual eval runs by hand rather than trusting
the harness — that would mean the granularity chosen is finer than the
scoring method can cleanly support.

---

## [2026-10-22] Target corpus size: 200-500 documents, not ~20

**Chose:** A minimum of 200 documents (target 200-500), sourced per
`docs/corpus-requirements.md`'s per-source breakdown (NHTSA 50-70, DoD 20-30,
FAA 20-30 = 90-130 planned), topped up from the richest source (NHTSA) if the
combined total falls short of 200.

**Rejected:** A small pilot-sized corpus (~20 documents), which would be far
faster to acquire, manifest, and iterate on. Rejected because retrieval
problems are invisible below roughly 100 documents — with only 20 documents,
dense retrieval, filtering, and reranking all look like they work regardless
of whether the underlying technique is sound, simply because there isn't
enough distractor content for a bad retriever to rank a wrong document above
the right one. Every Increment-1 measurement (the project's entire thesis —
measured deltas against a recorded baseline) would be noise at that scale.

**Trade-off accepted:** A 200+ document corpus takes materially longer to
acquire, verify (SHA256, `%PDF` magic bytes, page-count sanity, licence
determination per document), and manifest than a 20-document pilot would, and
makes manual review of the full corpus impractical — the acceptance checks in
`docs/corpus-requirements.md` (format diversity, no TSB bulletins present,
page-count distribution) exist specifically because the corpus is too large
to eyeball exhaustively.

**How we'd know this was wrong:** if, even at 200+ documents, recall@5 is
saturated (near 1.0) for the naive baseline — meaning the corpus isn't
actually hard enough to discriminate between retrieval techniques in
Increment 1 — the target should move toward 500 and/or toward documents with
denser cross-references between them, not stay at 200.

---

## [2026-10-24] Local Pass-2 review tool: Vite+React+TS at frontend/admin/, iframe PDF viewer, direct Node fs persistence

**Chose:** A third interchangeable Pass-2 interface at `frontend/admin/`
(Vite + React + TypeScript), placed inside `frontend/` as its own sub-app
because it's intended to seed a later admin app rather than stay a
throwaway script. PDFs are served via a Vite `configureServer` middleware
(one `npm run dev`, no second process); page-jump uses the browser's native
PDF viewer, `<iframe src="/pdfs/:docId#page=N">`; decisions persist via
direct Node `fs` JSONL read/write in `server/goldenStore.ts`, reimplementing
`src/eval/review_golden.py`'s `save_jsonl`/`next_question_id`/accept-
reject-flag logic in TypeScript rather than shelling out to Python.

**Rejected:**
- *A separate Express/Node static server* — an extra process to remember to
  start defeats the point of a faster workflow.
- *react-pdf / pdfjs-dist for v1* — a real dependency bought nothing the
  actual ask needed; the requirement was "open to the right page," not
  highlight the evidence text on it. `PdfPane`'s prop interface (`docId`,
  `page`) is kept narrow so swapping in `react-pdf` later for highlighting
  doesn't ripple into the rest of the app.
- *Shelling out to `review_golden.py`'s Python functions per request* —
  cross-process latency, Windows subprocess quoting, and encoding risk
  (the project already had to work around a `utf-8-sig` BOM once) for only
  ~40 lines of logic to port.
- *Reusing the pre-built `corpus/.cache/review_export.json` as a static
  data source* — it was built for the offline/Artifact reviewer and can go
  stale if `candidates.jsonl` changes without someone remembering to
  re-run the export script. The new server derives the same
  `{doc_id, page, region, excerpt}` shape live from `candidates.jsonl` +
  `corpus/.cache/page_catalog.jsonl` on every `/api/candidates` request
  instead.

**Trade-off accepted:** Three independent implementations of the same JSONL
read/write/next-id logic now exist (Python in `review_golden.py`, and
TypeScript in `frontend/admin/server/goldenStore.ts`) and must be kept in
schema agreement by convention — documented in `frontend/admin/README.md` —
not by shared code. Re-editing an already-accepted candidate patches the
matching `questions.jsonl` row in place by its stored `question_id`, rather
than minting a new `qNNN` or leaving a stale duplicate.

**How we'd know this was wrong:** if the TypeScript and Python
implementations drift (e.g. differing `notes` formatting on accepted
questions, or a reject-reason field renamed in one but not the other) and
corrupt `golden/questions.jsonl`'s consistency across the three interfaces;
or if `frontend/admin/` never actually becomes the seed of an admin app,
in which case it should have been a disposable `eval/` script after all.

---

## [2026-10-24] frontend/admin/ styling: Bootstrap 5.3 via Sass source customization, not utility-fighting

**Chose:** Bootstrap 5.3 as the styling framework for `frontend/admin/`,
customized through its documented Sass workflow (`src/styles/custom.scss`
overrides `$primary`, `$success`, fonts, and radii *before* importing
Bootstrap's source) rather than loading the prebuilt CSS and overriding it
with higher-specificity rules afterward. Dark mode uses Bootstrap's native
`data-bs-theme` color-mode mechanism, synced from `prefers-color-scheme` in
`src/main.tsx`, with the dark palette supplied as a `--bs-*` custom-property
override block — Bootstrap's own documented pattern, not a parallel
hand-rolled dark stylesheet. Every component was rewritten to use Bootstrap's
own classes (`.btn`, `.badge`, `.card`, `.list-group`, `.progress`) instead
of bespoke ones of the same name, specifically to avoid the class-name
collisions (`.btn`, `.badge`, `.progress` all being real Bootstrap
components) that a "just add the CSS file" approach would have produced.

**Rejected:** `sass-embedded` for the Sass compiler — it spawns a native
Dart Sass subprocess, which failed with `spawn UNKNOWN` in this sandboxed
dev environment. Switched to the plain `sass` package (pure JS, no
subprocess) instead.

**Trade-off accepted:** A real build-time dependency (Sass) where there was
none before, and a compiled-CSS step between source and what the browser
loads, in exchange for customization that doesn't fight Bootstrap's own
cascade.

**How we'd know this was wrong:** if `custom.scss`'s variable overrides
drift out of sync with a future Bootstrap upgrade (a renamed variable
silently falling back to Bootstrap's default instead of erroring), or if
`sass`'s slower pure-JS compile becomes a noticeable `npm run dev` startup
cost worth trading back for `sass-embedded` once whatever blocked its
subprocess spawn is understood.

## [2026-10-27] Document Parser Choice, Database Choice, Index Choice.

**Document Parser Selection:**

I selected Docling because it is open source and runs on both CPU and CUDA.
It uses a DocLayNet-trained layout model and TableFormer for table structure
recognition, and it supports additional model integrations
(https://docling-project.github.io/docling/usage/model_catalog/#image-classifier-picture-classifier).
Output formats include Markdown, JSON, and DoclingDocument.

Published comparisons consistently rank Docling above Unstructured on table
structure extraction, but the available benchmarks are weak. The most
methodologically complete comparison is vendor-published for a product that
has since been discontinued; another derives its headline figure from a single
48-cell table; and the two disagree on Unstructured by 18 points. I chose
Docling based on the direction of those results plus ecosystem fit — CPU and
CUDA support, DoclingDocument output, and TableFormer for tables — and I treat
the accuracy claim as unverified until I run my own extraction evaluation.

Docling configurations I considered:

| Configuration | Models | Purpose |
|---|---|---|
| A — Standard baseline | Heron layout + RapidOCR + TableFormer Accurate + CodeFormulaV2 | Strong starting point with separately configurable stages |
| B — Higher-accuracy layout | Egret Large + RapidOCR + TableFormer Accurate + CodeFormulaV2 | Test whether the larger layout model improves difficult pages |
| C — VLM alternative | Docling VLM pipeline with Granite-Docling-258M; compare SmolDocling and GOT-OCR-2.0 | Evaluate end-to-end parsing on complex or image-heavy documents (lighter VLM option) |
| D — VLM alternative | Docling VLM pipeline with mineru2_pro (1.2B model) | Heavier VLM alternative within the Docling pipeline |

I also referred to OmniDocBench on PDFs
(https://arxiv.org/html/2412.07626v2). From that paper, my understanding of
per-task leaders (OmniDocBench v1, Dec 2024; later superseded on v1.5 by
GLM-OCR, PaddleOCR-VL, and MinerU 2.5) is:

- Layout detection — DocLayout-YOLO
- Table recognition — RapidTable
- Text recognition — PaddleOCR
- Formula recognition — Mathpix (GPT-4o and UniMERNet-B are also strong)
- Specialized VLM — GOT-OCR
- General VLM — Qwen2-VL-72B

Practical routing implied by that work:

- Scanned PDFs → OCR-based pipelines
- Complex layouts or embedded visual content → VLMs

For general document parsing, MinerU is a strong alternative: it already
includes its own layout-detection and parsing stages, and it ranks well as a
full pipeline across tables, text, and reading order.

Preferred starting point by document condition:

| Document condition | Preferred starting point |
|---|---|
| Clean vector PDF with ordinary text | Native PDF text extraction |
| Vector PDF with complex columns and tables | MinerU or another layout-aware pipeline |
| Scanned PDF with ordinary text | OCR pipeline using PaddleOCR, or a complete parser |
| Scanned PDF with dense tables | Layout detection + OCR / table recognition |
| Complex diagrams with meaningful visual relationships | Pipeline plus targeted VLM analysis |
| Poor-quality scans or unusual layouts | Compare pipeline and VLM outputs on representative pages |
| Formula-heavy technical papers | Parser with formula support; specialized formula recognition where needed |

I am going with Docling. There is no single best pipeline or VLM for every
document type, and building a custom multi-model parsing stack would mean
pipeline construction, output normalization across models, evaluation harness
work, and custom routing. Docling already provides a ready-to-use document
parser pipeline, so I am accepting that trade-off to avoid that complexity.

**Database Selection:**

I evaluated **pgvector**, **Qdrant**, **Milvus**, and **Neo4j**. I selected
**pgvector**.

**Chose: pgvector (Postgres + vector extension).** It is open source, easy to
deploy, and integrates cleanly with Python. One database holds tenant metadata,
business entities as relational SQL rows, and vectors together — no cross-DB
join, sync, or dual-write stabilisation. Backup, restore, and migration stay
ordinary Postgres operations. The vector index is derived and disposable; the
canonical document store stays separate. That is why starting on pgvector is
cheap to reverse if measurement later forces a move.

**Trade-offs I accept with pgvector.**
- Postgres `tsvector` is **not BM25**: it has no IDF weighting, so lexical
  scores must be fused myself (typically with RRF). This corpus is full of part
  numbers and identifiers where lexical search matters. That is the real
  weakness, and it lands in Increment 1.
- pgvector applies filters **after** the HNSW graph walk, so a selective filter
  can discard every approximate candidate and hurt recall. I will filter by
  `doc_id`, `chunk_type`, and `index_version_id`, and I will measure that
  behaviour on this corpus.

**Rejected for now: Qdrant and Milvus.** Both are strong purpose-built vector
stores. Relative to pgvector they typically offer faster specialised HNSW
paths, first-class hybrid / BM25-style lexical search, and mature filtered
retrieval. I did **not** choose them for Increment 0 because a dedicated vector
DB plus a separate relational store is over-engineering for ~200 documents: no
single-DB ACID boundary across metadata and vectors, and I would need two
systems (relational + vector) with cross-DB consistency. I will re-evaluate
Qdrant/Milvus in **Increment 1** on index build time, query latency, BM25 /
hybrid quality on identifier queries, and filtered-recall — and move only if
measurement beats pgvector enough to justify the second service.

**Deferred: Neo4j.** I am not selecting Neo4j yet. I will first measure
multi-hop question answering with hybrid RAG and contextual / layout-aware
chunking. Graph retrieval is justified only if that path fails the multi-hop
slice of the eval set.

**Indexing Selection:**

I am choosing **HNSW** over **IVFFlat** in pgvector.

**Why not IVFFlat as the primary index.** IVFFlat partitions vectors into
`lists` clusters via k-means at build time, then at query time scans only the
nearest `probes` lists. That makes builds fast and memory light, but the
centroids are fixed when the index is created. As the corpus grows — especially
when new embedding clusters appear — those centroids no longer represent the
data well, so recall drops until a rebuild (`REINDEX`) recomputes them. HNSW
has no training step and can be created on an empty table; inserts grow the
graph without that centroid-staleness failure mode.

**Published / measured comparisons I am using as priors** (my own corpus
numbers will replace these once I measure on the Increment 0 index):

| Property | IVFFlat | HNSW |
|---|---|---|
| Index build (AWS blog, ~58k rows, pgvector 0.5 → 0.6) | ~15 s | ~81 s → ~30 s after 0.6 build optimisations |
| Query latency (same AWS setup) | ~2.4 ms | ~1.5 ms (vs ~650 ms sequential scan) |
| Build vs query trade (independent 100k-vector measure) | ~5 s build; strong recall when data matches the original clusters | ~67 s build; ~50% larger index; recall stays stable as new vectors arrive |
| After inserting vectors from *new* clusters (same 100k→150k measure) | Recall@10 fell from ~0.997 to **0.473** at `probes=10` until `REINDEX`; after rebuild, recall returned to ~1.0 | Grown-by-insert recall stayed within ~0.003 of a fresh HNSW build (no rebuild required) |
| Recall/latency knob | `ivfflat.probes` (more lists scanned → higher recall and latency) | `hnsw.ef_search` (wider graph search → higher recall and latency) |

Sources: AWS Database Blog on pgvector IVFFlat vs HNSW; Neon’s pgvector
guidance (HNSW has no IVF training step; slower build, more memory); and the
public 100k-vector IVFFlat-vs-HNSW measurement on new-cluster inserts.

**HNSW advantages for this project.** Higher speed–recall trade-off for online
queries; no periodic rebuild tax as I add documents across increments;
incremental inserts keep recall stable; tunable with `m` /
`ef_construction` (build quality) and `ef_search` (query recall). That fits a
corpus that will grow and an eval loop that cannot afford silent recall decay
from stale IVF centroids.

**Trade-off I accept.** HNSW takes longer to build and uses more memory than
IVFFlat. For the first bulk load I will **insert all vectors first, then
`CREATE INDEX` with HNSW** — building HNSW on an empty table and inserting into
it is substantially slower than load-then-index. I will record build time,
query p95, and recall@k for the chosen `(m, ef_construction, ef_search)` in
this log once the full corpus is indexed.

**How I'd know this was wrong:** if HNSW build time or memory becomes the
binding constraint at full corpus size while measured recall@k on IVFFlat
(with a rebuild policy) matches HNSW within tolerance — then IVFFlat with
scheduled reindex would be the better fit.
---


## Debug drill

_(Pending — per CLAUDE.md, once per increment the author breaks something
deliberately and fixes it without AI help, recorded here under this heading.
Not yet performed for Increment 0.)_
