# Vault — Skills & Commands Reference

Quick reference for all automation built into this vault. Run skills as slash commands inside Claude Code (e.g. type `/ob-wiki-update` in the chat).

---

## Skills (slash commands)

### `/ob-wiki-update`
**What it does:** Ingests new raw notes from `Data/` since the last update and synthesizes learnings into the `Level Knowledge/` wiki. Rewrites wiki pages in place — never appends. Also sorts the inbox and updates this help file. Does **not** check for contradictions or sync graph colors — run `/ob-wiki-contradictions` and `/wiki-graph-sync` separately for those.

**When to use:** After new meetings, Slack captures, or Claude sessions have been saved to `Data/`. Run daily or whenever you want the wiki to reflect recent activity.

**Full rerun:** If it has been 7+ days since the last full rerun, you will be prompted to choose between a full rerun (reprocesses all `Data/` files) or a standard incremental update.

---

### `/ob-slack-activity`
**What it does:** Pulls today's Slack activity (messages sent, mentions received, channel pings) and appends a formatted daily entry to `Data/Work/Slack Activity/YYYY-MM.md`.

**When to use:** At the end of the workday to capture what you were working on and who you interacted with.

---

### `/ob-zoom` (command)
**What it does:** Searches for today's Zoom meetings that have AI summaries available and exports them to `Data/Meetings/`.

**When to use:** After meetings have finished and Zoom has processed the AI summary (usually within an hour of the meeting ending).

---

### `/ob-guru`
**What it does:** Fetches one or more Guru cards using the Guru MCP and saves a formatted summary with a link to `Data/Resources/Guru/`.

**When to use:** When you want to capture a Guru card into the vault — search for it by keyword or paste a card ID.

---

### `/ob-asana`
**What it does:** Generates a daily Asana briefing (overdue, due today, upcoming, recently completed) for the current user and saves it to `Data/Work/Asana/`.

**When to use:** Start of day, to see what's on your plate before diving into other work.

---

### `/ob-todo`
**What it does:** Generates a daily and a weekly to-do list by combining Asana tasks due today/this week, action items pulled from recent meeting notes and wiki pages, and unchecked items carried over from the previous list. Every item is labeled 🔴 High / 🟡 Medium / 🟢 Low. Saves both to `Level Playbook/planning/`.

**When to use:** Start of day or week, to get one prioritized checklist instead of checking Asana, meeting notes, and the wiki separately.

---

### `/ob-insight`
**What it does:** Analyzes `Level Knowledge/` over a user-specified time window (e.g., "last week", "June 2026", "last 30 days") to surface key trends, signals worth watching, knowledge gaps, improvement opportunities, and anything noteworthy. Dives into raw `Data/` sources via wiki References when pages are low-confidence or a claim needs verification. Saves a structured report to `Level Playbook/insights/`.

**When to use:** Whenever you want a synthesized picture of what's been happening — client health, process drift, emerging patterns — without manually reading every wiki page.

**Examples:** `/ob-insight last week` · `/ob-insight June 2026` · `/ob-insight last 30 days`

---

### `/ob-sentiment`
**What it does:** Predicts how a client, person, or group feels about Level's performance by mining meeting notes, Slack activity, and wiki pages for sentiment signals. Produces a structured report with an overall health label, evidence quotes, confidence, trend direction, and recommended actions — optionally saved as a wiki sentiment page.

**When to use:** Relationship health checks — "how is [client] feeling about us", "are we at risk of losing [client]", mood checks before a QBR.

---

### `/ob-praise-me`
**What it does:** Looks back over a user-specified time window (default: 1 week) and surfaces wins, accomplishments, and moments of excellence — client wins, process gains, productivity boosts, demonstrations of Core Values/Key Behaviors — with metrics wherever possible. Saves a celebratory report to `Level Playbook/insights/`.

**When to use:** When you want a morale boost, a self-review input, or a recap of recent wins to share up the chain.

---

### `/ob-diss-me`
**What it does:** Looks back over a user-specified time window (default: 1 week) and surfaces honest, specific areas for improvement — missed commitments, over-promising, delivery delays, communication lapses — evaluated against Level's Core Values and Key Behaviors. Saves a candid report to `Level Playbook/insights/` and appends to a running history file.

**When to use:** When you want unvarnished, constructive feedback on your own recent performance.

---

### `/ob-wiki-lint`
**What it does:** Audits the `Level Knowledge/` wiki for contradictions, orphan pages, missing concept pages, stale claims, and pages with low confidence that haven't been updated. Writes a prioritized report to `Level Playbook/wiki-lint/`.

**When to use:** Periodically to keep the wiki healthy, or before sharing wiki content externally.

---

### `/ob-wiki-contradictions`
**What it does:** Runs the full lint + triage pipeline, presents a prioritized, numbered action plan, and implements whichever items you select. Does not touch graph colors — run `/wiki-graph-sync` afterward if the fixes changed wiki structure.

**When to use:** When you want to actually fix what `/ob-wiki-lint` finds, not just read a report.

---

### `/wiki-graph-sync`
**What it does:** Syncs `.obsidian/graph.json` color groups against the canonical color table in `.claude/tagging.md` and the current `Level Knowledge/` domain structure — adds missing groups, updates drifted colors, removes obsolete groups.

**When to use:** After wiki structure changes (new domain, moved pages) or whenever graph view colors look wrong. Not run automatically by any other skill.

---

## Agents (invoked automatically by skills)

### `ob-inbox`
**What it does:** Sorts miscellaneous files from `Data/Inbox/` into the appropriate `Data/` subfolder, creating new subfolders when needed. Classifies and vision-extracts images.

**Triggered by:** `/ob-wiki-update` (Step 0) — runs automatically before every wiki update.

**Manual use:** You can also ask Claude to "sort the inbox" directly.

---

### `wiki-lint`
**What it does:** Lints every page in `Level Knowledge/` for contradictions, stale claims, orphans, and missing frontmatter; writes the report to `Level Playbook/wiki-lint/`.

**Triggered by:** `/ob-wiki-lint` and `/ob-wiki-contradictions`.

---

### `wiki-triage`
**What it does:** Takes a wiki-lint report and produces a numbered, prioritized action plan (no file writes).

**Triggered by:** `/ob-wiki-contradictions`, after the lint report is generated.

---

### `wiki-graph-sync`
**What it does:** Does the actual sync work for the `/wiki-graph-sync` skill — adds missing groups, updates drifted colors, removes obsolete groups.

**Triggered by:** `/wiki-graph-sync`.

---

## Automatic behaviors (hooks)

### Session transcript export
**What it does:** At the end of every Claude Code session, the full conversation is automatically exported to `Data/Claude/<session-title>.md`.

**When it runs:** On every session stop — no action needed. The transcript becomes a raw source that `/ob-wiki-update` can ingest. Cross-platform: `.claude/export-session-to-obsidian.ps1` (Windows) / `.claude/export-session-to-obsidian.sh` (Mac/Linux).

---

## How the vault works

```
Data/          ← immutable raw inputs (never edited by Claude)
  Meetings/    ← Zoom exports
  Work/        ← Slack activity, Asana reports, working docs
  Claude/      ← session transcripts (auto-exported)
  Knowledge/   ← external reference material, articles, guides saved for future use
  Inbox/       ← drop zone; sorted by ob-inbox
  Resources/   ← Guru cards, reference docs
  Personal/    ← personal notes

Level Knowledge/   ← wiki; Claude rewrites in place
  index.md         ← master catalog and cursor
  log.md           ← append-only operation log
  clients/         ← one sub-folder per client
  processes/       ← how we do things
  tools/           ← platforms and software
  analytics/       ← metrics, models, datasets
  team/            ← people
  decisions/       ← closed decisions kept for pattern recognition
  organization/    ← company culture, policies, and brand

Level Playbook/    ← deeper analysis derived from the wiki
  insights/        ← /ob-insight, /ob-praise-me, /ob-diss-me reports
  wiki-lint/        ← /ob-wiki-lint reports
  planning/        ← /ob-todo daily.md and weekly.md (overwritten in place, not dated)
```

**Wiki update cycle:** `/ob-wiki-update` reads the `last_updated` cursor from `index.md`, finds all `Data/` files modified since then, triages them to wiki domains, rewrites the relevant pages, and advances the cursor. Every 7 days it offers a full rerun to catch cross-file connections that incremental updates miss.

**Protected section:** Every wiki page has a `## Notes` section that Claude will never modify — use it for your own observations, context, or annotations.

---

*This file is automatically updated by `/ob-wiki-update` when skills, agents, or hooks change.*
