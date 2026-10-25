# Golden set — Pass 2 review

A local React app for the one step `docs/golden-set-method.md` says may never be
automated: opening each golden-set candidate's source PDF page and confirming the
answer is actually correct. Question, answer, evidence quote and page-text context sit
on the left; the real source PDF opens on the right, already scrolled to the right page.

This is the third of three interchangeable interfaces onto the same two files —
`golden/candidates.jsonl` and `golden/questions.jsonl` — alongside
`src/eval/review_golden.py` (terminal) and a claude.ai Artifact-based mobile reviewer.
All three must stay in schema agreement (see `decisions.md`'s entry on this tool); this
app reimplements the accept/reject/flag/edit logic directly in TypeScript rather than
calling into the Python tool.

It's intended as the seed of a later admin app, which is why it lives under
`frontend/admin/` rather than a disposable top-level script — but today it's local-only,
reads files straight off disk, and isn't deployed anywhere. It has nothing to do with
whatever gets built directly under `frontend/` for Increment 4's production frontend.

## Running it

```bash
cd frontend/admin
npm install
npm run dev
```

Opens at `http://localhost:5183`. One command — the dev server also serves the PDFs and
the small review API, so there's no second process to start.

**Prerequisites:**
- `corpus/raw/` populated (run `python src/corpus/fetch_corpus.py` from the repo root if
  not — see the root README).
- `corpus/.cache/page_catalog.jsonl` built (`python src/eval/golden_pages.py`). The app
  shows a clear error on load if this is missing rather than failing silently.

For a full walkthrough of every React component, every piece of state, and why each one
exists, see [`docs/FRONTEND_FLOW.md`](docs/FRONTEND_FLOW.md).

## How it works

- `server/` is a Vite plugin (`configureServer`) that adds three routes to the dev
  server: `GET /pdfs/:docId` (streams the PDF, looked up by `doc_id` in
  `corpus/manifest.json` — never a raw path in the URL), `GET /api/candidates` (all 285
  candidates plus page-text context computed live from
  `corpus/.cache/page_catalog.jsonl`), and `POST /api/decision` (accept/reject/flag/edit,
  writing straight into `golden/candidates.jsonl` and `golden/questions.jsonl`).
- PDFs open via the browser's own PDF viewer — `<iframe src="/pdfs/:docId#page=N">` —
  not a bundled PDF-rendering library. This was a deliberate choice for v1: the ask was
  "jump to the right page," not "highlight the evidence text on it." See `decisions.md`.
- Multi-hop candidates (two source locations) get a small switcher in the PDF pane.
  Unanswerable candidates with no source location (the out-of-scope DoD case) show a
  placeholder instead of a broken iframe.
- Re-editing a candidate that's already been accepted patches the existing
  `questions.jsonl` row in place (by its stored `question_id`) rather than minting a
  duplicate.
- Responsive from phone to ultrawide: below 1200px (Bootstrap's `xl` breakpoint) there
  isn't room for all three columns, so a List/Review/PDF tab bar shows one pane at a
  time instead; at 1200px+ it's the full three-column layout, all three panes visible
  at once. See `docs/FRONTEND_FLOW.md` for the exact mechanics.

## Styling

Bootstrap 5.3, customized through its own documented Sass workflow rather than
overriding the compiled CSS after the fact: `src/styles/custom.scss` sets variables
(`$primary`, `$success`, fonts, radii, ...) *before* `@import "bootstrap/scss/bootstrap"`,
mapping this project's palette onto Bootstrap's theme. Dark mode uses Bootstrap's native
`data-bs-theme` color-mode system (not a hand-rolled `prefers-color-scheme` stylesheet) —
`src/main.tsx` sets that attribute from the OS preference and keeps it in sync on change.
The dark palette itself is a small `[data-bs-theme="dark"] { --bs-*: ...; }` override
block at the bottom of `custom.scss`, which is Bootstrap's own documented pattern for
per-mode tweaks. `src/App.css` is intentionally almost empty — layout and components come
from Bootstrap's utility classes and `.btn` / `.badge` / `.card` / `.list-group` /
`.progress` components, not custom CSS.

Note: this app uses the plain `sass` package, not `sass-embedded` — the latter spawns a
native compiler subprocess that failed to start in at least one sandboxed dev
environment (`spawn UNKNOWN`). `sass` is pure JS, slightly slower to compile, more
portable.

## What's committed vs. not

Source, config and this README are committed — none of it embeds corpus content.
`node_modules/`, `dist/` and `.vite/` are gitignored at the repo root. Candidate and page
text are always fetched live from the running dev server, never written into a committed
file.
