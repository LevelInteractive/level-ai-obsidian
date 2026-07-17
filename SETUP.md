# Set up this vault

This guide prepares a new machine and a new user to run the vault safely. The vault works without cloud embeddings: QMD performs retrieval locally, while Codex or Claude reviews bounded evidence and maintains the wiki.

## What you need

Required:

- **Windows, macOS, or Linux** with PowerShell (Windows) or Bash (macOS/Linux).
- **Python 3.11 or newer.** The indexer uses only the Python standard library; no project `pip` packages are required.
- **Node.js or Bun** to install the QMD command-line tool.
- **QMD CLI and agent skill**. The CLI must be on your `PATH`; install the QMD skill/plugin in each agent you intend to use so it can invoke QMD commands and MCP tools correctly.
- **Codex or Claude Code** to run the project skills. Obsidian is recommended for viewing and editing the vault.

Recommended:

- Git, so configuration and generated-state changes can be reviewed.
- Internet access for the initial QMD installation and its local model downloads.

Ollama and Qdrant are **not required** for the current ingestion workflow. They remain separate experiments under `.kb-indexer/retrieval/`.

## 1. Obtain the vault

Clone the repository or copy the complete vault, including hidden folders:

```text
.agents/   .claude/   .codex/   .config/   .kb-indexer/   .obsidian/
```

Do not copy another user's local credentials or machine-specific settings. Review `.claude/settings.local.json` and any local agent configuration before use; keep secrets outside version control.

Open the vault root in Obsidian after setup. Do not place application configuration inside `Data/` or `Level Knowledge/`.

## 2. Create the local Python runtime

From the vault root:

```powershell
# Windows
py -3 -m venv .kb-indexer\.venv
& .\.kb-indexer\.venv\Scripts\python.exe --version
```

```bash
# macOS/Linux
python3 -m venv .kb-indexer/.venv
./.kb-indexer/.venv/bin/python --version
```

All indexer scripts use this environment. There is no `requirements.txt` to install for the deterministic indexer scripts.

## 3. Install and configure QMD

Install QMD using its current upstream instructions. The common Node installation is:

```bash
npm install -g @tobilu/qmd
qmd --version
```

Create the three collections expected by this vault. Run the matching commands from the vault root once:

```powershell
# Windows PowerShell
qmd collection add "$PWD\Data" --name data
qmd collection add "$PWD\Level Knowledge" --name level-knowledge
qmd collection add "$PWD\Level Playbook" --name level-playbook
qmd embed
qmd status
```

```bash
# macOS/Linux
qmd collection add "$PWD/Data" --name data
qmd collection add "$PWD/Level Knowledge" --name level-knowledge
qmd collection add "$PWD/Level Playbook" --name level-playbook
qmd embed
qmd status
```

These commands build a local QMD index and download any models QMD needs. Models are loaded locally; no Ollama server is required. See the [QMD project documentation](https://github.com/tobi/qmd) for current platform prerequisites and model-storage details.

### Install the QMD agent skill

Installing the `qmd` executable alone is not enough for an agent to use the QMD workflow reliably. Install the QMD skill/plugin for every agent that will operate this vault.

**Claude Code** (the upstream recommended installation):

```bash
claude plugin marketplace add tobi/qmd
claude plugin install qmd@qmd
```

**Codex:** install the QMD skill from the [`tobi/qmd`](https://github.com/tobi/qmd) repository with Codex's skill installer, then confirm it is available in that Codex environment. Keep the project `.mcp.json` QMD server definition enabled as well.

After installation, restart the relevant agent session and verify it can run `qmd status` or call the QMD MCP `status` tool. The CLI, the agent skill, and the MCP connection are complementary: the CLI runs local indexing; the skill teaches the agent how to use it; MCP exposes targeted retrieval tools.

### Optional MCP connection

The vault's `.mcp.json` config starts QMD in stdio mode with:

```json
{ "command": "qmd", "args": ["mcp"] }
```

Ensure your chosen agent loads that project MCP configuration, or add the same server definition to its user/project MCP settings. Confirm with a simple QMD query before relying on it.

For a temporary shared local server during a batch, the ingestion packet can start and stop `qmd mcp --http` automatically. Do not expose it beyond localhost unless you intentionally secure and configure it.

## 4. Initialize vault state

For a newly copied **existing** vault, bootstrap source state once. This records the current corpus without re-ingesting it:

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\scan_source_state.py --bootstrap
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\bootstrap_entity_registry.py
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\build_dependency_graph.py
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\validate_metadata.py .\.kb-indexer\metadata\state\entity-registry.json .\.kb-indexer\metadata\state\dependency-graph.json --check-files
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/scan_source_state.py --bootstrap
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/bootstrap_entity_registry.py
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/build_dependency_graph.py
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/validate_metadata.py ./.kb-indexer/metadata/state/entity-registry.json ./.kb-indexer/metadata/state/dependency-graph.json --check-files
```

If you want the existing raw corpus synthesized into a new, empty wiki, do **not** bootstrap and assume it has been reviewed. Decide on a deliberate full migration plan first.

## 5. Configure the agent and policy

- Read `AGENTS.md` when using Codex, or `.claude/CLAUDE.md` when using Claude. They contain the shared safety and workflow rules.
- Keep `.config/tagging.md` as the sole tag, taxonomy, and graph-color policy. Customize it before creating your own domains or controlled tags.
- Check the session-export hook for your chosen agent: `.Codex/` for Codex and `.claude/` for Claude. It must write transcripts to the corresponding `Data/` folder.
- Optional source integrations such as Slack, Zoom, Guru, or Asana need their own authenticated connector setup. Configure those credentials in the integration/provider, never in wiki pages or committed vault files.

## 6. First safe run

1. Put one or two non-sensitive test files in `Data/Inbox/`.
2. Ask your agent to run `/ob-ingest`.
3. Confirm the result reports: Inbox prepared, a source delta, successful packet status, validated wiki changes (or a justified no-op), dependency-graph refresh when pages changed, refreshed retrieval, and accepted source state.
4. Inspect the changed wiki pages, especially `## References`, confidence, and untouched `## Notes`.
5. Run `/wiki-graph-sync --dry-run` after structural changes; run the normal sync only if the result is correct.
6. Run `/ob-wiki-lint` after a meaningful batch. Use `/ob-wiki-contradictions` only when you are ready to choose which proposed fixes to apply.

## Routine use

- Add raw material to `Data/Inbox/` or the appropriate `Data/` subfolder.
- Run `/ob-ingest`; hash-based state identifies only new or content-changed sources.
- Treat moved/deleted raw files as maintenance work, not new content.
- Run graph sync and lint deliberately; they are intentionally separate from ingestion.

## Troubleshooting

| Problem | Check |
|---|---|
| `qmd` is not found | Reinstall QMD, open a new shell, and verify `qmd --version`. Ensure the Node/Bun global bin directory is on `PATH`. |
| QMD has no results | Run `qmd status`, confirm the three collection names, then run `qmd embed`. |
| Ingestion stops before review | Read the Inbox handoff, source-delta report, and ingest packet. Do not accept the source state manually. |
| Source keeps reappearing | Its content hash changed, prior validation failed, or the delta was not accepted. Inspect the run report rather than deleting state files. |
| Graph colors look stale | Run `/wiki-graph-sync --dry-run`; reload Obsidian's graph view after an actual sync. |

For daily operation, use `HELP.md`. For the detailed indexer commands and generated metadata, see `.kb-indexer/README.md`.
