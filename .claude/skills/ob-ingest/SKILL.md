---
name: ob-ingest
description: >
  Runs the complete safe ingestion cycle for this vault: sort Data/Inbox,
  detect hash-based source changes, prepare a bounded QMD/graph packet, update
  approved Level Knowledge pages, validate the result, refresh retrieval, and
  accept source state. Use when the user asks to ingest, process, or run the
  full cycle for new vault sources.
---

# ob-ingest

Coordinate the vault ingestion cycle. Treat each stage as a gate: never accept
a source-state delta when a preceding stage failed, was incomplete, or left a
source requiring review.

## Runtime

Run indexer scripts from the vault root with the local runtime:

- Windows: `& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\<script>.py`
- macOS/Linux: `./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/<script>.py`

Generate one UTC `run-id` and use it for the source delta and ingest packet.
Keep the resulting JSON and Markdown reports as the audit record.

## Workflow

1. Invoke the `ob-inbox` subagent and wait for its structured handoff.
   Use Claude's Agent tool with `subagent_type: "ob-inbox"`.
   - If it reports `partial` or any blocked file, stop and present the
     blocker. Do not scan a mixed inbox state.
   - If it reports `empty`, continue: sources may already be in `Data/`.

2. Run `scan_source_state.py --scan --run-id <run-id>`. Read its delta.
   - If there are no new or changed routing sources and no moved/deleted files,
     accept that exact delta; report that there was no synthesis work.
   - If moved or deleted files exist, stop for reference and dependency-graph
     maintenance. They must not be semantically re-ingested as new material.

3. Run `prepare_ingest_packet.py --source-state-report <delta.json>
   --run-id <run-id> --qmd-http`.
   - Require a successful command, no metadata errors, and successful QMD
     refresh before proceeding.
   - Read the packet and its explicit source list, selected pages, queue, and
     new-topic cues. Never expand discovery to a blanket `Data/` scan.

4. Invoke `/ob-wiki-update` with the packet paths. It reviews only those
   sources and candidates, then writes supported `Level Knowledge/` page
   changes. If review leaves an unresolved blocker, stop without acceptance.

5. Validate the accepted wiki changes before source-state acceptance:
   - inspect each changed page for valid frontmatter, protected `## Notes`,
     accurate `## References`, consistent confidence metadata/footnote, and
     credential redaction;
   - run `validate_metadata.py .kb-indexer/metadata/state/entity-registry.json
     .kb-indexer/metadata/state/dependency-graph.json --check-files`;
   - update `Level Knowledge/index.md` and `Level Knowledge/log.md` only
     when the approved page changes require it.
   Stop on any validation failure; leave the delta unaccepted.

6. Refresh retrieval for the approved wiki changes:
   `refresh_qmd_index.py --level-knowledge-only`. Stop on failure.

7. Accept the exact delta with `scan_source_state.py --accept <delta.json>`.
   Acceptance is the final mutation. Do not accept a stale delta; rescan and
   restart if its base state no longer matches.

## Completion report

Return:

```text
Ingest run: <run-id> — accepted | stopped | no-op
Inbox: empty | N files prepared
Source delta: new / changed / moved / deleted / touched
Packet: path; QMD status
Wiki: pages changed/created; rejected or queued candidates
Validation: passed | failed
QMD post-write refresh: passed | failed | not needed
Source state: accepted | unchanged
Follow-up: ...
```

Do not update `HELP.md`, run graph-color sync, or run contradiction lint
automatically. They remain separate deliberate operations.
