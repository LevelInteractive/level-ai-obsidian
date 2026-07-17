# Vault — Skills & Commands Reference

Quick reference for all automation built into this vault. Run skills as slash commands in your configured agent (for example, type `/ob-ingest` in the chat).

New to this vault or moving it to a new machine? Start with [SETUP.md](SETUP.md).

---

## Skills (slash commands)

### `/ob-wiki-update`
**What it does:** Evidence-reviews the bounded source-and-page packet produced by ingestion preflight, then applies approved targeted wiki-page edits or independently justified creations. It does not scan all `Data/`, sort the inbox, run QMD, or advance source state.

**When to use:** After `/ob-ingest` has produced a successful bounded ingest packet for new meetings, Slack captures, references, or sessions. It is normally invoked by ingestion rather than run on its own.

**Operational boundary:** Inbox sorting, hash-based source discovery, QMD/graph routing, acceptance, and source-state advancement belong to ingestion, not this review skill.

---

### `/ob-ingest`
**What it does:** Runs the complete safe ingest cycle: inbox preparation,
hash-based source discovery, bounded QMD/graph preflight, wiki review/write,
validation, retrieval refresh, and source-state acceptance.

**When to use:** After adding new material to the vault, when you want one
command to process it safely.

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
**What it does:** Generates a daily and a weekly to-do list by combining Asana tasks due today/this week, action items pulled from recent meeting notes and wiki pages, and unchecked items carried over from the previous list. Every item is labeled by priority. Saves both to `Level Playbook/planning/`.

**When to use:** Start of day or week, to get one prioritized checklist instead of checking Asana, meeting notes, and the wiki separately.

---

### `/ob-insight`
**What it does:** Analyzes `Level Knowledge/` over a user-specified time window (e.g., "last week", "June 2026", "last 30 days") to surface key trends, signals worth watching, knowledge gaps, improvement opportunities, and anything noteworthy. Dives into raw `Data/` sources via wiki References when pages are low-confidence or a claim needs verification. Saves a structured report to `Level Playbook/insights/`.

**When to use:** Whenever you want a synthesized picture of what's been happening without manually reading every wiki page.

**Examples:** `/ob-insight last week` · `/ob-insight June 2026` · `/ob-insight last 30 days`

---

### `/ob-similarity-update`
**What it does:** Builds a read-only similarity graph over `Data/` using QMD retrieval, then groups high-confidence related sources and flags uncertain connections for review. It does not write wiki pages.

**When to use:** When you want to find related sources or refresh the knowledge graph before deciding how to consolidate the wiki.

---

### `/ob-similarity-consolidate`
**What it does:** Resolves the similarity graph's confirmed clusters and updates the appropriate `Level Knowledge/` pages using evidence, confidence, and decay rules.

**When to use:** After `/ob-similarity-update`, when you are ready to turn reviewed source clusters into wiki synthesis.

---

### `/ob-sentiment`
**What it does:** Predicts how a client, person, or group feels about your organization's performance by mining meeting notes, Slack activity, and wiki pages for sentiment signals. Produces a structured report with an overall health label, evidence quotes, confidence, trend direction, and recommended actions — optionally saved as a wiki sentiment page.

**When to use:** Relationship health checks, mood checks before a review meeting, or "are we at risk of losing this client" questions.

---

### `/ob-praise-me`
**What it does:** Looks back over a user-specified time window (default: 1 week) and surfaces wins, accomplishments, and moments of excellence — with metrics wherever possible. Saves a celebratory report to `Level Playbook/insights/`.

**When to use:** When you want a morale boost, a self-review input, or a recap of recent wins to share up the chain.

---

### `/ob-diss-me`
**What it does:** Looks back over a user-specified time window (default: 1 week) and surfaces honest, specific areas for improvement — missed commitments, over-promising, delivery delays, communication lapses. Saves a candid report to `Level Playbook/insights/` and appends to a running history file.

**When to use:** When you want unvarnished, constructive feedback on your own recent performance.

---

### `/ob-wiki-lint`
**What it does:** Runs full-vault deterministic checks for structure, links, freshness, and metadata, then sends only a small changed/risk-rotation set for semantic contradiction review. Writes shared active issues, a numbered approval plan, and a dated report.

**When to use:** Periodically to keep the wiki healthy, or before sharing wiki content externally.

---

### `/ob-wiki-contradictions`
**What it does:** Presents the lint pipeline's numbered plan and applies only the issue numbers you explicitly select. It snapshots selected pages, protects `## Notes`, then verifies the result before re-linting. It does not sync graph colors.

**When to use:** When you want to actually fix what `/ob-wiki-lint` finds, not just read a report.

---

### `/wiki-graph-sync`
**What it does:** Deterministically syncs `.obsidian/graph.json` color groups from `.config/tagging.md` and current top-level wiki domains. It writes only real changes, preserves all other graph settings, and has an explicit read-only tag-audit mode.

**When to use:** After wiki structure changes (new domain, moved pages) or whenever graph view colors look wrong. Not run automatically by any other skill.

**Useful modes:** `--dry-run` previews the structured change set without writing. `--audit-tags` scans frontmatter for controlled tags used on 3+ pages that have no color group; it never assigns a color or changes configuration.

---

## Operational workflow: ingest to contradiction correction

Use `/ob-ingest` for normal source processing. It is a gated workflow: a later step never accepts a source change if an earlier step failed or needs review.

1. **Prepare Inbox.** `ob-inbox` routes `Data/Inbox/` files into the appropriate immutable `Data/` location, handles images, and reports any blocked items. A partial Inbox result stops the run.
2. **Detect source changes.** The source-state scanner compares SHA-256 hashes against the accepted manifest. New and content-changed files proceed; unchanged files do not. Moved or deleted files stop for reference/dependency maintenance rather than being treated as new knowledge.
3. **Create a bounded packet.** `prepare_ingest_packet.py` refreshes QMD as needed and produces an explicit source list, candidate wiki pages, queued ambiguities, taxonomy cues, and preflight results. It avoids a blanket reread of `Data/`.
4. **Review evidence and write synthesis.** `/ob-wiki-update` reads only packet sources and the relevant candidate pages. It can enrich or correct an existing page, create an independently justified page, or make no change. It preserves `## Notes` and cites only sources actually used.
5. **Validate before acceptance.** Ingestion checks page metadata, references, confidence, protected notes, redaction, and entity/dependency metadata. It updates `index.md` and `log.md` only when approved wiki changes require them.
6. **Refresh derived state and retrieval.** When approved wiki pages changed, refresh the dependency graph and validate the refreshed metadata. Then refresh QMD for approved `Level Knowledge/` changes. A graph or QMD failure stops the run before acceptance.
7. **Accept source state.** Only after those refreshes succeed is the exact source delta accepted into the hash-based state manifest. A failed run leaves the source eligible for the next run.
8. **Maintain and audit separately.** Run `/wiki-graph-sync` after structural changes, and `/ob-wiki-lint` periodically or before relying on wiki content externally. Neither runs automatically during ingestion.
9. **Fix contradictions deliberately.** `/ob-wiki-lint` performs full deterministic checks and limits semantic review to a bounded risk set. `/ob-wiki-contradictions` presents its numbered plan, waits for your selection, validates the selected fix packet, applies only those corrections, and re-lints to verify them.

**Rule of thumb:** hashes decide what changed; QMD narrows what to read; the wiki reviewer writes only supported synthesis; validation protects acceptance; lint detects quality issues; contradiction fixes require approval.

---

## Agents (invoked automatically by skills)

### `ob-inbox`
**What it does:** Sorts miscellaneous files from `Data/Inbox/` into the appropriate `Data/` subfolder, creating new subfolders when needed. Classifies and vision-extracts images.

**Triggered by:** ingestion preflight, before source-state scanning and
`prepare_ingest_packet.py`. It may also be run directly to clear the inbox.

**Manual use:** You can also ask Claude to "sort the inbox" directly.

---

### `wiki-lint`
**What it does:** Reviews only the pages and evidence listed by `prepare_wiki_lint.py` for claim conflicts or stale interpretations, then writes a structured review for the shared finalizer.

**Triggered by:** `/ob-wiki-lint` and `/ob-wiki-contradictions`.

---

### `wiki-graph-sync`
**What it does:** Thin wrapper around the deterministic graph-sync script. The script adds missing canonical groups, corrects drifted colors, removes obsolete domain groups, and preserves manual non-conflicting groups.

**Triggered by:** `/wiki-graph-sync`.

---

## Automatic behaviors (hooks)

### Session transcript export
**What it does:** At the end of every Claude Code session, the full conversation is automatically exported to `Data/Claude/<session-title>.md`.

**When it runs:** On every session stop — no action needed. The transcript becomes a raw source that `/ob-ingest` can process. Cross-platform: `.claude/export-session-to-obsidian.ps1` (Windows) / `.claude/export-session-to-obsidian.sh` (Mac/Linux).

---

## How the vault works

`Level Knowledge/interests/` holds durable personal hobbies, craft practice, and learning topics. New domains may be created whenever recurring sources have a clear, lasting category that does not fit the existing wiki.

```
Data/          ← immutable raw inputs (never edited by Claude)
  Meetings/    ← Zoom exports
  Work/        ← Slack activity, Asana reports, and other working docs
  Claude/      ← session transcripts (auto-exported)
  Knowledge/   ← external reference material, articles, guides saved for future use
  Inbox/       ← drop zone; sorted by ob-inbox
  Resources/   ← Guru cards, reference docs
  Personal/    ← personal notes

Level Knowledge/   ← wiki; Claude rewrites synthesis pages in place
  index.md         ← master catalog and domain registry
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

**Wiki update cycle:** Ingestion compares current `Data/` files with the accepted SHA-256 source-state manifest, routes only new or content-changed sources, and sends the resulting bounded packet to `/ob-wiki-update` for evidence review. The manifest advances only after post-write validation and QMD retrieval refresh succeed. Hash comparison replaces a former cursor-based change detector.

**Protected section:** Every wiki page has a `## Notes` section that Claude will never modify — use it for your own observations, context, or annotations.

---

*Keep this file aligned when skills, agents, hooks, or the operating workflow change. `/ob-wiki-update` does not modify it during a normal ingest run.*
