---
name: wiki-graph-sync
description: >
  Deterministically syncs Obsidian graph colors from .config/tagging.md and
  top-level Level Knowledge domains. Use for graph colors, graph groups, or a
  graph color audit after wiki structure changes.
---

# wiki-graph-sync

Run the token-free command from the vault root:

```text
.kb-indexer/.venv/Scripts/python.exe .kb-indexer/scripts/sync_wiki_graph.py
```

On macOS/Linux, use `python3 .kb-indexer/scripts/sync_wiki_graph.py`.

- Use `--dry-run` for a no-write diff.
- Use `--audit-tags` only when the user explicitly asks to audit uncolored tags.
  It reports candidates and never changes `.config/tagging.md` or `graph.json`.
- A normal no-op run writes nothing and adds no log row.
- A new top-level domain is assigned the next configured domain-palette color
  and registered in `.config/tagging.md` before graph.json is updated.

The script preserves every graph setting except `colorGroups`. If it changes
the graph, tell the user to reload the graph view before changing graph settings.
