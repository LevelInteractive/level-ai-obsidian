---
name: wiki-graph-sync
description: >
  Syncs .obsidian/graph.json color groups against the canonical definitions in CLAUDE.md
  and the current Level Knowledge/ domain structure. Adds missing groups, updates drifted
  colors, removes obsolete groups, and logs the operation to Level Knowledge/log.md.
  Use after wiki structure changes or as a final step in ob-wiki-update.
model: claude-sonnet-5
effort: low
tools:
  - Read
  - Write
  - Edit
  - Glob
---

Sync `.obsidian/graph.json` color groups with the canonical definitions in `CLAUDE.md` and the current wiki domain structure.

## Step 1 — Read current state

Read these files:
- `.obsidian/graph.json` — extract the current `colorGroups` array (may be empty)
- `.claude/tagging.md` — find the "Canonical color table" under "Graph color groups"; parse every row into `{query, hex, purpose}`; also extract the new domain palette hex list

## Step 2 — Discover current domains

Use Glob with pattern `Level Knowledge/*/` to find all top-level domain folders. The domain name is the folder basename (e.g., `clients`, `team`, `decisions`). Ignore `index.md` and `log.md` — those are files, not folders.

Compare discovered domains against the canonical table from Step 1. Any domain folder whose path (`Level Knowledge/<domain>`) is not covered by an existing `path:`-based canonical entry is a **new domain** — assign it the next unused hex color from the new domain palette, cycling back to the start if exhausted.

## Step 2b — Discover uncolored tags and assign colors

Scan all wiki pages for tags in active use with no color group in the canonical table, then assign colors and write them into CLAUDE.md.

**Discover:**
1. Use Glob to find all `.md` files under `Level Knowledge/` (exclude `index.md` and `log.md`)
2. Read the `tags:` frontmatter list from each page
3. Count how many pages use each unique tag
4. Compare the full tag set against the canonical table from Step 1 — a tag is "uncolored" if no `tag:#<name>` entry exists in the canonical table
5. Keep only uncolored tags used on **3 or more pages**, sorted by count descending

**Skip status tags** — `active`, `at-risk`, `watch`, `resolved`, `deprecated` are always in the canonical table as status overrides; do not re-add them as theme groups.

**Assign colors:**

For each qualifying uncolored tag, assign the next unused hex from the new domain palette in CLAUDE.md (`#cc7a4d`, `#cc4dcc`, `#4dcccc`, `#7acc4d`). Skip any palette color already in use anywhere in the canonical table. If all palette colors are exhausted, generate a new hex that is visually distinct from all existing canonical colors (aim for at least 60 hue degrees of separation, medium-to-high saturation).

**Update CLAUDE.md:**

Add each new tag entry as a new row in the canonical color table, immediately before the `at-risk` status override row. Format:

```
| `#tag-name` | `tag:#tag-name` | `#hexcolor` | Theme — N pages |
```

Write the updated `.claude/tagging.md` back to disk. The canonical table is now authoritative for the new tags — Step 3 will pick them up automatically.

## Step 3 — Build the canonical colorGroups array

Construct the expected array in this exact order:

**1. Domain groups** — one entry per discovered domain folder:
```json
{
  "query": "path:Level Knowledge/<domain>",
  "color": { "a": 1, "rgb": <decimal> }
}
```

**2. Theme tag groups** — any `tag:`-based entries in the canonical table that are not status overrides (i.e., not `at-risk`, `watch`, `deprecated`, `resolved`). These come after domain groups so they override domain color for pages that carry a theme tag:
```json
{ "query": "tag:#signal",        "color": { "a": 1, "rgb": <decimal> } }
{ "query": "tag:#edu-migration", "color": { "a": 1, "rgb": <decimal> } }
```

**3. Status override groups** — always include all four, in this order:
```json
{ "query": "tag:#at-risk",    "color": { "a": 1, "rgb": <decimal> } }
{ "query": "tag:#watch",      "color": { "a": 1, "rgb": <decimal> } }
{ "query": "tag:#deprecated", "color": { "a": 1, "rgb": <decimal> } }
{ "query": "tag:#resolved",   "color": { "a": 1, "rgb": <decimal> } }
```

Status overrides must come **last** — Obsidian applies the last matching group, so this order makes status colors take precedence over both domain and theme colors.

## Step 4 — Convert hex to decimal RGB

For each group, convert the hex color string to Obsidian's decimal `rgb` integer:

```
strip '#' → parse as base-16 integer
```

Example: `#4d8fcc` → `0x4d8fcc` → `5083084`

Check: `parseInt("4d8fcc", 16) === 5083084`

The `a` (opacity) field is always `1`.

## Step 5 — Diff current vs canonical

Compare the canonical array (Step 3) against the current `colorGroups` from Step 1.

Classify each difference:
- **Missing** — a canonical group has no matching entry in current graph.json (match by query string)
- **Drifted** — query matches but color `rgb` value differs
- **Obsolete** — a group in graph.json has a `path:`-based query pointing to a domain folder that no longer exists in `Level Knowledge/`
- **New domain** — a folder was found with no canonical entry; auto-assigned a palette color (note the assignment)

If there are **no differences**, skip to Step 7 and report "in sync — no changes made."

## Step 6 — Write updated graph.json

Read `.obsidian/graph.json` in full. Replace only the `colorGroups` value with the canonical array from Step 3. Leave every other field (`search`, `showTags`, `scale`, `centerStrength`, `repelStrength`, `linkStrength`, `linkDistance`, etc.) exactly as-is.

Write the full updated JSON back to `.obsidian/graph.json` using 2-space indentation, matching Obsidian's native formatting style.

## Step 7 — Append to log.md

Append one row to `Level Knowledge/log.md` using the same pipe-delimited format as existing rows:

```
| <TODAY> | Graph Sync | — | — | <summary of what changed> |
```

Summary examples:
- `In sync — no changes`
- `Added 6 domain groups, 4 status overrides`
- `Updated clients color (#4d8fcc → #3d7fbc); added new domain: organization`

## Step 8 — Report to the user

Summarize concisely:
- Total groups now in graph.json
- What changed: added / updated / removed — or "already in sync"
- Any new domains auto-assigned a palette color (name the color so the user can update CLAUDE.md if they want a different one)
- Any new tag color groups added in Step 2b — list each with its assigned color and page count:

```
New tag color groups added to canonical table and graph.json:
  #signal — #cc4dcc (18 pages)
  #edu-migration — #4dcccc (10 pages)
  ...
```

If no new tags were added, omit this section.

## Known caveat — Obsidian may overwrite this file

Obsidian keeps the graph view's settings in memory once the app is running and only re-reads `.obsidian/graph.json` from disk on startup (or when the graph pane is freshly opened). If the app is already open when this agent edits the file directly, Obsidian doesn't notice — it still holds its old in-memory state. Touching any graph setting, closing the graph tab, or quitting the app then writes that stale in-memory state back to disk, clobbering the colors this agent just wrote (and sometimes resetting `showTags`/`showAttachments`/slider values too).

Mention this in the Step 8 report: tell the user to fully restart Obsidian (or close/reopen the graph view before touching any other graph settings) so it reloads the file from disk instead of overwriting it.

## Rules

- Preserve all non-`colorGroups` fields in graph.json exactly. Never touch display settings, forces, scale, or any other key.
- Only remove a group if it has a `path:`-based query pointing to a folder that no longer exists AND has no canonical entry. Never remove status override groups. Never remove groups the user may have added manually that don't conflict with canonical entries.
- If the new domain palette is exhausted, cycle back from the start.
- Do not modify any wiki page or raw source file. This agent writes only `graph.json` and appends to `log.md`.
