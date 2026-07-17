"""Create and verify a bounded, approval-gated wiki-fix packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from datetime import date

from prepare_wiki_lint import REQUIRED, VAULT_ROOT, frontmatter

NOTES = re.compile(r"^## Notes\s*$([\s\S]*?)(?=^## |\Z)", re.MULTILINE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def notes_digest(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = NOTES.search(text)
    return hashlib.sha256((match.group(0) if match else "").encode()).hexdigest()


def structural_errors(path: Path) -> list[str]:
    """Return post-fix invariants that apply to every selected wiki page."""
    meta = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    missing = [field for field in REQUIRED if not meta.get(field)]
    errors = [f"missing required frontmatter ({', '.join(missing)}): {path}"] if missing else []
    if meta.get("last_updated"):
        try:
            date.fromisoformat(str(meta["last_updated"]))
        except ValueError:
            errors.append(f"invalid last_updated after fix: {path}")
    return errors


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_actions(plan: dict[str, Any], numbers: set[int]) -> list[dict[str, Any]]:
    actions = [item for item in plan.get("actions", []) if int(item.get("number", -1)) in numbers]
    if len(actions) != len(numbers):
        found = {int(item["number"]) for item in actions}
        missing = sorted(numbers - found)
        raise ValueError(f"unknown action numbers: {missing}")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot and verify only selected wiki contradiction fixes.")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--select", required=True, help="Comma-separated action numbers.")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    plan = load(args.plan)
    numbers = {int(value.strip()) for value in args.select.split(",") if value.strip()}
    actions = selected_actions(plan, numbers)
    if not args.verify:
        pages = {}
        for action in actions:
            paths = [(action.get("page"), "issue-page"), (action.get("inbound_page"), "inbound-page")]
            for path, role in paths:
                if not path or not path.startswith("Level Knowledge/"):
                    continue
                absolute = VAULT_ROOT / path
                if not absolute.is_file():
                    raise ValueError(f"missing selected page: {path}")
                pages[path] = {
                    "sha256": digest(absolute), "notes_sha256": notes_digest(absolute), "role": role,
                    "require_frontmatter": absolute.name not in {"index.md", "log.md"},
                }
        packet = {"version": 1, "plan_run_id": plan.get("run_id"), "actions": actions, "pages": pages}
        args.packet.parent.mkdir(parents=True, exist_ok=True)
        args.packet.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote fix packet for {len(actions)} action(s) and {len(pages)} page(s).")
        return 0
    packet = load(args.packet)
    failures: list[str] = []
    for path, before in packet.get("pages", {}).items():
        absolute = VAULT_ROOT / path
        if not absolute.is_file():
            failures.append(f"missing page after fix: {path}")
            continue
        if notes_digest(absolute) != before["notes_sha256"]:
            failures.append(f"protected Notes changed: {path}")
        if before.get("require_frontmatter", True):
            failures.extend(structural_errors(absolute))
    if failures:
        print("Fix validation failed:")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"Fix validation passed for {len(packet.get('pages', {}))} page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
