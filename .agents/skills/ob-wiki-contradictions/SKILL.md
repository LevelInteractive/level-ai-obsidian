---
name: ob-wiki-contradictions
description: >
  Detects wiki contradictions through the deterministic bounded lint pipeline,
  presents a numbered approval plan, and applies only user-selected fixes.
  Use when asked to check, resolve, or correct wiki contradictions.
---

# ob-wiki-contradictions

This is the approval boundary for contradiction correction.

1. Invoke `/ob-wiki-lint` and wait for its deterministic preflight, bounded
   semantic review, and finalizer to complete.
2. Read `.kb-indexer/metadata/reports/current/wiki-lint-plan.md` and present
   its numbered actions without adding an AI triage pass.
3. Stop for explicit user selection. Accept individual numbers, comma lists,
   ranges, `all P1`, or `all`.
4. Before writing, run:

   ```text
   validate_wiki_fixes.py --plan <current plan json> --select <numbers> --packet <run>/fix-packet.json
   ```

   Read only the selected packet pages, including a proposed inbound catalog page
   when an orphan action supplies one, and evidence named by those actions.
5. Apply only selected corrections. For a genuine orphan, add the packet's
   proposed link only after confirming its catalog section is appropriate. Never
   edit `## Notes`, invent facts, or change pages outside the packet.
6. Run the same validator with `--verify`. If it fails, report the failure
   and leave active issues open. If it passes, rerun the bounded lint scope for
   the changed pages to refresh claims and confirm the selected issue IDs.

Do not auto-fix, run graph-color sync, or alter raw `Data/`.
