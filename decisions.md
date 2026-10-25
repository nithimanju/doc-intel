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

---

## Debug drill

_(Pending — per CLAUDE.md, once per increment the author breaks something
deliberately and fixes it without AI help, recorded here under this heading.
Not yet performed for Increment 0.)_
