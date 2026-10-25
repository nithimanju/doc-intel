# Frontend flow

Every React piece in `frontend/admin/src/`, what it holds, and why — written against
the code as it stands, not a summary from memory. See `../README.md` for how to run the
app and what the server side (`server/`) does; this document is the browser side only.

```
src/
  main.tsx                        entry point
  App.tsx                         root component: data fetch, selection, decisions
  App.css                         the ~15 lines not covered by Bootstrap utilities
  styles/custom.scss              Bootstrap theme customization (not React; see README)
  api/
    client.ts                     the only two functions that talk to the server
  components/
    CandidateSidebar.tsx          left column: filterable, scrollable candidate list
    ReviewPane.tsx                middle column: question/answer/evidence + actions
    PdfPane.tsx                   right column: the source PDF, jumped to the right page
    ProgressBar.tsx               header: reviewed/accepted/rejected/flagged counts
    StatusBadge.tsx                small colored pill used inside the sidebar rows
../shared/types.ts                 types shared with server/ -- the data contracts below
```

Component tree, as actually rendered:

```
<App>
 ├─ <ProgressBar>                          (inside <header>)
 ├─ <CandidateSidebar>                     (always rendered once candidates load)
 ├─ <ReviewPane>                           (only when a candidate is selected)
 │   └─ (no child components -- all markup is inline JSX)
 └─ <PdfPane>                              (only when a candidate is selected)
     └─ (no child components -- all markup is inline JSX)
```

`StatusBadge` is used only inside `CandidateSidebar`'s row list, not at the `App` level.
All three main panes are always mounted (not conditionally unmounted by screen size);
below Bootstrap's `xl` breakpoint (1200px) `App` wraps each one in a `<div>` that shows
only the pane matching its `mobileView` state and hides the other two via CSS — see §2's
"Responsive layout" and §10's pane-switching flow for the full mechanics.

---

## 1. `src/main.tsx` — entry point

The only file that touches the DOM directly (`document.getElementById`) and the only
place `ReactDOM.createRoot` is called. Four things happen here, in order:

1. **Stylesheet imports.** `./styles/custom.scss` (Bootstrap compiled from source with
   this project's variable overrides) then `./App.css` (the handful of rules Bootstrap's
   utility classes don't cover: `html/body/#root { height: 100% }`, the body font, and
   the `.review-grid` layout fix). Import order matters: `App.css` loads second so its
   rules can win ties against Bootstrap's own cascade where needed.
2. **`syncBootstrapTheme()`** — a plain function, not a React hook (there's no component
   mounted yet to hook into). Reads `window.matchMedia("(prefers-color-scheme: dark)")`
   and sets `data-bs-theme="dark"` or `"light"` on `<html>`. This is Bootstrap 5.3's own
   color-mode switch, not a custom theme system — every Bootstrap color utility and
   component reads CSS variables that `[data-bs-theme="..."]` selectors override.
3. **`syncBootstrapTheme()` runs once immediately** (so the very first paint is already
   in the right mode, before React even renders), then **an event listener** is attached
   to the same media query so flipping the OS theme while the tab is open updates
   `data-bs-theme` live, without a reload.
4. **`createRoot(...).render(<StrictMode><App /></StrictMode>)`** — mounts the React
   tree into `#root` (declared in `index.html`). `StrictMode` is a React development aid:
   it intentionally double-invokes components and effects in dev to surface
   side-effect bugs; it does nothing in a production build. It wraps `<App>` and nothing
   else — there is exactly one component below it.

Nothing in this file is itself a rendered React element with visible output; its whole
job is wiring, done before the first `<App>` render.

---

## 2. `src/App.tsx` — root component

The only component that calls the API, owns `candidates` and `selectedIdx`, and decides
which of the three columns to show. Every other component is handed data as props and
reports user actions back up via callback props — no other component fetches or mutates
server state directly.

### State (`useState`)

| State | Type | Starts as | Set by |
|---|---|---|---|
| `candidates` | `CandidateWithContext[] \| null` | `null` | the initial fetch effect; `handleDecision` after every successful decision |
| `error` | `string \| null` | `null` | the fetch effect's `.catch`, and `handleDecision`'s `catch` |
| `selectedIdx` | `number \| null` | `null` | the fetch effect (picks the first pending candidate); `handleSelect` (from `CandidateSidebar`'s `onSelect` callback); `handleDecision` (advances to the next pending candidate) |
| `submitting` | `boolean` | `false` | `handleDecision`, for the duration of one `POST /api/decision` call |
| `mobileView` | `"list" \| "review" \| "pdf"` | `"list"` | the pane-switcher tab buttons; `handleSelect` (forces `"review"` on selection) |

`candidates === null` is the load-in-progress state (distinct from `[]`, which would
mean "loaded, zero candidates" — that case can't happen with this dataset, but the type
keeps the distinction honest). `selectedIdx === null` means either nothing has loaded yet
or every candidate has a decision already (the "all caught up" branch).

`mobileView` only matters below Bootstrap's `xl` breakpoint (1200px) — see
"Responsive layout" below. At `xl`+ all three panes are always shown regardless of its
value, so it's simply unused there.

### Effect: initial fetch (`useEffect`, `[]` — runs once on mount)

Calls `fetchCandidates()` (see §6). On success: stores the array in `candidates`, then
finds the first row with `pass2_status === "pending"` via `Array.findIndex` and selects
it (`selectedIdx`) — or falls back to index `0` if every row already has a decision
(`data.length ? 0 : null`, so an empty array still produces `null` rather than `0`,
though in practice the dataset is never empty). On failure: stores the message in
`error`, which short-circuits the whole render (see "Render branches" below).

### Derived value: `selected` (`useMemo`)

```ts
const selected = useMemo(
  () => (candidates && selectedIdx !== null ? candidates[selectedIdx] : null),
  [candidates, selectedIdx],
);
```

The single `CandidateWithContext` object currently shown in `ReviewPane` and `PdfPane`,
or `null` when nothing is selected. `useMemo` here is a minor optimization (array
indexing is cheap) but mainly documents intent: `selected` is a *derived* value, never
stored as its own piece of state, so it can never drift out of sync with
`candidates`/`selectedIdx`.

### Handler: `handleSelect(idx)`

Passed to `CandidateSidebar` as its `onSelect` prop (not `setSelectedIdx` directly).
Does two things: `setSelectedIdx(idx)` (the actual selection) and
`setMobileView("review")`. The second part only has a visible effect below the `xl`
breakpoint, where it jumps straight to the Review pane after a sidebar tap — on a phone,
picking a candidate and then *also* having to tap a "Review" tab would be a pointless
extra step. At `xl`+ it's a harmless no-op (the pane switcher is hidden there).

### Handler: `handleDecision(action, extra?)`

The one function that mutates server state. Called by `ReviewPane` with one of
`"accept" | "reject" | "flag" | "edit"` and, for `edit`, the new `{ question, answer }`
text.

1. Bails out silently if nothing is selected or candidates haven't loaded
   (`selectedIdx === null || !candidates`) — defensive; the UI never actually allows
   calling this without a selection.
2. Sets `submitting = true` (disables every action button in `ReviewPane` for the
   duration, so a double-click can't fire two decisions and mint two question ids).
3. Awaits `sendDecision({ idx: selectedIdx, action, ...extra })` (see §6).
4. On success: replaces just the changed row in a *new* `candidates` array
   (`[...candidates]` then `next[selectedIdx] = updated`) — never mutates the old array
   in place, so React's reference-equality check on `candidates` correctly detects the
   change.
5. **Advance-or-stay logic:** for `accept`/`reject`/`flag` (anything but `edit`),
   searches the *new* array for the next `pending` row (excluding the one just decided)
   and selects it, moving the reviewer straight to the next item. For `edit`, it
   deliberately does *not* advance — editing is usually done to re-check something, so
   staying on the same candidate avoids yanking the view away right after a correction.
6. On failure: stores the message in `error` (same `error` state the initial fetch uses
   — see the render branch below for what that does to the whole page).
7. `finally`: `submitting = false`, whether the call succeeded or failed.

### Render branches

`App` renders exactly one of four things, checked in this order:

1. **`error` is set** → a centered `container` with an `h4` "Could not load", the error
   message, and a hint pointing at the two most likely causes (dev server not running
   from the repo root; `corpus/.cache/page_catalog.jsonl` missing). This branch fires for
   *both* the initial-load failure and a failed decision — a failed accept/reject/flag/
   edit blanks the whole app rather than leaving it in an ambiguous partial state.
2. **`candidates` is still `null`** → "Loading candidates…", centered, same container
   styling as the error state for visual consistency.
3. **Otherwise**, the real UI:
   - `<div className="d-flex flex-column vh-100">` — full-viewport-height flex column,
     the outermost layout box.
   - `<header>` — a flex row, space-between, containing the `<h1>` title and
     `<ProgressBar candidates={candidates} />`. `border-bottom` + `bg-body` so it reads
     as a distinct bar from the content below regardless of light/dark theme.
   - **The pane-switcher tab bar** (`<div className="d-xl-none d-flex border-bottom
     bg-body" role="tablist">`) — `d-xl-none` means this entire bar only exists visually
     below the `xl` breakpoint; at `xl`+ all three panes show at once, so there's nothing
     to switch between. Three `<button role="tab">`s ("List" / "Review" / "PDF"), each
     `flex-fill` (equal width, filling the bar), styled `btn-primary` when it matches the
     current `mobileView` and `btn-light` otherwise, each with `aria-selected` reflecting
     the same comparison. "Review" and "PDF" are `disabled={!selected}` — there's nothing
     to review or open before a candidate is selected, so those tabs are inert (not
     hidden — inert, so their presence still communicates "there are three views" even
     before one is available).
   - `<div className="review-grid flex-grow-1">` — the responsive layout container (see
     `App.css`: a plain flex column below `xl`, the three-column CSS grid at `xl`+, with
     `min-height: 0` on both the container and its children so internal scrolling works
     either way). Always contains a wrapper around `<CandidateSidebar>`; then **either**:
     - `selected` is truthy → wrappers around `<ReviewPane>` and `<PdfPane>` as the
       second and third children, **or**
     - `selected` is `null` (every candidate has a decision) → a single centered
       "All caught up" message spanning where those two would be (this message doesn't
       participate in the mobile pane-switcher at all — it just occupies the grid/flex
       container directly).

### Responsive layout: the three pane wrappers

Each of the three real panes is rendered inside its own wrapper `<div>` rather than
passed straight to `.review-grid`, specifically so each one can carry its own
visibility classes without `CandidateSidebar`/`ReviewPane`/`PdfPane` needing to know
anything about screen width:

```tsx
<div className={`${mobileView === "list" ? "d-flex" : "d-none"} d-xl-flex flex-column h-100`}>
  <CandidateSidebar ... />
</div>
```

Read as: "hidden unless `mobileView` matches this pane — except at `xl`+, where it's
always `flex` no matter what `mobileView` is." Bootstrap generates `.d-xl-flex` inside an
`@media (min-width: 1200px)` block, so at that width it overrides the base `d-flex`/
`d-none` class unconditionally — this is ordinary, intentional Bootstrap responsive-
utility layering, not a specificity hack. The same pattern wraps `ReviewPane` (keyed off
`mobileView === "review"`) and `PdfPane` (keyed off `mobileView === "pdf"`). Each wrapper
also carries `h-100` so the panel inside it (which sets its own `h-100` internally) has a
definite height to resolve against, both in flex-column mode and in grid mode.

---

## 3. `src/components/CandidateSidebar.tsx` — left column

Props: `candidates` (the full list, every status — not pre-filtered by the parent),
`selectedIdx`, and `onSelect(idx)`.

### State

- `typeFilter: AnswerType | "all"` — which `answer_type` to show, driven by the first
  `<select>`.
- `statusFilter: Pass2Status | "all"` — which `pass2_status` to show, driven by the
  second `<select>`.

Both filters are local UI state, not lifted to `App` — `App` never needs to know what's
currently filtered, only what's selected.

### Derived value: `ordered` (`useMemo`, deps: `[candidates, typeFilter, statusFilter]`)

Three steps, built once per dependency change rather than on every render:

1. `candidates.map((c, idx) => ({ c, idx }))` — pairs every candidate with its original
   array index, because that index (not the filtered position) is what `onSelect` and
   `PdfPane`/`ReviewPane` need.
2. Two `.filter()` calls applying `typeFilter` and `statusFilter` (each a no-op when set
   to `"all"`).
3. `.sort()` by a fixed `TYPE_ORDER` (`table_numeric, multi_hop, unanswerable,
   ambiguous, single_fact` — harder/rarer types first), falling back to original index
   order within the same type. `byType` is a small `Map<index, rank>` built once per
   render of this memo so the sort comparator is a cheap lookup, not a `TYPE_ORDER.indexOf`
   call per comparison.

### Handler: `jumpToNextPending()`

Finds the first `ordered` entry with `pass2_status === "pending"` and calls
`onSelect(idx)`. Operates on the *filtered/sorted* list, not the raw `candidates` array
— "next pending" respects whatever filters are currently active, matching what's
actually visible on screen.

### JSX, element by element

- `<aside className="d-flex flex-column h-100 border-end bg-body">` — the whole
  component's root; a flex column so the filter bar and the scrollable list stack
  vertically and the list can grow to fill remaining height.
  - **Filter bar** (`<div className="d-flex flex-wrap gap-2 p-2 border-bottom">`):
    - Type `<select>` (`form-select form-select-sm w-auto`) — one `<option>` per entry
      in `TYPE_ORDER` plus an `"All types"` default. `value`/`onChange` wired straight to
      `typeFilter`.
    - Status `<select>` — four fixed `<option>`s (`pending`/`accepted`/`rejected`/
      `flagged_hard`) plus `"All statuses"`. Wired to `statusFilter`.
    - `<button>` "Next pending →" (`btn btn-sm btn-outline-primary ms-auto` — `ms-auto`
      pushes it to the right end of the flex row) → calls `jumpToNextPending`.
  - **The list** (`<div className="list-group list-group-flush overflow-y-auto
    flex-grow-1">`): Bootstrap's list-group component, `flush` to drop the outer border
    (the `<aside>` already has one), `overflow-y-auto` + `flex-grow-1` so this is the
    one part of the sidebar that scrolls while the filter bar stays fixed.
    - One `<button>` per entry in `ordered`, each `list-group-item
      list-group-item-action` (Bootstrap's clickable-row styling) plus `.active` when
      `idx === selectedIdx` (Bootstrap's own selected-state styling — solid primary
      background). Inside each row, left to right:
      - index number (`font-monospace text-body-secondary small`, fixed `1.8em` width so
        numbers align in a column regardless of digit count)
      - `answer_type` (`text-uppercase text-primary-emphasis small`, fixed `5.5em` width,
        `flexShrink: 0` so a long question text never compresses it)
      - the question text itself (`text-truncate small flex-grow-1 text-start` — takes
        all remaining row width and ellipsizes instead of wrapping)
      - `<StatusBadge status={c.pass2_status} />` (§5)
    - A fallback `<div>` ("No candidates match these filters.") shown only when `ordered`
      is empty — otherwise the list would just render as a blank area with no
      explanation.

---

## 4. `src/components/ReviewPane.tsx` — middle column

Props: `candidate` (the currently selected `CandidateWithContext` — never `null`; `App`
only renders this component when one exists), `submitting`, and `onDecision(action,
extra?)`.

### State

- `editing: boolean` — whether the question/answer are currently shown as editable
  textareas instead of static text.
- `draftQ`, `draftA: string` — the in-progress edited text, seeded from
  `candidate.question`/`candidate.answer`.

### Effect (`useEffect`, deps: `[candidate.idx]`)

Runs every time the selected candidate changes (not on every re-render of the same
candidate — `candidate.idx` is the dependency, not `candidate` itself, so an in-place
update to the same candidate, e.g. after a successful edit, does *not* reset the form).
Resets `editing` to `false` and reseeds `draftQ`/`draftA` from the new candidate. Without
this, switching candidates while mid-edit would carry the previous candidate's draft
text onto the new one.

### Derived value: `needsReview`

`candidate.licence === "needs_review-manufacturer_authored_mandatory_disclosure"` — a
plain boolean, recomputed each render (cheap enough not to need `useMemo`). Controls
whether the "licence: needs review" badge shows.

### JSX, element by element

Root: `<div className="d-flex flex-column gap-3 h-100 overflow-y-auto border-end p-3
pb-5">` — scrolls independently of the sidebar and PDF pane (see `App.css`'s
`.review-grid` note for why `h-100` + `overflow-y-auto` need the `min-height: 0` fix on
the parent grid to actually work).

1. **Badge row** (`<div className="d-flex flex-wrap gap-2">`):
   - `answer_type` — `badge rounded-pill text-bg-primary` (solid, always shown)
   - `source` (`faa`/`nhtsa`) — `text-bg-secondary` (solid; see `StatusBadge.tsx`'s
     comment on why the `-subtle` variant isn't used)
   - `confidence: {value}` — `text-bg-danger` when `confidence === "low"` (draws the eye
     to candidates worth extra scrutiny), otherwise the same solid `text-bg-secondary`
   - `licence: needs review` — only when `needsReview`, `text-bg-warning`
   - `{question_id}` (e.g. `q047`) — only once the candidate has been accepted at least
     once, `text-bg-success font-monospace` (monospace because it's an id, not prose)
2. **Question/answer**, two mutually exclusive branches on `editing`:
   - **Editing:** a labeled `<textarea className="form-control font-monospace
     small">` for the question (3 rows) and one for the answer (2 rows), each a
     controlled input (`value`/`onChange` wired to `draftQ`/`draftA`).
   - **Not editing:** the question as a `<p className="fs-5 fw-semibold mb-0">`, and the
     answer as `<code className="d-inline-block bg-body-tertiary border rounded px-2 py-1
     fs-6">` — rendered as inline code specifically because answers are often literal
     values (part numbers, dates, dollar amounts) that benefit from a monospace,
     visually-distinct treatment.
3. **Evidence quotes** — only rendered when `candidate.evidence_quotes.length > 0`
   (always true except for the hand-constructed `unanswerable`/`ambiguous` rows, which
   carry no quote). One `<blockquote>` per quote (`multi_hop` candidates have two,
   matching their two source locations), styled with a left accent border
   (`border-start border-primary border-3`) and monospace text, since these are verbatim
   excerpts, not paraphrases.
4. **Page context** — only rendered when `candidate.contexts.length > 0` (empty only for
   the one `unanswerable` candidate whose `source_locations` is `[]`). A native
   `<details open>`/`<summary>` disclosure (not React state — the browser owns open/
   closed state here, and it defaults open since checking context is the core task of
   this screen), containing one `<div className="card">` per location:
   - `card-header` — `{doc_id} · p.{page} · {region}` (region omitted if empty)
   - `card-body` as a `<pre>` — the raw excerpt text, `whiteSpace: "pre-wrap"` so line
     breaks in the source page are preserved, with its own `overflow-y: auto` and a
     `220px` max height so one very long excerpt can't push the rest of the pane down
     off-screen.
5. **Notes** — `candidate.notes` rendered as small italic text, only when non-empty
   (every real candidate has notes; this guard is defensive).
6. **Action bar** (`<div className="d-flex gap-2 mt-auto sticky-bottom bg-body border
   rounded p-2 shadow-sm">`) — `mt-auto` pushes it to the bottom of the flex column when
   content is shorter than the pane; `sticky-bottom` (a genuine Bootstrap utility, not
   custom CSS) keeps it pinned to the bottom of the *scrolling* pane once content
   overflows, so the buttons are reachable without scrolling all the way down. Two
   mutually exclusive button sets on `editing`:
   - **Editing:** "Cancel" (`btn btn-outline-secondary`, just sets `editing = false`,
     discarding `draftQ`/`draftA` — they get reseeded from `candidate` next time editing
     starts anyway) and "Save edit" (`btn btn-success`, calls
     `onDecision("edit", { question: draftQ, answer: draftA })` then sets `editing =
     false` immediately — it doesn't wait for the request to resolve, since `App`'s
     `handleDecision` already owns the submitting/error lifecycle).
   - **Not editing:** "Reject" (`btn btn-danger`), "Accept" (`btn btn-success`), "Edit"
     (`btn btn-outline-secondary`, local-only — flips `editing = true`, no `onDecision`
     call), "Flag hard" (`btn btn-outline-warning`). All four are `disabled={submitting}`.

---

## 5. `src/components/PdfPane.tsx` — right column

Props: `contexts` (`LocationContext[]` — just the array of `{doc_id, page, region,
excerpt}` the selected candidate carries; this component never sees the rest of the
candidate).

### State

- `locIdx: number` — which of `contexts[]` is currently displayed (relevant only for
  `multi_hop` candidates, which have two).

### Effect (`useEffect`, deps: `[contexts]`)

Resets `locIdx` to `0` whenever the `contexts` array reference changes (i.e. whenever a
different candidate is selected — `App` always passes a fresh array per candidate).

### The `safeIdx` clamp — a real bug fix, documented in code

```ts
const safeIdx = Math.min(locIdx, contexts.length - 1);
const loc = contexts[safeIdx];
```

React renders *before* a newly-committed effect runs. If the previous candidate was
`multi_hop` (`locIdx === 1`) and the next one selected has only one location, this
component re-renders once with the *old* `locIdx` (`1`) against the *new* `contexts`
(length `1`) before the `useEffect` above has a chance to reset it — `contexts[1]` would
be `undefined`, and the old code crashed reading `.doc_id` off it. Clamping `locIdx`
against the current `contexts.length` at render time (not just in the effect) fixes this
unconditionally, regardless of render timing.

### JSX, element by element

Two top-level return branches:

1. **`contexts.length === 0`** (the one `unanswerable` candidate with no source) — a
   centered placeholder: "No source location." plus an explanation that this is
   intentional (out-of-scope by construction), not a loading or error state.
2. **Otherwise**, `<div className="d-flex flex-column h-100">`:
   - **Toolbar** (`<div className="d-flex align-items-center flex-wrap gap-2 p-2
     border-bottom small text-body-secondary">`):
     - A Bootstrap `btn-group` of per-location buttons ("Loc 1 · p.498", "Loc 2 ·
       p.492", ...), **rendered only when `contexts.length > 1`** — single-location
       candidates (the overwhelming majority) show no switcher at all. The button
       matching `safeIdx` gets `btn-primary`; the rest get `btn-outline-secondary`.
       Clicking one calls `setLocIdx(i)`.
     - A monospace label showing the *currently displayed* location:
       `{doc_id} · page {page} · {region}`.
   - **The PDF itself:** `<iframe key={src} title="Source PDF" src={src}
     className="flex-grow-1 border-0 w-100" />`, where `src` is built as
     `` `/pdfs/${encodeURIComponent(loc.doc_id)}#page=${loc.page}` `` — the `#page=N`
     fragment is honored by Chromium/Firefox's built-in PDF.js viewer, landing the
     reader directly on the right page with no custom PDF-rendering code at all (see
     `decisions.md`'s entry on this tool for why `react-pdf`/`pdfjs-dist` was rejected
     for v1). **`key={src}`** is deliberate: React normally patches an existing
     `<iframe>` in place when only its `src` attribute changes, which is not guaranteed
     to re-navigate reliably for a hash-only change; keying on the full `src` string
     forces React to unmount and remount a fresh `<iframe>` on every location switch,
     guaranteeing a real navigation every time.

---

## 6. `src/components/ProgressBar.tsx` — header summary

Props: `candidates` (the full array — this component computes its own counts rather
than receiving pre-computed numbers, since it's cheap and keeps `App` from needing to
know anything about how progress is displayed).

No state, no effects — a pure function of its props, recomputed every render:

```ts
const counts = { accepted: 0, rejected: 0, flagged_hard: 0, pending: 0 };
for (const c of candidates) counts[c.pass2_status]++;
const reviewed = total - counts.pending;
const pct = (n) => (total ? (100 * n) / total : 0);
```

### JSX

- Outer `<div className="d-flex flex-column gap-1 flex-grow-1 flex-xl-grow-0"
  style={{ minWidth: "160px", maxWidth: "320px" }}>` — `minWidth`/`maxWidth` keep the
  header from visibly reflowing as the numbers inside change width (e.g. `9` accepted vs
  `186` accepted), while staying narrow enough (`160px` minimum, not a fixed `320px`) to
  fit a small phone's header alongside the title. `flex-grow-1` lets it fill the header's
  remaining width below `xl` (where the header is often the widest element on the page);
  `flex-xl-grow-0` turns growth off again at `xl`+, where the header has room to spare and
  a stretched progress bar would look odd next to a short title.
- Bootstrap's `progress`/`progress-bar` components, used as a **stacked** bar: three
  sibling `.progress-bar` divs (`bg-success`, `bg-danger`, `bg-warning`), each with an
  inline `width: {pct}%` — Bootstrap's stacked-progress pattern, not a single bar with a
  changing color.
- A row of four counts below the bar (`d-flex flex-wrap gap-2 gap-xl-3` — `flex-wrap` so
  the four items drop to a second line rather than overflowing on a narrow phone, with a
  tighter gap below `xl` and Bootstrap's default spacing above it): total reviewed
  (`<strong>{reviewed}</strong>/{total} reviewed`), then accepted/rejected/flagged each
  colored to match its segment (`text-success`/`text-danger`/`text-warning-emphasis`).
  `font-monospace` plus `fontVariantNumeric: "tabular-nums"` so the digits don't shift
  horizontally as counts change width.

---

## 7. `src/components/StatusBadge.tsx` — small reusable pill

Props: `status: Pass2Status`. The only component reused by another component
(`CandidateSidebar`) rather than directly by `App`.

Two lookup tables keyed by `Pass2Status`:
- `VARIANT` — the Bootstrap badge class (`text-bg-secondary` for `pending`,
  `text-bg-success` for `accepted`, `text-bg-danger` for `rejected`,
  `text-bg-warning` for `flagged_hard`). The code comment here is the canonical
  explanation for why every badge in this app uses the **solid** `text-bg-*` form
  rather than Bootstrap's lighter `-subtle` variant: the `-subtle`/`-emphasis` pair is
  auto-computed by Bootstrap's Sass `tint-color`/`shade-color` mixins from whatever base
  color is supplied, and this project's custom `$secondary` (a desaturated brown-gray)
  produces near-invisible text when run through that computation. Solid badges sidestep
  it entirely.
- `LABEL` — the display text (`"flagged"` for `flagged_hard`, otherwise the status name
  verbatim).

Renders a single `<span className="badge rounded-pill {VARIANT[status]}">
{LABEL[status]}</span>`.

---

## 8. `src/api/client.ts` — the only two network calls

Not components — plain async functions, imported only by `App.tsx`. No other file in
`src/` calls `fetch()` directly.

- **`fetchCandidates()`** — `GET /api/candidates`. On a non-OK response, attempts to
  parse an `{error}` JSON body for a useful message, falling back to a generic
  `"GET /api/candidates failed (status)"` if the body isn't JSON (`.catch(() => ({}))`
  guards against a non-JSON error page, e.g. a raw 500 stack trace). Returns the parsed
  array typed as `CandidateWithContext[]`, trusting the server's shape (no runtime
  validation on the client — the server and client share `shared/types.ts`, so a
  mismatch would be a build-time type error during development, not a runtime surprise
  in production).
- **`sendDecision(req)`** — `POST /api/decision` with `req` as a JSON body. Always reads
  the response body as JSON, then narrows it: `"ok" in body` distinguishes a successful
  `DecisionResponse` from an `{error}` response using a TypeScript type guard rather than
  checking `res.ok` alone — both the HTTP status *and* the parsed shape have to agree the
  call succeeded. Returns just `body.candidate`, not the whole envelope, so `App` never
  has to unwrap `{ok, candidate}` itself.

---

## 9. `shared/types.ts` — the data contracts (not a React file, but what every prop is typed against)

Every `interface`/`type` here is imported by both `server/` (Node) and `src/` (browser)
from the same file — see `decisions.md`'s entry on this tool for why that matters
(schema agreement across three interchangeable review interfaces: this app, the terminal
tool, and the claude.ai Artifact reviewer).

- **`AnswerType`** — the five golden-set question categories; drives `CandidateSidebar`'s
  type filter and `TYPE_ORDER` sort, and `ReviewPane`'s first badge.
- **`Pass2Status`** — the four review states; drives `StatusBadge`, `ProgressBar`'s
  counts, and `CandidateSidebar`'s status filter.
- **`SourceLocation`** — `{doc_id, page, region}`, one entry per place in the corpus an
  answer comes from (almost always one; two for `multi_hop`; zero for the one
  out-of-scope `unanswerable` row).
- **`Candidate`** — the full shape of one `golden/candidates.jsonl` row, as read and
  written by `server/goldenStore.ts`. `question_id`, once set, is what lets
  `ReviewPane`'s re-edit flow patch the matching `golden/questions.jsonl` row instead of
  minting a duplicate.
- **`LocationContext`** — a `SourceLocation` plus the `excerpt` text the server computed
  from `corpus/.cache/page_catalog.jsonl`; this is what `PdfPane`'s toolbar label and
  `ReviewPane`'s context cards actually render.
- **`CandidateWithContext`** — what `GET /api/candidates` actually returns: a
  `Candidate` plus `idx` (its position in the array — the stable identifier `App` uses
  for `selectedIdx` and that `handleDecision` sends back to the server) and `contexts`
  (one `LocationContext` per `source_locations` entry).
- **`Question`** — one `golden/questions.jsonl` row; not directly rendered by any
  component (the browser never reads `questions.jsonl`), but defines the server's write
  shape, which `ReviewPane`'s "Accept"/"Save edit" flow ultimately produces.
- **`DecisionAction`** / **`DecisionRequest`** / **`DecisionResponse`** — the exact
  request/response shape `api/client.ts` and `server/index.ts`'s `/api/decision` route
  agree on; `ReviewPane`'s `onDecision` callback signature is built directly from
  `DecisionAction` plus the optional fields of `DecisionRequest`.

---

## 10. End-to-end flows

**On page load:** `main.tsx` sets the theme attribute → mounts `<App>` → `App`'s mount
effect calls `fetchCandidates()` → on success, `candidates` and `selectedIdx` (first
pending row) are set → `App` re-renders into the three-column layout → `CandidateSidebar`
renders its filtered/sorted list from `candidates`, `ReviewPane` and `PdfPane` render
from `selected` (the `candidates[selectedIdx]` memo).

**Clicking a sidebar row:** `CandidateSidebar`'s `onClick` calls the `onSelect` prop
(`App`'s `handleSelect`) → `setSelectedIdx(idx)` and `setMobileView("review")` both fire
→ `App` re-renders → `selected` memo recomputes → `ReviewPane` and `PdfPane` both receive
a new `candidate`/`contexts` prop → `ReviewPane`'s effect resets its edit-draft state
(keyed on `candidate.idx`); `PdfPane`'s effect resets `locIdx` to `0` (keyed on the new
`contexts` array) and its `safeIdx` clamp guarantees no crash even before that effect
runs. Below `xl`, the `mobileView` change also means the visible pane flips from List to
Review in the same update, so the reviewer lands directly on the new candidate's content
instead of having to tap a "Review" tab separately.

**Switching panes on a narrow screen:** tapping "List"/"Review"/"PDF" in the tab bar
calls `setMobileView(...)` directly — no other state changes. `App` re-renders; each of
the three pane wrappers recomputes its `d-flex`/`d-none` class against the new
`mobileView`, so exactly one pane becomes visible and the other two disappear. Nothing
unmounts in the React sense (all three panes stay mounted the whole time, just
`display: none`), so a hidden `ReviewPane`'s edit-in-progress text or a hidden
`PdfPane`'s scroll position are preserved, not lost, when switching back to them. At
`xl`+ this tab bar doesn't render at all, so there's nothing to click and no mode to be
in — all three panes are simply always visible.

**Clicking Accept/Reject/Flag:** `ReviewPane`'s button `onClick` calls `onDecision(action)`
(no `extra`) → `App.handleDecision` sets `submitting = true`, disabling every button in
`ReviewPane` → `sendDecision` POSTs to the server → on success, the one changed row is
spliced into a new `candidates` array, and (since the action isn't `"edit"`) the next
pending candidate is auto-selected → `submitting = false` re-enables the buttons on
whatever candidate is now shown.

**Editing then saving:** clicking "Edit" is purely local (`setEditing(true)`, no network
call) → the question/answer render as `<textarea>`s bound to `draftQ`/`draftA` → "Save
edit" calls `onDecision("edit", {question, answer})` and immediately exits edit mode
(`setEditing(false)`) without waiting for the request → the same `handleDecision` path
runs, but the "advance to next pending" step is skipped for `edit`, so the reviewer stays
on the same (now-updated) candidate.

**Switching a multi-hop location:** clicking "Loc 2 · p.492" in `PdfPane`'s button group
calls `setLocIdx(1)` → `safeIdx` becomes `1` → `loc` becomes `contexts[1]` → `src` is
rebuilt with the new `doc_id`/`page` → the `key={src}` change forces React to unmount and
remount the `<iframe>`, guaranteeing the browser's PDF viewer actually navigates to the
new page rather than silently ignoring a hash-only `src` update.

**Filtering the sidebar:** changing either `<select>` updates `typeFilter`/`statusFilter`
→ the `ordered` memo recomputes (filter + sort) → the list re-renders with only matching
rows → "Next pending →" and keyboard/mouse selection both operate on this same filtered
list, so what's clickable always matches what's visible.
