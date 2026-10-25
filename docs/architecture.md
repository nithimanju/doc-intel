# doc-intel — Target Architecture and Gap Analysis

**Written:** 24 Oct 2026
**Status:** target architecture, not a build spec. Most choices stay gated on
measurement from Increment 1 onward.

---

## Scope discipline — read this first

This is where I think the system is heading. It does **not** authorise building
all of it.

I wrote it to stop myself from two failure modes:

1. **Premature specification.** Picking a reranker before I've measured retrieval
   is a guess dressed up as a decision.
2. **Menu-as-requirement.** The component list below is a menu of what exists,
   not a checklist. Taking all of it is a year of work and most of it would not
   move my numbers.

Every component is tagged:

- **NOW** — decide before Increment 1. Expensive or disruptive to reverse.
- **MEASURE** — decide by experiment in the named increment. Do not pre-commit.
- **LATER** — real technique, out of scope for this project. I know it; I skip it.
- **SKIP** — actively wrong here. Named so I remember why.

---

## The two-plane model

| Plane | Contents | Who builds it |
|---|---|---|
| **Data plane** | Ingest, index, retrieve, generate | Most document QA systems |
| **Control plane** | Evaluation, observability, guardrails, index lifecycle | Rarely built with equal depth |

Differentiation for this project lives in the control plane. I already own the
hardest box in it — a golden set with CI gating. When forced to choose, I invest
in control-plane depth over data-plane breadth.

---

# Data plane

## 1. Document extraction — NOW (strategy), MEASURE (components, Increment 1)

**Decide now:** layout-aware parsing as primary, vision-model fallback for pages
where structure extraction fails. Never plain text dumping.

**Rule that matters:** extraction quality has to be measurable on its own, not
only through retrieval. I'll build a small extraction eval — ~20 pages annotated
by hand, table-cell accuracy and reading-order correctness. Without that, an
extraction regression looks like a retrieval regression and I will debug the
wrong layer for a day.

**Candidates (measure, don't pre-pick):** Docling, MinerU, Unstructured, and a
vision-LLM path. The comparison is the deliverable, not the choice.

**External benchmark:** OmniDocBench (Ouyang et al., CVPR 2025, arXiv 2412.07626)
is the reference for PDF parsing across layouts. Running a subset and reporting
where my pipeline lands is a claim few document systems actually make. Public
leaderboards are thin and several entries are vendor self-reports — I'll cite my
own numbers, not theirs.

**SKIP:** training my own layout detector. Months of work for little project
value.

## 2. Chunking — MEASURE (Increment 1)

Not deciding this in Increment 0. It is the highest-variance knob in the system,
and the point of a baseline is to measure against it.

I'll test these in order, each against the baseline:

| Strategy | Hypothesis to test |
|---|---|
| Fixed-size (baseline) | Reference point only |
| Layout-aware (respect table and section boundaries) | Should fix table-split failures |
| Contextual (prepend document/section context) | Should fix orphaned-reference failures |
| Parent-document / small-to-big | Retrieve precise, generate with surrounding context |
| Late chunking | Embed long, chunk after — preserves cross-chunk context |

**Pattern I don't want to miss:** small-to-big. Retrieve on small precise chunks,
then expand to the parent section for generation. That decouples retrieval
granularity from generation context — they are different problems.

**LATER:** agentic chunking. Expensive per document; rarely beats layout-aware on
structured corpora.

## 3. Retrieval — MEASURE (Increment 1), architecture NOW

**Decide now:** multi-stage. Broad recall (50–200 candidates) → rerank → small
set (3–10) to the generator. That shape is settled practice; the components
inside it are experiments.

**Measure in Increment 1:**
- Dense alone / sparse alone / hybrid with RRF — and the fusion weighting
- Reranker: cross-encoder vs late-interaction (ColBERT-style), precision gain vs
  added p95 latency
- Query transformation: rewriting, HyDE, decomposition — these often hurt; I
  measure before I believe them
- k at each stage

**Corpus-specific hypothesis:** part numbers and stock numbers tokenize badly and
embed poorly. I expect BM25 to beat dense on identifier queries and lose on
procedural ones. If that shows up in the per-question-type breakdown, hybrid
weighting by detected query type is a defensible, measured optimisation.

**Query routing (Adaptive RAG) — MEASURE (Increment 2):** not every query needs
the full pipeline. Route simple lookups to cheap retrieval, complex ones to the
agentic path. Primarily a cost and latency win; I justify it with numbers.

## 4. Embedding and reranking models — MEASURE (Increment 1)

I'll pick two or three candidates, measure on *this* corpus, and record the
result. MTEB rankings do not transfer to a technical-document corpus with heavy
identifier content — that transfer gap is a design constraint, not a surprise.

**Matryoshka embeddings** are worth knowing: truncatable dimensions let me trade
index size against recall without re-embedding. Cheap experiment if index size
becomes a constraint.

## 5. Database selection — NOW

Three distinct stores. Conflating them is a common mistake:

| Store | Choice | Reasoning |
|---|---|---|
| **Canonical source of truth** | S3/local filesystem + Postgres metadata | Must stay separate from the index. The index is derived, disposable, rebuildable. |
| **Vector index** | **pgvector to start** | One fewer service, transactional with metadata, sensible starting point. Migrate to Qdrant when a measurement forces it. |
| **Graph** (if justified) | Neo4j — **MEASURE, Increment 2** | Only if I can show graph retrieval beats hybrid on multi-hop questions in my eval set |

**Why pgvector rather than Qdrant, even though I know Qdrant:** it removes a
service from the deployment, and the migration path — start on pgvector, measure
filtered-query p95 at N vectors, move when it exceeds budget — is better
engineering than picking the sophisticated option on day one. Start simple;
change when evidence forces it.

**Do not build GraphRAG just because work has a graph.** My eval set has ~25%
multi-hop questions. I'll measure whether hybrid handles them. If it does, a
graph is unjustified complexity — and documenting that is the correct outcome.

## 6. Generation and citation — NOW

**Decide now:** span-level citations, not document-level. Every claim in the
answer maps to a quoted span with a page and region.

I already have the mechanism — `evidence_quote` in the golden set is the same
primitive.

**Differentiating addition: citation verification.** After generation,
programmatically check that each cited span actually supports the claim attached
to it. Most systems cite and hope. Verifying catches a class of hallucination
that faithfulness scoring misses, and almost nobody builds it. See the gap
analysis below.

---

# Control plane

## 7. Evaluation — DONE (Increment 0), extend throughout

The hard part is already in place. Extensions I want:

- **Per-question-type breakdown**, not a single aggregate. recall@5 of 0.68 means
  nothing; "0.84 on single-fact, 0.41 on multi-hop, 0.52 on table" is actionable.
- **Refusal accuracy** as a separate metric for the ~15% unanswerable rows —
  never folded into retrieval numbers.
- **Retrieval failure taxonomy** — see gap analysis. Highest-value addition still
  available.
- **Online eval loop** — user feedback becomes candidate golden questions.

## 8. Observability and tracing — NOW

**Decide now:** per-stage tracing with cost and latency attribution per query.
Not just "this query took 2.3s" — the breakdown across parse, embed, retrieve,
rerank, generate.

**Tool:** I know Arize Phoenix. Langfuse would teach me something new and is
strong on prompt versioning and cost tracking. Either is defensible; I'll pick
one and record why in `decisions.md`.

**Instrument beyond the obvious:**
- Cost per query, attributed per stage — enables the Increment 3 cost work
- Retrieval hit rate in production vs eval-set recall (the gap is informative)
- Embedding drift against a baseline distribution

## 9. Caching — MEASURE (Increment 3)

Three tiers, increasing risk:

| Tier | What it caches | Risk |
|---|---|---|
| Embedding cache | Query → vector | None. Build it. |
| Retrieval cache | Query → candidate set | Low. Invalidate on index version change. |
| Semantic answer cache | Similar query → prior answer | **High.** Near-miss semantic hits return subtly wrong answers. |

**The trap:** semantic answer caching is widely promoted with large reported cost
savings, and it is the one that silently degrades correctness. If I build it, I
measure accuracy *on cache hits* against the eval set. A cache that is 90%
cheaper and 8% wrong is not a win. Measuring that beats implementing it
uncritically.

Provider-side prompt caching for long system prompts first — free money.

## 10. Index lifecycle — NOW (design), build Increment 1

Underrated and rarely built. Three mechanisms I want:

1. **Content-hash delta indexing.** Reindex only what changed. Full rebuilds are
   the default when you haven't thought about this.
2. **Index versioning with rollback.** Every index version carries embedding
   model, chunking config, and prompt hash. **Never mix embeddings from
   different models in one index** — retrieval becomes unpredictable and hard to
   diagnose.
3. **Re-embedding triggers.** A stated policy for when corpus drift or a model
   change forces a rebuild.

Tie index version to eval results: every row in the results table names the
index version that produced it. That one discipline makes the results table
trustworthy.

## 11. Agents and orchestration — Increment 2

**Decide now:** LangGraph, with explicit state, checkpointing, and resumption.
Reusing what I know from work is fine here — differentiation is not framework
novelty.

**Build:** retrieval as a tool, MCP server exposing those tools, human-in-the-loop
interrupt on low confidence, one multi-agent sub-flow only where it genuinely
helps.

**Design stance:** most of this document QA system should be a *workflow*, not an
agent. Agents earn their cost on open-ended multi-step tasks, not on "retrieve
and answer." I want to be explicit about which parts are deliberately not
agentic, and why.

**LATER:** four-layer memory hierarchies and temporal knowledge graphs from
current agent literature. Real techniques, wrong scope — document QA has no
long-running session state to manage.

## 12. Security — Increment 3, highest-value gap

Full detail belongs in the Increment 3 threat model. Architecture-level
decisions now:

- **Indirect prompt injection is the primary threat.** Third-party documents
  flow into a vision LLM. Assume document content is adversarial.
- **Least privilege for tools.** An agent with retrieval and a write tool is a
  different risk class from retrieval alone.
- **Output validation as a control**, not just a quality measure. Schema
  conformance is a security boundary.
- **Tenant isolation** enforced at the index level, with a test proving
  cross-tenant retrieval is impossible. Simulate three tenants.

Frameworks to map against: OWASP Top 10 for LLM Applications 2026, OWASP Top 10
for Agentic Applications, MITRE ATLAS.

## 13. Auth — NOW, keep minimal

- API: key-based auth, per-key rate limiting, per-key cost budget
- UI: OAuth only if the demo needs user identity; otherwise skip it
- **Tenant scoping on every retrieval call**, enforced in the data layer rather
  than the application layer

I am not building a full identity system. Undifferentiated work, outside scope.

## 14. Infrastructure and IaC — NOW

**Recommendation: ECS Fargate, defined in Terraform.**

Reasoning, including the deliberate trade:

- **Terraform rather than CDK** — industry default for this kind of infra, keeps
  the deployment portable.
- **Fargate rather than Kubernetes** — right choice for a single service. A
  cluster here would be over-engineering; knowing why not to reach for K8s is
  part of the decision.
- CI/CD: GitHub Actions, eval-gated deploys. Deploy only on green eval.

**SKIP:** streaming ingestion (Kafka, Flink, Debezium). Corpus is static.
Significant scope, zero measurement value here. I know the pattern; it doesn't
apply.

## 15. Prompt optimization standards — NOW

- Prompts live in `prompts/` as files, under version control
- Every run records the prompt hash
- Prompt changes are A/B'd through the eval harness — never shipped on vibes
- Structured output via tool schema, never prompt instruction alone

**On DSPy GEPA:** I use it at work as a defensible alternative to fine-tuning.
Using it here is fine — but the strong version is a *measured* comparison:
hand-written prompt vs GEPA-optimised, on my eval set, with the delta recorded.

## 16. Notifications — NOW, deliberately minimal

Two alerts only: eval regression in CI, and a cost threshold breach. That is the
entire requirement. A notification system here is undifferentiated work.

---

# Gap analysis — what the best systems have that typical builds don't

Ordered by return on hours invested.

## 1. Retrieval failure taxonomy — DO THIS FIRST

**Status:** missing. **Effort:** ~4 hrs. **Value:** very high.

Classify *why* each failing eval question failed, not just that it failed:

| Failure mode | What it indicates |
|---|---|
| Answer not in corpus | Golden set error, or genuinely unanswerable |
| Chunk boundary split the answer | Chunking strategy |
| Identifier mismatch (part number embedded poorly) | Need lexical retrieval |
| Reranker demoted the correct chunk | Reranker tuning |
| Retrieved but generator ignored it | Generation or context-ordering problem |
| Multi-hop: one location found, not both | Retrieval strategy for multi-hop |
| Query ambiguous | Query understanding |

This turns "recall@5 = 0.68" into "32% failures: 40% chunk-boundary, 30%
identifier mismatch, 20% multi-hop, 10% ambiguous" — which tells me exactly what
to build next. Most systems never do this. It also makes every later increment
targeted instead of speculative.

Nothing else on this list comes close on return.

## 2. Citation verification — high value, rare

**Status:** missing. **Effort:** ~6 hrs. **Value:** very high.

Programmatically verify that each cited span supports the claim attached to it.
Report a citation-precision metric. Most systems cite and hope; verification
catches hallucinations that faithfulness scoring misses because the citation
looks plausible.

## 3. Index versioning with rollback

**Status:** missing. **Effort:** ~4 hrs. **Value:** high — this is what
production systems actually need.

Every index version records embedding model, chunking config, and prompt hash.
Results rows name their index version. Rollback is one command.

## 4. Cost attribution per query stage

**Status:** missing. **Effort:** ~3 hrs. **Value:** high.

I need to know what each stage costs per query. Prerequisite for any credible
cost claim in Increment 3. Most systems cannot answer "what does a query cost?"
at all.

## 5. Online evaluation loop

**Status:** missing. **Effort:** ~5 hrs. **Value:** high.

Thumbs-down in the UI becomes a candidate golden question in a review queue. The
eval set grows from real usage instead of freezing at the Increment 0 size. That
is the difference between a living system and a demo.

## 6. Extraction-level evaluation

**Status:** missing. **Effort:** ~4 hrs. **Value:** medium-high.

~20 hand-annotated pages, table-cell accuracy and reading order. Without it I
cannot attribute a failure to extraction vs retrieval, and that attribution is
half the debugging work in a document system.

## 7. Multi-granularity retrieval (small-to-big)

**Status:** missing. **Effort:** ~4 hrs. **Value:** medium.

Retrieve precise, generate with the parent section. Decouples the two
granularities. Measure it in Increment 1 like anything else.

## 8. Abstain-rate discipline

**Status:** partially done — the unanswerable slice of the golden set is ahead
of most builds.

Make refusal a first-class reported metric with a target, not a side effect.

---

## What I am not building, and why

Naming what I deliberately leave out keeps scope honest.

| Not building | Why |
|---|---|
| GraphRAG | Measure whether hybrid handles the multi-hop slice first. Unjustified complexity otherwise. |
| Streaming ingestion (Kafka/Flink/CDC) | Static corpus. Pattern understood, inapplicable. |
| Agent memory hierarchies | No long-running sessions in document QA. |
| Fine-tuned embeddings | Measure off-the-shelf first; the gain rarely justifies the pipeline. |
| Kubernetes | Single service. Fargate is correct; a cluster would be unjustified complexity. |
| Semantic answer caching (uncritically) | Measure accuracy on cache hits before trusting it. |
| Own layout detection model | Months of work for little project value. |

---

## Positioning against best-in-class

Honest read on where this project can land:

**Where I can match or exceed typical production systems:** evaluation rigour,
failure analysis, citation verification, index lifecycle discipline. These are
engineering-discipline items, not scale items, and they are achievable solo.

**Where I cannot compete, and should not pretend to:** corpus scale, latency at
load, multi-region, team-scale operational maturity. I will not claim those.
Saying "at ~250 documents these numbers hold; here is what I expect to break at
250,000 and why" is stronger than an inflated claim.

**Target summary this architecture is built to support:**

> ~250 technical documents, golden eval set with an unanswerable slice, hybrid
> retrieval with reranking and a measured recall@k lift from baseline,
> span-level citations with verified citation precision, failure taxonomy
> driving each change, index-versioned and CI-gated, deployed on Fargate via
> Terraform with cost attributed per query stage.

Every clause in that sentence is a measurement I own, not a technology I listed.
That is the whole design goal.

---

## Sources

- OmniDocBench: Ouyang et al., "OmniDocBench: Benchmarking Diverse PDF Document
  Parsing with Comprehensive Annotations," CVPR 2025 (arXiv 2412.07626)
- Practitioner synthesis of 2026 RAG practice:
  https://github.com/dpsdagain/RAG/blob/main/rag_state_of_the_art_2026.md
  (useful component inventory; treat its statistics with caution — several are
  presented without sources)
- OWASP Top 10 for LLM Applications 2026 and for Agentic Applications:
  https://genai.owasp.org
