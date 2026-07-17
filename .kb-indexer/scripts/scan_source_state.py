"""Maintain a hash-based, two-phase change manifest for routable Data sources.

The scanner is deliberately separate from routing. A normal scan writes a delta
report but does not change the accepted source state. After the associated
shadow/review/acceptance cycle succeeds, accept that exact delta to advance the
manifest. This prevents a failed review from silently losing a source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INDEXER_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = INDEXER_ROOT.parent
DATA_ROOT = VAULT_ROOT / "Data"
METADATA_ROOT = INDEXER_ROOT / "metadata"
DEFAULT_STATE_PATH = METADATA_ROOT / "state" / "source-state.json"
DEFAULT_DELTA_DIR = METADATA_ROOT / "source-deltas"
TRACKED_SUFFIXES = frozenset({".md", ".pdf"})
EXCLUDED_PREFIXES = ("Data/Assets/", "Data/Claude/.state/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_id(path: Path, vault_root: Path = VAULT_ROOT) -> str:
    return path.relative_to(vault_root).as_posix()


def is_tracked(path: Path, vault_root: Path = VAULT_ROOT) -> bool:
    identifier = source_id(path, vault_root)
    return path.suffix.lower() in TRACKED_SUFFIXES and not identifier.startswith(EXCLUDED_PREFIXES)


def state_id(files: dict[str, dict[str, Any]]) -> str:
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("files"), dict):
        raise ValueError(f"Invalid source state: {path}")
    expected = state_id(payload["files"])
    if payload.get("state_id") != expected:
        raise ValueError(f"Source state fingerprint does not match its files: {path}")
    return payload


def snapshot_sources(data_root: Path = DATA_ROOT, vault_root: Path = VAULT_ROOT, prior_files: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, dict[str, Any]], int]:
    """Return source descriptors and the number of files that required hashing.

    Size and nanosecond mtime make normal scans cheap: only files whose stat
    fingerprint changed are rehashed. `--verify-all` callers pass no prior
    state, intentionally hashing every tracked file as an integrity audit.
    """
    descriptors: dict[str, dict[str, Any]] = {}
    hashed = 0
    for path in sorted(data_root.rglob("*")):
        if not path.is_file() or not is_tracked(path, vault_root):
            continue
        identifier = source_id(path, vault_root)
        stat = path.stat()
        prior = (prior_files or {}).get(identifier)
        if prior and prior.get("size_bytes") == stat.st_size and prior.get("mtime_ns") == stat.st_mtime_ns:
            digest = prior["sha256"]
        else:
            digest = sha256(path)
            hashed += 1
        descriptors[identifier] = {
            "sha256": digest,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    return descriptors, hashed


def classify(prior_files: dict[str, dict[str, Any]], current_files: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    new = [{"path": path, **current_files[path]} for path in sorted(set(current_files) - set(prior_files))]
    deleted = [{"path": path, **prior_files[path]} for path in sorted(set(prior_files) - set(current_files))]
    changed: list[dict[str, Any]] = []
    touched: list[dict[str, Any]] = []
    for path in sorted(set(prior_files) & set(current_files)):
        prior, current = prior_files[path], current_files[path]
        if prior["sha256"] != current["sha256"]:
            changed.append({"path": path, "previous_sha256": prior["sha256"], **current})
        elif prior != current:
            touched.append({"path": path, **current})

    # A move is unambiguous only when one missing path and one new path share a
    # hash. Duplicate-content files remain separate new/deleted events.
    by_hash_new: dict[str, list[dict[str, Any]]] = {}
    by_hash_deleted: dict[str, list[dict[str, Any]]] = {}
    for entry in new:
        by_hash_new.setdefault(entry["sha256"], []).append(entry)
    for entry in deleted:
        by_hash_deleted.setdefault(entry["sha256"], []).append(entry)
    moved: list[dict[str, Any]] = []
    moved_new: set[str] = set()
    moved_deleted: set[str] = set()
    for digest in sorted(set(by_hash_new) & set(by_hash_deleted)):
        if len(by_hash_new[digest]) == len(by_hash_deleted[digest]) == 1:
            incoming, outgoing = by_hash_new[digest][0], by_hash_deleted[digest][0]
            moved.append({"from": outgoing["path"], "to": incoming["path"], "sha256": digest})
            moved_new.add(incoming["path"])
            moved_deleted.add(outgoing["path"])
    return {
        "new": [entry for entry in new if entry["path"] not in moved_new],
        "changed": changed,
        "moved": moved,
        "deleted": [entry for entry in deleted if entry["path"] not in moved_deleted],
        "touched": touched,
    }


def build_delta(prior_state: dict[str, Any], current_files: dict[str, dict[str, Any]], hashed_files: int) -> dict[str, Any]:
    changes = classify(prior_state["files"], current_files)
    routing_sources = [entry["path"] for group in ("new", "changed") for entry in changes[group]]
    snapshot = {
        "version": 1,
        "files": current_files,
        "state_id": state_id(current_files),
    }
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_state_id": prior_state["state_id"],
        "snapshot": snapshot,
        "scan": {"tracked_files": len(current_files), "hashed_files": hashed_files},
        "changes": changes,
        "routing_sources": routing_sources,
        "maintenance_required": bool(changes["moved"] or changes["deleted"]),
        "writes": "delta report only; accepted source state is unchanged until this delta is accepted",
    }


def markdown_report(delta: dict[str, Any]) -> str:
    lines = ["# Source-State Delta", "", f"Generated: {delta['generated_at']}", "", "This report does not advance source state. Accept it only after the associated ingest cycle succeeds.", "", "## Scan", "", f"- Tracked files: {delta['scan']['tracked_files']}", f"- Files hashed this scan: {delta['scan']['hashed_files']}", f"- Sources requiring routing: {len(delta['routing_sources'])}", ""]
    for group, title in (("new", "New"), ("changed", "Changed"), ("moved", "Moved"), ("deleted", "Deleted"), ("touched", "Timestamp/size changed, content unchanged")):
        entries = delta["changes"][group]
        lines.extend([f"## {title}", ""])
        if group == "moved":
            lines.extend(f"- `{entry['from']}` → `{entry['to']}`" for entry in entries)
        else:
            lines.extend(f"- `{entry['path']}`" for entry in entries)
        if not entries:
            lines.append("- None.")
        lines.append("")
    if delta["maintenance_required"]:
        lines.extend(["## Required maintenance", "", "- Moved or deleted sources require reference/graph review. They are deliberately not routed as new knowledge.", ""])
    return "\n".join(lines)


def write_state(path: Path, files: dict[str, dict[str, Any]]) -> None:
    payload = {"version": 1, "accepted_at": datetime.now(timezone.utc).isoformat(), "state_id": state_id(files), "files": files}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect Data source changes using an accepted SHA-256 state manifest.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--bootstrap", action="store_true", help="Create an initial accepted manifest without routing existing sources.")
    actions.add_argument("--scan", action="store_true", help="Create a non-mutating delta report against accepted state.")
    actions.add_argument("--accept", type=Path, help="Accept a previously generated delta after its ingest cycle succeeds.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DELTA_DIR)
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("source-delta-%Y%m%dT%H%M%SZ"))
    parser.add_argument("--verify-all", action="store_true", help="Hash every tracked file instead of trusting unchanged size/mtime metadata.")
    args = parser.parse_args()

    if args.bootstrap:
        if args.state.exists():
            parser.error(f"State already exists: {args.state}. Use --scan or remove it deliberately.")
        files, hashed = snapshot_sources(prior_files=None)
        write_state(args.state, files)
        print(f"Bootstrapped {args.state} with {len(files)} tracked files ({hashed} hashed); no sources routed.")
        return 0

    if args.accept:
        current = load_state(args.state)
        if current is None:
            parser.error("Cannot accept a delta without an accepted source state; run --bootstrap first.")
        delta = json.loads(args.accept.read_text(encoding="utf-8"))
        if delta.get("version") != 1 or delta.get("base_state_id") != current["state_id"]:
            parser.error("Delta does not match the current accepted state; rescan before accepting.")
        snapshot = delta.get("snapshot", {})
        files = snapshot.get("files")
        if not isinstance(files, dict) or snapshot.get("state_id") != state_id(files):
            parser.error("Delta snapshot is invalid.")
        write_state(args.state, files)
        print(f"Accepted {args.accept}; source state now tracks {len(files)} files.")
        return 0

    prior = load_state(args.state)
    if prior is None:
        parser.error("No accepted source state exists; run --bootstrap first to avoid routing the entire vault.")
    current_files, hashed = snapshot_sources(prior_files=None if args.verify_all else prior["files"])
    delta = build_delta(prior, current_files, hashed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.run_id}.json"
    markdown_path = args.output_dir / f"{args.run_id}.md"
    json_path.write_text(json.dumps(delta, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(delta), encoding="utf-8")
    print(f"Wrote source-state delta to {json_path} ({len(delta['routing_sources'])} source(s) require routing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
