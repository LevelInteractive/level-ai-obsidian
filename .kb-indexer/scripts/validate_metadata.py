"""Validate Phase 0 entity-registry and dependency-graph metadata without third-party packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[a-f0-9]{64}$")
ENTITY_ID = re.compile(r"^(client|person|tool|process|metric|decision|organization|project):[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENTITY_KINDS = {"client", "person", "tool", "process", "metric", "decision", "organization", "project"}
EDGE_TYPES = {"references", "links_to", "mentions", "alias_of", "candidate_for_review"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: invalid JSON ({exc})") from exc


def is_vault_path(value: Any, prefix: str | None = None) -> bool:
    return isinstance(value, str) and "\\" not in value and ".." not in value.split("/") and (prefix is None or value.startswith(prefix))


def require_keys(item: dict[str, Any], required: set[str], allowed: set[str], label: str, errors: list[str]) -> None:
    missing = required - item.keys()
    extra = item.keys() - allowed
    if missing:
        errors.append(f"{label}: missing keys: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{label}: unsupported keys: {', '.join(sorted(extra))}")


def validate_evidence(items: Any, label: str, errors: list[str]) -> None:
    if not isinstance(items, list) or not items:
        errors.append(f"{label}: evidence must be a non-empty list")
        return
    for index, evidence in enumerate(items):
        entry_label = f"{label}.evidence[{index}]"
        if not isinstance(evidence, dict):
            errors.append(f"{entry_label}: must be an object")
            continue
        require_keys(evidence, {"path", "kind"}, {"path", "kind", "note"}, entry_label, errors)
        if not is_vault_path(evidence.get("path")) or not str(evidence.get("path", "")).startswith(("Data/", "Level Knowledge/")):
            errors.append(f"{entry_label}: path must be a vault-relative Data/ or Level Knowledge/ path")
        if evidence.get("kind") not in {"source", "wiki_page"}:
            errors.append(f"{entry_label}: kind must be source or wiki_page")


def validate_registry(registry: Any, errors: list[str]) -> None:
    if not isinstance(registry, dict):
        errors.append("entity registry: root must be an object")
        return
    require_keys(registry, {"version", "entities"}, {"version", "generated_at", "entities"}, "entity registry", errors)
    if registry.get("version") != 1:
        errors.append("entity registry: version must be 1")
    entities = registry.get("entities")
    if not isinstance(entities, list):
        errors.append("entity registry: entities must be a list")
        return
    ids: set[str] = set()
    aliases: dict[str, str] = {}
    for index, entity in enumerate(entities):
        label = f"entity registry.entities[{index}]"
        if not isinstance(entity, dict):
            errors.append(f"{label}: must be an object")
            continue
        require_keys(entity, {"id", "kind", "canonical_name", "wiki_pages", "aliases", "evidence", "status"}, {"id", "kind", "canonical_name", "wiki_pages", "aliases", "evidence", "status"}, label, errors)
        entity_id = entity.get("id")
        if not isinstance(entity_id, str) or not ENTITY_ID.fullmatch(entity_id):
            errors.append(f"{label}: invalid entity id")
        elif entity_id in ids:
            errors.append(f"{label}: duplicate entity id {entity_id}")
        else:
            ids.add(entity_id)
        if entity.get("kind") not in ENTITY_KINDS or (isinstance(entity_id, str) and entity.get("kind") != entity_id.split(":", 1)[0]):
            errors.append(f"{label}: kind must match the entity id prefix")
        pages = entity.get("wiki_pages")
        if not isinstance(pages, list) or not pages or any(not is_vault_path(page, "Level Knowledge/") or not str(page).endswith(".md") for page in pages):
            errors.append(f"{label}: wiki_pages must be non-empty Level Knowledge/*.md paths")
        validate_evidence(entity.get("evidence"), label, errors)
        if entity.get("status") not in {"active", "deprecated", "merged", "ambiguous"}:
            errors.append(f"{label}: invalid status")
        entity_aliases = entity.get("aliases")
        if not isinstance(entity_aliases, list):
            errors.append(f"{label}: aliases must be a list")
            continue
        for alias_index, alias in enumerate(entity_aliases):
            alias_label = f"{label}.aliases[{alias_index}]"
            if not isinstance(alias, dict):
                errors.append(f"{alias_label}: must be an object")
                continue
            require_keys(alias, {"name", "normalized", "state", "evidence"}, {"name", "normalized", "state", "evidence"}, alias_label, errors)
            normalized = alias.get("normalized")
            if not isinstance(normalized, str) or not SLUG.fullmatch(normalized):
                errors.append(f"{alias_label}: normalized must be a lowercase slug")
            elif alias.get("state") == "confirmed":
                prior = aliases.setdefault(normalized, str(entity_id))
                if prior != entity_id:
                    errors.append(f"{alias_label}: confirmed alias {normalized} also maps to {prior}")
            if alias.get("state") not in {"confirmed", "ambiguous", "rejected"}:
                errors.append(f"{alias_label}: invalid alias state")
            validate_evidence(alias.get("evidence"), alias_label, errors)


def validate_graph(graph: Any, errors: list[str]) -> None:
    if not isinstance(graph, dict):
        errors.append("dependency graph: root must be an object")
        return
    require_keys(graph, {"version", "nodes", "edges"}, {"version", "generated_at", "nodes", "edges"}, "dependency graph", errors)
    if graph.get("version") != 1:
        errors.append("dependency graph: version must be 1")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        errors.append("dependency graph: nodes must be a list")
        return
    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        label = f"dependency graph.nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{label}: must be an object")
            continue
        require_keys(node, {"id", "kind"}, {"id", "kind", "sha256"}, label, errors)
        node_id, kind = node.get("id"), node.get("kind")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"{label}: id must be a non-empty string")
        elif node_id in node_ids:
            errors.append(f"{label}: duplicate node id {node_id}")
        else:
            node_ids.add(node_id)
        if kind not in {"source", "wiki_page", "entity"}:
            errors.append(f"{label}: invalid kind")
        if kind == "source" and not is_vault_path(node_id, "Data/"):
            errors.append(f"{label}: source IDs must be Data/ paths")
        if kind == "wiki_page" and (not is_vault_path(node_id, "Level Knowledge/") or not str(node_id).endswith(".md")):
            errors.append(f"{label}: wiki_page IDs must be Level Knowledge/*.md paths")
        if kind == "entity" and (not isinstance(node_id, str) or not ENTITY_ID.fullmatch(node_id)):
            errors.append(f"{label}: entity IDs must use the canonical entity format")
        if kind in {"source", "wiki_page"} and (not isinstance(node.get("sha256"), str) or not SHA256.fullmatch(node["sha256"])):
            errors.append(f"{label}: source/wiki_page nodes require a lowercase SHA-256")
        if kind == "entity" and "sha256" in node:
            errors.append(f"{label}: entity nodes must not carry a SHA-256")
    edges = graph.get("edges")
    if not isinstance(edges, list):
        errors.append("dependency graph: edges must be a list")
        return
    for index, edge in enumerate(edges):
        label = f"dependency graph.edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{label}: must be an object")
            continue
        require_keys(edge, {"from", "to", "type", "evidence"}, {"from", "to", "type", "evidence"}, label, errors)
        if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
            errors.append(f"{label}: endpoints must refer to declared nodes")
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"{label}: invalid edge type")
        evidence = edge.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not is_vault_path(path) or not str(path).startswith(("Data/", "Level Knowledge/")) for path in evidence):
            errors.append(f"{label}: evidence must be non-empty Data/ or Level Knowledge/ paths")


def check_files(registry: dict[str, Any], graph: dict[str, Any], vault_root: Path, errors: list[str]) -> None:
    paths: set[str] = set()
    for entity in registry.get("entities", []):
        paths.update(entity.get("wiki_pages", []))
        for evidence in entity.get("evidence", []):
            paths.add(evidence.get("path", ""))
        for alias in entity.get("aliases", []):
            for evidence in alias.get("evidence", []):
                paths.add(evidence.get("path", ""))
    for node in graph.get("nodes", []):
        if node.get("kind") in {"source", "wiki_page"}:
            paths.add(node.get("id", ""))
    for edge in graph.get("edges", []):
        paths.update(edge.get("evidence", []))
    for relative in sorted(path for path in paths if relative_path_safe(path)):
        if not (vault_root / relative).is_file():
            errors.append(f"file check: referenced path does not exist: {relative}")


def relative_path_safe(path: Any) -> bool:
    return is_vault_path(path) and str(path).startswith(("Data/", "Level Knowledge/"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate entity and dependency metadata.")
    parser.add_argument("entity_registry", type=Path)
    parser.add_argument("dependency_graph", type=Path)
    parser.add_argument("--check-files", action="store_true", help="Verify vault paths exist; omit for self-contained fixtures.")
    args = parser.parse_args()
    errors: list[str] = []
    try:
        registry = load_json(args.entity_registry)
        graph = load_json(args.dependency_graph)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    validate_registry(registry, errors)
    validate_graph(graph, errors)
    if args.check_files:
        check_files(registry, graph, Path(__file__).resolve().parent.parent.parent, errors)
    if errors:
        print("Metadata validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Metadata validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
