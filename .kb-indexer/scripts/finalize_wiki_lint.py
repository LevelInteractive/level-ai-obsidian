"""Merge deterministic and bounded semantic lint findings into stable outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from prepare_wiki_lint import DEFAULT_CACHE, RUNS, VAULT_ROOT, WIKI_ROOT, sha256

INDEXER_ROOT = Path(__file__).resolve().parent.parent
CURRENT = INDEXER_ROOT / "metadata" / "reports" / "current"
PLAYBOOK = VAULT_ROOT / "Level Playbook" / "wiki-lint"
ACTIVE_JSON = CURRENT / "wiki-lint-active.json"
ACTIVE_MD = CURRENT / "wiki-lint-active.md"
PLAN_JSON = CURRENT / "wiki-lint-plan.json"
PLAN_MD = CURRENT / "wiki-lint-plan.md"


def load(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def identity(finding: dict[str, Any]) -> str:
    raw = json.dumps({key: finding.get(key) for key in ("category", "page", "detail", "target")}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def severity_rank(value: str) -> int:
    return {"P1-critical": 1, "P2-warning": 2, "P3-info": 3}.get(value, 4)


def initial_cache() -> dict[str, Any]:
    pages: dict[str, Any] = {}
    for path in WIKI_ROOT.rglob("*.md"):
        if path.name in {"index.md", "log.md"}:
            continue
        relative = path.relative_to(VAULT_ROOT).as_posix()
        pages[relative] = {
            "sha256": sha256(path), "last_semantic_lint": None,
            "semantic_status": "unreviewed", "claims": [],
            "references": [], "conflicts": [], "archived_claims": [],
        }
    return {"version": 2, "last_run": None, "pages": pages}


def markdown_active(findings: list[dict[str, Any]], run_id: str) -> str:
    lines = [
        "---", "title: Wiki Linter — Active Issues", "type: lint-active",
        f"last_run: {date.today().isoformat()}", f"issues_found: {len(findings)}", "---",
        "# Wiki Linter — Active Issues", "", f"*Run: {run_id} | Issues: {len(findings)}*", "",
    ]
    if not findings:
        lines.append("*No active issues.*")
    for finding in findings:
        page = finding.get("page") or "vault metadata"
        lines.append(
            f"- [{finding['severity']}] {finding['category']} — {page} — {finding['detail']} "
            f"*(open since: {finding['open_since']}; id: {finding['id']})*"
        )
    return "\n".join(lines) + "\n"


def action_for(finding: dict[str, Any], number: int) -> dict[str, Any]:
    mechanical = finding["category"] in {"FRONTMATTER", "REFERENCE", "MISSING-PAGE", "ORPHAN", "STALE", "CONFIDENCE-DECAY"}
    action = {
        "number": number, "issue_id": finding["id"], "priority": finding["severity"],
        "category": finding["category"], "page": finding.get("page"),
        "detail": finding["detail"], "requires_evidence_review": not mechanical,
        "suggested_fix": finding.get("suggested_fix") or (
            "Apply the exact mechanical correction and retain protected Notes." if mechanical
            else "Read the packet-listed evidence, decide the claim, and update only the approved page section."
        ),
    }
    if finding["category"] == "ORPHAN" and finding.get("suggested_inbound_page"):
        action.update({
            "inbound_page": finding["suggested_inbound_page"],
            "inbound_section": finding.get("suggested_inbound_section"),
            "suggested_link": finding.get("suggested_link"),
            "suggestion_reason": finding.get("suggestion_reason"),
            "suggested_fix": (
                f"Add {finding.get('suggested_link')} to {finding['suggested_inbound_page']} "
                f"under {finding.get('suggested_inbound_section')}; retain the catalog's existing format."
            ),
        })
    return action


def markdown_plan(actions: list[dict[str, Any]], run_id: str) -> str:
    lines = [f"# Wiki Contradiction Plan — {run_id}", ""]
    if not actions:
        return "\n".join(lines + ["*No actionable issues.*", ""])
    for action in actions:
        target = action["page"] or "vault metadata"
        review = "evidence review required" if action["requires_evidence_review"] else "mechanical"
        lines.extend([
            f"## [{action['number']}] [{action['priority']}] {action['category']} — {target}",
            f"- Issue: {action['detail']}", f"- Fix: {action['suggested_fix']}", f"- Mode: {review}", "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize bounded wiki-lint results and produce a deterministic approval plan.")
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--semantic-review", type=Path, help="Optional bounded reviewer JSON; absent means deterministic-only.")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()
    scope = load(args.scope, None)
    if not isinstance(scope, dict) or scope.get("version") != 1:
        parser.error("scope must be a valid version 1 lint packet")
    review = load(args.semantic_review, {"version": 1, "pages": {}, "findings": []}) if args.semantic_review else {"version": 1, "pages": {}, "findings": []}
    if review.get("version") != 1 or review.get("run_id", scope["run_id"]) != scope["run_id"]:
        parser.error("semantic review must match scope run_id")
    cache = load(args.cache, initial_cache())
    if cache.get("version") != 2 or not isinstance(cache.get("pages"), dict):
        cache = initial_cache()
    for path in list(cache["pages"]):
        if not (VAULT_ROOT / path).is_file():
            del cache["pages"][path]
    for item in scope.get("pages_to_read", []):
        path = item["path"]
        entry = cache["pages"].setdefault(path, {"claims": [], "semantic_status": "unreviewed"})
        entry["sha256"] = item["sha256"]
    for path, entry in review.get("pages", {}).items():
        if path not in cache["pages"] or not isinstance(entry, dict):
            continue
        cache["pages"][path].update({
            "sha256": entry.get("sha256", cache["pages"][path].get("sha256")),
            "last_semantic_lint": date.today().isoformat(), "semantic_status": "reviewed",
            "claims": entry.get("claims", []), "references": entry.get("references", []),
            "conflicts": entry.get("conflicts", []), "archived_claims": entry.get("archived_claims", []),
        })
    cache["last_run"] = date.today().isoformat()
    reviewed = sum(1 for entry in cache["pages"].values() if entry.get("semantic_status") == "reviewed")
    cache["coverage"] = {"reviewed": reviewed, "total": len(cache["pages"])}

    prior = load(ACTIVE_JSON, {"findings": []})
    prior_dates = {item.get("id"): item.get("open_since") for item in prior.get("findings", []) if item.get("id")}
    findings = [item for item in scope.get("mechanical_findings", []) + review.get("findings", []) if isinstance(item, dict)]
    unique: dict[str, dict[str, Any]] = {}
    for finding in findings:
        finding = dict(finding)
        finding.setdefault("severity", "P3-info")
        finding.setdefault("category", "UNKNOWN")
        finding.setdefault("detail", "no detail")
        finding["id"] = finding.get("id") or identity(finding)
        finding["open_since"] = prior_dates.get(finding["id"]) or date.today().isoformat()
        unique[finding["id"]] = finding
    merged = sorted(unique.values(), key=lambda item: (severity_rank(item["severity"]), item["category"], str(item.get("page"))))
    actions = [action_for(item, index) for index, item in enumerate(merged, 1)]
    run_dir = args.scope.parent
    final = {"version": 1, "run_id": scope["run_id"], "generated_at": datetime.now().isoformat(),
             "scope": str(args.scope), "findings": merged, "actions": actions, "metrics": scope.get("metrics", {}),
             "cache_coverage": cache["coverage"]}
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    run_dir.joinpath("final.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    CURRENT.mkdir(parents=True, exist_ok=True)
    ACTIVE_JSON.write_text(json.dumps({"version": 1, "run_id": scope["run_id"], "findings": merged}, indent=2) + "\n", encoding="utf-8")
    ACTIVE_MD.write_text(markdown_active(merged, scope["run_id"]), encoding="utf-8")
    PLAN_JSON.write_text(json.dumps({"version": 1, "run_id": scope["run_id"], "actions": actions}, indent=2) + "\n", encoding="utf-8")
    PLAN_MD.write_text(markdown_plan(actions, scope["run_id"]), encoding="utf-8")
    PLAYBOOK.mkdir(parents=True, exist_ok=True)
    report = PLAYBOOK / f"wiki-lint-{date.today().isoformat()}.md"
    report.write_text("# Wiki Lint Report\n\n" + markdown_active(merged, scope["run_id"]), encoding="utf-8")
    print(f"Finalized {len(merged)} findings; semantic coverage {reviewed}/{len(cache['pages'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
