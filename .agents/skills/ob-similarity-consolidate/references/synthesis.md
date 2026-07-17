# Wiki synthesis spec

Self-contained rules for writing and updating `Level Knowledge/` pages. This is `ob-similarity-update`'s
own copy of the synthesis machinery — it does not reference `ob-wiki-update`. The only external
dependency is `.config/tagging.md` (the vault-wide canonical tag vocabulary, shared by all skills).

> **Maintenance note:** the wiki page format is also implemented in `ob-wiki-update/SKILL.md`. If the
> page format itself changes (frontmatter fields, section order, confidence footnote, decay
> thresholds), both files must be updated or the two ingestion paths will write inconsistent pages.

---

## Frontmatter (every page)

```yaml
---
title: Page Title
type: client-overview | client-issues | client-trends | client-sentiment | client-wins | process | tool | analytics | team | decision | organization
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
```

## Section order (every page)

1. `# Title` + one-sentence lede + `[^confidence]`
2. `![[photo]]` — team pages only, immediately after the lede
3. Domain-specific sections (Overview, Steps, Issues, etc.)
4. `## Attachments` — auto-linked images; omit if none
5. `## Notes` — **PROTECTED. Never read-modify-write this section. If absent, add it empty before `## References`.**
6. `## References` — wikilinks to every raw source that informed the page
7. `[^confidence]: ...` footnote definition at the very bottom

## Naming

Lowercase, hyphen-separated, special characters stripped. Examples: `csu/overview.md`,
`signal-operations.md`, `kyle-taljan.md`. Clients get a sub-folder (`clients/<slug>/`); other
domains are flat files (`<domain>/<slug>.md`) until one topic grows big enough to split.

---

## Templates

### clients/[name]/overview.md
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
[Auto-linked images; omit if none]

## Notes
<!-- Your personal notes here — Claude will never modify this section -->

## References
[Wikilinks to every raw source file that informed this page]

[^confidence]: **{High/Medium/Low}** — {rationale: source count, recency, cross-confirmation}.
```

### clients/[name]/issues.md
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
[Current blockers, bugs, data quality problems — one bullet per issue with date first seen]

## Resolved
[Past issues that were closed — keep for pattern recognition]

## Attachments
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### clients/[name]/trends.md
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
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### clients/[name]/sentiment.md
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
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### clients/[name]/wins.md
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
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### processes/[name].md
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
## Steps
## Owner
## Tools
## Gotchas
## Attachments
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### tools/[name].md
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
## Key workflows
## Access
## Known issues
## Attachments
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### analytics/[name].md
```markdown
---
type: analytics
last_updated: YYYY-MM-DD
confidence: high | medium | low
tags:
  - active
---
# [Metric / Model / Dataset Name]

[One-sentence description of what this measures and why it matters.][^confidence]

## Definition
## Calculation
## Where it lives
## Common questions
## Attachments
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### team/[name].md
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

![[name-slug.jpg]]  <!-- only if a photo exists in Data/Assets/team/; omit otherwise -->

## Role & Responsibilities
## Expertise
## Working notes
## Attachments
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### decisions/[name].md
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
## Context
## Rationale
## Trade-offs considered
## Date
## Attachments
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{High/Medium/Low}** — {rationale}.
```

### New-domain page (minimum shape)
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
## Notes
<!-- Your personal notes here — Claude will never modify this section -->
## References

[^confidence]: **{Level}** — {rationale}.
```

---

## Merge logic (updating an existing page)

Read the page in full first — including `## Notes`. Then classify each existing claim against the
cluster's new sources:

- **Confirmed** (new source agrees) → keep, add the new source to References
- **Contradicted** (new source differs) → update to the new information
- **Expanded** (new source adds depth) → enrich in place, don't replace
- **Unaddressed** (new source silent) → preserve as-is, subject to the decay pass below

Carry forward all unaddressed content. Pages deepen over time; never reset a page to only what the
latest sources say. Prefer targeted edits to the changed sections over full rewrites (except for a
brand-new page or a restructure).

### `## Notes` scan (confidence signal only — never modify the section)
- **Confirming** note (matches a body claim) → resets that claim's decay clock
- **Contradicting** note, no new sources → add `[CONFLICT]` to `## Open Questions`, drop confidence one level
- **Contradicting** note, new sources agree with the page not the note → add `[CONFLICT - OUTDATED NOTE]` open question, drop one level, follow the sources not the note
- **New info** in a note → surface as a candidate claim / open question
- **Empty** → neutral

---

## Expansion pass

After merging, make a second pass to make the page *smarter*, not just longer:
- Answer any `## Open Questions` the new sources resolve; move the answer into the body and remove the question (partial answers: update the question to reflect what's now known)
- Deepen shallow one-line claims where sources add mechanism/reason/exception
- Add connections (wikilinks) the page didn't make before
- Refine over-flat claims the sources reveal to be more nuanced

Do not pad, do not restate, do not add sections without 3+ substantive bullets of real content.

---

## Decay pass

For each **unaddressed** claim, find the page's most recent source date (parse `YYYY-MM-DD` from
`## References` filenames; a confirming `## Notes` signal counts as today). Apply by page type:

| Page type | `high`→`medium` | `medium`→`low` |
|---|---|---|
| client-overview, client-issues, client-sentiment | 45 days | 90 days |
| client-trends | 30 days | 60 days |
| team | 60 days | 120 days |
| process, tool, analytics | 90 days | 180 days |
| decision | no decay | no decay |
| organization | 180 days | 360 days |

- Within `high`→`medium`: no decay
- Past `high`→`medium`, within `medium`→`low`: lower `high` to `medium`
- Past `medium`→`low`: lower to `low`; move significantly stale claims to `## Archived Claims`
  (placed just before `## Notes`), format: `- [claim] *(last seen: YYYY-MM-DD)*`

Never decay `## Open Questions`, `## Notes`, `## References`, or `decision` pages.

---

## Confidence synthesis (three-way)

Confidence = f(source count & consistency, source recency, `## Notes` signal):

| Sources | Notes signal | Confidence |
|---|---|---|
| 3+ consistent, within threshold | any non-contradicting | high |
| 3+ consistent, within threshold | contradicting | medium (flag conflict) |
| 1–2, or aging | confirming | medium |
| 1–2, or aging | none | medium |
| past decay threshold | confirming | medium |
| past decay threshold | none | low |
| past decay threshold | contradicting | low (flag conflict) |
| no sources | confirming notes only | low |

Hard rules: notes alone can't reach `high` (needs Data/ confirmation); a contradicting note always
drops at least one level; a confirming note blocks `medium`→`low` decay but not `high`→`medium`.

Footnote format:
```
[^confidence]: **High** — sourced from 4 Signal Ops transcripts (Jun 4–25, 2026); cross-confirmed.
[^confidence]: **Medium** — 1 dedicated sync + 2 mentions; some details inferred.
[^confidence]: **Low** — single Claude session; not confirmed in a meeting context.
```

---

## Wikilinks

Link entities to their pages using `[[filename|Display Name]]` (bare filename, no path, no `.md`):

| Mention | Link to |
|---|---|
| client / account | `clients/<slug>` |
| tool / platform | `tools/<slug>` |
| team member | `team/<slug>` |
| process / workflow | `processes/<slug>` |
| metric / model / data source | `analytics/<slug>` |
| decision | `decisions/<slug>` |

Link the first mention per section, not every occurrence. Never link inside headings or frontmatter.
Link even if the target page doesn't exist yet (Obsidian shows it as unresolved).

---

## References

`## References` lists every raw source that contributed content — one bullet, bare wikilink:
```markdown
## References
- [[2026-06-25 Weekly Signal Operations Check-In]]
- [[Slack Messages 2026-06]]
```
List only files that actually contributed. On an update, merge new sources in — never wipe prior
references. Claude session files use their session title as the filename.

---

## Images

- **Processed** (`Data/Assets/processed/`): if a source `.md` used for a page has a same-base-name
  image there, embed `![[original.png]]` in the most relevant section.
- **Attachments** (`Data/Assets/attachments/`): scan for filenames containing the page title / client /
  tool / topic slug. If matches, add `## Attachments` before `## Notes` with `![[file]]` embeds. If
  no matches, omit the section. Never remove a user-added attachment.
- **Team photos** (`Data/Assets/team/`): match a file containing the person's first/last name or slug;
  embed after the lede. Omit if none.

---

## Claude session handling (`Data/Claude/`)

These files are conversation transcripts between the user and Claude. They reveal **intent, focus,
and active work** — not decisions or facts established the way a meeting or Slack thread would.
Treat them differently from other cluster members:

| What the session shows | What it signals |
|---|---|
| Building or debugging something specific | Active work — update "Notes" / "Working notes" with current focus, not a factual/decision section |
| Exploratory questions about a topic | Investigation, not a decision — don't present as settled |
| Referencing a client, tool, or process in depth | That entity is currently active/high-priority |
| A decision or approach explicitly agreed on in the session | Can be promoted to the `decisions` domain if concrete enough |

**Be conservative:** don't let a session's exploratory framing get written up as a decided fact.
Prefer adding to "Working notes," "Notes," or "Open Questions" over overwriting a factual section.

**Skip sessions that are purely infrastructure/tooling** (setting up git, configuring hooks,
building or maintaining this vault's own skills) — these carry no wiki-relevant knowledge about
clients, processes, or work, and clustering them with substantive sessions would dilute the cluster.

---

## Sensitive content — scrub before writing

Never carry into a wiki page: API keys, secret tokens, private keys, passwords / credential
assignments, PEM blocks, connection strings with embedded credentials, Bearer/Basic auth tokens,
webhook URLs with token segments. Keep: emails, phone numbers, names, roles, addresses, plain URLs,
hashed values. If a source appears to contain real credentials, note it in the run report so the user
can sanitize the original.

---

## Restructuring & new domains

**Move a page** when new sources make its correct location clear (a "general" page that's actually
client-specific, a client page that's actually broad, a page that's outgrown its file). To move:
recreate at the new path with all content merged, update every backlink you can find, leave a
one-line redirect at the old path (`*This page has moved — see [[new-slug|New Title]].*`), update
`index.md`, log the move. Only restructure on clear evidence, never on a single mention.

**Create a new domain** when novel content recurs across multiple sources, would generate 2–3 real
pages, and doesn't fit the existing domains. Name it lowercase-plural (`organization/`, `vendors/`,
`campaigns/`, `experiments/`). Register it in `index.md`, log it, and add a graph color group to
`.obsidian/graph.json` (next unused palette color; convert hex to decimal `R×65536 + G×256 + B`).

---

## Tagging

Read `.config/tagging.md` at the start of each run — it is the single source of truth for the
controlled vocabulary, application rules, and the auto-creation threshold. Every page gets a status
tag; client tags go on related non-client pages; theme tags when substantively on-theme. Do not
duplicate the vocabulary here.
