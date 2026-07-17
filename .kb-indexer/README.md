# KB Indexer

Supporting tooling for this vault's retrieval and metadata layers. The Markdown vault remains authoritative; this folder stores optional retrieval code plus generated metadata that helps scope future ingest and lint work.

## Layout

| Folder | Purpose |
|---|---|
| `retrieval/` | Optional local Qdrant/Ollama retrieval prototype |
| `metadata/` | Generated entity registry, dependency graph, and review reports |
| `scripts/` | Registry, graph, and validation commands |
| `contracts/` | Versioned JSON contracts for generated metadata |
| `fixtures/` | Small validation examples using real vault paths |
| `docs/` | Baseline and operating notes |
| `.venv/` | Local Python runtime; not tracked |

## Metadata workflow

From the vault root on Windows:

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\bootstrap_entity_registry.py
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\build_dependency_graph.py
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\validate_metadata.py `
  .\.kb-indexer\metadata\state\entity-registry.json `
  .\.kb-indexer\metadata\state\dependency-graph.json --check-files
```

On Linux or macOS, use the virtual environment's `bin/python` executable:

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/bootstrap_entity_registry.py
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/build_dependency_graph.py
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/validate_metadata.py \
  ./.kb-indexer/metadata/state/entity-registry.json \
  ./.kb-indexer/metadata/state/dependency-graph.json --check-files
```

Run the final validation command before using generated metadata for routing. See [docs/BASELINE.md](docs/BASELINE.md) and [[knowledge-system-roadmap|Knowledge System Roadmap]] for scope and next steps.

## Incremental graph refresh

Refresh source fingerprints and only the graph contributions of changed wiki pages. New or removed wiki pages, or a changed entity-registry membership, deliberately trigger a safe full deterministic rebuild.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\refresh_dependency_graph.py `
  --source "Data/Meetings/2026-07-06 AMC Signal KickOff Meeting.md"
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/refresh_dependency_graph.py \
  --source "Data/Meetings/2026-07-06 AMC Signal KickOff Meeting.md"
```

The run writes `metadata/reports/current/dependency-graph-refresh.md` and a small state file. It does not edit Markdown or raw Data.

## Impact review

Pass changed `Data/` files explicitly to the read-only resolver. It combines graph evidence, confirmed entity matches, bounded one-hop context, and QMD discovery; it never edits wiki pages.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\resolve_impact.py `
  --source "Data/Meetings/2026-07-06 AMC Signal KickOff Meeting.md"
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/resolve_impact.py \
  --source "Data/Meetings/2026-07-06 AMC Signal KickOff Meeting.md"
```

The selected review set and any overflow queue are written to `metadata/reports/current/impact-review.md` and `metadata/reports/current/impact-review.json`.

### QMD freshness preflight

By default, the preflight embeds all collections after its incremental update, keeping both wiki discovery and raw-source queries fresh. Add `--level-knowledge-only` only when discovery is the sole concern.

Run this before a discovery-assisted ingest or a side-by-side discovery measurement. QMD updates incrementally, so unchanged collections remain cheap; the command records the refresh in `metadata/reports/current/qmd-index-refresh.*`.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\refresh_qmd_index.py
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/refresh_qmd_index.py
```

## Prepare a bounded ingest packet

## Hash-based source discovery

`metadata/state/source-state.json` is the accepted SHA-256 inventory for routable raw sources (`.md` and `.pdf`, excluding assets and Claude session-state files). It replaces date-cursor discovery. A normal scan compares inexpensive size/mtime metadata first and hashes only files whose metadata changed; it still distinguishes a same-size content edit by SHA-256. Use `--verify-all` periodically to hash the whole tracked set as an integrity audit.

Bootstrap once after migration. This records the existing corpus without routing or re-ingesting it:

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\scan_source_state.py --bootstrap
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/scan_source_state.py --bootstrap
```

For each subsequent ingestion cycle, create a non-mutating delta. It lists `new`, `changed`, `moved`, `deleted`, and metadata-only `touched` sources; only new and changed files are routed.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\scan_source_state.py --scan
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\prepare_ingest_packet.py `
  --source-state-report .\.kb-indexer\metadata\source-deltas\<run-id>.json --qmd-http
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/scan_source_state.py --scan
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/prepare_ingest_packet.py \
  --source-state-report ./.kb-indexer/metadata/source-deltas/<run-id>.json --qmd-http
```

Do not accept a delta until the shadow/review/write/validation cycle succeeds. After acceptance, commit that exact report; a stale report is rejected if the accepted manifest has changed in the meantime.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\scan_source_state.py `
  --accept .\.kb-indexer\metadata\source-deltas\<run-id>.json
```

Moved and deleted files deliberately do not enter semantic routing. They require source-reference and dependency-graph maintenance; a timestamp-only touch does not trigger synthesis.

Personal/web clippings are never allowed to route into work domains through semantic discovery. Once a personal domain exists, they may be considered only for pages in that domain. If QMD misses a personal clipping, a bounded lexical overlap check can queue an existing Interests page for evidence review. Daily notes do not use semantic routing; agent transcripts and generic `Data/Work/Analytics/` references are review-only and require corroborating evidence before a wiki update. A scoped Slack delta can only queue a client page when that client is explicitly named in the new section.

For meetings and scoped Slack deltas, the resolver queries each substantive level-three topic section separately. A whole meeting with no usable topic sections is review-only: one broad semantic hit cannot automatically select a wiki page.

When a non-reference operational source describes both a pipeline failure and remediation work (such as validation, isolation, monitoring, retries, or backfill), the report emits a **new-topic review cue**. It suggests a domain/title but never creates a page automatically.

Run the complete deterministic preflight for one explicit raw source. It refreshes QMD, validates generated metadata, resolves the bounded page-review set, and writes an auditable packet under `metadata/shadow-runs/`. It never edits `Data/` or `Level Knowledge/`.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\prepare_ingest_packet.py `
  --source "Data/Meetings/2026-07-09 Data Time.md"
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/prepare_ingest_packet.py \
  --source "Data/Meetings/2026-07-09 Data Time.md"
```

For a dated addition to a monthly aggregate capture, scope the preflight to that exact level-two heading. Historical `## References` elsewhere in the file are suppressed; QMD candidates are queued for review rather than selected automatically.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\prepare_ingest_packet.py `
  --source "Data/Work/Slack Activity/Slack Messages 2026-07.md" `
  --section "July 11, 2026"
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/prepare_ingest_packet.py \
  --source "Data/Work/Slack Activity/Slack Messages 2026-07.md" \
  --section "July 11, 2026"
```

For a multi-source batch, add `--qmd-http`. The runner starts QMD's localhost HTTP daemon, reuses its warm model process for every semantic discovery query, then stops it in cleanup. The existing CLI mode remains the default fallback.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\prepare_ingest_packet.py `
  --qmd-http `
  --source "Data/Knowledge/first-source.md" `
  --source "Data/Work/Analytics/second-source.md"
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/prepare_ingest_packet.py \
  --qmd-http \
  --source "Data/Knowledge/first-source.md" \
  --source "Data/Work/Analytics/second-source.md"
```

The report records whether the daemon was started by the run and whether cleanup succeeded. On Windows, the runner hides the brief console windows created by the background daemon start and stop commands. It binds only to `http://localhost:8181`; use `--qmd-http-endpoint` only when deliberately running QMD on another local port.

## Mock trial suite

The deterministic mock suite exercises resolver behavior without calling QMD or reading/writing vault content. Its `current` mode verifies the current implementation; its `target` mode expresses the safety behavior required before graph-scoped routing can become the default. Both must pass before graph-scoped routing becomes the default.

```powershell
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\run_mock_trials.py --mode current
& .\.kb-indexer\.venv\Scripts\python.exe .\.kb-indexer\scripts\run_mock_trials.py --mode target
```

```bash
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/run_mock_trials.py --mode current
./.kb-indexer/.venv/bin/python ./.kb-indexer/scripts/run_mock_trials.py --mode target
```

Scenarios live in `fixtures/impact-trials/scenarios.json`. The suite currently contains 58 mock-source routing cases plus 14 parser, link-resolution, scoped-delta, recovery, and QMD HTTP lifecycle checks (72 total). Eight reusable, realistic incoming Markdown documents live under `fixtures/incoming-sources/`; they model fresh `Data/Meetings` and `Data/Knowledge` captures without entering the real vault or QMD index. Coverage includes direct evidence, entity and alias policies, source-type controls, topic-section routing, QMD selection/queues/outages/limits, personal-domain boundaries, malformed metadata, duplicate filenames, source relocation, participant-only meeting titles, historical-reference suppression for aggregate-source deltas, new-topic cues, and hidden-window, startup/endpoint/interruption cleanup checks. Add a regression case whenever a live trial exposes a routing miss.
