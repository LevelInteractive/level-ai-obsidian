# AI Obsidian

A template for a personal knowledge vault that pairs **Obsidian** with **Claude Code** (and, optionally, **Codex**). Claude reads what happens in your day (meetings, Slack, sessions, notes) and maintains a living wiki of what it means — so you can ask "what's going on with X" and get a synthesized answer instead of re-reading a folder of transcripts.

## How it works

The vault is organized as three layers, based on the Karpathy three-layer model:

| Layer | Folder | What it is |
|---|---|---|
| **Input** | `Data/` | Raw, immutable captures — meeting exports, Slack activity, Claude session transcripts, daily notes. Never rewritten. |
| **Synthesis** | `Level Knowledge/` | Claude's living understanding of that reality — one page per client, tool, process, person, decision, etc. Rewritten in place as understanding improves. |
| **Deliverable** | `Level Playbook/` | Deeper, point-in-time analysis derived from the wiki — insight reports, lint audits, planning docs. |

A retrieval layer sits underneath all three: **QMD** indexes `Data/`, `Level Knowledge/`, and `Level Playbook/` for hybrid keyword/semantic search, and `.kb-indexer/` tracks a hash-based inventory of what's already been ingested so every update only touches what actually changed.

Claude is the process that reads the inputs, maintains the synthesis, and produces deliverables from it. You interact with it through **skills** (slash commands) — see [`HELP.md`](HELP.md) for the full list, or just ask in plain English (e.g. "ingest my inbox," "give me a win report").

## Workflow

The vault runs on five workflows:

1. **Ingest** (`/ob-ingest`) — the gated entry point for new sources. Sorts the inbox, uses a SHA-256 hash inventory (not a date cursor) to find only new or changed `Data/` files, builds a bounded QMD/metadata packet for just those sources, hands it to `/ob-wiki-update` for evidence-reviewed page writes, validates the result, refreshes dependency metadata and retrieval, and only then accepts the source delta. A later step never accepts a change if an earlier one failed or needs review.
2. **Query** — just ask a question in plain English. Claude reads `Level Knowledge/index.md`, answers from high-confidence pages directly, and only drops into raw `Data/` sources (via QMD-targeted retrieval) when a page is low-confidence, the question needs more precision than the wiki captures, or two pages contradict each other.
3. **Lint & fix contradictions** (`/ob-wiki-lint`, `/ob-wiki-contradictions`) — `ob-wiki-lint` runs deterministic whole-wiki checks (stale claims, orphans, missing frontmatter) plus a bounded semantic contradiction review, and is read-only. `/ob-wiki-contradictions` runs it, presents a numbered fix plan, and applies only the items you explicitly select.
4. **Similarity graph** (`/ob-similarity-update`, `/ob-similarity-consolidate`) — finds connections QMD's semantic search can see but folder structure and explicit wikilinks miss. `ob-similarity-update` builds and flags candidate clusters from `Data/`; `ob-similarity-consolidate` resolves what was flagged and synthesizes wiki pages from the confirmed clusters.
5. **Graph sync** (`/wiki-graph-sync`) — keeps Obsidian's graph view colors in sync with the wiki's domain structure and controlled tag vocabulary. Run it after adding a new domain, moving pages, or when colors look wrong; nothing else triggers it automatically.

Day to day, this looks like:
1. Drop any new raw file into `Data/Inbox/` (some capture happens on its own — session transcripts export automatically, and Slack/Zoom/Asana skills pull on demand and file straight into the right subfolder — but anything else lands in the inbox).
2. Run **Ingest** (`/ob-ingest`) periodically to sort the inbox and fold new material into the wiki.
3. **Query** whenever you need an answer.
4. Run **Lint** occasionally to keep the wiki healthy, and **Graph sync** after structural changes.

## Retrieval and scale

Earlier versions of this template relied on a full-document read/update pattern — every ingest re-read a growing pile of `Data/` to decide what changed, which becomes slow and expensive past a few hundred documents.

That's been replaced with a retrieval-backed pipeline, and it's already wired into this template:

- **QMD** (`https://github.com/tobi/qmd`) provides local hybrid search (BM25 + embeddings + reranking) over `Data/`, `Level Knowledge/`, and `Level Playbook/` — see `.mcp.json` for the MCP server registration and `SETUP.md` for the one-time collection setup.
- **`.kb-indexer/`** tracks a SHA-256 source-state manifest so ingestion only routes new or content-changed files, never a blanket re-read. It also maintains an entity registry and dependency graph used to scope impact review and wiki-lint to a bounded set of pages rather than the whole wiki.
- Ingest packets are explicitly bounded (`prepare_ingest_packet.py`) — the LLM reviews only the sources and candidate pages the packet names, not the full corpus.

If you're extending this template, keep that shape: write raw captures to `Data/`, let the hash-state scanner and QMD decide what's new, and keep the LLM's read scope bounded to what a packet actually names.

## Setup

**Prerequisites:**
- [Obsidian](https://obsidian.md) desktop app
- [Claude Code](https://claude.com/claude-code) CLI, and/or Codex
- Python 3.11+ and Node.js/Bun (for the local indexer and QMD CLI — no cloud embeddings required)
- Optional, for specific skills: a Guru account (`ob-guru`), Zoom (`ob-zoom`), Asana (`ob-asana`) — via MCP servers or API access you configure yourself

**Getting started:** see [`SETUP.md`](SETUP.md) for the full, cross-platform walkthrough (Python venv, QMD install and collection setup, QMD agent skill install, initial source-state bootstrap, and a first safe `/ob-ingest` run). The short version:

1. Clone or copy this repo, including the hidden `.agents/`, `.claude/`, `.codex/`, `.config/`, and `.kb-indexer/` folders, to where you want your vault to live.
2. Open the folder as a vault in Obsidian, and open the same folder in Claude Code and/or Codex.
3. Personalize [`.claude/CLAUDE.md`](.claude/CLAUDE.md) (and `AGENTS.md` if you use Codex) — written generically on purpose; adapt wording, domains, and tagging vocabulary (`.config/tagging.md`) to your own context.
4. Install QMD and its agent skill, then run the one-time collection setup — see `SETUP.md`.
5. Set up the `obsidian` MCP server (referenced in `.claude/settings.local.json`) if you want Claude to read/write notes directly rather than through shell commands.
6. Drop your first raw files into `Data/Inbox/`, then run `/ob-ingest` to sort them and do the first synthesis pass.

See [Workflow](#workflow) above for the ongoing rhythm once the vault is seeded.

## What's in here

- **`Data/`** — raw sources, organized by type (`Meetings/`, `Work/`, `Claude/`, `Daily/`, `Inbox/`, `Knowledge/`, `Resources/`, `Personal/`, `Assets/`). Drop any new raw file into `Data/Inbox/` — the `ob-inbox` agent sorts it into the right subfolder (and vision-extracts images) the next time `/ob-ingest` runs, or on demand if you ask Claude to "sort the inbox."
- **`Level Knowledge/`** — the wiki: `index.md` is the master catalog, `log.md` is an append-only operation log, and each domain (`clients/`, `processes/`, `tools/`, `analytics/`, `team/`, `decisions/`, `organization/`, plus any custom domains) gets its own folder
- **`Level Playbook/`** — generated reports: `insights/`, `wiki-lint/`, `planning/`, `Hub/` (latest-report shortcuts), `sentiment/`
- **`.claude/`** — Claude Code skills, agents, commands, and hooks that drive the automation
- **`.agents/`** — the same skills mirrored for Codex-family agents, kept behaviorally aligned with `.claude/`
- **`.codex/`** — Codex agent definitions and config
- **`.config/`** — `tagging.md`, the single source of truth for controlled tags, taxonomy rules, and graph colors
- **`.kb-indexer/`** — retrieval and metadata tooling: QMD collection scripts, the hash-based source-state scanner, entity registry, and dependency-graph impact resolution. Generated state is deliberately excluded from a fresh template checkout.
- **`HELP.md`** — reference for every skill, agent, and hook — kept aligned manually when the workflow changes, not auto-regenerated during ingest
- **`SETUP.md`** — full cross-platform setup walkthrough for a new machine or a new user

For the full architecture, page conventions, and workflow specs, see [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — that file is the source of truth Claude itself reads on every session.

## Cross-platform

Every hook and skill in this vault supports both Windows and macOS/Linux — paths are derived dynamically from the vault root, never hardcoded, and any OS-level script ships as a `.ps1`/`.sh` pair.

## Customizing this template

This repo is meant to be forked or copied, not used as-is. The two files worth editing first:
- **`.claude/CLAUDE.md`** — vault conventions, page templates, and workflow definitions
- **`.config/tagging.md`** — your controlled tag vocabulary and graph color scheme

Everything else (skills, agents) is generic enough to work unmodified, but feel free to add, remove, or adapt skills as your own workflow diverges from the template.
