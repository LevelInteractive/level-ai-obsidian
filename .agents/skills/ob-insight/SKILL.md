---
name: ob-insight
description: >
  Analyzes Level Knowledge wiki pages over a user-specified time window to surface key trends,
  missed signals, improvement opportunities, and anything else noteworthy. Can dive into raw
  Data/ sources via wiki References when pages are low-confidence or the question needs depth.
  Use when the user runs /ob-insight, asks for "insights from last week", "what did I miss this
  month", "trends from the past X days", or any request to synthesize patterns from the knowledge base.
---

# ob-insight

Surface trends, gaps, and opportunities from the Level Knowledge wiki over a specified time period.
Read the wiki first; follow raw references as needed to go deeper.

## Vault paths

- **Vault root**: `the vault root (derive dynamically from cwd -- never hardcode)`
- **Wiki root**: `Level Knowledge\`
- **Wiki index**: `Level Knowledge\index.md`
- **Raw sources**: `Data\Meetings`, `Data\Work`, `Data\Daily`, `Data\Inbox`, `Data\Resources`, `Data\Personal`, `Data\Codex`
- **Output**: `Level Playbook\insights\insight\`
- **Hub (latest)**: `Level Playbook\Hub\latest-insights.md`
- **History**: `Level Playbook\insights\Insights History.md`

## Step 0 — Parse the time window

Read the user's args to determine the analysis window. Supported formats:

| Input | Interpretation |
|---|---|
| `last week` | 7 days ending today |
| `last 2 weeks` | 14 days ending today |
| `last month` / `June` / `June 2026` | Calendar month |
| `last N days` | N days ending today |
| `YYYY-MM-DD to YYYY-MM-DD` | Explicit range |
| *(no args)* | Default: last 14 days |

Derive `window_start` and `window_end` (both inclusive, format `YYYY-MM-DD`). Today is `window_end` unless the user specifies otherwise.

Announce the window to the user before proceeding:
> Analyzing Level Knowledge for **{window_start} → {window_end}**...

## Step 1 — Identify relevant wiki pages

Read `Level Knowledge\index.md` to get the full list of wiki pages and domains.

Then read each wiki page's YAML frontmatter to determine which pages fall within scope:

**Primary scope** — pages with `last_updated` on or after `window_start`:
- These are pages that changed during the window — high relevance.

**Secondary scope** — pages NOT updated in the window but referenced by in-scope pages:
- These provide context for understanding what changed.

**All-domains scan** — for trend detection, read at least the overview page for every active client and one representative page from each domain, even if their `last_updated` is before the window. Pattern detection requires baseline context.

Read all in-scope pages in full. Note each page's `confidence` level as you go — it governs whether you need to dive into raw sources.

## Step 2 — Decide when to go deeper into Data/

After reading the wiki pages, identify where a deeper dive would sharpen the insight:

| Trigger | Action |
|---|---|
| Page `confidence: low` and you're drawing conclusions from it | Read all files listed in its `## References` section |
| Page `confidence: medium` and the insight depends on a specific claim | Read the most relevant 1–2 reference files |
| Two pages appear to contradict each other | Read both pages' references to resolve |
| A claim is time-sensitive (e.g., a metric or status) and may have changed | Check the most recent reference file |
| The user's question asks for something more specific than the wiki captures | Read whichever reference files contain that detail |
| A pattern looks interesting but thin — only one page supports it | Check related references to confirm or discard |

Follow `## References` wikilinks into `Data/` to check the supporting raw files. Rather than reading each reference file in full, use `qmd` to jump straight to the relevant passage:

```
mcp__qmd__query(searches=[{type:"vec", query:"<the specific claim being checked>"}], intent="verifying a wiki claim against its source", collections=["data"], limit=5)
```

Then pull just the surrounding context with `mcp__qmd__get(file=hit.file, fromLine=max(1, line-20), maxLines=80)`. Only read a reference file in full if the snippet doesn't resolve the question (e.g. the claim depends on reading a whole thread's arc, not one passage).

Use the information to either confirm the insight or revise it. Update your working notes but **do not modify any wiki pages** during this skill — insights are read-only.

## Step 3 — Synthesize insights

With the wiki pages (and any raw sources read in Step 2), generate a structured insight report covering these lenses:

### Key Trends
What is moving — metrics, client relationships, model performance, team focus, tooling adoption. Look for directional change: up, down, accelerating, plateauing. Minimum: one trend per active client, plus cross-client patterns if any exist.

### Signals Worth Watching
Things that are not yet problems but show early signs of friction, drift, or risk. Include:
- Pages tagged `watch` or `at-risk`
- Metrics trending the wrong direction
- Clients with no recent positive signals
- Processes or tools with unresolved issues
- Open Questions on wiki pages that have been sitting unanswered

### Missed or Under-Documented
Gaps in the knowledge base relative to the window's activity:
- Topics that appear in raw sources but have no corresponding wiki page
- Wiki pages whose `last_updated` is significantly older than the most recent related raw source (staleness gap)
- Entities mentioned frequently in references but with no dedicated page
- Decisions that appear to have been made in Data/ files but aren't in `Level Knowledge\decisions\`

### Improvement Opportunities
Concrete, actionable improvements derived from the patterns — not generic advice:
- Process inefficiencies visible in multiple client issues
- Tool gaps or workarounds that recur across clients
- Confidence gaps: pages that have stayed `medium` or `low` despite multiple source files existing
- Pages with no `## Notes` content that would benefit from user annotation

### Noteworthy Items
Anything that doesn't fit the above categories but stands out:
- Wins worth celebrating or communicating
- Unusual patterns that break prior trends
- Decisions made that have implications not yet reflected in other wiki pages
- Cross-client patterns (e.g., the same issue affecting CSU and NBU simultaneously)

## Step 4 — Assess confidence in the insight

After synthesizing, evaluate how confident you are in the overall insight report:

| Factor | Effect on confidence |
|---|---|
| Most key pages are `confidence: high` | Raises |
| Raw sources were read to confirm key claims | Raises |
| Relying heavily on `confidence: low` pages without reading their references | Lowers |
| Large gaps in the wiki (few pages updated in the window) | Lowers — note the limitation |
| Contradictions found between pages | Note explicitly; don't resolve without reading sources |

State confidence at the top of the report: **High / Medium / Low** with a one-line rationale.

## Step 5 — Write the report

Save the report to:
```
Level Playbook\insights\insight\insight-{window_start}-to-{window_end}.md
```

**Report structure:**

```markdown
---
type: insight
window: YYYY-MM-DD to YYYY-MM-DD
generated: YYYY-MM-DD
confidence: high | medium | low
---

# Insight Report — {window_start} to {window_end}

*{Confidence level} confidence — {one-line rationale}.*

## Key Trends
[Bullet list — one trend per entry, with supporting page wikilinks]

## Signals Worth Watching
[Bullet list — flag anything that needs attention; link to relevant wiki pages]

## Missed or Under-Documented
[Bullet list — gaps in the knowledge base; note which Data/ files hint at the gap]

## Improvement Opportunities
[Numbered list — concrete and actionable; link to the relevant pages]

## Noteworthy Items
[Bullet list — wins, surprises, cross-cutting patterns]

## Sources consulted
[Two sub-lists: wiki pages read and raw Data/ files read (if any)]

### Wiki pages
- [[page-slug|Page Title]] — confidence: high/medium/low

### Raw sources
- [[filename]] — *reason consulted*
```

After saving the dated report, update both hub files:

**Latest Insights** — overwrite with the current report:

Write the full report content to `Level Playbook\Hub\latest-insights.md`, prefixed with:
```markdown
> *Last updated: {window_start} → {window_end} (generated {today})*
```

**Insights History** — append a summary entry to `Level Playbook\Hub\Insights History.md`.

If the file doesn't exist yet, create it with this header first:
```markdown
# Insights History

A running log of every ob-insight report. Most recent entry at the top.

---
```

Then prepend a new entry at the top of the log (after the header, before any existing entries):

```markdown
## {window_start} → {window_end} · confidence: {high|medium|low} · generated {today}

**Key Trends:** [1–2 sentence summary of the most important trend(s) from this window.]

**Signals Worth Watching:** [Top 1–2 items flagged.]

**Top Opportunity:** [Single most actionable improvement opportunity.]

→ Full report: [[insight-{window_start}-to-{window_end}]]

---
```

Tell the user:
> Insight report saved → `Level Playbook\insights\insight\insight-{window_start}-to-{window_end}.md`
> Hub updated → `Level Playbook\Hub\latest-insights.md`
> History updated → `Level Playbook\Hub\Insights History.md`

Then print the full report inline so the user can read it without opening the file.

## Step 6 — Offer follow-up actions

After presenting the report, list any follow-up actions you recommend:

- **Wiki gaps identified** → offer to run `/ob-wiki-update` to fill them
- **Low-confidence pages confirmed by raw sources** → offer to promote confidence on those pages
- **Contradictions found** → offer to run `/wiki-contradictions` for a full audit
- **Stale pages** → list them so the user can decide whether to archive or refresh

Keep this section brief — it's a menu, not a task list.

## Rules

- **Read-only** — never modify wiki pages or Data/ files during this skill.
- **History is append-only** — never delete or rewrite existing entries in `Insights History.md`; only prepend new ones. Insight is analysis, not maintenance.
- **Cite everything** — every claim in the report must trace back to a specific wiki page or raw source. No unsupported assertions.
- **Be specific** — "CSU match rate dropped from 82% to 74% in June" beats "CSU has data quality issues."
- **Be conservative** — if the wiki is thin and raw sources weren't read, say so in the confidence rating. A cautious Medium is better than an inflated High.
- **No hallucination** — if you don't have data for a section, write "No data in this window" rather than filling it with plausible-sounding inference.
- **Respect `## Notes`** — read user notes for context but never include their content in the output report without explicit user consent.
