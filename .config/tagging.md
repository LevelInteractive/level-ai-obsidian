# Wiki Tagging Configuration

Single source of truth for all tagging in this vault. Read by:
- `ob-wiki-update` — to apply tags to wiki pages and auto-create new theme tags
- `wiki-graph-sync` — to build `graph.json` color groups

---

## Controlled vocabulary

Tags handle cross-cutting concerns that folder structure and wikilinks cannot — status across all domains, client associations on non-client pages, and thematic groupings.

| Category | Tags |
|---|---|
| Status | `active` `at-risk` `watch` `resolved` `deprecated` |
| Clients | `csu` `nbu` `aim` `country-financial` |
| Themes | `signal` `data-quality` `gclid` `edu-migration` `sstm` `incrementality` |
| Temporal | `q3-2026` `launch-target` |

**Rules:**
- Status tags apply to any domain — every page should have at least one
- Client tags go on **non-client pages** that relate to a client (e.g., `signal-operations.md` gets `csu nbu`; the CSU overview page does not need `csu` — it lives in the `clients/csu/` folder)
- Theme tags cluster cross-cutting topics so they surface together regardless of domain
- Temporal tags flag time-sensitive items; remove when the deadline passes

**In YAML frontmatter:**
```yaml
tags:
  - active
  - csu
  - signal
  - launch-target
```

No `#` prefix in YAML — Obsidian adds it automatically.

### Auto-creating new theme tags

`ob-wiki-update` may expand the controlled vocabulary when a concept appears substantively in 3+ distinct source files in a single run. "Substantively" means the concept is a central topic in the file — not just mentioned in passing.

**If the threshold is met:**
1. Derive a tag name — lowercase, hyphen-separated, concise (e.g., `attribution`, `pulse`, `mmm`)
2. Append it to the appropriate category row in the table above
3. Apply the new tag to all pages updated in the run that are substantively about that theme
4. Report the new tag(s) in the run summary

**What can be auto-created:**
- **Theme tags** — yes (recurring technical or business topic: a tool, process, or methodology)
- **Client tags** — yes, only if a genuinely new client appears across 3+ sources with no existing client tag
- **Status tags** — no (fixed semantics; never auto-create)
- **Temporal tags** — no (manually managed; never auto-create)

If a concept appears in fewer than 3 sources, skip tagging for it — do not invent a tag.

---

### Dynamic taxonomy proposals

Folders describe durable subject scope; tags remain cross-cutting labels. New subjects are proposed from independent raw-source evidence and are never created from a single semantic hit.

- **Two independent source hashes**: eligible to propose a new page in the best-fitting existing domain.
- **Three related proposed pages** with the same broader subject: eligible to propose a new top-level folder.
- **Personal technical learning** belongs in `interests/`; work-applied software and workflows belong in `tools/`; work-applied models and methods belong in `analytics/`.
- Proposal records live in `.kb-indexer/metadata/`; actual page or folder creation happens only during an evidence-reviewed wiki update, which also registers it in `index.md`, `log.md`, and graph configuration.

Before either proposal is eligible, run an **independence check** against the current wiki:

1. Search existing page titles, summaries, and relevant body sections with lexical and semantic retrieval.
2. If an existing page already covers the subject at the proposed scope, update or extend that page instead.
3. A new page needs a distinct purpose, audience, lifecycle, or set of decisions that cannot be represented as a section of the existing page.
4. A new folder additionally needs three genuinely separate child-page scopes; three sources about one broad subject are not enough.
5. When the result is uncertain, record a review cue rather than creating a page or folder.

## Graph color groups

`wiki-graph-sync` builds `.obsidian/graph.json` from the canonical color table below. Three-tier system applied in order — Obsidian uses the **last matching group**, so later tiers override earlier ones:

1. **Domain groups** (path-based) — color pages by wiki domain folder
2. **Theme tag groups** (tag-based) — override domain color for pages carrying a theme tag
3. **Status override groups** (tag-based) — override everything for pages needing attention

**Color format:** Obsidian's `colorGroups` uses a decimal `rgb` integer. Convert hex: `parseInt(hex.replace('#',''), 16)`. Opacity `a` is always `1`.

### Canonical color table

| Group | Query | Hex | Purpose |
|---|---|---|---|
| Clients | `path:Level Knowledge/clients` | `#4d8fcc` | All client pages |
| Team | `path:Level Knowledge/team` | `#5ca65c` | Team member pages |
| Decisions | `path:Level Knowledge/decisions` | `#9a5cbf` | Decision records |
| Tools | `path:Level Knowledge/tools` | `#5ca6a6` | Tool pages |
| Analytics | `path:Level Knowledge/analytics` | `#c4607a` | Analytics and model pages |
| Processes | `path:Level Knowledge/processes` | `#c4a060` | Process documentation |
| Organization | `path:Level Knowledge/organization` | `#cc7a4d` | Culture, values, and policy pages |
| `#signal` | `tag:#signal` | `#cc4dcc` | Theme — 17 pages |
| `#data-quality` | `tag:#data-quality` | `#4dcccc` | Theme — 11 pages |
| `#gclid` | `tag:#gclid` | `#7acc4d` | Theme — 8 pages |
| `#edu-migration` | `tag:#edu-migration` | `#4d5acc` | Theme — 8 pages |
| `#sstm` | `tag:#sstm` | `#cc4daa` | Theme — 7 pages |
| `#csu` | `tag:#csu` | `#4dcc9a` | Theme — 4 pages |
| `#nbu` | `tag:#nbu` | `#d4cc4d` | Theme — 3 pages |
| `#q3-2026` | `tag:#q3-2026` | `#4db8cc` | Theme — 3 pages |
| `#launch-target` | `tag:#launch-target` | `#7a4dcc` | Theme — 3 pages |
| `at-risk` | `tag:#at-risk` | `#e05c5c` | At-risk items — overrides domain color |
| `watch` | `tag:#watch` | `#e09020` | Watch items — overrides domain color |
| `deprecated` | `tag:#deprecated` | `#888888` | Deprecated pages — overrides domain color |
| `resolved` | `tag:#resolved` | `#6aaa6a` | Resolved decisions and closed issues |

### New domain palette

Assign in order when a new top-level domain folder is added with no canonical entry above:
`#cc4dcc`, `#4dcccc`, `#7acc4d`, `#cc7a4d`

(Cycle back to the start if exhausted. Skip any color already in use in the canonical table.)

### Theme tag color audit

Routine `wiki-graph-sync` never creates tag colors or changes this table.
Run `sync_wiki_graph.py --audit-tags` explicitly to report controlled-vocabulary
tags used on 3+ wiki pages that lack a color group. Review the report, then add
an approved row manually before a later sync applies it:

```
| `#tag-name` | `tag:#tag-name` | `#hexcolor` | Theme — N pages |
```

Theme groups belong before the status override rows so status colors continue
to take precedence in Obsidian.
