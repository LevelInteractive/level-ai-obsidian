"""Deterministically synchronize Obsidian graph colors from vault configuration."""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
STATUS_TAGS = {"active", "at-risk", "watch", "resolved", "deprecated"}
STATUS_OVERRIDES = {"at-risk", "watch", "deprecated", "resolved"}
TABLE_ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
CODE = re.compile(r"`([^`]+)`")
FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def clean(value: str) -> str:
    return value.strip().strip("`")


def parse_color_table(text: str) -> list[dict[str, str]]:
    start = text.index("### Canonical color table")
    end = text.index("### New domain palette", start)
    entries: list[dict[str, str]] = []
    for line in text[start:end].splitlines():
        match = TABLE_ROW.match(line)
        if not match or clean(match.group(1)) in {"Group", "---"}:
            continue
        group, query, color, purpose = (clean(value) for value in match.groups())
        if query.startswith(("path:", "tag:")) and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            entries.append({"group": group, "query": query, "hex": color.lower(), "purpose": purpose})
    return entries


def parse_palette(text: str) -> list[str]:
    start = text.index("### New domain palette")
    next_heading = re.search(r"^###\s+", text[start + 1:], re.MULTILINE)
    end = start + 1 + next_heading.start() if next_heading else len(text)
    return [value.lower() for value in re.findall(r"#[0-9a-fA-F]{6}", text[start:end])]


def controlled_tags(text: str) -> set[str]:
    start = text.index("## Controlled vocabulary")
    end = text.index("## Graph color groups", start)
    return {value.lstrip("#") for value in CODE.findall(text[start:end])}


def domains(root: Path) -> list[str]:
    wiki = root / "Level Knowledge"
    return sorted(path.name for path in wiki.iterdir() if path.is_dir())


def rgb(hex_color: str) -> int:
    return int(hex_color.removeprefix("#"), 16)


def group(query: str, hex_color: str) -> dict[str, Any]:
    return {"query": query, "color": {"a": 1, "rgb": rgb(hex_color)}}


def choose_color(palette: list[str], used: set[str]) -> str:
    for color in palette:
        if color not in used:
            return color
    return palette[len(used) % len(palette)]


def add_domain_rows(text: str, new_domains: list[tuple[str, str]]) -> str:
    if not new_domains:
        return text
    # Domain rows must precede theme/status rows, but no individual tag name is
    # special. This keeps the policy resilient if its vocabulary changes.
    table_start = text.find("### Canonical color table")
    tag_rows = [
        match.start()
        for match in re.finditer(r"^\|.*?`tag:#", text, flags=re.MULTILINE)
        if match.start() > table_start
    ]
    insert_at = tag_rows[0] if tag_rows else -1
    if insert_at < 0:
        raise ValueError("could not find a theme or status tag row in tagging.md")
    rows = "".join(
        f"| {domain.replace('-', ' ').title()} | `path:Level Knowledge/{domain}` | `{color}` | Auto-assigned domain color |\n"
        for domain, color in new_domains
    )
    return text[:insert_at] + rows + text[insert_at:]


def expected_groups(entries: list[dict[str, str]], discovered: list[str], current: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    by_query = {entry["query"]: entry for entry in entries}
    domain_entries = [entry for entry in entries if entry["query"].startswith("path:")]
    theme_entries = [entry for entry in entries if entry["query"].startswith("tag:#") and entry["group"].lstrip("#") not in STATUS_OVERRIDES]
    status_entries = [entry for entry in entries if entry["group"].lstrip("#") in STATUS_OVERRIDES]
    active_domain_queries = {f"path:Level Knowledge/{domain}" for domain in discovered}
    canonical = [group(entry["query"], entry["hex"]) for entry in domain_entries if entry["query"] in active_domain_queries]
    canonical += [group(entry["query"], entry["hex"]) for entry in theme_entries]
    canonical_queries = {item["query"] for item in canonical} | {entry["query"] for entry in status_entries}
    manual = []
    for item in current:
        query = item.get("query", "")
        obsolete_path = query.startswith("path:Level Knowledge/") and query.removeprefix("path:Level Knowledge/").split("/", 1)[0] not in discovered
        if query not in canonical_queries and not obsolete_path:
            manual.append(copy.deepcopy(item))
    canonical += manual
    canonical += [group(entry["query"], entry["hex"]) for entry in status_entries]
    stale_config = [entry["query"] for entry in domain_entries if entry["query"] not in active_domain_queries]
    return canonical, stale_config


def diff_groups(current: list[dict[str, Any]], expected: list[dict[str, Any]]) -> dict[str, list[str]]:
    current_by_query = {item.get("query"): item for item in current}
    expected_by_query = {item.get("query"): item for item in expected}
    return {
        "added": sorted(query for query in expected_by_query if query not in current_by_query),
        "updated": sorted(query for query in expected_by_query if query in current_by_query and expected_by_query[query] != current_by_query[query]),
        "removed": sorted(query for query in current_by_query if query not in expected_by_query),
    }


def page_tags(path: Path) -> list[str]:
    match = FRONT.match(path.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return []
    tags: list[str] = []
    collecting = False
    for line in match.group(1).splitlines():
        if line.strip() == "tags:":
            collecting = True
            continue
        if collecting and line.startswith("  - "):
            tags.append(line[4:].strip().lstrip("#"))
        elif collecting and line and not line.startswith((" ", "\t")):
            break
    return tags


def audit_tags(root: Path, config_text: str) -> dict[str, Any]:
    known = controlled_tags(config_text)
    colored = {entry["query"].removeprefix("tag:#") for entry in parse_color_table(config_text) if entry["query"].startswith("tag:#")}
    counts: Counter[str] = Counter()
    pages_scanned = 0
    for path in (root / "Level Knowledge").rglob("*.md"):
        if path.name in {"index.md", "log.md"}:
            continue
        pages_scanned += 1
        counts.update(page_tags(path))
    candidates = [{"tag": tag, "pages": count} for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                  if tag in known and tag not in colored and tag not in STATUS_TAGS and count >= 3]
    return {"mode": "audit-tags", "candidates": candidates, "pages_scanned": pages_scanned}


def append_log(root: Path, summary: str) -> None:
    path = root / "Level Knowledge" / "log.md"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"| {date.today().isoformat()} | Graph Sync | — | — | {summary} |\n")


def sync(root: Path, dry_run: bool = False) -> dict[str, Any]:
    config_path, graph_path = root / ".config" / "tagging.md", root / ".obsidian" / "graph.json"
    config_text = config_path.read_text(encoding="utf-8")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    current = graph.get("colorGroups", [])
    discovered = domains(root)
    entries = parse_color_table(config_text)
    known_domain_queries = {entry["query"] for entry in entries if entry["query"].startswith("path:")}
    palette, used = parse_palette(config_text), {entry["hex"] for entry in entries}
    new_domains: list[tuple[str, str]] = []
    for domain in discovered:
        query = f"path:Level Knowledge/{domain}"
        if query not in known_domain_queries:
            color = choose_color(palette, used)
            used.add(color)
            new_domains.append((domain, color))
    proposed_config = add_domain_rows(config_text, new_domains)
    proposed_entries = parse_color_table(proposed_config)
    expected, stale_config = expected_groups(proposed_entries, discovered, current)
    changes = diff_groups(current, expected)
    changed = bool(new_domains or any(changes.values()))
    result = {"mode": "dry-run" if dry_run else "sync", "changed": changed, "domains": discovered,
              "new_domains": [{"domain": domain, "hex": color} for domain, color in new_domains],
              "stale_config_domains": stale_config, "groups_before": len(current), "groups_after": len(expected), **changes}
    if changed and not dry_run:
        if new_domains:
            config_path.write_text(proposed_config, encoding="utf-8")
        graph["colorGroups"] = expected
        graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
        summary = f"Added {len(changes['added'])}, updated {len(changes['updated'])}, removed {len(changes['removed'])} graph groups"
        if new_domains:
            summary += "; new domains: " + ", ".join(f"{domain} ({color})" for domain, color in new_domains)
        append_log(root, summary)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Obsidian graph color groups deterministically.")
    parser.add_argument("--vault-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--audit-tags", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()
    root = args.vault_root.resolve()
    config_text = (root / ".config" / "tagging.md").read_text(encoding="utf-8")
    result = audit_tags(root, config_text) if args.audit_tags else sync(root, args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
    elif args.audit_tags:
        print(f"Tag audit: {len(result['candidates'])} uncolored controlled tag candidate(s).")
        for item in result["candidates"]:
            print(f"- #{item['tag']}: {item['pages']} pages")
    elif not result["changed"]:
        print("Graph colors already in sync; no files changed.")
    else:
        print(f"Graph sync {'would change' if args.dry_run else 'changed'} {result['groups_before']} to {result['groups_after']} groups.")
        print(f"Added: {len(result['added'])}; updated: {len(result['updated'])}; removed: {len(result['removed'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
