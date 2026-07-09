---
name: wiki-graph-sync
description: >
  Syncs .obsidian/graph.json color groups against the canonical color table in .claude/tagging.md
  and the current Level Knowledge/ domain structure. Use when the user runs /wiki-graph-sync, asks
  to "sync the graph colors", "fix graph view colors", "update graph groups", or after wiki
  structure changes (new domain, moved pages) that might leave graph.json out of date.
---

# wiki-graph-sync

Thin orchestration skill — the actual sync logic lives in the `wiki-graph-sync` agent.

Not invoked automatically by `ob-wiki-update` or `ob-wiki-contradictions` — those skills focus on
content only. Run this skill directly whenever graph colors need to be brought in sync.

## Step 1 — Run the wiki-graph-sync agent

Use the Agent tool with `subagent_type: "wiki-graph-sync"`. Pass vault root and today's date:

```
Sync graph view color groups.
Vault root: <vault root — the folder containing CLAUDE.md>
Today's date: <today's date>
```

Wait for it to complete.

## Step 2 — Report to the user

Summarize what changed: groups added, colors updated, groups removed. The agent logs the sync to
`Level Knowledge/log.md` itself — no additional logging needed here.
