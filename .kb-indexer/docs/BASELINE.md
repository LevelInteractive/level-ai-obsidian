# Knowledge Metadata Baseline

Recorded: 2026-07-11

## Existing retrieval systems

- `.mcp.json` declares a `qmd` stdio MCP server (`qmd mcp`). QMD 2.5.3 is installed and healthy: its local index holds 335 files / 1,483 vectors, with `data` (188 files), `level-knowledge` (121), and `level-playbook` (26) collections. One document was pending embedding at the check time. The sandbox shell cannot access the npm install location directly, but the normal user environment can run QMD.
- `.kb-indexer/` already contains a local Qdrant/Ollama retrieval implementation. It indexes changed files by SHA-256 into the `nicks_nook` collection, uses `nomic-embed-text`, and provides semantic plus optional BM25/reranked search.
- This milestone does not change either retrieval implementation. The entity registry and dependency graph are retrieval-engine-neutral metadata that both can consume later.

## Metadata contract

The following files are the stable Phase 0 contract:

- `contracts/entity-registry.schema.json`
- `contracts/dependency-graph.schema.json`
- `scripts/validate_metadata.py`

They use vault-relative POSIX paths, SHA-256 content fingerprints, and typed edges. Markdown and immutable Data files remain authoritative.

## Validation

From the vault root on Windows:

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\validate_metadata.py `
  .kb-indexer\fixtures\entity-registry.valid.json `
  .kb-indexer\fixtures\dependency-graph.valid.json
```

On macOS/Linux, use the workspace Python (for example `python3 .kb-indexer/scripts/validate_metadata.py …`) after creating the equivalent virtual environment.

Add `--check-files` when validating real metadata. It verifies that source and wiki-page paths resolve under the vault root; the included fixtures now use real, read-only vault paths too.

## Follow-up

Document the QMD update/embedding cadence before Phase 2 uses it as the default candidate retriever. The metadata work itself is not blocked: direct evidence, aliases, and wikilinks are deterministic routing signals.
