# Corpus Acquisition — Requirements and Research Findings

**Researched:** 22 Oct 2026
**Status:** not yet downloaded. Build the downloader, then run and verify.

---

## Targets

| Source | Target | Licence position |
|---|---|---|
| NHTSA recall documents | 50-70 | Part 573 reports are US government records — public domain |
| DoD issuances (publicly releasable) | 20-30 | US government works — public domain |
| FAA Advisory Circulars | 20-30 | US government works — public domain |
| **Total** | **90-130** | |

---

## LICENSING WARNING — read before downloading NHTSA content

**NHTSA Technical Service Bulletins are manufacturer documents.** NHTSA hosts
them under its Office of Defects Investigation, but the documents themselves are
authored and copyrighted by OEMs. Republishing them in a public portfolio repo is
a copyright risk.

**Use Part 573 Safety Recall Reports instead.** These are filed with NHTSA as
government records, are routinely published by the agency, and are safe to
redistribute. They are also structurally richer for our purposes: part numbers,
affected-vehicle tables, remedy procedures, and chronologies.

If TSB content is wanted, store **metadata and index records only** (which are
government data), never the bulletin PDFs.

Record the licence determination per document in `manifest.json`. Do not write
"public domain" without having checked the source.

---

## Source 1 — NHTSA recall documents

### What exists
- **Recalls API:** `https://api.nhtsa.gov/recalls/recallsByVehicle` — returns
  JSON **metadata only**, no document files.
- **Flat files:** `https://static.nhtsa.gov/odi/ffdd/` hosts the ODI flat-file
  downloads (recalls, complaints, investigations, manufacturer communications).
  These are index data and include document references.
- **Document files:** recall report PDFs are served from
  `https://static.nhtsa.gov/odi/rcl/<year>/<filename>.PDF`. Filenames come from
  the flat-file index, not from a guessable pattern.
- **data.gov catalogue entry** for the ODI TSB system is a **metadata download**,
  not the bulletin PDFs. Do not mistake it for a document corpus.

### Approach
1. Pull the recalls flat file from `static.nhtsa.gov/odi/ffdd/`
2. Parse it for Part 573 report document references
3. Fetch 50-70 PDFs spanning multiple manufacturers and years — deliberately
   diversify, since format varies by OEM and by era, which is the interesting
   part for a document-intelligence system
4. Record the flat-file row alongside each document in the manifest

### Uncertainty
The exact flat-file schema and document-URL construction were not verified
during research. Expect one iteration here. Verify against a handful of
documents before scaling to 70.

---

## Source 2 — DoD issuances

### What exists
- Index: `https://www.esd.whs.mil/DD/issuances/dodm/` (DoD Manuals), with
  sibling paths for `dodi` (Instructions) and `dodd` (Directives)
- PDFs: `https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodm/<id>.pdf`

### Approach
Fetch the index page, regex for `/Portals/54/Documents/DD/issuances/` PDF links,
take 20-30. Prefer **Manuals (DoDM)** over Directives — manuals are longer, have
numbered paragraph hierarchies, enclosures and tables, which exercise structural
extraction. Directives are short policy statements and teach the system little.

### Note
Only publicly posted issuances. Anything requiring CAC authentication is out of
scope — do not attempt it.

---

## Source 3 — FAA Advisory Circulars

### What exists
This source is **two-hop**, which is the main finding from research:

1. Topic listing pages:
   `https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.list/parentTopicID/<id>`
   Known topic IDs: 110, 120, 121, 133, 155, 188 (there are more; enumerate from
   the AC landing page)
2. Listing pages link to **information pages**, not PDFs:
   `.../index.cfm/go/document.information/documentID/<documentID>`
3. The PDF link is on the information page. Observed PDF pattern:
   `https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_<number>.pdf`
   The naming is inconsistent (e.g. `AC_00.2-13.pdf`), so **do not construct
   these URLs** — extract them from the information pages.

### Alternative bulk source
The National Transportation Library has an FAA circulars collection at
`https://rosap.ntl.bts.gov/collection_faacirculars`. Repository platforms often
expose OAI-PMH or a REST API, which would be far cheaper than crawling
faa.gov. **Check this first** — it may remove the two-hop crawl entirely.

### Prefer these ACs
Specification-dense, table-heavy circulars teach the system more than policy
prose. AC 43.13-1B (Acceptable Methods, Techniques, and Practices) and similar
maintenance/airworthiness circulars are ideal.

---

## Downloader requirements

Write it as `src/corpus/fetch_corpus.py`. It must:

1. **Be resumable.** Skip documents already present with a matching SHA256.
   You will run this more than once.
2. **Rate-limit politely.** These are public agency servers. Add a delay between
   requests and set a real User-Agent identifying the project.
3. **Treat each source independently.** A failure in one source must not abort
   the others. Report per-source counts at the end.
4. **Write `corpus/manifest.json`** with one entry per document:
   `doc_id`, `source`, `source_url`, `retrieved_at`, `licence`, `page_count`,
   `sha256`, `bytes`, `description`.
5. **Compute page counts** (pypdf or similar). If a PDF fails to parse, record
   it with `page_count: null` and a `parse_error` field rather than dropping it —
   malformed PDFs are part of the real problem space and should be visible.
6. **Verify downloads.** Reject HTML error pages saved as `.pdf` (check the
   `%PDF` magic bytes). This is the most common silent failure in corpus
   scraping.
7. **Log a summary table**: per source, requested / fetched / skipped / failed.

### Do not
- Hardcode document URLs. Crawl the indexes so the script stays usable.
- Flatten filenames into a single namespace without recording the original.
  Keep `corpus/raw/<source>/<original_filename>`.

---

## Acceptance checks before declaring the corpus done

- [ ] ≥200 documents total (top up from the richest source if short)
- [ ] Every file begins with `%PDF`
- [ ] `manifest.json` entry count equals file count in `corpus/raw/`
- [ ] Every entry has a non-empty `licence` field that was actually determined,
      not assumed
- [ ] Page-count distribution inspected — if everything is 1-2 pages, the corpus
      is too thin to be interesting; re-select
- [ ] At least 3 distinct document formats/layouts represented
- [ ] No NHTSA TSB bulletin PDFs present (metadata only, per the warning above)
- [ ] `decisions.md` entry recording corpus choice and the two rejected
      alternatives

---

## Why this corpus

Recorded here so it can be defended in interview:

- **Verifiable by the author.** Golden-set construction needs domain knowledge to
  tell a correct answer from a plausible one. Automotive recall documents sit
  adjacent to the author's professional domain.
- **Legally publishable.** The project ships to a public URL.
- **Structurally hard.** Part numbers, tables, procedures, cross-references and
  diagrams — the properties that break naive RAG and therefore the properties
  worth measuring.
- **Format heterogeneity.** Three agencies and many OEMs means genuinely varied
  layouts, which is the realistic case and the one most portfolio projects avoid.

Rejected: arXiv papers (easy to obtain, prose-shaped, teach nothing about
document structure) and OEM service manuals (copyrighted, not publishable).
