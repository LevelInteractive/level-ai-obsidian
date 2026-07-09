---
name: ob-wiki-lint
description: >
  Lint the Level Knowledge wiki for contradictions, stale claims, orphan pages,
  and missing frontmatter. Writes a report to Level Playbook/wiki-lint/ and a
  condensed active-issues list to .claude/linter.md.
  Use when the user runs /ob-wiki-lint, asks to "lint the wiki", "check for contradictions",
  "find stale pages", or "audit the knowledge base".
---

# ob-wiki-lint

Invoke the `wiki-lint` subagent to audit every page in `Level Knowledge/` and produce an
actionable report in `Level Playbook/wiki-lint/wiki-lint-YYYY-MM-DD.md`, plus a condensed
active-issues list at the fixed path `.claude/linter.md`. The agent overwrites `.claude/linter.md`
wholesale on every run — it never carries stale issues over from a prior run. `ob-wiki-contradictions`
reads `.claude/linter.md` directly for triage instead of tracking the dated report path.

**Performance:** the agent maintains a cache at `.claude/lint-cache.json`. Every 7th day (or if the
cache is missing/corrupt) it runs a Full audit — re-reads and re-extracts every page. In between, it
runs Incrementally: only pages whose `last_updated` changed since the last run get re-read; everything
else reuses cached extraction. Reads are also batched per domain folder rather than one page at a time.
Contradiction/staleness checks always evaluate the full 72-page picture regardless of mode — only the
I/O cost changes, not the coverage. Structural checks (orphans, missing concept pages) query the
`obsidian` CLI's vault-wide link index directly instead of building the graph by hand — always complete,
independent of lint mode, and dramatically faster than a from-scratch scan (requires the Obsidian desktop
app to be running).

## How to invoke

Use the Agent tool with `subagent_type: "wiki-lint"`. Pass the vault root and today's date
in the prompt so the agent has full context:

```
Run the wiki-lint audit.
Vault root: <vault root from current working directory>
Today's date: <today's date>
```

The agent handles all steps autonomously: listing pages, extracting claims, detecting
contradictions, checking staleness, finding structural issues, and writing the report.

## What it checks

| Check | Method |
|---|---|
| Factual contradictions | Cross-page claim comparison |
| Status tag conflicts | Cross-page tag comparison |
| Stale vs. source files | PowerShell LastWriteTime vs. page last_updated |
| Stale vs. related pages | Date comparison from frontmatter |
| Orphan pages | `obsidian orphans` (CLI), filtered to `Level Knowledge/` |
| Missing concept pages | `obsidian unresolved` (CLI), filtered to `Level Knowledge/` sources |
| Missing frontmatter fields | Per-page field check |
