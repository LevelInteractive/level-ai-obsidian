# CLAUDE.md — Personal Knowledge Vault

## What this vault is

This vault is a personal knowledge operating system built on the Karpathy Three-layer model:

- **`Data/`** — the input layer. Raw, immutable captures of reality: meetings, Slack activity, daily notes, Claude sessions. Never rewrite these. They are the record of what happened.
- **`Level Knowledge/`** — the synthesis layer. Claude's living, maintained understanding of that reality. Rewritten in place as understanding improves. Never appended to.
- **`Level Playbook/`** — the deliverable layer. Deeper analysis derived from the Knowledge layer and digging into the recorded references.

Claude is the process that reads the inputs, maintains the synthesis, and acts from the synthesis.

---

## Project structure

| Path | Role |
|---|---|
| `Data/Meetings/` | Immutable source — Zoom meeting exports |
| `Data/Work/Slack Activity/` | Immutable source — daily Slack captures |
| `Data/Claude/` | Immutable source — session transcripts |
| `Data/Daily/`, `Data/Inbox/`, `Data/Personal/` | Immutable source — other captures |
| `Data/Knowledge/` | Immutable source — external reference material, articles, guides saved for future use |
| `Data/Work/Analytics/` | Immutable source — analytics methodology docs, model specs, and data science references |
| `Data/Assets/team/` | Profile photos and avatars — linked from team wiki pages |
| `Data/Assets/attachments/` | Screenshots and diagrams — linked manually from notes |
| `Data/Assets/processed/` | Original images after vision extraction — companion `.md` in `Data/` |
| `Level Knowledge/` | Wiki — LLM-generated and maintained pages |
| `Level Knowledge/index.md` | Master catalog — update on every wiki operation |
| `Level Knowledge/log.md` | Append-only operation log — record every ingest and lint run |
| `.kb-indexer/` | Retrieval and metadata tooling — QMD collection scripts, hash-based source-state tracking, dependency-graph impact resolution. Generated state lives here and is never committed as vault "data" |

---

## Page types and conventions

Every wiki page must have YAML frontmatter:

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

### Naming

- Filenames: `kebab-case` matching the concept — e.g., `signal-operations.md`, `csu/overview.md`
- Cross-references: use `[[wikilinks]]` for all internal links
- Source references: wikilinks to bare filenames in `Data/` — Obsidian resolves them uniquely

### Page sections (standard order)

Every wiki page follows this section order. Sections marked **protected** are never modified by Claude.

| Section | Purpose | Managed by |
|---|---|---|
| `# Title` + lede + `[^confidence]` | One-sentence summary with confidence marker | Claude |
| `![[photo]]` | Profile photo embed — team pages only | Claude (auto-linked from `Data/Assets/team/`) |
| Domain-specific sections | Content sections per page type (Overview, Steps, Issues, etc.) | Claude |
| `## Attachments` | Images from `Data/Assets/attachments/` relevant to this page — omitted if none | Claude (auto-refreshed) |
| `## Notes` | **Protected** — user's personal annotations; Claude never modifies this | User |
| `## References` | Wikilinks to every raw source that informed this page | Claude |
| `[^confidence]: ...` | Confidence footnote definition | Claude |

### Sensitive content handling

Both `ob-inbox` and `ob-wiki-update` scrub credentials before writing files to their destination.

**Redacted (replaced with `[REDACTED]`):** API keys, secret tokens, passwords, private key PEM blocks, connection strings with embedded credentials, Bearer/Basic auth tokens, webhook URLs with embedded token segments.

**Kept (never redacted):** Email addresses, phone numbers, names, physical addresses, plain URLs, hashed values (bcrypt/SHA).

If a raw file in `Data/Inbox/` contains real credentials, `ob-inbox` writes a cleaned copy to the destination and flags the redaction in its summary. `ob-wiki-update` never carries raw credential strings into wiki pages regardless — and flags any suspicious files in the run report.

### Image handling

Images dropped into `Data/Inbox/` are processed by `ob-inbox` into one of three paths:

| Type | Signal | Where it goes |
|---|---|---|
| Profile photo | Filename contains a team member name, "headshot", "avatar", or "profile" | `Data/Assets/team/` — auto-linked from team wiki pages |
| Content image | Whiteboard, chart, slide, or screenshot with meaningful text/data | Vision-extracted to `.md` in `Data/`; original to `Data/Assets/processed/` |
| Attachment | Screenshot or diagram with no extractable text | `Data/Assets/attachments/` — auto-linked from relevant wiki pages |

### Wiki structure

```
Level Knowledge/
├── index.md          ← master catalog; update on every operation
├── log.md            ← append-only operation log
├── clients/
│   └── <client>/     ← sub-folder per client
│       ├── overview.md
│       ├── issues.md
│       ├── trends.md
│       ├── sentiment.md
│       └── wins.md
├── processes/
├── tools/
├── analytics/
├── team/
├── decisions/
└── <new-domain>/     ← created as new topic areas emerge (see below)
```

**The six core domains are a starting point, not a ceiling.** When raw sources contain recurring content that doesn't fit any existing domain, create a new top-level folder. Good candidates: `organization/` (culture, values, key behaviors, org structure), `interests/` (durable personal learning and practices, distinct from work-applied `tools/`/`analytics/`), `vendors/` (external partners), `campaigns/` (specific media campaigns), `experiments/` (A/B tests, holdout studies). A new top-level domain is only created after three genuinely separate child-page scopes justify it — otherwise leave a review cue instead of creating the folder. Register every new domain in `index.md` and log its creation in `log.md`.

### Tagging

Tag vocabulary, graph color groups, and auto-creation rules are defined in **`.config/tagging.md`**. That file is the single source of truth — read it for the full controlled vocabulary, color table, and the dynamic taxonomy proposal rules for new pages/domains. Both `ob-wiki-update` and `wiki-graph-sync` reference it directly.

### Confidence levels

| Level | Meaning |
|---|---|
| `high` | 3+ consistent sources; facts cross-confirmed by multiple participants; recently updated |
| `medium` | 1-2 sources, or some details inferred; based partly on a Claude session; verify before acting externally |
| `low` | Single Claude session only; not confirmed in a meeting context |

Confidence lives in both YAML (for filtering) and as a `[^confidence]` footnote in the page body (for rationale). When updating a page, re-evaluate confidence based on all available sources. Point-in-time decisions do not decay just because time has passed.

---

## Workflows

### Ingest (`/ob-ingest`)

`/ob-ingest` is the normal entry point for new sources. Ingestion is gated — it runs the complete cycle end to end rather than writing directly to the wiki:

1. **Sort inbox** — `ob-inbox` agent moves files from `Data/Inbox/` into the correct `Data/` subfolder before scanning; images are classified and vision-extracted if needed; stop on partial or blocked files.
2. **Detect changes** — a hash-based source-state inventory (not a date cursor) identifies new and content-changed files. Moved or deleted files stop for reference/dependency maintenance instead of being silently dropped or re-routed.
3. **Prepare a bounded packet** — `prepare_ingest_packet.py` (in `.kb-indexer/scripts/`) builds a scoped QMD/metadata packet covering only the new or changed sources. This never substitutes a full `Data/` scan.
4. **Review and write** — `/ob-wiki-update` reviews only the packet's sources and candidate pages, then writes only evidence-supported changes: merge new learnings, update `confidence`, `last_updated`, and `tags` in frontmatter, embed relevant images from `Data/Assets/`, add or refresh `## Attachments`, update `## References`, update the `[^confidence]` footnote; never modify `## Notes`.
5. **Restructure if needed** — if new sources reveal a page is in the wrong domain or scope, move it and leave a redirect at the old path.
6. **Validate** — check metadata, references, notes, confidence, and redaction. Update `index.md` and `log.md` only when approved changes require it.
7. **Refresh and accept** — refresh QMD for approved wiki pages, then accept the exact source-state delta. Acceptance is always the last step.

`/ob-ingest` does not automatically run graph sync, lint, contradiction correction, or update `HELP.md` — those are separate, deliberate steps. Run `/ob-wiki-contradictions` to find and fix conflicts, and `/wiki-graph-sync` to bring graph view colors in sync, whenever needed.

### Query

1. Read `Level Knowledge/index.md` to identify relevant pages
2. Read those pages — use confidence levels to weight claims appropriately
3. If all relevant pages are `confidence: high`: synthesize and answer from the wiki alone
4. **Follow `## References` wikilinks into `Data/` when any of these are true:**
   - A relevant page is `confidence: medium` or `low` and the question requires certainty
   - The question asks for something more specific than the wiki captures (exact quote, precise date, verbatim wording, specific number)
   - Two wiki pages contradict each other — read both pages' references to resolve
   - The wiki page has an open question the source might answer
   - The user explicitly asks to go deeper or check the source
5. Synthesize an answer; cite with `[[wikilinks]]` to wiki pages (and source files if read)
6. If the deeper dive reveals something the wiki is missing or wrong: update the relevant page

The wiki is the default. Raw sources are the escalation path triggered by low confidence or explicit need — not the starting point. Use QMD for targeted cross-vault retrieval; read the returned passages and surrounding lines, not whole collections, and fall back to broader reading only when retrieval is insufficient.

### Lint (`/ob-wiki-lint`)

`ob-wiki-lint` performs deterministic whole-wiki checks and bounded semantic contradiction review. It is read-only for wiki content:

1. Scan all wiki pages for internal contradictions (e.g., two pages making conflicting claims about the same fact)
2. Identify orphan pages — pages with no incoming `[[wikilinks]]` from other wiki pages
3. Flag missing concepts — entities referenced with `[[wikilinks]]` that have no page yet
4. Find stale claims — pages whose `updated` date is significantly older than related pages that have been revised
5. Flag low-confidence pages that have not been updated after additional sources became available
6. Save results to `Level Playbook/wiki-lint/wiki-lint-YYYY-MM-DD.md`
7. Write a condensed active-issues list to the fixed path `.claude/linter.md`, overwriting any previous run's contents wholesale — `ob-wiki-contradictions` reads this file directly for triage instead of tracking the dated report path

**Performance:** `wiki-lint` caches per-page extraction in `.claude/lint-cache.json`. It does a Full re-read of every page every 7 days (or if the cache is missing); other runs are Incremental — only pages changed since the last run get re-read, batched per domain folder, with everything else reused from cache. Every check still evaluates the full wiki, not just the changed pages — the cache only changes I/O cost, not coverage.

### Contradictions (`/ob-wiki-contradictions`)

`ob-wiki-contradictions` is the approval boundary for contradiction correction — it never auto-fixes:

1. Invoke `/ob-wiki-lint` and wait for the deterministic preflight, bounded semantic review, and finalization.
2. Present the numbered plan exactly as produced. It does not hand off to a separate triage agent — the deterministic lint pipeline produces the prioritized, actionable plan directly.
3. Stop for explicit user selection.
4. Validate the selected fixes before reading or editing pages.
5. Read only the listed pages/evidence and apply only selected corrections. Never modify `## Notes`, raw `Data/`, or unselected pages.
6. Re-verify after applying; leave issues open on failure.

Do not auto-fix or run graph-color sync as part of this workflow.

### Similarity graph (`/ob-similarity-update` and `/ob-similarity-consolidate`)

Two-skill pair for finding connections QMD's semantic search can see but folder structure and explicit wikilinks miss:

- **`ob-similarity-update`** builds and maintains a similarity graph over `Data/` — queries QMD for each file's k-nearest neighbors (wiki-first, then raw data if no confident wiki fit), judges which candidates are genuinely related, and groups related files into clusters. It makes every confident connection it can and flags anything ambiguous (candidate cluster merges, files that may belong to more than one topic, thin single-file clusters) for consolidation. It does not write to `Level Knowledge/` itself.
- **`ob-similarity-consolidate`** reads that graph, resolves everything flagged, and synthesizes/updates `Level Knowledge/` pages from the confirmed clusters using its own confidence model and decay rules. This is the only one of the pair that writes to the wiki.

### Graph view groups (`/wiki-graph-sync`)

`.obsidian/graph.json` stores color group definitions for the Obsidian graph view. The `wiki-graph-sync` skill (backed by the `wiki-graph-sync` agent) manages this file using the canonical color table in **`.config/tagging.md`**. To change a color or add a new group, update that file — the agent will apply it on next sync. Every sync is logged to `Level Knowledge/log.md`. It is a no-op when already aligned.

Routine sync never auto-assigns theme tag colors. Run `sync_wiki_graph.py --audit-tags` (read-only) to report controlled-vocabulary tags used on 3+ pages that lack a color group, then add an approved row to `.config/tagging.md` manually before the next sync applies it.

Run `/wiki-graph-sync` manually whenever wiki structure changes (new domain, moved pages) or graph colors look wrong. It is not invoked automatically by `/ob-ingest`, `ob-wiki-update`, or `ob-wiki-contradictions` — content updates and graph syncing are separate, deliberate steps.

---

## Skills and commands

| Name | Type | What it does |
|---|---|---|
| `ob-ingest` | Skill | The gated entry point for new sources — sorts the inbox, detects hash-based source changes, prepares a bounded ingest packet, invokes `ob-wiki-update`, validates the result, refreshes QMD, and accepts the source-state delta |
| `ob-wiki-update` | Skill | Evidence-reviews a bounded ingestion packet and applies only the approved `Level Knowledge/` page changes supported by its sources — run via `/ob-ingest`, or directly after `prepare_ingest_packet.py` |
| `ob-slack-activity` | Skill | Pulls today's Slack activity and appends it to `Data/Work/Slack Activity/YYYY-MM.md` |
| `ob-zoom` | Command | Finds today's Zoom meetings with AI summaries and exports them to `Data/Meetings/` |
| `ob-guru` | Skill | Fetches Guru cards via MCP and saves formatted summaries to `Data/Resources/Guru/` |
| `ob-insight` | Skill | Analyzes `Level Knowledge/` over a time window to surface trends, gaps, and opportunities — dives into raw sources as needed; saves report to `Level Playbook/insights/` |
| `ob-wiki-lint` | Skill | Runs deterministic whole-wiki checks and bounded semantic contradiction review; read-only for wiki content — writes report to `Level Playbook/wiki-lint/` |
| `ob-wiki-contradictions` | Skill | Runs `ob-wiki-lint`, presents its numbered plan for approval, and applies only user-selected, validated fixes — never auto-fixes or alters `Data/` |
| `ob-similarity-update` | Skill | Builds and maintains a similarity graph over `Data/` using QMD semantic search — clusters related files and flags ambiguous connections for `ob-similarity-consolidate` |
| `ob-similarity-consolidate` | Skill | Resolves everything `ob-similarity-update` flagged and synthesizes/updates `Level Knowledge/` pages from the confirmed clusters — the only one of the pair that writes to the wiki |
| `wiki-graph-sync` | Skill | Syncs `.obsidian/graph.json` color groups against the canonical table in `.config/tagging.md` — run manually after wiki structure changes or when graph colors look wrong |
| `ob-asana` | Skill | Generates a daily Asana briefing — overdue, due today, upcoming, recently completed by you — and saves it to `Data/Work/Asana/` |
| `ob-todo` | Skill | Generates a daily and weekly to-do list — Asana tasks, meeting/wiki action items, carried-over unchecked items, each labeled by priority — and saves both to `Level Playbook/planning/` |
| `ob-sentiment` | Skill | Predicts how a client or stakeholder feels about performance by mining vault sources for sentiment signals; produces a structured report and can save it as a wiki sentiment page |
| `ob-praise-me` | Skill | Looks back over a time window and surfaces wins, accomplishments, and demonstrations of key behaviors/values; saves a report to `Level Playbook/insights/` |
| `ob-diss-me` | Skill | Looks back over a time window and surfaces honest, specific areas for improvement, anchored against core values and key behaviors; saves a report to `Level Playbook/insights/` |
| `ob-inbox` | Agent | Sorts files from `Data/Inbox/` into appropriate `Data/` subfolders; vision-extracts content images |
| `wiki-lint` | Agent | Performs the deterministic whole-wiki checks and bounded semantic review behind the `ob-wiki-lint` skill |
| `wiki-graph-sync` | Agent | Does the actual sync work for the `wiki-graph-sync` skill — adds missing groups, updates drifted colors, removes obsolete groups |

---

## Hooks

A **Stop hook** fires at the end of every session and exports the conversation transcript to `Data/Claude/<session-title>.md`. Two script files handle cross-platform execution:
- `.claude/export-session-to-obsidian.ps1` — Windows
- `.claude/export-session-to-obsidian.sh` — Mac/Linux

---

## MCP servers

- The `obsidian` MCP server is enabled via `.claude/settings.local.json`. It gives Claude direct read/write access to vault files without needing shell commands for basic note operations.
- The `qmd` MCP server (`.mcp.json`, stdio, `qmd mcp`) exposes QMD's hybrid search/retrieval tools directly — search, get, multi-get, and status — for targeted cross-vault retrieval instead of loading whole collections into context. Requires the `qmd` CLI to be installed and on `PATH`. Run `qmd skill install` once to also get QMD's own bundled search-craft skill.

---

## Platform integration

- Claude session exports go to `Data/Claude/` through `.claude/` hooks.
- Skill files contain detailed command contracts; agents are thin orchestrators. Keep the Codex (`.codex/`, `.agents/`) and Claude (`.claude/`) skill/agent behavior aligned, differing only for platform invocation and session paths.

---

## Cross-platform requirement

When creating hooks, skills, or commands for this vault, always support both **Windows and macOS/Linux**:

- Provide `.ps1` and `.sh` script pairs — never a single script that assumes one OS
- Use the `"os"` field in `settings.json` to route hooks to the correct script
- Derive the vault root dynamically from the script's own location — never hardcode paths or usernames:
  - PowerShell: `$vault_root = (Resolve-Path "$PSScriptRoot\..").Path`
  - Bash: `vault_root="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")`
- Use `$env:USERNAME` (Windows) and `$USER` (Mac/Linux) for the display name
- Mac/Linux scripts may use Python 3 for JSON parsing (ships with macOS 12.3+); Windows scripts should use native PowerShell
- Run indexer scripts through `.kb-indexer/.venv`: Windows `& .\.kb-indexer\.venv\Scripts\python.exe ...`; macOS/Linux `./.kb-indexer/.venv/bin/python ...`

Hook entry pattern in `.claude/settings.json`:
```json
{
  "type": "command",
  "command": "powershell -File \".claude\\your-hook.ps1\"",
  "shell": "powershell",
  "os": ["windows"]
},
{
  "type": "command",
  "command": "bash .claude/your-hook.sh",
  "shell": "bash",
  "os": ["mac", "linux"]
}
```

## Hardcoded paths

All skills and commands in this vault derive the vault root dynamically from the current working directory or script location — never a hardcoded path. If you add a new skill or command, follow the same pattern.
