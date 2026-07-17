"""Build a deterministic, bounded lint packet for Level Knowledge.

This script deliberately performs no semantic adjudication and never changes wiki
content.  It checks mechanics across the entire wiki, then emits the exact pages
and evidence a reviewer may read for contradictions and claim refresh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from build_dependency_graph import (
    DATA_ROOT,
    INDEXER_ROOT,
    VAULT_ROOT,
    WIKI_ROOT,
    file_hash,
    indexed_paths,
    links,
    resolve_link,
    split_references,
    vault_path,
)
from validate_metadata import check_files, load_json, validate_graph, validate_registry

METADATA = INDEXER_ROOT / "metadata"
STATE = METADATA / "state"
RUNS = METADATA / "wiki-lint-runs"
DEFAULT_CACHE = STATE / "wiki-lint-cache.json"
DEFAULT_GRAPH = STATE / "dependency-graph.json"
DEFAULT_REGISTRY = STATE / "entity-registry.json"
DEFAULT_SOURCE_STATE = STATE / "source-state.json"
DEFAULT_QMD = METADATA / "reports" / "current" / "qmd-index-refresh.json"
REQUIRED = ("title", "type", "last_updated", "confidence", "tags")
LINK = re.compile(r"\[\[(.+?)\]\]")
FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
CONFLICT = re.compile(r"^\s*-\s*\[(CONFLICT(?:\s*-\s*OUTDATED NOTE)?)\]\s*(.+)$", re.MULTILINE)
ARCHIVED = re.compile(r"\*\(last seen:\s*(\d{4}-\d{2}-\d{2})\)\*", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frontmatter(text: str) -> dict[str, Any]:
    match = FRONT.match(text)
    if not match:
        return {}
    result: dict[str, Any] = {}
    current_list: str | None = None
    for raw in match.group(1).splitlines():
        if raw.startswith("  - ") and current_list:
            result.setdefault(current_list, []).append(raw[4:].strip())
            continue
        if ":" not in raw or raw.startswith((" ", "\t")):
            current_list = None
            continue
        key, value = raw.split(":", 1)
        current_list = key.strip()
        value = value.strip().strip('"').strip("'")
        result[current_list] = [] if not value else value
    return result


def parsed_page(path: Path, source_exact: dict[str, str], source_stems: dict[str, list[str]],
                wiki_exact: dict[str, str], wiki_stems: dict[str, list[str]]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = frontmatter(text)
    body, reference_links = split_references(text)
    references: list[str] = []
    findings: list[dict[str, Any]] = []
    for target in reference_links:
        resolved, reason = resolve_link(target, source_exact, source_stems)
        if resolved:
            references.append(resolved)
        else:
            findings.append({"category": "REFERENCE", "page": vault_path(path), "target": target,
                             "detail": reason or "missing"})
    for target in links(body):
        resolved, reason = resolve_link(target, wiki_exact, wiki_stems)
        if resolved:
            continue
        source, _ = resolve_link(target, source_exact, source_stems)
        if not source:
            findings.append({"category": "MISSING-PAGE", "page": vault_path(path), "target": target,
                             "detail": reason or "missing"})
    missing = [field for field in REQUIRED if not meta.get(field)]
    if missing:
        findings.append({"category": "FRONTMATTER", "page": vault_path(path),
                         "detail": f"missing: {', '.join(missing)}"})
    try:
        updated = date.fromisoformat(str(meta.get("last_updated", "")))
    except ValueError:
        updated = None
        if meta.get("last_updated"):
            findings.append({"category": "FRONTMATTER", "page": vault_path(path),
                             "detail": "last_updated is not YYYY-MM-DD"})
    conflicts = [{"kind": m.group(1), "text": m.group(2).strip()} for m in CONFLICT.finditer(text)]
    archived = [m.group(1) for m in ARCHIVED.finditer(text)]
    return {
        "path": vault_path(path), "sha256": sha256(path), "frontmatter": meta,
        "updated": updated.isoformat() if updated else None, "references": sorted(set(references)),
        "findings": findings, "conflicts": conflicts, "archived_dates": archived,
    }


def decay_days(page_type: str, confidence: str) -> int | None:
    windows = {
        "client-overview": (45, 90), "client-issues": (45, 90), "client-sentiment": (45, 90),
        "client-trends": (30, 60), "team": (60, 120), "process": (90, 180),
        "tool": (90, 180), "analytics": (90, 180), "organization": (180, 360),
    }
    if page_type == "decision":
        return None
    values = windows.get(page_type, (90, 180))
    return values[0] if confidence == "high" else values[1] if confidence == "medium" else None


def issue(category: str, page: str | None, detail: str, severity: str = "P3-info",
          extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"category": category, "page": page, "detail": detail, "severity": severity}
    if extra:
        payload.update(extra)
    payload["id"] = hashlib.sha256(
        json.dumps({key: payload.get(key) for key in ("category", "page", "detail")}, sort_keys=True).encode()
    ).hexdigest()[:16]
    return payload


def load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 2, "pages": {}, "coverage": {"reviewed": 0, "total": 0}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 2, "pages": {}, "coverage": {"reviewed": 0, "total": 0}, "invalid": True}
    return data if data.get("version") == 2 and isinstance(data.get("pages"), dict) else {
        "version": 2, "pages": {}, "coverage": {"reviewed": 0, "total": 0}, "invalid": True
    }


def graph_maps(graph: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    neighbors: dict[str, set[str]] = defaultdict(set)
    by_source: dict[str, set[str]] = defaultdict(set)
    hashes: dict[str, str] = {}
    for node in graph.get("nodes", []):
        if node.get("sha256"):
            hashes[str(node["id"])] = str(node["sha256"])
    for edge in graph.get("edges", []):
        left, right, kind = str(edge.get("from")), str(edge.get("to")), edge.get("type")
        neighbors[left].add(right)
        neighbors[right].add(left)
        if kind == "references":
            by_source[right].add(left)
    return neighbors, by_source, hashes


def catalog_incoming(wiki_exact: dict[str, str], wiki_stems: dict[str, list[str]]) -> dict[str, int]:
    """Count master-catalog links without turning index.md into a graph node."""
    index = WIKI_ROOT / "index.md"
    incoming: dict[str, int] = defaultdict(int)
    if not index.is_file():
        return incoming
    for target in links(index.read_text(encoding="utf-8", errors="replace")):
        resolved, _ = resolve_link(target, wiki_exact, wiki_stems)
        if resolved:
            incoming[resolved] += 1
    return incoming


def orphan_recommendation(page_id: str, record: dict[str, Any]) -> dict[str, str]:
    """Provide a bounded catalog edit for a genuine, uncatalogued orphan."""
    relative = Path(page_id).relative_to("Level Knowledge")
    section = relative.parts[0].replace("-", " ").title() if len(relative.parts) > 1 else "Knowledge"
    title = str(record.get("frontmatter", {}).get("title") or relative.stem.replace("-", " ").title())
    return {
        "suggested_inbound_page": "Level Knowledge/index.md",
        "suggested_inbound_section": section,
        "suggested_link": f"[[{relative.stem}|{title}]]",
        "suggestion_reason": "not linked from the master catalog or another wiki page",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare deterministic full-wiki lint findings and bounded semantic scope.")
    parser.add_argument("--run-id", default=datetime.now().strftime("wiki-lint-%Y%m%dT%H%M%S"))
    parser.add_argument("--mode", choices=("routine", "backfill", "full", "verify-fixes"), default="routine")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--source-state", type=Path, default=DEFAULT_SOURCE_STATE,
                        help="Accepted source fingerprints; unchanged files are not rehashed.")
    parser.add_argument("--qmd-refresh", type=Path, default=DEFAULT_QMD)
    parser.add_argument("--output-dir", type=Path, default=RUNS)
    parser.add_argument("--rotation-size", type=int, default=6)
    parser.add_argument("--backfill-size", type=int, default=15)
    parser.add_argument("--neighbor-degree-cap", type=int, default=12)
    parser.add_argument("--page", action="append", default=[], help="Explicit wiki page for verify-fixes.")
    args = parser.parse_args()

    wiki_exact, wiki_stems = indexed_paths(WIKI_ROOT)
    source_exact, source_stems = indexed_paths(DATA_ROOT)
    pages = {
        vault_path(path): parsed_page(path, source_exact, source_stems, wiki_exact, wiki_stems)
        for path in sorted(WIKI_ROOT.rglob("*.md")) if path.name not in {"index.md", "log.md"}
    }
    cache = load_cache(args.cache)
    deterministic: list[dict[str, Any]] = []
    for record in pages.values():
        deterministic.extend(issue(item["category"], item["page"], item["detail"], extra={"target": item.get("target")})
                             for item in record["findings"])
        for marker in record["conflicts"]:
            deterministic.append(issue("CONFLICT", record["path"], marker["text"], "P1-critical",
                                       {"kind": marker["kind"]}))

    errors: list[str] = []
    try:
        registry, graph = load_json(args.registry), load_json(args.graph)
        validate_registry(registry, errors)
        validate_graph(graph, errors)
        check_files(registry, graph, VAULT_ROOT, errors)
    except ValueError as exc:
        errors.append(str(exc))
        graph = {"nodes": [], "edges": []}
    if errors:
        deterministic.extend(issue("GRAPH-INVALID", None, error, "P2-warning") for error in errors)
    neighbors, by_source, graph_hashes = graph_maps(graph)
    incoming = defaultdict(int)
    for edge in graph.get("edges", []):
        if edge.get("type") == "links_to" and str(edge.get("to", "")).startswith("Level Knowledge/"):
            incoming[str(edge["to"])] += 1
    for page_id, count in catalog_incoming(wiki_exact, wiki_stems).items():
        incoming[page_id] += count
    for page_id, record in pages.items():
        if incoming[page_id] == 0:
            deterministic.append(issue("ORPHAN", page_id, "no incoming wiki or catalog links", extra=orphan_recommendation(page_id, record)))
        if graph_hashes.get(page_id) and graph_hashes[page_id] != record["sha256"]:
            deterministic.append(issue("GRAPH-STALE", page_id, "page hash differs from dependency graph", "P2-warning"))
        latest_source: date | None = None
        for reference in record["references"]:
            source = VAULT_ROOT / reference
            if not source.is_file():
                continue
            source_day = datetime.fromtimestamp(source.stat().st_mtime).date()
            latest_source = max(latest_source, source_day) if latest_source else source_day
            if record["updated"] and (source_day - date.fromisoformat(record["updated"])).days > 14:
                deterministic.append(issue("STALE", page_id, f"cited source changed {source_day}: {reference}", "P2-warning",
                                           {"source": reference}))
        threshold = decay_days(str(record["frontmatter"].get("type", "")), str(record["frontmatter"].get("confidence", "")))
        if threshold and latest_source and (date.today() - latest_source).days > threshold:
            deterministic.append(issue("CONFIDENCE-DECAY", page_id,
                                       f"confidence exceeds {threshold}-day source-age window", "P2-warning"))
        if record["archived_dates"] and latest_source and any(latest_source > date.fromisoformat(value) for value in record["archived_dates"]):
            deterministic.append(issue("ARCHIVED-REVIVAL", page_id, "newer cited source may revive archived claim"))

    cached_pages = cache.get("pages", {})
    # A missing cache means semantic coverage is unknown, not that every wiki
    # page changed simultaneously.  Backfill/rotation establishes that initial
    # coverage in bounded batches; only pages already known to the cache can be
    # content-changed.
    changed_pages = {
        page_id for page_id, record in pages.items()
        if page_id in cached_pages and cached_pages[page_id].get("sha256") != record["sha256"]
    }
    try:
        source_state = load_json(args.source_state) if args.source_state.is_file() else {"files": {}}
    except ValueError as exc:
        deterministic.append(issue("SOURCE-STATE-INVALID", None, str(exc), "P2-warning"))
        source_state = {"files": {}}
    source_files = source_state.get("files", {}) if isinstance(source_state, dict) else {}
    changed_sources: set[str] = set()
    for node_id, graph_digest in graph_hashes.items():
        if not node_id.startswith("Data/"):
            continue
        source_path = VAULT_ROOT / node_id
        if not source_path.is_file():
            changed_sources.add(node_id)
            continue
        accepted = source_files.get(node_id, {})
        stat = source_path.stat()
        if accepted.get("mtime_ns") == stat.st_mtime_ns and accepted.get("size_bytes") == stat.st_size:
            current_digest = accepted.get("sha256")
        else:
            # Only a source whose cheap filesystem signature changed needs a
            # fresh hash. This keeps routine lint from rereading Data/.
            current_digest = sha256(source_path)
        if current_digest != graph_digest:
            changed_sources.add(node_id)
    seeds = set(changed_pages)
    for source in changed_sources:
        seeds.update(by_source.get(source, set()))
    if args.page:
        seeds.update(args.page)
    reasons: dict[str, set[str]] = defaultdict(set)
    for page_id in seeds:
        if page_id in pages:
            reasons[page_id].add("changed-hash" if page_id in changed_pages else "explicit")
    for source in changed_sources:
        for page_id in by_source.get(source, set()):
            reasons[page_id].add("changed-source-reference")
    for page_id in list(reasons):
        candidates = [item for item in neighbors.get(page_id, set()) if item in pages]
        for neighbor in sorted(candidates)[:args.neighbor_degree_cap]:
            reasons[neighbor].add(f"neighbor:{page_id}")
    unreviewed = [page_id for page_id in sorted(pages) if cache.get("pages", {}).get(page_id, {}).get("semantic_status") != "reviewed"]
    if args.mode == "backfill":
        for page_id in unreviewed[:args.backfill_size]:
            reasons[page_id].add("backfill")
    elif args.mode == "full":
        for page_id in pages:
            reasons[page_id].add("full")
    elif args.mode == "routine":
        for page_id in unreviewed[:args.rotation_size]:
            reasons[page_id].add("rotation-unreviewed")
        if len(reasons) < args.rotation_size:
            ranked = sorted(pages, key=lambda value: cache.get("pages", {}).get(value, {}).get("last_semantic_lint", ""))
            for page_id in ranked:
                if len(reasons) >= args.rotation_size + len(seeds):
                    break
                reasons[page_id].add("rotation")

    qmd_health = "missing"
    if args.qmd_refresh.is_file():
        try:
            qmd_data = json.loads(args.qmd_refresh.read_text(encoding="utf-8"))
            qmd_health = "fresh" if qmd_data.get("embedding_scope") else "unknown"
        except json.JSONDecodeError:
            qmd_health = "invalid"
    if qmd_health != "fresh":
        deterministic.append(issue("QMD-STALE", None, f"QMD refresh receipt is {qmd_health}"))
    scoped = [{"path": page_id, "sha256": pages[page_id]["sha256"], "reasons": sorted(why)}
              for page_id, why in sorted(reasons.items()) if page_id in pages]
    pairs: list[dict[str, str]] = []
    for page in scoped:
        for neighbor in sorted(item for item in neighbors.get(page["path"], set()) if item in reasons and item > page["path"]):
            pairs.append({"left": page["path"], "right": neighbor, "reason": "graph-neighbor"})
    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    packet = {
        "version": 1, "run_id": args.run_id, "mode": args.mode, "generated_at": datetime.now().isoformat(),
        "pages_total": len(pages), "cache_coverage": {"reviewed": len(pages) - len(unreviewed), "total": len(pages)},
        "metadata_health": {"graph": "valid" if not errors else "invalid", "qmd": qmd_health,
                            "cache": "invalid" if cache.get("invalid") else "valid"},
        "pages_to_read": scoped, "evidence_to_read": [{"path": path, "reasons": ["changed-source"]}
                                                       for path in sorted(changed_sources)],
        "candidate_pairs": pairs, "mechanical_findings": deterministic,
        "metrics": {"changed_pages": len(changed_pages), "changed_sources": len(changed_sources),
                    "semantic_pages": len(scoped), "candidate_pairs": len(pairs), "qmd_queries": 0},
    }
    path = run_dir / "scope.json"
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote lint scope to {path} ({len(scoped)}/{len(pages)} semantic pages).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
