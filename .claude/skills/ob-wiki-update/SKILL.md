---
name: ob-wiki-update
description: >
  Reads new raw notes from Data/ since the last wiki update and synthesizes learnings into the
  Level Knowledge wiki. Use when the user runs /ob-wiki-update or asks to "update the wiki",
  "sync the knowledge base", or "push new learnings to Level Knowledge".
---

# ob-wiki-update

Sweep all raw sources in `Data/` that are newer than the last wiki update, extract learnings, and
update the `Level Knowledge/` wiki in place.

## Vault paths

- **Vault root**: the current working directory (the folder containing `CLAUDE.md`) — never hardcode a path; other users run this vault from a different location
- **Raw sources**: `Data\` — Step 2 scans the whole tree recursively, so no fixed subfolder list needs to be maintained here; new subfolders under `Data\` are picked up automatically
- **Wiki root**: `Level Knowledge\`
- **Wiki index**: `Level Knowledge\index.md`
- **Wiki domains**: not fixed. Use Glob to list the current top-level folders under `Level Knowledge\` (excluding `index.md` and `log.md`) at the start of every run — this is the live domain set. The six core domains (`clients`, `processes`, `tools`, `analytics`, `team`, `decisions`) always exist; treat any additional folders found (e.g. `organization`, `vendors`) as active domains too and route content to them in Step 3.

## Step 0 — Sort the inbox

Before discovering new raw files, invoke the `ob-inbox` agent to sort any unsorted files from `Data/Inbox/` into the appropriate `Data/` subfolders. This ensures that anything recently dropped in the inbox is in the right place before the wiki update sweep runs.

Use the Agent tool with `subagent_type: "ob-inbox"`. Wait for it to complete before proceeding.

If `Data/Inbox/` is empty or contains no sortable files, the agent will report that and you continue.

## Step 1 — Read the cursor and check for full rerun

Read `Level Knowledge\index.md`. Parse both `last_updated` and `last_full_rerun` from the YAML frontmatter.

**Check days since last full rerun:**

Calculate the number of days between `last_full_rerun` and today.

- If `last_full_rerun` is `null` or missing, treat it as never — prompt immediately.
- If 7 or more days have elapsed, ask the user before proceeding:

  > It's been X days since the last full wiki rerun (last: YYYY-MM-DD). A full rerun reprocesses all Data/ files to catch connections between old and new data. Would you like to do a full rerun now, or continue with the incremental update?

- If the user says **full rerun**: set `last_updated` to `null` in `index.md` before Step 2. After the run completes, update `last_full_rerun` to today's date in `index.md`.
- If the user says **incremental** (or fewer than 7 days have elapsed): proceed normally using `last_updated` as the cutoff.

**Incremental cutoff:**

- If `last_updated` is `null` or missing: treat the cutoff as the beginning of time (read all files).
- Otherwise: the cutoff date is that value (format `YYYY-MM-DD`). Only process files modified on or after that date.

## Step 2 — Discover new raw files

Run this PowerShell command to list raw files modified since the cutoff:

```powershell
# Replace VAULT_ROOT with the current working directory and CUTOFF with the date string (or use [datetime]::MinValue if null)
$cutoff = [datetime]"CUTOFF"
Get-ChildItem "VAULT_ROOT\Data" -Recurse -File |
  Where-Object { $_.LastWriteTime -ge $cutoff -and $_.Extension -eq ".md" } |
  Select-Object FullName, LastWriteTime |
  Sort-Object LastWriteTime
```

If no files are found, tell the user the wiki is already up to date and stop.

## Step 3 — Read and triage raw files

Read each file returned in Step 2. For each file, identify which wiki domains it touches.
A single raw file can inform multiple domains. Use the table below as a guide:

| Signal in raw file | Domain |
|---|---|
| Client name, campaign, account | `clients` |
| "how we do X", workflow, SOP, process | `processes` |
| Software, platform, integration, tool name | `tools` |
| Metric, model, data source, dashboard, SQL | `analytics` |
| Person's name, role, team, responsibility | `team` |
| "we decided", "going forward", "approach" | `decisions` |

This table covers only the six core domains. If the live domain list from the Vault paths step includes custom domains (e.g. `organization`, `vendors`), also check the raw file against those — read a sample of that domain's existing pages to infer its scope, since custom domains don't have a fixed signal table.

Ignore content that is purely personal, conversational filler, or has no wiki value.

### Sensitive content — scrub before writing to wiki

When reading raw files, **never carry sensitive material into wiki pages**. Apply this rule during synthesis: if a raw file contains any of the patterns below, omit or redact the value when writing wiki content.

| Scrub this | Keep this |
|---|---|
| API keys, secret tokens, private keys | Email addresses |
| Passwords and credential assignments (`password=`, `api_secret=`, `client_secret=`, etc.) | Phone numbers |
| Private key PEM blocks (`-----BEGIN * KEY-----`) | Names, roles, addresses |
| Connection strings with embedded credentials (`postgresql://user:pass@...`) | URLs without credentials |
| Bearer / Basic auth token values | Hashed values (bcrypt, SHA) |
| Webhook URLs with embedded token segments | |

Wiki pages are synthesized summaries — raw credential strings should never appear in them regardless. This rule is a backstop for cases where a raw file (e.g., a Claude session, a `.env` snippet pasted into a note) accidentally contains secrets.

If you encounter a raw file that appears to contain **real credentials** (not placeholders), note it in your Step 8 report so the user can review and sanitize the original file.

### Claude session files (`Data/Claude/`)

These are conversation transcripts between the user and Claude. They reveal **intent, focus, and active work** rather than decisions or facts from meetings. Treat them differently:

| What you see in the session | What it signals |
|---|---|
| Building or debugging something specific | The user is actively working on this — update the relevant tool/process/client "Notes" or "Working notes" with current focus |
| Asking exploratory questions about a topic | The user is investigating — note as interest/exploration, not as a decision |
| Referencing a client, tool, or process in depth | That entity is currently active or high-priority |
| A decision or approach explicitly agreed on | Can be promoted to the `decisions` domain if concrete enough |

**Be conservative with Claude sessions:** Conversations are exploratory. Don't present an idea discussed as a decision made. Prefer adding to "Working notes", "Notes", or "Open Questions" sections rather than overwriting factual sections.

**Skip sessions that are purely infrastructure/tooling** (e.g., setting up git, configuring hooks, building this vault) — those don't contain wiki-relevant knowledge about clients or work.

## Step 4 — Update wiki pages

Domains use one of two structures depending on depth:

- **Flat** (`domain/topic.md`) — for processes, tools, analytics, team, decisions. One file per topic.
- **Sub-folder** (`domain/entity/page.md`) — for clients, and any other domain that grows complex enough to need multiple focused pages per entity.

---

### Sub-folder domains: Clients

Each client gets its own sub-folder: `Level Knowledge\clients\<client-slug>\`

Inside that folder, maintain these focused pages. **Only create a page when there is real content to put in it** — don't create empty stubs.

| File | Contains |
|---|---|
| `overview.md` | What the client does, what Level does for them, goals & KPIs, key contacts, tools & integrations |
| `issues.md` | Active problems, blockers, data quality issues, model failures, complaints, unresolved friction |
| `trends.md` | Performance trends over time, conversion rate changes, volume patterns, data quality trajectory |
| `sentiment.md` | Relationship health, communication tone from meetings, escalations, trust signals, client satisfaction |
| `wins.md` | Successful launches, performance improvements, model milestones, positive client feedback |

You may also create additional pages when a topic has enough depth to warrant it — e.g. `integrations.md`, `data.md`, `roadmap.md`. Use judgment: a page should have at least 3–5 substantive bullet points to justify existence.

**Triage logic — when you find something about a client, route it to:**

| Signal | Page |
|---|---|
| "not working", "data issue", "bug", "blocked", "delay", "concern" | `issues.md` |
| "improved", "trending up/down", "rate is X", "volume", "week over week" | `trends.md` |
| "client said", "frustrated", "happy", "escalated", "relationship", "trust" | `sentiment.md` |
| "launched", "live", "success", "milestone", "client praised", "great result" | `wins.md` |
| Contacts, goals, KPIs, tools, what Level does for them | `overview.md` |

**Creating a new client:**
1. Create the folder: `Level Knowledge\clients\<client-slug>\`
2. Always create `overview.md` first
3. Add other pages only as content warrants

**Updating an existing page:**
1. Read the existing page in full — including `## Notes` — before writing anything
2. Scan `## Notes` for confidence signals:
   - **Confirming** — user mentions something that matches a claim in the body: treat as recency evidence; that claim's decay clock resets
   - **Contradicting** — user mentions something conflicting with a claim or new sources conflict with the user's note. The direction matters:
     - **Note contradicts page body (no new Data/ sources):** The note may be correct and the page body questionable. Add to `## Open Questions`: `[CONFLICT] Page claims X; your Notes suggests Y — verify and update`. Drop confidence one level.
     - **New Data/ sources contradict the note:** The note may be outdated. Add to `## Open Questions`: `[CONFLICT - OUTDATED NOTE] Your Notes says X, but new sources indicate Y — your note may need updating`. Drop confidence one level. Do **not** silently overwrite the page body to match the note — follow the new sources instead.
   - **New information** — user mentions something not in the body: surface as a candidate claim or new open question
   - **Empty or no notes** — neutral; rely on source recency alone
3. Treat the existing body content as prior knowledge — accumulated understanding from all previous sources
4. For each claim in the existing page, classify it against the new sources:
   - **Confirmed** — new sources say the same thing: keep as-is, add the new source to References
   - **Contradicted** — new sources say something different: update to reflect the new information
   - **Expanded** — new sources add depth or nuance: enrich the existing claim rather than replacing it
   - **Unaddressed** — new sources don't mention it: preserve as-is; subject to decay check below
5. Carry forward all unaddressed content. The page should deepen over time, not reset to only what the latest sources say.
6. Determine the new `confidence` level using the three-way synthesis — see Confidence synthesis section below
7. Update `last_updated`, `confidence`, and `tags` in frontmatter

---

### Flat domains: Processes, Tools, Analytics, Team, Decisions

For these domains, each topic is a single file: `Level Knowledge\<domain>\<slug>.md`

When a flat-domain topic grows large enough that one file becomes unwieldy, convert it to a sub-folder using the same pattern as clients (create `<slug>/overview.md` and split content into focused pages). This is rare — most topics stay flat.

---

### File naming (all domains)

Use lowercase, hyphen-separated names. Strip special characters.
Examples: `csu/overview.md`, `signal-operations.md`, `kyle-taljan.md`

---

### Templates

#### clients/[name]/overview.md

```markdown
---
type: client-overview
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Client Name]

[One-sentence description of who this client is and what Level does for them.][^confidence]

## Overview
[What they do; what Level does for them]

## Goals & KPIs
[Key metrics they care about]

## Key Contacts
[Name — Role — notes]

## Tools & Integrations
[Platforms and data sources in play]

## Open Questions
[Unresolved items with no better home]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale: number of sources, how recent, cross-confirmation level}.
```

#### clients/[name]/issues.md

```markdown
---
type: client-issues
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Client Name] — Issues

*Active and resolved friction points tracked as of last update.*[^confidence]

## Active
[Current blockers, bugs, data quality problems, unresolved friction — one bullet per issue with date first seen]

## Resolved
[Past issues that were closed — keep for pattern recognition]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### clients/[name]/trends.md

```markdown
---
type: client-trends
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Client Name] — Trends

*Performance trajectory and data quality trends over time.*[^confidence]

## Performance
[Conversion rates, lead volumes, CPL/CPA over time]

## Data Quality
[Match rates, error rates, GA4/CRM coverage trajectory]

## Notable Patterns
[Anything that changed direction or surprised the team]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### clients/[name]/sentiment.md

```markdown
---
type: client-sentiment
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Client Name] — Sentiment

*Relationship health and communication indicators.*[^confidence]

## Relationship Health
[Overall: strong / neutral / at risk — and why]

## Recent Signals
[Specific quotes, meeting tone, escalations, praise — with dates]

## Watch
[Anything that could become a problem if not addressed]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### clients/[name]/wins.md

```markdown
---
type: client-wins
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Client Name] — Wins

*Confirmed milestones and successes.*[^confidence]

[Bullet list of successes with dates: launches, performance improvements, model milestones, client praise]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### processes

```markdown
---
type: process
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Process Name]

[One-sentence description of what this process is and why it exists.][^confidence]

## Overview
[What this process is and why it exists]

## Steps
[How it works, in order]

## Owner
[Who is responsible]

## Tools
[What tools are used]

## Gotchas
[Edge cases, known failure modes, things that surprised us]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### tools

```markdown
---
type: tool
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Tool Name]

[One-sentence description of what this tool is and how Level uses it.][^confidence]

## What we use it for
[Purpose at Level; which teams use it]

## Key workflows
[The most common things we do with it]

## Access
[Who has it; how to get access]

## Known issues
[Limitations, bugs, workarounds]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### analytics

```markdown
---
type: analytics
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Metric / Model / Dataset Name]

[One-sentence description of what this metric or model measures and why it matters.][^confidence]

## Definition
[What it measures or represents]

## Calculation
[How it is computed; SQL or formula if known]

## Where it lives
[Data source, warehouse table, dashboard location]

## Common questions
[Recurring questions or misunderstandings about this metric]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### team

```markdown
---
type: team
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Full Name]

[One-sentence summary of their role and primary area of ownership.][^confidence]

## Role & Responsibilities
[Title and what they own]

## Expertise
[What they are the go-to person for]

## Working notes
[Collaboration style, preferences, context useful for working with them]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

#### decisions

```markdown
---
type: decision
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Decision Title]

[One-sentence summary of what was decided and when.][^confidence]

## Decision
[What was decided, in one sentence]

## Context
[Why this came up; what problem it solved]

## Rationale
[Why this option was chosen]

## Trade-offs considered
[What was not chosen and why]

## Date
[YYYY-MM-DD]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page — one bullet per source]

[^confidence]: **{High/Medium/Low}** — {brief rationale}.
```

### Expansion pass — deepening existing pages

After merging new source content into an existing page, run a second pass focused on expansion. The goal is not just to add new facts but to make the page smarter.

**For each section of the existing page, ask:**

| Question | Action |
|---|---|
| Does this section have an open hypothesis or unanswered question? | Look for evidence in the new sources — if found, answer it and move it out of Open Questions |
| Is a claim here shallow (one line) when the new sources add context? | Deepen it in place — add the mechanism, the reason, the exception |
| Does a new source reveal a connection the page doesn't make yet? | Add the connection explicitly — wikilink the entities involved |
| Does this section have a claim that the new sources reveal is more nuanced than stated? | Refine rather than replace — keep the original claim and layer on the nuance |

**What expansion is not:**
- Expanding does not mean adding every detail from every source — only add what genuinely strengthens the page
- Do not pad sections with restatements of what's already there
- Do not create new sections unless the new material is substantive enough to warrant it (3+ bullets minimum)

**Open Questions are a priority target for the expansion pass.** If a question in `## Open Questions` gets answered by new sources, move the answer to the relevant section and remove the question. If it gets partially answered, update the question to reflect what's now known vs. what remains open.

---

### Decay pass — flagging stale claims

After the expansion pass, check each claim classified as "unaddressed" (new sources did not mention it) against the page's source recency.

**Step 1 — find the most recent source date.** Look at the page's `## References` section. Extract the date from each source filename (most are named `YYYY-MM-DD Title`). Find the most recent date across all references. If `## Notes` contains a confirming signal, treat today as the effective recency date for the claims it confirms — user notes reset the decay clock.

**Step 2 — apply the decay threshold by page type:**

| Page type | `high` → `medium` | `medium` → `low` |
|---|---|---|
| `client-overview`, `client-issues`, `client-sentiment` | 45 days | 90 days |
| `client-trends` | 30 days | 60 days |
| `team` | 60 days | 120 days |
| `process`, `tool`, `analytics` | 90 days | 180 days |
| `decision` | No decay | No decay |
| `organization` | 180 days | 360 days |

**Step 3 — act:**
- Most recent source (or user note) is within the `high` → `medium` threshold: no decay, carry all unaddressed claims forward as-is
- Past the `high` → `medium` threshold but within `medium` → `low`: lower confidence to `medium` if currently `high`
- Past the `medium` → `low` threshold: lower confidence to `low`; move significantly stale claims to `## Archived Claims`

**`## Archived Claims` section** — place immediately before `## Notes`:
```markdown
## Archived Claims

*These claims have not been confirmed by any source in the past N days. They may still be accurate — verify before acting on them.*

- [Stale claim text] *(last seen: YYYY-MM-DD)*
```

Use the page's most recent reference date as `last seen`. When a future update confirms an archived claim, move it back to the appropriate section and remove the `*(last seen: ...)*` marker.

**Never decay:**
- `## Open Questions` — already uncertain by definition
- `## Notes` — protected
- `## References` — historical record
- `decision` pages — point-in-time records; decay does not apply

---

### Confidence synthesis — three-way model

The `confidence` level on every page is the result of three inputs:

1. **Source count and consistency** — how many `Data/` sources back the claims, and do they agree?
2. **Source recency** — how recently were those sources dated? (see Decay pass thresholds above)
3. **User notes** — what signals did `## Notes` contain? (see Notes scan in step 4)

| Sources | User Notes signal | Confidence |
|---|---|---|
| 3+ consistent, within threshold | Any non-contradicting | `high` |
| 3+ consistent, within threshold | Contradicting | Flag conflict; set `medium` |
| 1–2 sources OR sources aging | Confirming | `medium` |
| 1–2 sources OR sources aging | No notes | `medium` |
| Sources past decay threshold | Confirming | `medium` — notes prevent full decay |
| Sources past decay threshold | No notes | `low` |
| Sources past decay threshold | Contradicting | Flag conflict; set `low` |
| No sources | Confirming notes only | `low` — not externally confirmed |

**Hard rules:**
- User notes alone cannot elevate a page above `medium` — `high` requires Data/ source confirmation
- A contradicting note always drops confidence by at least one level regardless of source quality
- A confirming note prevents `medium` → `low` decay but not `high` → `medium` decay

**Update the `[^confidence]` footnote** to reflect the actual reasoning — mention if user notes played a role, and name any sections that are aging or best-supported.

---

### Linking images to wiki pages

When writing or rewriting any wiki page, check for relevant images in `Data/Assets/` and link them where appropriate.

---

**Processed images** (`Data/Assets/processed/`)

When a raw source file used to inform this wiki page was generated by vision extraction (i.e., its companion image exists in `Data/Assets/processed/`), embed the original image directly in the wiki page. Place the embed in the most relevant section — immediately after the text that the image illustrates:

```markdown
![[original-filename.png]]
```

To detect companion images: for each `.md` source file read during Step 3, check whether a file with the same base name exists in `Data/Assets/processed/`. If it does, that source was vision-extracted and its image should be embedded in the wiki page it informs.

---

**Attachments** (`Data/Assets/attachments/`)

When writing or rewriting a wiki page, scan `Data/Assets/attachments/` for image files whose name contains words from the page title, client name, tool name, or topic slug (e.g., a file named `signal-architecture.png` is relevant to `tools/signal.md`).

If one or more matches are found, add an `## Attachments` section to the page, immediately before `## Notes`:

```markdown
## Attachments

![[signal-architecture.png]]
![[signal-flow-diagram.jpg]]

## Notes
```

If no matches are found, omit the section entirely — do not add an empty `## Attachments`.

---

### Team profile photos

When writing or rewriting a team page, check whether a profile photo exists for that person in `Data/Assets/team/`. Match by looking for any image file whose name contains the person's first name, last name, or slug (e.g., `jane-doe`, `jane`, `doe`).

If a match is found, add the image embed at the top of the page body, immediately after the lede line:

```markdown
# Jane Doe

ML Engineer / Data Engineer owning...[^confidence]

![[jane-doe.jpg]]
```

If no photo exists, omit the embed — do not add a placeholder.

### Restructuring existing pages

As new information accumulates, a page's scope may shift. During each update, assess whether existing pages are still in the right location — not just whether their content is current.

**Signals that a page needs to move:**

| Signal | What to do |
|---|---|
| A "general" process or tool page turns out to only apply to one client | Move content to `clients/<client>/` (e.g., a new `data.md` or `integrations.md` page) |
| A client-specific page describes something that applies broadly across clients | Promote to `processes/` or `tools/` and add the client tag |
| A flat-domain page has grown so large it covers multiple distinct sub-topics | Split into a sub-folder (`<slug>/overview.md`, `<slug>/detail.md`, etc.) |
| Two pages cover the same topic from different angles | Merge into one; pick the more appropriate location |

**How to move a page:**

1. Create the page at the new location using the appropriate template, merging in all existing content
2. **Find every real backlink to the old page** — run `obsidian backlinks file="<old page title>" format=json` (requires the Obsidian desktop app running; if the command fails or isn't available, skip this step and rely on the redirect note alone). For each file it returns, open it and update its `[[old-page-slug]]` wikilink(s) to point directly at `[[new-page-slug|New Page Title]]` instead of leaving them pointing at the old page. This keeps the graph accurate immediately rather than depending on every future reader following a redirect.
3. Replace the old file's content with a one-line redirect note — do this even after updating backlinks, as a safety net for anything the CLI check might miss (e.g. links added while the app was closed):
   ```markdown
   *This page has moved — see [[new-page-slug|New Page Title]].*
   ```
   Do not delete the old file.
4. Update `index.md`: remove the old entry, add the new one
5. Log the move in `log.md`: `| YYYY-MM-DD | Moved <old-path> → <new-path> | [reason] |`

**Important:** Only restructure when new sources make the correct location clear. Do not speculatively reorganize based on a single mention. If uncertain, update the page in place and add an open question flagging the potential scope issue.

### Creating new domains

If content from a raw source doesn't fit any existing domain, create a new top-level domain folder rather than forcing it into a poor fit.

**When to create a new domain:**
- The topic recurs across multiple source files and warrants its own persistent home
- It would generate at least 2–3 pages with real content
- It represents a coherent category that is meaningfully different from the six existing domains

**When NOT to create a new domain:**
- A single mention that could go in a "Notes" section of an existing page
- Content that fits `processes/`, `tools/`, `decisions/`, or `team/` with a small stretch

**How to name it:**
- Lowercase, hyphen-separated, plural noun: `organization/`, `vendors/`, `campaigns/`, `experiments/`
- Keep it broad enough to hold future pages but specific enough to be meaningful

**Flat vs. sub-folder:**
- Start flat (`domain/topic.md`) unless the domain clearly has multiple facets per entity from the start
- Promote to sub-folder later if a single topic grows large enough to split

**Template:**
Adapt the closest existing template. At minimum, every page in a new domain must have:
```markdown
---
type: <domain-singular>
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Page Title]

[One-sentence description.][^confidence]

## [Sections appropriate to the topic]

## Attachments
[Images from Data/Assets/attachments/ relevant to this page — added automatically by wiki update if matches found; omit section if empty]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to source files]

[^confidence]: **{Level}** — {rationale}.
```

**Examples of likely new domains:**

| Domain | What goes there |
|---|---|
| `organization/` | Company culture, core values, key behaviors, org structure, Level-wide initiatives |
| `vendors/` | External partners, agencies, data providers, managed service relationships |
| `campaigns/` | Specific media campaigns with their own strategy, timeline, and results |
| `experiments/` | A/B tests, holdout studies, incrementality experiments |

**After creating a new domain:**
1. Create the folder: `Level Knowledge\<domain>\`
2. Register it in `Level Knowledge\index.md` — add a new section with a table for that domain
3. Note it in `Level Knowledge\log.md` as a new domain created
4. Add a color group entry to `.obsidian\graph.json` — append to the `colorGroups` array using the next unused color from the palette below

**Color palette for graph groups** (assign in order — skip colors already in use):

| # | Hex | RGB (decimal) | Suggested for |
|---|---|---|---|
| 1 | #3498DB | 3447003 | clients ✓ |
| 2 | #2ECC71 | 3066993 | processes ✓ |
| 3 | #E67E22 | 15105570 | tools ✓ |
| 4 | #9B59B6 | 10181046 | analytics ✓ |
| 5 | #1ABC9C | 1752220 | team ✓ |
| 6 | #E74C3C | 15158332 | decisions ✓ |
| 7 | #F1C40F | 15844367 | organization |
| 8 | #34495E | 3426654 | vendors |
| 9 | #E91E63 | 15277667 | campaigns |
| 10 | #00BCD4 | 48340 | experiments |
| 11 | #8BC34A | 9159498 | — |
| 12 | #FF5722 | 16733986 | — |

**Format for the new entry:**
```json
{"query": "path:\"Level Knowledge/<domain>\"", "color": {"a": 1, "rgb": <decimal>}}
```

Read the current `.obsidian\graph.json`, append the new entry to `colorGroups`, and write it back. Do not modify any other fields. Then add a matching row to the `## Graph color legend` table in `Level Knowledge\index.md` using the format `| 🔵 | #RRGGBB | domain |` — pick the closest emoji circle to the actual color.

If all 12 palette colors are already in use, generate a new hex color that:
- Is visually distinct from all colors already in the `colorGroups` array
- Has medium-to-high saturation (avoid near-white, near-black, or near-grey)
- Is legible against both light and dark backgrounds (avoid very pale or very dark values)
- Does not closely resemble any existing group color (aim for at least 60 hue degrees of separation)

Convert the chosen hex to a decimal RGB integer using `R×65536 + G×256 + B` and use that as the `rgb` value.

## Step 5 — Update index.md

After all pages are written:

1. For each new page created, add a row to the correct table in `index.md`.
   Format: `| [[filename\|Display Name]] | One-line description |`
   (bare filename, not full path — Obsidian resolves it)
2. Update the `last_updated` frontmatter field in `index.md` to today's date (`YYYY-MM-DD`).
3. If this was a full rerun, also update `last_full_rerun` to today's date.
4. Write the updated `index.md` back to disk.

## Step 6 — Update HELP.md

Rewrite `HELP.md` at the vault root to reflect the current set of skills, agents, and hooks. This keeps the reference document accurate as automation evolves.

**How to generate it:**

1. Read all `SKILL.md` files under `.claude/skills/` — extract the skill name and description from each
2. Read `.claude/settings.json` — extract any hooks (name, trigger event, what it does)
3. Check for any registered agent types referenced in skill files (e.g. `ob-inbox`, `ob-wiki-contradictions`, `wiki-graph-sync`) and any standalone skills (e.g. `ob-wiki-contradictions`, `wiki-graph-sync`)
4. Rewrite `HELP.md` at the vault root using the structure below

**Structure of HELP.md:**

```markdown
# <Vault Name> — Skills & Commands Reference

[One-line intro]

## Skills (slash commands)
[One section per skill: name as ### `/skill-name`, what it does, when to use it]

## Agents (invoked automatically by skills)
[One section per agent: what it does, what triggers it]

## Automatic behaviors (hooks)
[One section per hook: what it does, when it fires]

## How the vault works
[Static vault structure diagram and update cycle explanation — preserve this section verbatim unless the structure has genuinely changed]
```

**Rules:**
- Rewrite the whole file — do not append
- Preserve the `## How the vault works` section content unless the vault structure itself has changed
- If a skill or agent was removed since the last run, drop its section
- If a new skill or agent was added, add a section for it
- Keep descriptions concise — this is a quick reference, not documentation

## Step 7 — Report to the user

Summarize what was done:

```
Wiki updated — YYYY-MM-DD

Raw files processed: N
Pages updated: list each page that changed
Pages created: list each new page
Domains touched: clients, tools, ...

No changes: list any domains where nothing new was found
```

Keep it tight. The user can open the pages to review details.

## Tagging

Every page must have a `tags:` list in YAML frontmatter.

**Read `.claude/tagging.md` at the start of each run** — it is the single source of truth for the controlled vocabulary, application rules, and auto-creation threshold. The vocabulary table lives there, not here.

Key rules (see `.claude/tagging.md` for full detail):
- Every page gets a status tag (`active`, `at-risk`, `watch`, `resolved`, `deprecated`) — assess from the content
- Client tags go on non-client pages that relate to that client; client sub-folder pages do not need their own client tag
- Theme tags apply when the page is substantively about that theme
- Temporal tags flag time-sensitive items with near-term deadlines

**Auto-creating new theme tags:** During triage (Step 3), track recurring concepts not covered by any existing vocabulary tag. If a concept appears substantively in 3+ distinct source files in the current run, add it to the controlled vocabulary in `.claude/tagging.md` (append to the Themes row), apply it to relevant pages, and report it in the Step 8 summary. See `.claude/tagging.md` for the full auto-creation rules and category restrictions.

## Rules

- **Never append** to wiki pages — always rewrite the whole file using the template.
- **Never delete** a section that has content, even if the new raw sources don't mention it.
- **Never modify `## Notes`** — this section is reserved for the user's manual edits. Read it for context but do not rewrite, merge into, or delete anything in it. If the section doesn't exist on an existing page, add it as an empty section before `## References`.
- **`## Attachments` is managed automatically** — re-scan `Data/Assets/attachments/` on every update and refresh the section with current matches. If no matches exist and the section is empty, remove it. Never remove an attachment the user added manually — if it doesn't match the auto-scan, leave it and add auto-matched ones alongside it.
- **Prefer updating** an existing page over creating a new one. Only create if no existing page covers this topic.
- **Treat existing content as prior knowledge** — always read the existing page before writing. Content not addressed by new sources is preserved as-is. Content confirmed by new sources is kept and reinforced. Content contradicted by new sources is updated. Content expanded by new sources is deepened in place.
- **Read `## Notes` as a confidence signal** — scan it before writing. Confirming notes reset the decay clock for matching claims. Contradicting notes drop confidence and create a `[CONFLICT]` open question. New information in notes surfaces as a candidate claim. Never modify `## Notes` itself.
- **Decay confidence automatically** — if a page's most recent source is past the decay threshold for its type, lower `confidence` accordingly. User confirming notes can hold a page at `medium` but cannot restore `high` without Data/ sources.
- **Be conservative** — only write what is clearly supported by the raw sources or user notes. Do not invent or assume details.
- **Resolve Open Questions actively** — if a question in an existing page gets answered by new raw sources or user notes, move the answer to the relevant section and remove the question. If partially answered, update the question to reflect what's now known vs. what remains open.

## Wikilinks

Every wiki page must link to other wiki pages wherever entities are mentioned. This turns the
wiki into a navigable knowledge graph in Obsidian.

**Format:** `[[filename|Display Name]]` — use the bare filename (no path, no `.md` extension).
Obsidian resolves filenames uniquely across the vault. Example: `[[looker-studio|Looker Studio]]`.

**When writing or rewriting any page, apply these rules:**

| If the page mentions... | Link to... |
|---|---|
| A client or account name | `clients/<client-slug>` |
| A tool or platform | `tools/<tool-slug>` |
| A team member's name | `team/<name-slug>` |
| A process or workflow | `processes/<process-slug>` |
| A metric, model, or data source | `analytics/<slug>` |
| A key decision | `decisions/<slug>` |

**Link even if the target page doesn't exist yet.** Obsidian shows unresolved links in the graph;
they become live when the page is eventually created.

**Do not over-link.** Link the first mention of an entity per section, not every occurrence.
Never link inside headings or YAML frontmatter.

## Confidence

Every wiki page must have a `[^confidence]` footnote that rates how much to trust the content on that page.

**Levels:**

| Level | Meaning |
|---|---|
| **High** | 3+ consistent sources within the decay threshold; facts cross-confirmed by multiple participants; no contradicting user notes |
| **Medium** | 1–2 sources, or sources aging but user notes confirm; some details inferred; warrants verification before sharing externally |
| **Low** | Sources past decay threshold with no user confirmation; single session only; or contradicting signals present |

Confidence is determined by three-way synthesis of source count, source recency, and user `## Notes` signals — see the Confidence synthesis section in Step 4.

**Placement:** Put `[^confidence]` at the end of the lede line (the one-sentence summary right after the `# Heading`). Define it at the very bottom of the file, after `## References`.

**Format of the footnote definition:**
```
[^confidence]: **High** — sourced from 4 Signal Ops meeting transcripts (Jun 4–25, 2026); facts confirmed by multiple participants.
[^confidence]: **Medium** — based on 1 dedicated sync and 2 sprint mentions; some details inferred.
[^confidence]: **Low** — drawn from a single Claude session; not confirmed in a meeting context.
```

**When updating a page:** re-evaluate the confidence level. If new sources strengthen or weaken the picture, update the footnote accordingly. A page that was Medium can become High after multiple confirming meetings.

## References

Every wiki page must have a `## References` section at the bottom, listing every raw source file that informed the page's content.

**Format:** One bullet per source file, using a bare wikilink to the filename (no path, no `.md` extension):

```markdown
## References

- [[2026-06-25 Weekly Signal Operations Check-In]]
- [[2026-06-03 Level x CSU Snowflake Integration Discussion]]
- [[2026-06]]
- [[Build Signal scoring pipeline]]
```

Claude session files use the session title as the filename (e.g., `Build Signal scoring pipeline.md` → `[[Build Signal scoring pipeline]]`).

**Rules:**

- List only files you actually read that contributed content to this page — not every file processed in the run
- If a page is updated (not created), merge the new sources into the existing References section; don't wipe prior references
- Use the exact filename as it appears in the vault (no path prefix needed — Obsidian resolves by filename)
- References create backlinks: from Obsidian, opening a meeting note will show every wiki page that cited it

**Why this matters:** References turn each meeting note and Slack export into a hub. From any raw source, you can see all the wiki pages it informed. From any wiki page, you can trace back to the primary evidence.
