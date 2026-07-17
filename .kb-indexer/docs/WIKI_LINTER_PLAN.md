# Wiki Linter Architecture

## Status

The bounded lint pipeline is active as of 2026-07-16. It replaces the previous
full semantic reread and `wiki-triage` workflow. The remaining rollout work is
staged semantic coverage backfill and evidence-backed regression fixtures.

## Components

| Component | Responsibility |
|---|---|
| `prepare_wiki_lint.py` | Reads the full wiki for deterministic structural and freshness checks; emits a bounded semantic scope. |
| `wiki-lint` | Reviews only the packet's listed wiki pages and evidence; never edits content. |
| `finalize_wiki_lint.py` | Merges deterministic and semantic findings, maintains the cache, and writes the current issue list and numbered plan. |
| `validate_wiki_fixes.py` | Snapshots selected pages before correction and verifies protected Notes and frontmatter afterward. |
| `/ob-wiki-contradictions` | Approval boundary: presents the plan and applies only user-selected fixes. |

## Operational flow

1. Run `prepare_wiki_lint.py --mode routine --run-id <id>`.
2. It checks every wiki page deterministically: frontmatter, links, references,
   graph integrity, source freshness, confidence decay, explicit conflicts, and
   orphan pages. Links from `Level Knowledge/index.md` count as valid inbound
   catalog links even though the index is intentionally excluded from the
   dependency graph.
3. It uses the dependency graph, source-state fingerprints, changed page hashes,
   and a bounded rotation to create `scope.json`.
4. The reviewer reads only `pages_to_read`, `evidence_to_read`, and
   `candidate_pairs` from that scope and writes `review.json`.
5. The finalizer writes the canonical cache and reports:
   - `metadata/state/wiki-lint-cache.json`
   - `metadata/reports/current/wiki-lint-active.{json,md}`
   - `metadata/reports/current/wiki-lint-plan.{json,md}`
   - `Level Playbook/wiki-lint/wiki-lint-YYYY-MM-DD.md`
6. `/ob-wiki-contradictions` waits for explicit user action selection, snapshots
   the selected pages, applies only approved changes, verifies them, and runs a
   targeted follow-up lint.

## Efficiency policy

- Mechanical checks cover the full wiki but consume no model context.
- Routine semantic review is limited to changed/graph-related pages plus a
  six-page rotation.
- `backfill` reviews 15 unreviewed pages; `full` is an explicit all-page audit.
- Unchanged raw sources reuse accepted source-state hashes and are not reread.
- Routine lint checks the QMD refresh receipt only; it does not query QMD.

## Safety policy

- Detection never edits `Data/`, wiki content, or `## Notes`.
- A reviewer may not expand beyond its scope packet or run a vault-wide search.
- A genuine uncataloged orphan receives a proposed inbound catalog location and
  link. Selecting that action includes both the orphan and the catalog page in
  the fix packet; the proposed link remains subject to review.
- Contradictions require evidence for the same entity and attribute; uncertainty
  remains an issue rather than becoming an invented correction.
- Fixes require explicit selection and post-write validation.

## Remaining work

1. Establish semantic coverage through bounded backfill batches.
2. Add isolated fixtures for confirmed contradictions, stale claims, ambiguous
   history, broken links, and protected Notes validation.
3. Consider a QMD fallback only for high-risk unresolved findings with no direct
   graph or source evidence; keep it opt-in and bounded.
