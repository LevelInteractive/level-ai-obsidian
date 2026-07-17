"""Run bounded, read-only QMD cluster checks for proposed Interest topics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from prepare_ingest_packet import http_json, temporary_qmd_http


INDEXER_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = INDEXER_ROOT / "metadata" / "trials" / "interest-topics"


def parse_topic(value: str) -> tuple[str, str]:
    if "::" not in value:
        raise argparse.ArgumentTypeError("topic must use 'Label::semantic query' format")
    label, query = (part.strip() for part in value.split("::", 1))
    if not label or not query:
        raise argparse.ArgumentTypeError("topic label and query cannot be empty")
    return label, query


def main() -> int:
    parser = argparse.ArgumentParser(description="Test proposed Interest-topic clusters against Data/Knowledge with QMD.")
    parser.add_argument("--topic", action="append", required=True, type=parse_topic, help="Repeat: 'Label::semantic query'.")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("interest-topics-%Y%m%dT%H%M%SZ"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.limit < 2:
        parser.error("--limit must be at least 2")

    topics: list[dict[str, object]] = []
    with temporary_qmd_http(True, "http://localhost:8181") as (_provider, qmd_http):
        for label, query in args.topic:
            payload = http_json("http://localhost:8181/query", {
                "searches": [{"type": "lex", "query": query}, {"type": "vec", "query": query}],
                "collections": ["data"],
                "limit": args.limit,
                "rerank": False,
            }, timeout=90)
            members = [
                {"file": str(hit.get("file", "")), "score": round(float(hit.get("score", 0)), 3)}
                for hit in payload.get("results", [])
                if "Knowledge/" in str(hit.get("file", ""))
            ]
            topics.append({
                "label": label,
                "query": query,
                "members": members,
                "independent_evidence": len({entry["file"] for entry in members}),
                "eligible_for_interest_page": len({entry["file"] for entry in members}) >= 2,
            })

    report = {
        "version": 1,
        "mode": "read-only-interest-taxonomy-test",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "qmd_http": qmd_http,
        "creation_policy": "Two independent source files make a proposed Interest topic eligible for human-reviewed page creation; this test never creates a page.",
        "topics": topics,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.run_id}.json"
    markdown_path = args.output_dir / f"{args.run_id}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Interest Topic Cluster Test", "", f"Generated: {report['generated_at']}", "", report["creation_policy"], ""]
    for topic in topics:
        lines.extend([f"## {topic['label']}", "", f"- Evidence files: {topic['independent_evidence']}", f"- Eligible for human-reviewed page creation: {'yes' if topic['eligible_for_interest_page'] else 'no'}", ""])
        lines.extend(f"- `{member['file']}` ({member['score']})" for member in topic["members"])
        if not topic["members"]:
            lines.append("- No matching Data/Knowledge source returned.")
        lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote Interest topic test to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
