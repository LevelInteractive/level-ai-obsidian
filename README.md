# AI Obsidian

A template for a personal knowledge vault that pairs **Obsidian** with **Claude Code**. Claude reads what happens in your day (meetings, Slack, sessions, notes) and maintains a living wiki of what it means — so you can ask "what's going on with X" and get a synthesized answer instead of re-reading a folder of transcripts.

## How it works

The vault is organized as three layers, based on the Karpathy three-layer model:

| Layer | Folder | What it is |
|---|---|---|
| **Input** | `Data/` | Raw, immutable captures — meeting exports, Slack activity, Claude session transcripts, daily notes. Never rewritten. |
| **Synthesis** | `Level Knowledge/` | Claude's living understanding of that reality — one page per client, tool, process, person, decision, etc. Rewritten in place as understanding improves. |
| **Deliverable** | `Level Playbook/` | Deeper, point-in-time analysis derived from the wiki — insight reports, lint audits, planning docs. |

Claude is the process that reads the inputs, maintains the synthesis, and produces deliverables from it. You interact with it through **skills** (slash commands) — see [`HELP.md`](HELP.md) for the full list, or just ask in plain English (e.g. "update the wiki," "give me a win report").

## Workflow

The vault runs on four workflows:

1. **Ingest** (`/ob-wiki-update`) — sorts the inbox, finds every `Data/` file changed since the last run, triages it to the right wiki domain, and rewrites the affected pages in place: merging new learnings into what's already there rather than resetting the page. Roughly every 7 days it offers a full rerun to catch cross-file connections an incremental pass would miss.
2. **Query** — just ask a question in plain English. Claude reads `Level Knowledge/index.md`, answers from high-confidence pages directly, and only drops into raw `Data/` sources when a page is low-confidence, the question needs more precision than the wiki captures, or two pages contradict each other.
3. **Lint** (`/ob-wiki-contradictions`) — audits the wiki for contradictions, stale claims, orphan pages, and missing concepts (via `ob-wiki-lint` internally, so you don't need to run that separately), then produces a prioritized, numbered fix plan you can act on item by item. Run `/ob-wiki-lint` on its own if you just want the report, not the fix workflow.
4. **Graph sync** (`/wiki-graph-sync`) — keeps Obsidian's graph view colors in sync with the wiki's domain structure. Run it after adding a new domain or moving pages; nothing else triggers it automatically.

Day to day, this looks like:
1. Drop any new raw file into `Data/Inbox/` (some capture happens on its own — session transcripts export automatically, and Slack/Zoom/Asana skills pull on demand and file straight into the right subfolder — but anything else lands in the inbox).
2. Run **Ingest** periodically to sort the inbox and fold new material into the wiki.
3. **Query** whenever you need an answer.
4. Run **Lint** occasionally to keep the wiki healthy.

## Setup

**Prerequisites:**
- [Obsidian](https://obsidian.md) desktop app
- [Claude Code](https://claude.com/claude-code) CLI
- Optional, for specific skills: a Guru account (`ob-guru`), Zoom (`ob-zoom`), Asana (`ob-asana`) — via MCP servers or API access you configure yourself

**Getting started:**
1. Clone or copy this repo to where you want your vault to live.
2. Open the folder as a vault in Obsidian.
3. Open the same folder in Claude Code (`claude` in the folder, or open it from the desktop app).
4. Personalize [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — it's written generically ("the user") on purpose; adapt wording, domains, and tagging vocabulary (`.claude/tagging.md`) to your own context.
5. Set up the `obsidian` MCP server (referenced in `.claude/settings.local.json`) if you want Claude to read/write notes directly rather than through shell commands.
6. Drop your first raw files into `Data/Inbox/`, then run `/ob-wiki-update` to sort them and do the first synthesis pass.

See [Workflow](#workflow) above for the ongoing rhythm once the vault is seeded.

## What's in here

- **`Data/`** — raw sources, organized by type (`Meetings/`, `Work/`, `Claude/`, `Daily/`, `Inbox/`, `Knowledge/`, `Resources/`, `Personal/`, `Assets/`). Drop any new raw file into `Data/Inbox/` — the `ob-inbox` agent sorts it into the right subfolder (and vision-extracts images) the next time `/ob-wiki-update` runs, or on demand if you ask Claude to "sort the inbox."
- **`Level Knowledge/`** — the wiki: `index.md` is the master catalog, `log.md` is an append-only operation log, and each domain (`clients/`, `processes/`, `tools/`, `analytics/`, `team/`, `decisions/`, plus any custom domains) gets its own folder
- **`Level Playbook/`** — generated reports: `insights/`, `wiki-lint/`, `planning/`, `Hub/` (latest-report shortcuts)
- **`.claude/`** — skills, agents, commands, tagging vocabulary, and hooks that drive the automation
- **`HELP.md`** — up-to-date reference for every skill, agent, and hook, regenerated automatically whenever `/ob-wiki-update` runs

For the full architecture, page conventions, and workflow specs, see [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — that file is the source of truth Claude itself reads on every session.

## Cross-platform

Every hook and skill in this vault supports both Windows and macOS/Linux — paths are derived dynamically from the vault root, never hardcoded, and any OS-level script ships as a `.ps1`/`.sh` pair.

## Customizing this template

This repo is meant to be forked or copied, not used as-is. The two files worth editing first:
- **`.claude/CLAUDE.md`** — vault conventions, page templates, and workflow definitions
- **`.claude/tagging.md`** — your controlled tag vocabulary and graph color scheme

Everything else (skills, agents) is generic enough to work unmodified, but feel free to add, remove, or adapt skills as your own workflow diverges from the template.
