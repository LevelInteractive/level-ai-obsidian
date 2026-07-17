---
name: ob-wiki-lint
description: >
  Runs deterministic full-wiki checks and bounded semantic contradiction review.
  Use to lint the wiki, check contradictions, stale claims, broken references,
  or frontmatter without a full AI reread.
---

# ob-wiki-lint

Run the deterministic preflight first:

```text
.kb-indexer/scripts/prepare_wiki_lint.py --mode routine --run-id <UTC run id>
```

Read its `scope.json`. It always checks mechanical issues across the whole
wiki, but only lists a bounded semantic review set.

- If `pages_to_read` is non-empty, invoke `wiki-lint` with the scope path.
  The agent writes `review.json` and runs the finalizer.
- If it is empty, run `finalize_wiki_lint.py --scope <scope>` directly.
- Never substitute a blanket wiki scan, direct QMD query, or legacy cache.

Outputs are shared by Claude and Codex:

- active issues: `.kb-indexer/metadata/reports/current/wiki-lint-active.md`
- numbered approval plan: `.kb-indexer/metadata/reports/current/wiki-lint-plan.md`
- cache: `.kb-indexer/metadata/state/wiki-lint-cache.json`
- dated report: `Level Playbook/wiki-lint/wiki-lint-YYYY-MM-DD.md`

Detection is read-only for wiki content. It never changes `Data/` or
`## Notes`.
