"""Regression tests for deterministic graph-view synchronization."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sync_wiki_graph import audit_tags, sync


CONFIG = """# Config
## Controlled vocabulary
| Category | Tags |
|---|---|
| Status | `active` `at-risk` `watch` `resolved` `deprecated` |
| Themes | `signal` `uncategorized` |
## Graph color groups
### Canonical color table
| Group | Query | Hex | Purpose |
|---|---|---|---|
| Tools | `path:Level Knowledge/tools` | `#112233` | Tools |
| `#signal` | `tag:#signal` | `#445566` | Theme |
| `at-risk` | `tag:#at-risk` | `#778899` | Status |
| `watch` | `tag:#watch` | `#8899aa` | Status |
| `deprecated` | `tag:#deprecated` | `#99aabb` | Status |
| `resolved` | `tag:#resolved` | `#aabbcc` | Status |
### New domain palette
`#cc4dcc`, `#4dcccc`
### Theme tag color discovery
Explicit audit only.
"""


class GraphSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".config").mkdir()
        (self.root / ".obsidian").mkdir()
        (self.root / "Level Knowledge" / "tools").mkdir(parents=True)
        (self.root / "Level Knowledge" / "index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "Level Knowledge" / "log.md").write_text("# Log\n", encoding="utf-8")
        (self.root / ".config" / "tagging.md").write_text(CONFIG, encoding="utf-8")
        (self.root / ".obsidian" / "graph.json").write_text(json.dumps({"showTags": True, "colorGroups": []}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_dry_run_does_not_write_and_detects_groups(self) -> None:
        before = (self.root / ".obsidian" / "graph.json").read_text(encoding="utf-8")
        result = sync(self.root, dry_run=True)
        self.assertTrue(result["changed"])
        self.assertIn("path:Level Knowledge/tools", result["added"])
        self.assertEqual(before, (self.root / ".obsidian" / "graph.json").read_text(encoding="utf-8"))

    def test_noop_preserves_graph_and_log(self) -> None:
        sync(self.root)
        graph_before = (self.root / ".obsidian" / "graph.json").read_text(encoding="utf-8")
        log_before = (self.root / "Level Knowledge" / "log.md").read_text(encoding="utf-8")
        result = sync(self.root)
        self.assertFalse(result["changed"])
        self.assertEqual(graph_before, (self.root / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(log_before, (self.root / "Level Knowledge" / "log.md").read_text(encoding="utf-8"))

    def test_removes_obsolete_group_but_preserves_manual_group_and_settings(self) -> None:
        graph_path = self.root / ".obsidian" / "graph.json"
        graph_path.write_text(json.dumps({
            "showTags": True,
            "scale": 1.25,
            "colorGroups": [
                {"query": "path:Level Knowledge/deleted-domain", "color": {"a": 1, "rgb": 1}},
                {"query": "tag:#personal-manual", "color": {"a": 1, "rgb": 2}},
            ],
        }), encoding="utf-8")
        sync(self.root)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        queries = [item["query"] for item in graph["colorGroups"]]
        self.assertNotIn("path:Level Knowledge/deleted-domain", queries)
        self.assertIn("tag:#personal-manual", queries)
        self.assertTrue(graph["showTags"])
        self.assertEqual(graph["scale"], 1.25)

    def test_new_domain_and_tag_audit(self) -> None:
        (self.root / "Level Knowledge" / "analytics").mkdir()
        for index in range(3):
            (self.root / "Level Knowledge" / "tools" / f"page-{index}.md").write_text(
                "---\ntags:\n  - uncategorized\n---\n# Page\n", encoding="utf-8"
            )
        audit = audit_tags(self.root, (self.root / ".config" / "tagging.md").read_text(encoding="utf-8"))
        self.assertEqual(audit["candidates"], [{"tag": "uncategorized", "pages": 3}])
        result = sync(self.root)
        self.assertEqual(result["new_domains"], [{"domain": "analytics", "hex": "#cc4dcc"}])
        self.assertIn("path:Level Knowledge/analytics", (self.root / ".config" / "tagging.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
