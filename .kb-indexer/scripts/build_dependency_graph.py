"""Build deterministic source, wiki-page, and entity edges for this vault."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

INDEXER_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = INDEXER_ROOT.parent
WIKI_ROOT = VAULT_ROOT / "Level Knowledge"
DATA_ROOT = VAULT_ROOT / "Data"
LINK_PATTERN = re.compile(r"\[\[(.+?)\]\]")
REFERENCES_HEADING = re.compile(r"^## References\s*$", re.MULTILINE)
HEADING = re.compile(r"^##\s+", re.MULTILINE)
FOOTNOTE_DEFINITION = re.compile(r"^\[\^[^\]]+\]:", re.MULTILINE)


def vault_path(path: Path) -> str:
    return path.relative_to(VAULT_ROOT).as_posix()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def links(text: str) -> list[str]:
    targets: list[str] = []
    for match in LINK_PATTERN.finditer(text):
        target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.append(target.replace("\\", "/"))
    return targets


def split_references(text: str) -> tuple[str, list[str]]:
    match = REFERENCES_HEADING.search(text)
    if not match:
        return text, []
    following = HEADING.search(text, match.end())
    footnote = FOOTNOTE_DEFINITION.search(text, match.end())
    boundaries = [item.start() for item in (following, footnote) if item]
    end = min(boundaries) if boundaries else len(text)
    reference_text = text[match.end():end]
    return text[:match.start()] + text[end:], links(reference_text)


def indexed_paths(root: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return exact and basename indexes using vault-relative no-extension keys."""
    exact: dict[str, str] = {}
    by_stem: dict[str, list[str]] = defaultdict(list)
    for path in root.rglob("*.md"):
        relative = vault_path(path)
        if root == WIKI_ROOT and path.name in {"index.md", "log.md"}:
            continue
        key = relative.removesuffix(".md")
        exact[key] = relative
        if root == WIKI_ROOT:
            exact[key.removeprefix("Level Knowledge/")] = relative
        by_stem[path.stem.lower()].append(relative)
    return exact, by_stem


def resolve_link(target: str, exact: dict[str, str], by_stem: dict[str, list[str]]) -> tuple[str | None, str | None]:
    normalized = target.strip().removesuffix(".md").replace("\\", "/")
    if normalized in exact:
        return exact[normalized], None
    candidates = by_stem.get(Path(normalized).name.lower(), [])
    if len(candidates) == 1:
        return candidates[0], None
    return None, "ambiguous" if candidates else "missing"


def entity_page_index(registry: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for entity in registry["entities"]:
        for page in entity["wiki_pages"]:
            index[page] = entity["id"]
    return index


def build_graph(registry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    wiki_exact, wiki_stems = indexed_paths(WIKI_ROOT)
    source_exact, source_stems = indexed_paths(DATA_ROOT)
    entity_pages = entity_page_index(registry)
    nodes: dict[str, dict[str, str]] = {}
    edges: set[tuple[str, str, str, str]] = set()
    unresolved: dict[str, list[dict[str, str]]] = {"references": [], "wikilinks": [], "references_to_wiki": [], "body_source_links": []}

    for entity in registry["entities"]:
        nodes[entity["id"]] = {"id": entity["id"], "kind": "entity"}

    for page in sorted(WIKI_ROOT.rglob("*.md")):
        if page.name in {"index.md", "log.md"}:
            continue
        page_id = vault_path(page)
        nodes[page_id] = {"id": page_id, "kind": "wiki_page", "sha256": file_hash(page)}
        content = page.read_text(encoding="utf-8")
        body, reference_targets = split_references(content)

        own_entity = entity_pages.get(page_id)
        if own_entity:
            edges.add((page_id, own_entity, "mentions", page_id))

        for target in reference_targets:
            resolved, reason = resolve_link(target, source_exact, source_stems)
            if not resolved:
                wiki_target, wiki_reason = resolve_link(target, wiki_exact, wiki_stems)
                if wiki_target:
                    edges.add((page_id, wiki_target, "links_to", page_id))
                    unresolved["references_to_wiki"].append({"page": page_id, "target": target, "reason": "wiki_page"})
                    entity_id = entity_pages.get(wiki_target)
                    if entity_id:
                        edges.add((page_id, entity_id, "mentions", page_id))
                    continue
                unresolved["references"].append({"page": page_id, "target": target, "reason": reason or wiki_reason or "missing"})
                continue
            source_path = VAULT_ROOT / resolved
            nodes.setdefault(resolved, {"id": resolved, "kind": "source", "sha256": file_hash(source_path)})
            edges.add((page_id, resolved, "references", page_id))

        for target in links(body):
            resolved, reason = resolve_link(target, wiki_exact, wiki_stems)
            if not resolved:
                source_target, source_reason = resolve_link(target, source_exact, source_stems)
                if source_target:
                    source_path = VAULT_ROOT / source_target
                    nodes.setdefault(source_target, {"id": source_target, "kind": "source", "sha256": file_hash(source_path)})
                    # A source linked from ordinary page body text is useful
                    # navigation context, but it is not equivalent to an
                    # explicit `## References` evidence citation. Only the
                    # latter may drive an automatic impact selection.
                    edges.add((page_id, source_target, "links_to", page_id))
                    unresolved["body_source_links"].append({"page": page_id, "target": target, "reason": "source_file"})
                    continue
                unresolved["wikilinks"].append({"page": page_id, "target": target, "reason": reason or source_reason or "missing"})
                continue
            edges.add((page_id, resolved, "links_to", page_id))
            entity_id = entity_pages.get(resolved)
            if entity_id:
                edges.add((page_id, entity_id, "mentions", page_id))

    graph_edges = [
        {"from": source, "to": target, "type": edge_type, "evidence": [evidence]}
        for source, target, edge_type, evidence in sorted(edges)
    ]
    graph = {"version": 1, "generated_at": date.today().isoformat(), "nodes": sorted(nodes.values(), key=lambda node: node["id"]), "edges": graph_edges}
    return graph, unresolved


def review_report(graph: dict[str, Any], unresolved: dict[str, list[dict[str, str]]]) -> str:
    counts = defaultdict(int)
    for edge in graph["edges"]:
        counts[edge["type"]] += 1
    lines = [
        "# Dependency Graph Build Review", "", f"Generated: {graph['generated_at']}", "", "## Summary", "",
        f"- Nodes: {len(graph['nodes'])}", f"- Edges: {len(graph['edges'])}", f"- Source evidence edges: {counts['references']}", f"- Wiki link edges: {counts['links_to']}", f"- Entity mention edges: {counts['mentions']}", f"- Wiki links placed in References: {len(unresolved['references_to_wiki'])}", f"- Source links placed outside References: {len(unresolved['body_source_links'])}", f"- Unresolved References: {len(unresolved['references'])}", f"- Unresolved wikilinks: {len(unresolved['wikilinks'])}", "",
    ]
    for section, title in (("references_to_wiki", "Wiki Links Placed in References"), ("body_source_links", "Source Links Placed Outside References"), ("references", "Unresolved References"), ("wikilinks", "Unresolved Wikilinks")):
        lines.extend([f"## {title}", ""])
        if not unresolved[section]:
            lines.append("- None")
        else:
            for item in unresolved[section][:100]:
                lines.append(f"- `{item['target']}` from `{item['page']}` ({item['reason']})")
            if len(unresolved[section]) > 100:
                lines.append(f"- … {len(unresolved[section]) - 100} additional items")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build this vault's deterministic dependency graph.")
    parser.add_argument("--registry", type=Path, default=INDEXER_ROOT / "metadata" / "state" / "entity-registry.json")
    parser.add_argument("--output", type=Path, default=INDEXER_ROOT / "metadata" / "state" / "dependency-graph.json")
    parser.add_argument("--report", type=Path, default=INDEXER_ROOT / "metadata" / "reports" / "current" / "dependency-graph-review.md")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    graph, unresolved = build_graph(registry)
    args.output.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(review_report(graph, unresolved), encoding="utf-8")
    print(f"Wrote {len(graph['nodes'])} nodes and {len(graph['edges'])} edges to {args.output}")
    print(f"Wrote review report to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
