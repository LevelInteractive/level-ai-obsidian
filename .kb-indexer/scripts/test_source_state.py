"""Deterministic transition tests for the hash-based source-state scanner."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from scan_source_state import build_delta, classify, snapshot_sources, state_id


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_case(name: str, condition: bool) -> tuple[bool, str]:
    return condition, f"source-state-{name}: {'PASS' if condition else 'FAIL'}"


def main() -> int:
    outcomes: list[tuple[bool, str]] = []
    with tempfile.TemporaryDirectory() as directory:
        vault = Path(directory)
        data = vault / "Data"
        original = data / "Knowledge" / "original.md"
        write(original, "alpha")
        initial, initial_hashed = snapshot_sources(data, vault)
        prior = {"files": initial, "state_id": state_id(initial)}
        outcomes.append(assert_case("bootstrap-hashes-tracked-file", initial_hashed == 1 and set(initial) == {"Data/Knowledge/original.md"}))

        # A metadata-only touch should be rehashed once but should not route a
        # source because the digest remains unchanged.
        time.sleep(0.01)
        original.touch()
        touched_files, touched_hashed = snapshot_sources(data, vault, initial)
        touched = classify(initial, touched_files)
        outcomes.append(assert_case("timestamp-touch-not-routed", touched_hashed == 1 and len(touched["touched"]) == 1 and not touched["changed"]))

        # Same-size content changes must still route because SHA-256 differs.
        time.sleep(0.01)
        write(original, "bravo")
        changed_files, changed_hashed = snapshot_sources(data, vault, touched_files)
        changed = classify(touched_files, changed_files)
        outcomes.append(assert_case("same-size-content-change", changed_hashed == 1 and len(changed["changed"]) == 1 and changed["changed"][0]["path"] == "Data/Knowledge/original.md"))

        # A unique hash relocation is maintenance, not a new knowledge source.
        moved = data / "Personal" / "renamed.md"
        moved.parent.mkdir(parents=True, exist_ok=True)
        original.rename(moved)
        moved_files, _hashed = snapshot_sources(data, vault, changed_files)
        relocation = classify(changed_files, moved_files)
        outcomes.append(assert_case("move-not-routed", len(relocation["moved"]) == 1 and not relocation["new"] and not relocation["deleted"]))

        # A genuine new source routes, while a missing source is maintenance.
        write(data / "Meetings" / "new.md", "new source")
        (data / "Personal" / "renamed.md").unlink()
        final_files, _hashed = snapshot_sources(data, vault, moved_files)
        delta = build_delta({"files": moved_files, "state_id": state_id(moved_files)}, final_files, 1)
        outcomes.append(assert_case("new-and-deleted-separated", delta["routing_sources"] == ["Data/Meetings/new.md"] and len(delta["changes"]["deleted"]) == 1 and delta["maintenance_required"]))

    for _passed, line in outcomes:
        print(line)
    failures = sum(not passed for passed, _line in outcomes)
    print(f"{len(outcomes) - failures}/{len(outcomes)} source-state scenarios passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
