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
6. Drop your first raw files into `Data/` (or `Data/Inbox/` if unsorted), then run `/ob-wiki-update` to do the first synthesis pass.

Once seeded, a normal rhythm looks like: capture happens automatically (session transcripts export on their own; Slack/Zoom/Asana skills pull on demand) → run `/ob-wiki-update` periodically to fold new raw material into the wiki → ask questions or run report skills (`/ob-insight`, `/ob-praise-me`, `/ob-todo`, etc.) against the synthesized wiki.

## What's in here

- **`Data/`** — raw sources, organized by type (`Meetings/`, `Work/`, `Claude/`, `Daily/`, `Inbox/`, `Knowledge/`, `Resources/`, `Personal/`, `Assets/`)
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
