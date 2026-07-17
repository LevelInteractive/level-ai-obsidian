"""Incrementally refresh dependency-graph nodes and edges from changed vault files."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from build_dependency_graph import (
    DATA_ROOT,
    VAULT_ROOT,
    WIKI_ROOT,
    build_graph,
    entity_page_index,
    file_hash,
    indexed_paths,
    links,
    resolve_link,
    split_references,
    vault_path,
)

METADATA_ROOT = VAULT_ROOT / ".kb-indexer" / "metadata"


def sha256(path: Path) -> str:
    return file_hash(path)


def safe_source(value: str) -> tuple[Path, str]:
    path = (VAULT_ROOT / value).resolve()
    if not path.is_relative_to(DATA_ROOT.resolve()) or not path.is_file():
        raise ValueError(f"--source must identify an existing Data/ file: {value}")
    return path, vault_path(path)


def current_wiki_files() -> dict[str, Path]:
    return {
        vault_path(path): path
        for path in WIKI_ROOT.rglob("*.md")
        if path.name not in {"index.md", "log.md"}
    }


def page_contributions(
    page: Path,
    wiki_exact: dict[str, str],
    wiki_stems: dict[str, list[str]],
    source_exact: dict[str, str],
    source_stems: dict[str, list[str]],
    entity_pages: dict[str, str],
) -> tuple[set[tuple[str, str, str, str]], dict[str, dict[str, str]], dict[str, int]]:
    page_id = vault_path(page)
    content = page.read_text(encoding="utf-8")
    body, reference_targets = split_references(content)
    edges: set[tuple[str, str, str, str]] = set()
    sources: dict[str, dict[str, str]] = {}
    observations = {"unresolved_references": 0, "unresolved_wikilinks": 0, "references_to_wiki": 0, "body_source_links": 0}

    own_entity = entity_pages.get(page_id)
    if own_entity:
        edges.add((page_id, own_entity, "mentions", page_id))

    for target in reference_targets:
        resolved, _ = resolve_link(target, source_exact, source_stems)
        if resolved:
            source_file = VAULT_ROOT / resolved
            sources[resolved] = {"id": resolved, "kind": "source", "sha256": sha256(source_file)}
            edges.add((page_id, resolved, "references", page_id))
            continue
        wiki_target, _ = resolve_link(target, wiki_exact, wiki_stems)
        if wiki_target:
            observations["references_to_wiki"] += 1
            edges.add((page_id, wiki_target, "links_to", page_id))
            entity_id = entity_pages.get(wiki_target)
            if entity_id:
                edges.add((page_id, entity_id, "mentions", page_id))
        else:
            observations["unresolved_references"] += 1

    for target in links(body):
        wiki_target, _ = resolve_link(target, wiki_exact, wiki_stems)
        if wiki_target:
            edges.add((page_id, wiki_target, "links_to", page_id))
            entity_id = entity_pages.get(wiki_target)
            if entity_id:
                edges.add((page_id, entity_id, "mentions", page_id))
            continue
        source_target, _ = resolve_link(target, source_exact, source_stems)
        if source_target:
            source_file = VAULT_ROOT / source_target
            sources[source_target] = {"id": source_target, "kind": "source", "sha256": sha256(source_file)}
            edges.add((page_id, source_target, "references", page_id))
            observations["body_source_links"] += 1
        else:
            observations["unresolved_wikilinks"] += 1
    return edges, sources, observations


def existing_edges(graph: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {
        (edge["from"], edge["to"], edge["type"], edge["evidence"][0])
        for edge in graph["edges"]
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Dependency Graph Refresh Report", "", f"Generated: {summary['generated_at']}", "",
        f"**Mode:** {summary['mode']}", f"**Reason:** {summary['reason']}", "",
        "## Changes detected", "",
        f"- Wiki pages changed: {len(summary['changed_wiki_pages'])}",
        f"- Wiki pages added: {len(summary['added_wiki_pages'])}",
        f"- Wiki pages removed: {len(summary['removed_wiki_pages'])}",
        f"- Graph-backed source hashes changed: {len(summary['changed_sources'])}",
        f"- Explicit source inputs: {len(summary['explicit_sources'])}", "",
        "## Result", "",
        f"- Nodes: {summary['nodes']}", f"- Edges: {summary['edges']}",
    ]
    if summary["changed_wiki_pages"]:
        lines.extend(["", "## Recomputed pages", "", *[f"- `{page}`" for page in summary["changed_wiki_pages"]]])
    if summary["explicit_sources"]:
        lines.extend(["", "## Explicit sources", "", *[f"- `{path}`" for path in summary["explicit_sources"]]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Incrementally refresh the deterministic dependency graph.")
    parser.add_argument("--source", action="append", default=[], help="Explicit changed Data/ source to hash/add. Repeat as needed.")
    parser.add_argument("--full", action="store_true", help="Force a deterministic full graph rebuild.")
    parser.add_argument("--registry", type=Path, default=METADATA_ROOT / "state" / "entity-registry.json")
    parser.add_argument("--graph", type=Path, default=METADATA_ROOT / "state" / "dependency-graph.json")
    parser.add_argument("--state", type=Path, default=METADATA_ROOT / "state" / "dependency-graph-state.json")
    parser.add_argument("--output", type=Path, default=METADATA_ROOT / "state" / "dependency-graph.json")
    parser.add_argument("--report", type=Path, default=METADATA_ROOT / "reports" / "current" / "dependency-graph-refresh.md")
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    prior_nodes = {node["id"]: node for node in graph["nodes"]}
    prior_wiki = {node_id: node for node_id, node in prior_nodes.items() if node["kind"] == "wiki_page"}
    prior_sources = {node_id: node for node_id, node in prior_nodes.items() if node["kind"] == "source"}
    prior_entities = {node_id for node_id, node in prior_nodes.items() if node["kind"] == "entity"}
    current_files = current_wiki_files()
    current_entities = {entity["id"] for entity in registry["entities"]}
    added = sorted(set(current_files) - set(prior_wiki))
    removed = sorted(set(prior_wiki) - set(current_files))
    changed = sorted(page_id for page_id, path in current_files.items() if page_id in prior_wiki and sha256(path) != prior_wiki[page_id].get("sha256"))
    changed_sources = []
    for source_id, node in prior_sources.items():
        path = VAULT_ROOT / source_id
        if path.is_file() and sha256(path) != node.get("sha256"):
            changed_sources.append(source_id)
    explicit_sources = [safe_source(value) for value in args.source]

    registry_changed = current_entities != prior_entities
    full_reason = None
    if args.full:
        full_reason = "forced by --full"
    elif added or removed:
        full_reason = "wiki page added or removed; unchanged pages may gain or lose resolvable link targets"
    elif registry_changed:
        full_reason = "entity registry membership changed"

    if full_reason:
        refreshed, _ = build_graph(registry)
        mode, reason = "full", full_reason
    else:
        wiki_exact, wiki_stems = indexed_paths(WIKI_ROOT)
        source_exact, source_stems = indexed_paths(DATA_ROOT)
        entity_pages = entity_page_index(registry)
        changed_set = set(changed)
        nodes: dict[str, dict[str, str]] = {entity["id"]: {"id": entity["id"], "kind": "entity"} for entity in registry["entities"]}
        for page_id, path in current_files.items():
            nodes[page_id] = {"id": page_id, "kind": "wiki_page", "sha256": sha256(path)}
        for source_id, node in prior_sources.items():
            path = VAULT_ROOT / source_id
            if path.is_file():
                nodes[source_id] = {"id": source_id, "kind": "source", "sha256": sha256(path)}
        for path, source_id in explicit_sources:
            nodes[source_id] = {"id": source_id, "kind": "source", "sha256": sha256(path)}
        edges = {
            edge for edge in existing_edges(graph)
            if edge[0] not in changed_set and edge[0] not in set(removed) and edge[1] not in set(removed) and edge[1] in nodes
        }
        for page_id in changed:
            contributions, sources, _ = page_contributions(current_files[page_id], wiki_exact, wiki_stems, source_exact, source_stems, entity_pages)
            edges.update(contributions)
            nodes.update(sources)
        refreshed = {
            "version": 1,
            "generated_at": date.today().isoformat(),
            "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
            "edges": [{"from": source, "to": target, "type": edge_type, "evidence": [evidence]} for source, target, edge_type, evidence in sorted(edges)],
        }
        mode, reason = "incremental", "only changed wiki-page contributions and source hashes were refreshed"

    args.output.write_text(json.dumps(refreshed, indent=2) + "\n", encoding="utf-8")
    state = {"version": 1, "last_refresh": date.today().isoformat(), "registry_sha256": sha256(args.registry), "graph_sha256": sha256(args.output)}
    args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    summary = {
        "generated_at": date.today().isoformat(), "mode": mode, "reason": reason,
        "changed_wiki_pages": changed, "added_wiki_pages": added, "removed_wiki_pages": removed,
        "changed_sources": sorted(changed_sources), "explicit_sources": [source_id for _, source_id in explicit_sources],
        "nodes": len(refreshed["nodes"]), "edges": len(refreshed["edges"]),
    }
    args.report.write_text(render_report(summary), encoding="utf-8")
    print(f"Refreshed graph in {mode} mode: {len(refreshed['nodes'])} nodes, {len(refreshed['edges'])} edges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
