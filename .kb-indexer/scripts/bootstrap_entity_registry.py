"""Bootstrap canonical client and person entities from the existing Level Knowledge wiki."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

INDEXER_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = INDEXER_ROOT.parent
WIKI_ROOT = VAULT_ROOT / "Level Knowledge"
TITLE_PATTERN = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
H1_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
PARENTHETICAL_PATTERN = re.compile(r"^(?P<name>.+?)\s+\((?P<detail>.+)\)$")


def vault_path(path: Path) -> str:
    return path.relative_to(VAULT_ROOT).as_posix()


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def page_title(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    frontmatter = TITLE_PATTERN.search(content)
    if frontmatter:
        return frontmatter.group(1).strip().strip('"')
    h1 = H1_PATTERN.search(content)
    return h1.group(1).strip() if h1 else path.stem


def canonical_page(paths: list[Path], entity_slug: str) -> Path:
    exact = next((path for path in paths if path.stem == entity_slug), None)
    return exact or sorted(paths)[0]


def aliases_from_title(title: str, canonical_name: str, evidence: dict[str, str]) -> list[dict[str, Any]]:
    """Extract only aliases that the title itself explicitly asserts."""
    aliases: list[dict[str, Any]] = []
    match = PARENTHETICAL_PATTERN.match(title)
    if not match:
        return aliases
    short_name, detail = match.group("name").strip(), match.group("detail").strip()
    candidates = [short_name]
    if detail.lower().startswith("formerly "):
        candidates.append(detail[9:].strip())
    elif " / " in detail:
        candidates.extend(part.strip() for part in detail.split(" / "))
    else:
        candidates.append(detail)
    seen: set[str] = set()
    for candidate in candidates:
        normalized = slugify(candidate)
        if not normalized or normalized in seen or candidate == canonical_name:
            continue
        seen.add(normalized)
        aliases.append({"name": candidate, "normalized": normalized, "state": "confirmed", "evidence": [evidence]})
    return aliases


def build_client_entities() -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for directory in sorted(path for path in (WIKI_ROOT / "clients").iterdir() if path.is_dir()):
        pages = sorted(directory.glob("*.md"))
        if not pages:
            continue
        primary = canonical_page(pages, directory.name)
        title = page_title(primary)
        evidence = {"path": vault_path(primary), "kind": "wiki_page"}
        entities.append({"id": f"client:{directory.name}", "kind": "client", "canonical_name": title, "wiki_pages": [vault_path(page) for page in pages], "aliases": aliases_from_title(title, title, evidence), "evidence": [evidence], "status": "active"})
    return entities


def build_person_entities() -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for page in sorted((WIKI_ROOT / "team").glob("*.md")):
        title = page_title(page)
        evidence = {"path": vault_path(page), "kind": "wiki_page"}
        entities.append({"id": f"person:{page.stem}", "kind": "person", "canonical_name": title, "wiki_pages": [vault_path(page)], "aliases": [], "evidence": [evidence], "status": "active"})
    return entities


def review_report(registry: dict[str, Any]) -> str:
    entities = registry["entities"]
    clients = [entity for entity in entities if entity["kind"] == "client"]
    people = [entity for entity in entities if entity["kind"] == "person"]
    aliases = [(entity, alias) for entity in clients for alias in entity["aliases"]]
    lines = [
        "# Entity Registry Bootstrap Review", "", f"Generated: {registry['generated_at']}", "", "## Summary", "",
        f"- Canonical client entities: {len(clients)}", f"- Canonical person entities: {len(people)}", f"- Confirmed aliases inferred from page titles: {len(aliases)}", "- Automatic aliases inferred from narrative prose: 0", "",
        "## Review policy", "", "Only title-level assertions such as `(formerly TPA)` and `(IRA Financial)` were promoted automatically. Narrative claims such as ACC/AMC are intentionally excluded until explicit confirmation exists. Add unresolved variants as `ambiguous` aliases with evidence in a later review step; they must not route updates.", "",
        "## Confirmed aliases", "",
    ]
    lines.extend([f"- `{alias['name']}` → `{entity['id']}`" for entity, alias in aliases] or ["- None"])
    lines.extend(["", "## Outstanding review", "", "- Inspect new or changed client pages for explicitly documented rebrands, legal names, and abbreviations that are not present in their title.", "- Resolve or preserve ambiguous variants before adding them as routing aliases.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap client and person entities from Level Knowledge.")
    parser.add_argument("--output", type=Path, default=INDEXER_ROOT / "metadata" / "state" / "entity-registry.json")
    parser.add_argument("--report", type=Path, default=INDEXER_ROOT / "metadata" / "reports" / "current" / "entity-registry-review.md")
    args = parser.parse_args()
    registry = {"version": 1, "generated_at": date.today().isoformat(), "entities": build_client_entities() + build_person_entities()}
    registry["entities"].sort(key=lambda entity: entity["id"])
    args.output.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(review_report(registry), encoding="utf-8")
    print(f"Wrote {len(registry['entities'])} entities to {args.output}")
    print(f"Wrote review report to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
