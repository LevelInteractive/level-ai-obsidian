"""Incrementally refresh QMD collections and embeddings before discovery-assisted routing."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from resolve_impact import INDEXER_ROOT, qmd_executable

METADATA_ROOT = INDEXER_ROOT / "metadata"


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=300)
    return (result.stdout or result.stderr).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Incrementally refresh QMD before discovery-assisted routing.")
    parser.add_argument("--skip-embed", action="store_true", help="Update collection metadata only; do not generate embeddings.")
    parser.add_argument("--level-knowledge-only", action="store_true", help="Embed only Level Knowledge; use only when discovery is the sole concern.")
    parser.add_argument("--output", type=Path, default=METADATA_ROOT / "reports" / "current" / "qmd-index-refresh.json")
    parser.add_argument("--report", type=Path, default=METADATA_ROOT / "reports" / "current" / "qmd-index-refresh.md")
    args = parser.parse_args()

    executable = qmd_executable()
    if not executable:
        parser.error("QMD executable not found; set QMD_EXECUTABLE to override discovery")

    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        update_output = run([executable, "update"])
        embed_command = [executable, "embed", "-c", "level-knowledge"] if args.level_knowledge_only else [executable, "embed"]
        embed_output = "Skipped by --skip-embed." if args.skip_embed else run(embed_command)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.error(f"QMD refresh failed: {getattr(exc, 'stderr', '') or exc}")

    result = {
        "version": 1,
        "generated_at": generated_at,
        "qmd_executable": executable,
        "embedding_scope": "skipped" if args.skip_embed else ("level-knowledge" if args.level_knowledge_only else "all collections"),
        "update_output": update_output,
        "embed_output": embed_output,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(
        "# QMD Index Refresh\n\n"
        f"Generated: {generated_at}\n\n"
        f"- Collection update: completed\n"
        f"- Embedding refresh: {'skipped' if args.skip_embed else ('Level Knowledge only' if args.level_knowledge_only else 'all collections')}\n\n"
        "## Update output\n\n```text\n"
        f"{update_output}\n```\n\n## Embed output\n\n```text\n{embed_output}\n```\n",
        encoding="utf-8",
    )
    print(f"Wrote QMD refresh record to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
