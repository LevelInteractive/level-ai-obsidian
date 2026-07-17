"""Prepare a read-only, auditable ingest-routing review for explicit Data sources."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from resolve_impact import INDEXER_ROOT, METADATA_ROOT, WIKI_PREFIX, extract_markdown_section, qmd_executable, resolve_source, source_path
from validate_metadata import check_files, load_json, validate_graph, validate_registry


VAULT_ROOT = INDEXER_ROOT.parent
DEFAULT_OUTPUT_DIR = METADATA_ROOT / "shadow-runs"
_owned_qmd_http_process: subprocess.Popen[str] | None = None


def background_subprocess_options() -> dict[str, Any]:
    """Hide short-lived Windows consoles used for detached QMD lifecycle calls."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def qmd_process_command(executable: str, *arguments: str) -> list[str]:
    """Avoid npm's visible ``qmd.cmd`` wrapper when launching on Windows.

    Global npm shims are batch files. Their final line opens ``cmd.exe`` before
    handing off to Node, which can flash a console even with CREATE_NO_WINDOW.
    Run QMD's CLI entrypoint directly when it is available.
    Other installs and non-Windows systems retain the normal executable path.
    """
    path = Path(executable)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        entrypoint = path.parent / "node_modules" / "@tobilu" / "qmd" / "dist" / "cli" / "qmd.js"
        node = shutil.which("node")
        if node and entrypoint.is_file():
            return [node, str(entrypoint), *arguments]
    return [executable, *arguments]


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def qmd_http_provider(endpoint: str):
    """Return a QMD hybrid-search provider backed by its warm local HTTP service."""
    def provider(query: str, limit: int) -> tuple[list[tuple[str, float]], str | None]:
        try:
            payload = http_json(endpoint.rstrip("/") + "/query", {
                "searches": [{"type": "lex", "query": query}, {"type": "vec", "query": query}],
                "collections": ["level-knowledge"],
                "limit": limit,
                "rerank": False,
            }, timeout=90)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            return [], str(exc)
        results = payload.get("results", [])
        if not isinstance(results, list):
            return [], "QMD HTTP response did not contain a results list"
        matches: list[tuple[str, float]] = []
        for item in results[:limit]:
            file = str(item.get("file", ""))
            if file.startswith("qmd://level-knowledge/"):
                file = WIKI_PREFIX + file.removeprefix("qmd://level-knowledge/")
            elif file.startswith("level-knowledge/"):
                # QMD's REST endpoint returns collection-relative paths,
                # whereas its CLI JSON uses qmd:// URIs.
                file = WIKI_PREFIX + file.removeprefix("level-knowledge/")
            elif not file.startswith(WIKI_PREFIX):
                continue
            matches.append((file, float(item.get("score", 0))))
        return matches, None
    return provider


def start_qmd_http(endpoint: str) -> tuple[bool, str | None]:
    """Start a hidden, owned QMD HTTP process if one is not already running."""
    global _owned_qmd_http_process
    health_url = endpoint.rstrip("/") + "/health"
    try:
        if http_json(health_url).get("status") == "ok":
            return False, None
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass
    executable = qmd_executable()
    if not executable:
        return False, "qmd executable not found"
    try:
        # Do not use QMD's `--daemon`: it creates its own detached Windows
        # child without `windowsHide`, producing the console flash reported by
        # the user. This process is deliberately foreground from QMD's point
        # of view, but hidden and owned by this runner.
        _owned_qmd_http_process = subprocess.Popen(
            qmd_process_command(executable, "mcp", "--http"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            **background_subprocess_options(),
        )
    except OSError as exc:
        return False, str(exc).strip()
    for _attempt in range(20):
        try:
            if http_json(health_url).get("status") == "ok":
                return True, None
        except (urllib.error.URLError, TimeoutError, ValueError):
            if _owned_qmd_http_process.poll() is not None:
                exit_code = _owned_qmd_http_process.returncode
                _owned_qmd_http_process = None
                return False, f"QMD HTTP process exited during startup (code {exit_code})"
            time.sleep(0.25)
    stop_qmd_http()
    return False, "QMD HTTP process did not become healthy"


def stop_qmd_http() -> str | None:
    global _owned_qmd_http_process
    if _owned_qmd_http_process is not None:
        process, _owned_qmd_http_process = _owned_qmd_http_process, None
        try:
            process.terminate()
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        except OSError as exc:
            return str(exc).strip()
        return None
    executable = qmd_executable()
    if not executable:
        return "qmd executable not found during cleanup"
    try:
        subprocess.run(
            qmd_process_command(executable, "mcp", "stop"),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            **background_subprocess_options(),
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return (getattr(exc, "stderr", "") or str(exc)).strip()
    return None


@contextmanager
def temporary_qmd_http(enabled: bool, endpoint: str):
    """Yield a warm-QMD provider and always clean up a daemon this run owns."""
    state: dict[str, Any] = {"enabled": enabled, "endpoint": endpoint, "started_by_run": False, "cleanup_error": None}
    provider = None
    if enabled:
        started_by_run, error = start_qmd_http(endpoint)
        state["started_by_run"] = started_by_run
        state["startup_error"] = error
        if error is None:
            provider = qmd_http_provider(endpoint)
    try:
        yield provider, state
    finally:
        if state["started_by_run"]:
            state["cleanup_error"] = stop_qmd_http()


def refresh_qmd(level_knowledge_only: bool) -> dict[str, Any]:
    """Refresh QMD without changing source or wiki Markdown."""
    executable = qmd_executable()
    if not executable:
        return {"status": "unavailable", "detail": "qmd executable not found"}
    try:
        update = subprocess.run(qmd_process_command(executable, "update"), capture_output=True, text=True, check=True, timeout=300, **background_subprocess_options())
        embed_command = qmd_process_command(executable, "embed", "-c", "level-knowledge") if level_knowledge_only else qmd_process_command(executable, "embed")
        embed = subprocess.run(embed_command, capture_output=True, text=True, check=True, timeout=300, **background_subprocess_options())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "detail": (getattr(exc, "stderr", "") or str(exc)).strip()}
    return {
        "status": "completed",
        "embedding_scope": "level-knowledge" if level_knowledge_only else "all collections",
        "update_output": (update.stdout or update.stderr).strip(),
        "embed_output": (embed.stdout or embed.stderr).strip(),
    }


def validate_metadata_files(registry_path: Path, graph_path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        registry = load_json(registry_path)
        graph = load_json(graph_path)
    except ValueError as exc:
        return None, None, [str(exc)]
    validate_registry(registry, errors)
    validate_graph(graph, errors)
    check_files(registry, graph, VAULT_ROOT, errors)
    return registry, graph, errors


def source_state_packet(path: Path) -> tuple[list[str], dict[str, int]]:
    """Read the routable part of a non-mutating source-state delta report."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("routing_sources"), list) or not isinstance(payload.get("changes"), dict):
        raise ValueError(f"Invalid source-state delta: {path}")
    changes = payload["changes"]
    return [str(source) for source in payload["routing_sources"]], {
        key: len(changes.get(key, [])) if isinstance(changes.get(key, []), list) else 0
        for key in ("new", "changed", "moved", "deleted", "touched")
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Ingest Shadow Run",
        "",
        f"Run: `{report['run_id']}`",
        f"Generated: {report['generated_at']}",
        "",
        "This is a read-only routing report. It does not update `Data/` or `Level Knowledge/`.",
        "",
        "## Preconditions",
        "",
        f"- QMD refresh: {report['qmd_refresh']['status']}",
        f"- Metadata validation: {'passed' if not report['metadata_errors'] else 'failed'}",
        "",
    ]
    if report.get("source_state"):
        state = report["source_state"]
        lines.extend(["## Source-state delta", "", f"- Report: `{state['report']}`", f"- New: {state['counts']['new']}; changed: {state['counts']['changed']}; moved: {state['counts']['moved']}; deleted: {state['counts']['deleted']}; unchanged-content touches: {state['counts']['touched']}", ""])
    if report["metadata_errors"]:
        lines.extend(["### Metadata errors", ""])
        lines.extend(f"- {error}" for error in report["metadata_errors"])
        lines.append("")
    for result in report["sources"]:
        lines.extend([
            f"## {result['source']}",
            "",
            f"- Scope: {result['source_scope']}",
            f"- Source class: {result['source_class']}",
            f"- Discovery policy: {result['discovery_policy']}",
            f"- Direct evidence: {result['direct_evidence']}",
            f"- SHA-256: `{result['sha256']}`",
            f"- Entity matching: {result['entity_matching']}",
            f"- Selected: {len(result['selected'])}",
            f"- Queued: {len(result['queued'])}",
            "",
            "### Selected review set",
            "",
        ])
        lines.extend(
            f"- **{candidate['score']}** `{candidate['page']}` - {'; '.join(candidate['reasons'])}"
            for candidate in result["selected"]
        )
        if not result["selected"]:
            lines.append("- No automatic review candidates.")
        if result["queued"]:
            lines.extend(["", "### Review queue", ""])
            lines.extend(
                f"- **{candidate['score']}** `{candidate['page']}` - {'; '.join(candidate['reasons'])}"
                for candidate in result["queued"]
            )
        if result.get("retrieval_units"):
            lines.extend(["", "### Retrieval packets", ""])
            lines.extend(
                f"- `{unit['label']}` ({unit['characters']} characters; {'section' if unit['topic_scoped'] else 'whole source'})"
                for unit in result["retrieval_units"]
            )
        if result["new_topic_review"]:
            lines.extend(["", "### New-topic review cues", ""])
            lines.extend(
                f"- **{cue['suggested_domain']}/{cue['suggested_title']}** — {'; '.join(cue['reasons'])}"
                for cue in result["new_topic_review"]
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only QMD/graph ingest routing for explicit Data sources.")
    parser.add_argument("--source", action="append", help="Vault-relative Data/ source. Repeat for multiple sources.")
    parser.add_argument("--source-state-report", type=Path, help="Use new/changed sources from a non-mutating source-state delta report instead of explicit --source values.")
    parser.add_argument("--section", help="Exact level-two section heading to route as a source delta; valid only with one --source.")
    parser.add_argument("--run-id", help="Stable report name; defaults to a UTC timestamp.")
    parser.add_argument("--skip-qmd-refresh", action="store_true", help="Do not update/embed QMD; intended only for diagnostics.")
    parser.add_argument("--level-knowledge-only", action="store_true", help="Embed only Level Knowledge during the QMD preflight.")
    parser.add_argument("--qmd-http", action="store_true", help="Start a temporary localhost QMD HTTP daemon and reuse it for all discovery queries.")
    parser.add_argument("--qmd-http-endpoint", default="http://localhost:8181", help="Local QMD HTTP base URL; used with --qmd-http.")
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--qmd-limit", type=int, default=5)
    parser.add_argument("--qmd-min-score", type=float, default=0.5)
    parser.add_argument("--registry", type=Path, default=METADATA_ROOT / "state" / "entity-registry.json")
    parser.add_argument("--graph", type=Path, default=METADATA_ROOT / "state" / "dependency-graph.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    if args.budget < 1 or args.qmd_limit < 0 or not 0 <= args.qmd_min_score <= 1:
        parser.error("--budget must be at least 1 and limits cannot be negative")
    if bool(args.source) == bool(args.source_state_report):
        parser.error("Provide exactly one of --source or --source-state-report")
    source_state = None
    if args.source_state_report:
        try:
            sources, counts = source_state_packet(args.source_state_report)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        source_state = {"report": str(args.source_state_report), "counts": counts}
    else:
        sources = args.source or []
    if args.section and len(sources) != 1:
        parser.error("--section requires exactly one --source")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("shadow-%Y%m%dT%H%M%SZ")
    qmd_refresh = (
        {"status": "skipped", "detail": "no new or changed routable source"}
        if not sources
        else {"status": "skipped", "detail": "requested by --skip-qmd-refresh"}
        if args.skip_qmd_refresh
        else refresh_qmd(args.level_knowledge_only)
    )
    registry, graph, metadata_errors = validate_metadata_files(args.registry, args.graph)
    results: list[dict[str, Any]] = []
    with temporary_qmd_http(args.qmd_http and bool(sources), args.qmd_http_endpoint) as (provider, qmd_http):
        if not metadata_errors and registry is not None and graph is not None:
            for raw_source in sources:
                source, source_id = source_path(raw_source)
                full_content = source.read_text(encoding="utf-8", errors="ignore")
                scoped_content = extract_markdown_section(full_content, args.section) if args.section else None
                results.append(resolve_source(source, source_id, graph, registry, True, args.qmd_limit, args.qmd_min_score, args.budget, 12, qmd_provider=provider, content_override=scoped_content, use_direct_evidence=not bool(args.section), source_scope=f"section: {args.section}" if args.section else None))

    report = {
        "version": 1,
        "mode": "shadow",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_requested": sources,
        "source_state": source_state,
        "qmd_refresh": qmd_refresh,
        "qmd_http": qmd_http,
        "metadata_errors": metadata_errors,
        "sources": results,
        "writes": "metadata reports and the local QMD index only; no Data or Level Knowledge Markdown writes",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{run_id}.json"
    markdown_path = args.output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    print(f"Wrote shadow report to {json_path}")
    return 1 if metadata_errors or qmd_refresh["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
