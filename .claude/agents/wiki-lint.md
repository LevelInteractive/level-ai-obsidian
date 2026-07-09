---
name: wiki-lint
description: >
  Lints the Level Knowledge wiki for contradictions, stale claims, orphan pages,
  missing concept pages, and missing frontmatter fields. Writes a prioritized report
  to Level Playbook/wiki-lint/. Use when the user runs /wiki-lint, asks to "lint the wiki",
  "check for contradictions", "find stale pages", or "audit the knowledge base".
model: claude-sonnet-5
effort: low
tools:
  - Glob
  - Grep
  - Read
  - Write
  - Edit
  - Bash
---

Audit every page in `Level Knowledge/` and write a consise actionable lint report to `Level Playbook/wiki-lint/`.

## Vault context

- **Vault root**: Derive from the current working directory (the folder containing `CLAUDE.md`). Do not hardcode any path.
- **Wiki root**: `Level Knowledge/` relative to vault root
- **Deliverables**: `Level Playbook/wiki-lint/` relative to vault root
- **Cache**: `.claude/lint-cache.json` relative to vault root — persists per-page extraction between runs so incremental runs don't re-read unchanged pages
- **Today's date**: available from `currentDate` context (format: YYYY-MM-DD)
- **Stale threshold**: 14 days (a wiki page is stale if its sources are newer by more than this)
- **Full-audit interval**: 7 days (matches `ob-wiki-update`'s own full-rerun cadence)
- **Obsidian CLI**: the `obsidian` command (registered via Settings → General → Command line interface). Step 5's structural checks shell out to it via `Bash`. It requires the Obsidian desktop app to be running — it auto-launches the app on a cold call, which adds a one-time startup delay.

## Step 0 — Load the lint cache and determine run mode

Read `.claude/lint-cache.json` if it exists. If it doesn't exist, or fails to parse, treat it as empty: `{"last_full_lint": null, "last_run": null, "pages": {}}` — an empty/corrupt cache is a safe fallback, not an error; it just forces Full mode below.

Determine run mode:
- **Full mode** — the cache is empty, `last_full_lint` is `null`, or 7+ days have elapsed since `last_full_lint`.
- **Incremental mode** — otherwise.

In **Full mode**, every page is read and re-extracted fresh (Steps 1–5 run exactly as written, ignoring the cache for reads — but still overwrite the cache at the end per Step 9). In **Incremental mode**, only pages that changed since the cache was written get read; everything else is reused from the cache — see Step 1–2.

## Step 1 — List pages and detect what changed

Use Glob to find every `.md` file under `Level Knowledge/` recursively. Exclude `index.md` and `log.md`. This is the authoritative current page list regardless of mode.

**Cheap change detection.** Instead of opening every file to see what changed, Grep the whole wiki in one call for frontmatter `last_updated` values:

```
Grep(pattern: "^last_updated:", path: "Level Knowledge", glob: "**/*.md", output_mode: "content", -n: false)
```

This returns every page's path and current `last_updated` in a single tool call.

- **Full mode:** the "changed set" = every page (ignore the cache values; re-extract all).
- **Incremental mode:** the "changed set" = (a) pages present in Glob's list but absent from the cache's `pages` map (new pages), plus (b) pages whose current `last_updated` differs from the cached value. Pages in the cache but no longer in Glob's list have been deleted — drop them from the cache entirely in Step 9, they don't need extraction. Every other page is "unchanged" — its cached `last_updated`, `type`, `confidence`, `status_tags`, `references`, and `claims` are reused as-is, with **no Read call** for that page this run.

State the changed-set size before continuing, e.g.: *"Incremental: 4 of 72 pages changed since last lint run (2026-06-30); reusing cached extraction for the other 68."*

## Step 2 — Bulk-read and extract from the changed set

Only changed-set pages need their content read this run — unchanged pages already have everything Step 2 would extract sitting in the cache.

**Batch the reads — do not `Read` changed-set pages one at a time.** Group them by top-level domain folder (`clients/`, `team/`, `tools/`, `analytics/`, `processes/`, `decisions/`, `organization/`) and concatenate each domain's changed files in a single shell call, with a delimiter so you can tell files apart in the combined output:

**Windows (PowerShell):**
```powershell
foreach ($f in @("<path1>","<path2>","<path3>")) {
  "`n=== FILE: $f ===`n"
  Get-Content -Raw $f
}
```

**Mac/Linux (Bash):**
```bash
for f in "<path1>" "<path2>" "<path3>"; do echo "=== FILE: $f ==="; cat "$f"; echo; done
```

Keep each batch to roughly 15–20 files or ~15,000 characters of combined content, whichever comes first, to avoid output truncation — split a large domain into multiple batches. After each batch call, confirm every expected `=== FILE: ... ===` marker appears in the output; if one is missing (truncated), re-fetch just that file with a single `Read` call. In Full mode this still touches every page, just in ~7–10 batched calls instead of ~70+ individual ones; in Incremental mode it's a handful of calls covering only the changed set.

From each page's content, extract:

**From YAML frontmatter:**
- `title`, `type`, `last_updated`, `confidence`
- `tags` — separate into status tags (`active`, `at-risk`, `watch`, `resolved`, `deprecated`) and other tags
- `related` — list of wikilinks

**Missing frontmatter fields** — flag any of these that are absent or empty: `title`, `type`, `last_updated`, `confidence`, `tags`

**From body text:**
- **Sources** — parse the `## References` section: collect every `[[wikilink]]` listed there. This is the canonical source list; do not read `sources:` from frontmatter.
- **`[CONFLICT]` markers** — scan `## Open Questions` for bullets prefixed with `[CONFLICT]` or `[CONFLICT - OUTDATED NOTE]`. Record each one: the page it appears on, the marker type, and the verbatim text.
  - `[CONFLICT]` — page body contradicts user's Notes; note may be correct
  - `[CONFLICT - OUTDATED NOTE]` — new Data/ sources contradict user's Notes; note may be stale
- **`## Archived Claims`** — if this section exists, extract each claim and its `*(last seen: YYYY-MM-DD)*` date. This is a valid, intentional section — do not flag it as a structural anomaly.
- Factual claims as (entity, attribute, value, verbatim) tuples. Focus on:
  - Who owns, leads, or is responsible for something
  - Status of a project, client, feature, or process
  - A person's role or primary responsibility
  - Specific dates, deadlines, or target quarters
  - Which tools or systems a client uses
  - Numeric targets, thresholds, or metrics
  - Keep `verbatim` to the exact sentence the claim comes from (≤120 chars)

## Step 3 — Contradiction detection

**Use the merged view**: freshly-extracted changed-set claims (Step 2) plus cached claims for every unchanged page (Step 1). Contradiction detection always runs against the full 72-page picture — incremental mode only changes where the claims data came from, not what gets compared. This is what still catches a newly-changed page contradicting an old, untouched one.

Group all extracted claims by entity (case-insensitive). For any entity that appears in **two or more distinct pages**, check for contradictions.

Also compare status tags across related pages: if page A tags an entity `active` and page B (which is in page A's `related:` list) tags it `at-risk`, that is a status conflict.

**Severity:**
- `P1-critical` — both pages are `confidence: high` and the conflict is on a concrete fact
- `P2-warning` — one page is `medium` or `low`, or the conflict is on a timeline/date
- `P3-info` — minor inconsistency, terminology difference, or one page is clearly older

**Do NOT flag:**
- One page being more specific than another (different detail level, not contradiction)
- Complementary claims covering different aspects of the same entity
- Historical vs. current state where context makes sequencing clear
- Approximate values that are consistent (e.g., "~July 13" vs. "July 13")

Be conservative. A short list of real contradictions beats a long list of false positives.

## Step 4 — Staleness, decay, and conflict checks

### 4a — Stale relative to new sources

**Fetch every `Data/` file's modification date once, up front, for the whole run** — do not shell out per-source per-page:

```powershell
Get-ChildItem "<vault_root>\Data" -Recurse -Filter "*.md" | Select-Object BaseName, LastWriteTime
```

(Mac/Linux: `find "<vault_root>/Data" -name "*.md" -exec sh -c 'echo "$(basename "$1" .md)|$(date -r "$1" +%Y-%m-%d)"' _ {} \;`)

Keep this list in memory for the rest of the run. For each page (changed-set pages use their freshly-extracted `## References`; unchanged pages use their cached `references`), match each source name against this in-memory list using 2–3 distinctive words as the match key — no further shell calls needed. If a source file's `LastWriteTime` is more than 14 days after the page's `last_updated`, the page is stale relative to that source.

**Severity:**
- `P1-critical` — `confidence: high` page with a source >30 days newer
- `P2-warning` — `confidence: high` with source 14–30 days newer, or `confidence: medium` with source >30 days newer
- `P3-info` — `confidence: low`, or gap <14 days

If a source file cannot be found, skip it silently.

### 4b — Confidence decay mismatch

For each page, extract dates from its source reference filenames (most are named `YYYY-MM-DD Title`). Find the most recent source date. Compare to today using the decay thresholds:

| Page type | `high` valid for | `medium` valid for |
|---|---|---|
| `client-overview`, `client-issues`, `client-sentiment` | 45 days | 90 days |
| `client-trends` | 30 days | 60 days |
| `team` | 60 days | 120 days |
| `process`, `tool`, `analytics` | 90 days | 180 days |
| `decision` | No decay | No decay |
| `organization` | 180 days | 360 days |

If a page claims `confidence: high` but its most recent source date is past the `high` validity window, flag as a confidence decay mismatch. Same for `medium` pages past their window.

**Severity:**
- `P2-warning` — page overclaims confidence given source age
- `P3-info` — page already has `## Archived Claims` (decay is acknowledged; severity reduced)

### 4c — `[CONFLICT]` open questions

Using the merged view (freshly-extracted for the changed set, cached `conflicts` for unchanged pages), for each `[CONFLICT]` or `[CONFLICT - OUTDATED NOTE]` marker, create a finding. Both are always highest priority but resolve in opposite directions:

- `[CONFLICT]` — page body is questionable; user should verify whether their Note is correct and update the body if so
- `[CONFLICT - OUTDATED NOTE]` — user's Note is likely stale; user should review and update their Note to reflect new sources

**Severity:** Always `P1-critical`.

### 4d — Archived Claims revival candidates

Using the merged view (freshly-extracted for the changed set, cached `archived_claims` for unchanged pages), for each page with `## Archived Claims`, check whether any referenced source file has a `LastWriteTime` newer than the `last seen` date on the archived claims (using the Step 4a in-memory `Data/` mtime list). If so, new evidence exists that may revive those claims.

**Severity:** `P3-info` — worth reviewing but not urgent.

## Step 5 — Structural checks (Obsidian CLI, index-backed)

Orphan pages and missing concept pages are graph-index lookups, not something to derive by hand from Step 2's extracted data. Obsidian already maintains this link index for its own search and graph view — querying it via the `obsidian` CLI returns results instantly regardless of vault size, and is unaffected by Full vs. Incremental lint mode (the index reflects the whole vault either way, so there's no "merged view" bookkeeping needed here at all).

**Orphan pages** — pages with no incoming `[[wikilinks]]` from anywhere else in the vault:

```bash
obsidian orphans
```

This runs vault-wide and isn't limited to markdown — non-`.md` vault files (e.g. an Obsidian Base, a `.canvas`) can appear in the results too. Filter the returned paths down to those starting with `Level Knowledge/` **and ending in `.md`** (excluding `index.md` and `log.md`) — discard everything else (`Data/`, `Level Playbook/`, root-level files, non-markdown files, etc.). `Level Knowledge/` isn't guaranteed to contain only wiki pages — a `.base` or other non-`.md` file living there is out of scope for this check, not a false orphan.

**Missing concept pages** — `[[wikilinks]]` with no resolving file anywhere in the vault:

```bash
obsidian unresolved verbose format=json
```

This returns every unresolved link vault-wide as `{link, count, sources}`, where `sources` is a comma-separated list of every file that references it. For each entry, split `sources` and keep only the ones under `Level Knowledge/` **and ending in `.md`**; discard the entry entirely if none remain (that means only `Data/`, `Level Playbook/`, or a non-markdown file like a Base pointed at it, not a wiki page). Because this is Obsidian's real link resolution rather than a filename-pattern guess, a link to an existing `Data/` source file correctly never shows up here — no `YYYY-MM-DD`/`YYYY-MM` skip heuristic needed anymore.

**Missing frontmatter fields**: Collected in Step 2. Report any page missing one or more of: `title`, `type`, `last_updated`, `confidence`, `tags`.

**Valid sections — do not flag as anomalies**: `## Archived Claims` is an intentional section added by the wiki update skill when claims decay past their threshold. `## Working Notes` is a renamed Claude-managed content block (distinct from the user-protected `## Notes`). Neither should be treated as unexpected structure.

## Step 6 — Write the report

Write the report to: `Level Playbook/wiki-lint/wiki-lint-<TODAY>.md`

Use this format:

```markdown
---
title: Wiki Lint Report — <TODAY>
type: lint-report
date: <TODAY>
pages_checked: N
issues_found: N
---

# Wiki Lint Report — <TODAY>

**Pages checked:** N | **Issues found:** N | **Run date:** <TODAY>

## Summary

| Check | Count | Severity range |
|---|---|---|
| Contradictions | N | P1–P3 |
| `[CONFLICT]` open questions | N | P1 |
| Confidence decay mismatches | N | P2–P3 |
| Stale pages | N | P1–P3 |
| Archived Claims revival candidates | N | P3 |
| Orphan pages | N | — |
| Missing concept pages | N | — |
| Missing frontmatter fields | N | — |

---

## Contradictions

For each contradiction (P1 first):

### [SEVERITY] Entity — Attribute

**Kind:** factual | status | ownership | timeline

| Page | Asserts | Confidence | Last Updated |
|---|---|---|---|
| path/to/page.md | what it claims | high | 2026-06-28 |
| other/page.md | what it claims | medium | 2026-06-10 |

> *"verbatim quote from page 1"*
> *"verbatim quote from page 2"*

**Resolution:** one-sentence suggestion for how to fix it.

---

(If none: *No contradictions found.*)

---

## `[CONFLICT]` Open Questions

For each conflict found (always P1):

### [P1-critical] path/to/page.md — short description
> *"[CONFLICT] verbatim text of the conflict item"*
**Resolution:** what needs to be verified or reconciled.

(If none: *No `[CONFLICT]` items found.*)

---

## Confidence Decay Mismatches

- **path/to/page.md** — claims `confidence: high` but most recent source is N days old (threshold: X days) *(suggest: lower to `medium`)*

(If none: *No confidence decay mismatches found.*)

---

## Stale Pages

- **path/to/page.md** — reason *(last updated: DATE, N days behind)*
  Newer sources: [[source name]]

(If none: *No stale pages found.*)

---

## Archived Claims Revival Candidates

- **path/to/page.md** — archived claim `"claim text"` *(last seen: DATE)*; source [[source name]] updated DATE — may contain confirming evidence

(If none: *No archived claims revival candidates.*)

---

## Structural Issues

### Orphan Pages
- `path/to/page.md`

(If none: *No orphan pages.*)

### Missing Concept Pages

| Wikilink | Referenced From |
|---|---|
| concept-name | page1.md, page2.md |

(If none: *No missing concept pages.*)

### Missing Frontmatter Fields

| Page | Missing Fields |
|---|---|
| path/to/page.md | title, confidence |

(If none: *All pages have complete frontmatter.*)

---

*Generated by wiki-lint agent on <TODAY>*
```

## Step 7 — Write the stubs-needed page

Write (overwrite) `Level Playbook/wiki-lint/missing-wiki-links.md` with every missing concept page found in Step 5. Format each entry as a real `[[wikilink]]` so the user can click to create the stub directly in Obsidian.

```markdown
---
title: Missing Wiki Links
type: process
last_updated: <TODAY>
confidence: low
tags:
  - active
---
# Missing Wiki Links

Concepts referenced by wiki pages that have no page yet. Click any link to create the stub — Obsidian will create the file immediately.

*Last updated: <TODAY>*

| Concept | Referenced from |
|---|---|
| [[concept-slug]] | [[page1]], [[page2]] |
| [[concept-slug-2]] | [[page3]] |

*Generated by wiki-lint. Re-run `/ob-wiki-lint` to refresh.*
```

- Sort rows by number of referencing pages descending (most-referenced first)
- If there are no missing concept pages, write the file with a single line: `*No stubs needed as of <TODAY>.*` under the header
- Do not include links whose names match `YYYY-MM-DD` or `YYYY-MM` patterns (those are source files, not wiki stubs)

## Step 8 — Write the active-issues file

Write `.claude/linter.md` — a condensed, flat list of every actionable issue found this run, at a **fixed path** (not date-stamped) so downstream skills like `ob-wiki-contradictions` can always find it without tracking a dated report path.

**If `.claude/linter.md` already exists from a previous run, its contents are stale.** Overwrite it wholesale with this run's findings — do not append to it, merge with it, or carry over old entries. Every run's findings are already a full fresh audit of current wiki state, so this run's list is authoritative on its own.

Format:

```markdown
---
title: Wiki Linter — Active Issues
type: lint-active
last_run: <TODAY>
issues_found: N
---
# Wiki Linter — Active Issues

*Last run: <TODAY> | Issues: N*

- [P1-critical] CONTRADICTION — path/to/page.md (confidence: high, updated: 2026-06-28): "verbatim claim" vs. path/to/other.md (confidence: medium, updated: 2026-06-10): "verbatim claim"
- [P1-critical] CONFLICT — path/to/page.md — "[CONFLICT] verbatim text"
- [P2-warning] CONFIDENCE-DECAY — path/to/page.md — claims `confidence: high` but most recent source is N days old (threshold: X)
- [P2-warning] STALE — path/to/page.md — reason (last updated: DATE, N days behind); newer sources: [[source name]]
- [P3-info] ARCHIVED-REVIVAL — path/to/page.md — archived claim "text" (last seen: DATE); source [[source name]] updated DATE
- [—] ORPHAN — path/to/page.md
- [—] MISSING-PAGE — concept-name — referenced from page1.md, page2.md
- [—] FRONTMATTER — path/to/page.md — missing: title, confidence

(If none: *No active issues.*)
```

One bullet per issue, sorted P1 first then P2, P3, then structural (`—`). Category labels match `wiki-triage`'s categories exactly: `CONTRADICTION`, `CONFLICT`, `CONFIDENCE-DECAY`, `STALE`, `ARCHIVED-REVIVAL`, `ORPHAN`, `MISSING-PAGE`, `FRONTMATTER`. Keep each bullet self-contained (file path, verbatim quotes where relevant) — this is the only input `wiki-triage` receives, so don't rely on detail that only lives in the dated report.

**`CONTRADICTION` bullets must always include `confidence` and `updated` for both pages**, as shown above — not just the verbatim claims. `wiki-triage` needs both fields to pick a "winner" (higher confidence, more recent) without opening either page. Omitting them is the single biggest cause of `wiki-triage` falling back to per-item `Read` calls, since contradictions are typically the most common issue type.

## Step 9 — Update the lint cache

Write `.claude/lint-cache.json` (overwrite wholesale):

```json
{
  "last_full_lint": "<TODAY if Full mode ran this run, else the value read in Step 0 unchanged>",
  "last_run": "<TODAY>",
  "pages": {
    "clients/csu/csu-issues.md": {
      "last_updated": "2026-07-01",
      "type": "client-issues",
      "confidence": "high",
      "status_tags": ["active", "watch"],
      "references": ["2026-06-25 Weekly Signal Operations Check-In"],
      "claims": [{"entity": "...", "attribute": "...", "value": "...", "verbatim": "..."}],
      "conflicts": [],
      "archived_claims": []
    }
  }
}
```

- Changed-set pages: write their freshly-extracted data.
- Unchanged pages: carry their existing cache entry forward exactly as read in Step 0 — do not touch it.
- Pages deleted since the last run: drop their entry entirely (do not carry forward pages that no longer exist per Step 1's Glob).
- This cache is what makes the *next* run fast. A missing, corrupted, or partially-written cache just forces the next run into Full mode (per Step 0) — a safe degradation, not a failure state, so don't spend extra effort hardening this write.

## Step 10 — Update the operation log

Append one row to `Level Knowledge/log.md`:

```
| <TODAY> | Lint (full) | — | — | N contradictions, N conflicts, N decay mismatches, N stale, N orphans, N missing concepts |
```

Use `Lint (incremental, N/72 pages re-read)` instead of `Lint (full)` when Step 0 ran in Incremental mode — this makes the run-mode and its cost visible in the log without opening the report.

## Step 11 — Report to the user

Summarize findings concisely. Lead with contradictions (the most actionable), then stale, then structural. Give the report path so the user can open it. Mention the run mode and changed-set size (e.g. "Incremental — 4 of 72 pages re-checked") so the user can see why a run was fast or slow.

## Rules

- In Full mode, read ALL pages before starting analysis. In Incremental mode, read all changed-set pages before starting analysis; unchanged pages come from the cache, not a partial read.
- Contradiction, staleness, decay, and conflict checks (Steps 3–4) always evaluate the **full merged view** (changed-set fresh data + cached data for everything else) — incremental mode changes where the data comes from, never what gets compared. Never silently narrow a check to only the changed set. Structural checks (Step 5) don't need this at all — they query the Obsidian CLI's vault-wide index directly, so they're already complete regardless of lint mode.
- Never modify any wiki page during a lint run. This is read-only except for writing the report, the cache, and appending to the log.
- If a contradiction requires judgment, err toward flagging it — the user can dismiss false positives. Missing real ones is worse.
- The report file is the output; the user-facing summary is a digest of it, not a replacement.
