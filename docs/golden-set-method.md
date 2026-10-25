# Golden Set Construction — Efficient Method

**Purpose:** build ~70 validated evaluation questions in ~2.5 hours instead of
~5, without compromising ground-truth validity.

**This document is also the answer to "how did you build your eval set?"** —
which is the first question any serious interviewer asks about an eval harness.
Keep it current.

---

## The principle

Verification is faster than creation. Inventing a question from a page takes
~4 minutes; judging a pre-drafted question against a quoted evidence span takes
~45 seconds. So generate candidates in bulk, filter them automatically, and
spend human attention only on the irreducible judgment.

**What may be automated:** finding candidate passages, drafting question wording,
recording locations, detecting leaks and duplicates, checking corpus-dependence,
classifying question type, constructing unanswerable variants.

**What may never be automated:** confirming that the answer is actually correct.
That is the ground truth. If you automate it, you have no eval set, you have a
model agreeing with itself.

---

## Why page-level generation is safe (and chunk-level is not)

The circularity trap is not "generating from a passage." It is **defining ground
truth as that passage's chunk**.

- A **chunk** is an artifact of your pipeline. It changes in Increment 1. Ground
  truth defined on it dies.
- A **page** is a document-native unit. It exists before any chunking decision
  and survives all of them.

So: generate from pages, record `{doc_id, page, region}`, and require the
generator to emit the **exact quoted evidence span**.

**The quote is the portable join key.** When chunking changes, re-derive which
chunk contains the quote by string match. Ground truth never needs rebuilding.
This one field is what makes the whole eval set durable.

---

## Step 1 — Stratified page sampling (15 min)

Do not sample pages at random, and never take "the first page of each document."
Random sampling over-represents whatever is most common; first pages are title
pages and tables of contents.

Classify every page with cheap heuristics before sampling:

| Dimension | Buckets |
|---|---|
| Source | NHTSA / DoD / FAA |
| Content type | has_table / has_list / prose_only / mostly_figure |
| Position | front_matter / body / appendix |
| Density | token count quartile |

Then sample to fill a quota across buckets. You want tables over-represented
relative to their natural frequency, because tabular extraction is where
pipelines fail and therefore where measurement is most valuable.

Record the sampling plan. "I stratified by source, content type and position"
is a much stronger interview answer than "I picked some pages."

---

## Step 2 — Generation with evidence (30 min, mostly unattended)

One page per call. Require structured output:

```json
{
  "question": "...",
  "answer": "...",
  "evidence_quote": "verbatim span from the page, 10-40 words",
  "region_hint": "table 3, row 2 | paragraph 4 | figure 2 caption",
  "answer_type": "single_fact | table_numeric",
  "confidence": "high | medium | low"
}
```

**Prompt constraints that matter:**

- The question must not name where the answer lives. Ban "according to table 3",
  "in section 4.2", "on this page".
- The answer must be a specific value, entity, or short procedure — never a
  summary or a judgement.
- `evidence_quote` must be copied verbatim. If the model paraphrases, the
  candidate is rejected automatically at the gate stage.
- Generate **3 candidates per page** and keep the best at review. Overgenerating
  is cheap; re-running the pipeline later is not.

Target ~200 candidates for a final set of 70. The surplus is what lets you
reject freely instead of accepting mediocre questions to hit a count.

---

## Step 3 — Five automated gates (20 min to build, then free)

Run every candidate through these before a human sees it. They remove 50-60% of
candidates and cost nothing per run.

| Gate | Check | Reject when |
|---|---|---|
| **1. Quote fidelity** | `evidence_quote` appears verbatim on the cited page | No exact match |
| **2. Corpus dependence** | Ask a model the question with no context | It answers correctly |
| **3. Location leak** | Regex + LLM check for positional references | Question names a table, section or page |
| **4. Answer leak** | Answer string appears inside the question | Overlap above threshold |
| **5. Near-duplicate** | Embedding similarity against already-accepted set | Cosine above ~0.9 |

Gate 2 is the one people skip and it is the most important. A question a
general-purpose model answers without your documents measures nothing about your
retrieval. Expect it to kill 30-40% of candidates on a public corpus.

Log gate rejection counts. The distribution tells you whether your generation
prompt needs fixing, and it is a good detail to cite in interview.

---

## Step 4 — Fast review (~45 sec per question)

**Build a minimal review loop.** Editing JSONL by hand is the hidden time sink —
a 30-line terminal script that prints the question, proposed answer, evidence
quote and surrounding page text, then reads a single keypress, pays for itself
within fifteen questions.

```
[q047]  type: table_numeric   source: FAA AC 43.13-1B  p.142
Q: What torque value applies to a 1/4-inch bolt with a cadmium-plated nut?
A: 95-110 inch-pounds
EVIDENCE: "...1/4-28 … 95-110 in-lb when used with cadmium-plated nuts..."
[a]ccept  [e]dit  [r]eject  [s]kip  [f]lag-hard
```

**Two passes, not one.** They use different attention modes and separating them
is measurably faster:

- **Pass 1 — question quality only** (~15 sec each). Is this a good question? Is
  it well-formed, specific, non-leaking? Do not verify the answer yet.
- **Pass 2 — answer verification** (~60 sec each, survivors only). Open the
  source page. Confirm the answer is correct and complete. This is the
  irreducible work and the only part that cannot be delegated.

---

## Step 5 — The hard question types

Generic generation produces mostly easy single-fact questions. These two types
need deliberate construction.

### Multi-hop (target 25%)

**Do not ask an LLM to "write a multi-hop question."** It produces fake
multi-hop — two facts from the same page, retrievable in one shot.

Real method: find **page pairs sharing an entity** (a part number, a component,
a procedure reference) using co-occurrence over your own index. Feed both pages
and require that the answer need information from each. Then verify by
construction: if either page alone yields the answer, it is not multi-hop and it
gets rejected.

Record both locations in `source_locations`. Recall@k on multi-hop rows should be
scored as "all required locations retrieved", not "any".

### Unanswerable (target 15%)

Three reliable recipes, all cheap:

1. **Entity perturbation.** Take a valid question, swap the entity for one that
   does not exist in the corpus (a part number one digit off, a model year not
   covered). Verify absence by running retrieval and confirming nothing relevant
   returns.
2. **Out-of-scope field.** Ask for a field the document type never contains —
   pricing from a recall report, personnel names from a technical manual.
3. **Plausible-but-absent.** Ask about a procedure that would reasonably exist in
   a document of that type but does not appear in your corpus.

Recipe 1 is the most valuable because it is adversarially close to an answerable
question. A system that answers it confidently is hallucinating, and nothing else
in your harness catches that.

**Scoring note:** unanswerable rows are excluded from recall@k (there is nothing
to retrieve) and scored on refusal instead. Keep them in a separate metric —
`refusal_accuracy` — and never let them silently inflate or deflate retrieval
numbers. Decide this before you write the harness, not after.

---

## Step 6 — Quality control on yourself

You are a single annotator, which is a real validity threat and an interviewer
will raise it. Two cheap mitigations:

### Self-agreement check
Re-review a random 10% a day later, blind to your earlier decision. Measure
agreement with yourself.

- **>90% agreement** — criteria are well defined
- **75-90%** — tighten the written criteria in `golden/schema.md`
- **<75%** — your criteria are vague; the set is not trustworthy yet

Record the number. "I measured 93% self-agreement on a blind 10% re-review" is a
rigour signal almost no candidate can offer.

### Difficulty calibration — stop at 20

**Do not build all 70 before measuring anything.** After the first 20 accepted
questions, run the naive baseline.

| Baseline recall@5 | Meaning | Action |
|---|---|---|
| 0.90+ | Set is too easy; it cannot show improvement | Harder questions: more tables, more multi-hop |
| 0.40-0.80 | Useful spread | Continue to 70 |
| <0.30 | Too hard or retrieval is broken | Diagnose before generating more |

A golden set where naive RAG already scores 0.95 is worthless — there is no
headroom to measure. Finding that out at question 20 instead of question 70 saves
you four hours.

---

## Time budget

| Step | Time | Reusable? |
|---|---|---|
| Stratified sampling | 15 min | Yes |
| Build generation script | 20 min | Yes |
| Build the five gates | 20 min | Yes |
| Build review loop | 20 min | Yes |
| Generation run | 10 min | — |
| Pass 1 review (90 candidates) | 25 min | — |
| Pass 2 verification (70) | 70 min | — |
| Self-agreement re-review | 10 min | — |
| **Total** | **~3 hrs** | ~75 min of it is permanent infrastructure |

Against ~5 hours fully by hand — and the pipeline is reusable for Increment 1,
for any future corpus, and directly transferable to the work at Aksibu.

---

## The thing not to optimise

Every efficiency above targets candidate *generation* and *triage*. None of them
touch answer verification, because that is where ground truth comes from.

The failure mode is predictable: three hours into review, fatigue sets in and
"accept" starts looking like the fast path. A golden set with 15% wrong answers
produces metrics that look precise and are fiction, and every number you quote
afterwards is wrong in a way you cannot detect.

Hard rule: **when you stop opening source pages, stop reviewing.** Finish
tomorrow.

---

## Record for interviews

Keep these numbers in `README.md` as you go. Each one answers a question you
will be asked:

- Candidates generated / accepted / rejected, with per-gate rejection counts
- Final type distribution against target
- Self-agreement percentage on blind re-review
- Baseline recall@5 at question 20 and at question 70
- Mean human review time per question
