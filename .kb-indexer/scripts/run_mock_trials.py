"""Run deterministic impact-resolver regression scenarios without QMD or vault writes."""

from __future__ import annotations

import argparse
import json
import tempfile
import urllib.error
from pathlib import Path
from typing import Any

from build_dependency_graph import resolve_link, split_references
from resolve_impact import extract_markdown_section, is_clipping_reference, resolve_source
import prepare_ingest_packet as shadow

INDEXER_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENARIOS = INDEXER_ROOT / "fixtures" / "impact-trials" / "scenarios.json"
INCOMING_SOURCES_ROOT = INDEXER_ROOT / "fixtures" / "incoming-sources"


def pages(result: dict[str, Any], key: str) -> list[str]:
    return [entry["page"] for entry in result[key]]


def run_scenario(scenario: dict[str, Any], mode: str) -> tuple[bool, str]:
    expected = scenario[f"expected_{mode}"]
    fixture_hits = [(str(page), float(score)) for page, score in scenario.get("qmd_hits", [])]
    fixture_hits_by_query = {
        str(needle).lower(): [(str(page), float(score)) for page, score in hits]
        for needle, hits in scenario.get("qmd_hits_by_query", {}).items()
    }
    fixture_error = scenario.get("qmd_error")
    page_contents = {str(page): str(content) for page, content in scenario.get("page_contents", {}).items()}

    def mock_qmd(query: str, _limit: int) -> tuple[list[tuple[str, float]], str | None]:
        normalized_query = query.lower()
        for needle, hits in fixture_hits_by_query.items():
            if needle in normalized_query:
                return hits, fixture_error
        return fixture_hits, fixture_error

    def mock_page_content(page: str) -> str | None:
        return page_contents.get(page)

    fixture_source = scenario.get("fixture_source")
    fixture_content = (INCOMING_SOURCES_ROOT / str(fixture_source)).read_text(encoding="utf-8") if fixture_source else str(scenario["content"])
    source_section = scenario.get("source_section")
    if source_section:
        fixture_content = extract_markdown_section(fixture_content, str(source_section))
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.md"
        source.write_text(fixture_content, encoding="utf-8")
        result = resolve_source(
            source=source,
            source_id=scenario["source"],
            graph=scenario["graph"],
            registry=scenario["registry"],
            use_qmd=scenario.get("use_qmd", True),
            qmd_limit=5,
            qmd_min_score=0.6,
            budget=10,
            neighbor_degree_cap=12,
            qmd_provider=mock_qmd,
            page_content_provider=mock_page_content,
            use_direct_evidence=not bool(source_section),
            source_scope=f"section: {source_section}" if source_section else None,
        )

    actual = {"selected": pages(result, "selected"), "queued": pages(result, "queued")}
    if "qmd_error" in expected:
        actual["qmd_error"] = result["qmd_error"]
    if "new_topic_review" in expected:
        actual["new_topic_review"] = [entry["suggested_title"] for entry in result["new_topic_review"]]
    passed = actual == expected
    detail = "PASS" if passed else f"FAIL expected {expected}, got {actual}"
    return passed, f"{scenario['id']}: {detail}"


def bracketed_filename_reference_check() -> tuple[bool, str]:
    filename = "2026-07-08 [LVL-19] - Analytics & Looker Studio Office Hours"
    _body, references = split_references(f"# Page\n\n## References\n\n- [[{filename}]]\n")
    passed = references == [filename]
    detail = "PASS" if passed else f"FAIL expected {[filename]}, got {references}"
    return passed, f"bracketed-filename-reference: {detail}"


def structural_checks() -> list[tuple[bool, str]]:
    """Exercise graph and source-boundary behavior that is below resolver routing."""
    checks: list[tuple[bool, str]] = []

    background_options = shadow.background_subprocess_options()
    if shadow.os.name == "nt":
        passed = background_options.get("creationflags") == shadow.subprocess.CREATE_NO_WINDOW and background_options.get("startupinfo") is not None
    else:
        passed = background_options == {}
    checks.append((passed, "qmd-http-background-window-hidden: " + ("PASS" if passed else f"FAIL got {background_options}")))

    # QMD HTTP failures must fail closed: no discovery candidates are emitted.
    original_http_json = shadow.http_json
    try:
        shadow.http_json = lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("unreachable"))
        hits, error = shadow.qmd_http_provider("http://localhost:8181")("test", 5)
        passed = hits == [] and error and "unreachable" in error
        checks.append((bool(passed), "qmd-http-unavailable-endpoint: " + ("PASS" if passed else f"FAIL got {(hits, error)}")))
    finally:
        shadow.http_json = original_http_json

    # Startup without an executable must report an error rather than attempt a
    # partial CLI fallback that could hide the HTTP lifecycle failure.
    original_qmd_executable = shadow.qmd_executable
    try:
        shadow.qmd_executable = lambda: None
        started, error = shadow.start_qmd_http("http://localhost:8181")
        passed = not started and error == "qmd executable not found"
        checks.append((passed, "qmd-http-startup-unavailable: " + ("PASS" if passed else f"FAIL got {(started, error)}")))
    finally:
        shadow.qmd_executable = original_qmd_executable

    # Cleanup is guaranteed even if processing is interrupted after startup.
    original_start, original_stop = shadow.start_qmd_http, shadow.stop_qmd_http
    calls: list[str] = []
    try:
        shadow.start_qmd_http = lambda _endpoint: (True, None)
        shadow.stop_qmd_http = lambda: calls.append("stop") or None
        try:
            with shadow.temporary_qmd_http(True, "http://localhost:8181"):
                raise RuntimeError("interrupted")
        except RuntimeError:
            pass
        passed = calls == ["stop"]
        checks.append((passed, "qmd-http-interruption-cleanup: " + ("PASS" if passed else f"FAIL got {calls}")))
    finally:
        shadow.start_qmd_http, shadow.stop_qmd_http = original_start, original_stop

    # A pre-existing daemon belongs to the caller and must not be stopped.
    calls = []
    try:
        shadow.start_qmd_http = lambda _endpoint: (False, None)
        shadow.stop_qmd_http = lambda: calls.append("stop") or None
        with shadow.temporary_qmd_http(True, "http://localhost:8181"):
            pass
        passed = calls == []
        checks.append((passed, "qmd-http-existing-daemon-preserved: " + ("PASS" if passed else f"FAIL got {calls}")))
    finally:
        shadow.start_qmd_http, shadow.stop_qmd_http = original_start, original_stop

    resolved, reason = resolve_link(
        "2026-07-08 Office Hours",
        {},
        {"2026-07-08 office hours": ["Data/Meetings/2026-07-08 Office Hours.md", "Data/Knowledge/2026-07-08 Office Hours.md"]},
    )
    checks.append((resolved is None and reason == "ambiguous", "duplicate-basename-ambiguous: " + ("PASS" if resolved is None and reason == "ambiguous" else f"FAIL got {(resolved, reason)}")))

    exact = {"Data/Meetings/2026-07-08 Office Hours": "Data/Meetings/2026-07-08 Office Hours.md"}
    resolved, reason = resolve_link("Data/Meetings/2026-07-08 Office Hours", exact, {})
    checks.append((resolved == exact["Data/Meetings/2026-07-08 Office Hours"] and reason is None, "explicit-path-resolves-duplicate: " + ("PASS" if resolved == exact["Data/Meetings/2026-07-08 Office Hours"] and reason is None else f"FAIL got {(resolved, reason)}")))

    resolved, reason = resolve_link("Data/20 - Meetings/2026-07-08 Office Hours", exact, {})
    checks.append((resolved is None and reason == "missing", "relocated-source-old-path-missing: " + ("PASS" if resolved is None and reason == "missing" else f"FAIL got {(resolved, reason)}")))

    body, references = split_references("# Page\n\n[[source-in-body]]\n\n## References\n\n- [[source-in-references]]\n")
    passed = "[[source-in-body]]" in body and references == ["source-in-references"]
    checks.append((passed, "body-link-is-not-evidence-reference: " + ("PASS" if passed else f"FAIL got {(body, references)}")))

    passed = is_clipping_reference("---\ntags:\n  - CLIPPINGS\n---\n# Saved article\n")
    checks.append((passed, "clipping-tag-case-insensitive: " + ("PASS" if passed else "FAIL tag was not recognized")))

    passed = not is_clipping_reference("---\ntags:\n  - clippings\n# Missing closing delimiter\n")
    checks.append((passed, "malformed-frontmatter-safe: " + ("PASS" if passed else "FAIL malformed frontmatter was treated as clipping")))

    aggregate = "# July Slack\n\n## July 10, 2026\n\nLegacy note.\n\n## July 11, 2026\n\nNew coding-tool evaluation.\n"
    passed = extract_markdown_section(aggregate, "July 11, 2026") == "## July 11, 2026\n\nNew coding-tool evaluation.\n"
    checks.append((passed, "aggregate-source-section-extraction: " + ("PASS" if passed else "FAIL extracted the wrong Slack delta")))

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.md"
        source.write_text("# QMD recovery\nQMD uses collections and embeddings.", encoding="utf-8")
        graph = {"nodes": [{"id": "Level Knowledge/tools/qmd.md", "kind": "wiki_page"}], "edges": []}
        first = resolve_source(source, "Data/Knowledge/qmd-recovery.md", graph, {"entities": []}, True, 5, 0.6, 10, 12, qmd_provider=lambda _query, _limit: ([], "mock temporary outage"))
        second = resolve_source(source, "Data/Knowledge/qmd-recovery.md", graph, {"entities": []}, True, 5, 0.6, 10, 12, qmd_provider=lambda _query, _limit: ([('Level Knowledge/tools/qmd.md', 0.9)], None), page_content_provider=lambda _page: "# QMD\nCollections and embeddings support retrieval.")
    passed = first["qmd_error"] == "mock temporary outage" and not first["selected"] and [entry["page"] for entry in second["selected"]] == ["Level Knowledge/tools/qmd.md"]
    checks.append((passed, "qmd-failure-then-recovery: " + ("PASS" if passed else "FAIL recovery did not restore normal routing")))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated, deterministic impact-resolver trials.")
    parser.add_argument("--mode", choices=("current", "target"), default="current", help="Compare with current behavior or intended safety policy.")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    args = parser.parse_args()
    suite = json.loads(args.scenarios.read_text(encoding="utf-8"))
    outcomes = [run_scenario(scenario, args.mode) for scenario in suite["scenarios"]]
    outcomes.append(bracketed_filename_reference_check())
    outcomes.extend(structural_checks())
    for _passed, line in outcomes:
        print(line)
    failures = sum(not passed for passed, _line in outcomes)
    print(f"{len(outcomes) - failures}/{len(outcomes)} scenarios passed in {args.mode} mode.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
