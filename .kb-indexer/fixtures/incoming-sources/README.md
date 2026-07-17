# Mock Incoming Sources

These Markdown files model fresh documents that would normally arrive under
`Data/`. They are deliberately stored under `.kb-indexer/fixtures/` so test
runs never alter the real vault, advance an ingest cursor, or contaminate QMD.

`run_mock_trials.py` reads the selected files and supplies their declared mock
`Data/...` paths to the resolver. Add a matching scenario in
`fixtures/impact-trials/scenarios.json` for every new fixture.
