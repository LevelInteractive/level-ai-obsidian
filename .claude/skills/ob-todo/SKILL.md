---
name: ob-todo
description: >
  Generates a daily and a weekly to-do list by combining Asana tasks due today/this week,
  actionable items pulled from recent meeting notes and wiki pages, and unchecked items
  carried over from the previous list. Every item gets a priority label. Saves both to
  Level Playbook/planning/. Use when the user invokes /ob-todo, asks for "my to-do list",
  "what should I work on today", "what's on my plate this week", "daily/weekly todo",
  "generate my todos", or anything similar about planning near-term work.
---

# ob-todo

Generate a **daily** and a **weekly** to-do list for the current user by merging Asana tasks,
action items surfaced from recent meetings and wiki pages, and any unchecked items carried
over from the previous list. Every item is labeled with a priority. Save both as living
checklists to `Level Playbook/planning/`.

## User context

- **Vault path**: the current working directory (the folder containing `CLAUDE.md`) - never hardcode a path; other users run this vault from a different location
- **Target folder**: `Level Playbook/planning/`
- **User's name in vault sources**: derive from Asana `get_me` / vault context - never hardcode a name
- **Today's date**: available from `currentDate` context (format: YYYY-MM-DD)

---

## Step 1 — Establish date context

- `today` = today's date (YYYY-MM-DD) from `currentDate`.
- `weekStart` = the Monday on or before `today` (if today is Monday, `weekStart` = today).
- `yesterday` = today minus 1 day.
- `weekLookbackStart` = today minus 6 days (7-day trailing window, inclusive of today).

---

## Step 2 — Gather source data

Run these in parallel.

**A — Asana tasks:**
Call `mcp__claude_ai_Advanced_Asana__get_me` to get the current user's GID, then
`mcp__claude_ai_Advanced_Asana__get_my_tasks` to get all open tasks assigned to them. For any
task missing `due_on`, `permalink_url`, or priority info, enrich with
`mcp__claude_ai_Advanced_Asana__get_task`.

Classify each task by `due_on`:
| Bucket | Condition |
|---|---|
| Overdue | before `today` |
| Due Today | equals `today` |
| Due This Week | within `[today, weekStart + 6]` |

**B — Meeting action items:**
Glob `Data/Meetings/*.md`. Filter to files whose leading `YYYY-MM-DD` date is:
- `>= yesterday` for the daily list
- `>= weekLookbackStart` for the weekly list

For each matching file, read the `## Next Steps` section and extract bullet items under any
subheading that is the user's name, or a shared heading like "Team" / "Collaboration"
/ "All". Skip items assigned only to other named individuals. Record each item's text and the
source filename (for a `[[wikilink]]` back to it).

**C — Wiki open items:**
Glob `Level Knowledge/**/*.md`. Filter to pages whose frontmatter `last_updated` falls in the
same window as above (yesterday-forward for daily, 7-day trailing for weekly). Read each
match's `## Open Questions` section (where present) and extract bullets that read as an
action the user could take (mentions like "confirm", "decide", "TBD", "to be designed/decided",
"follow up", "verify") — skip purely descriptive open questions with no clear next action.
Record each item's text and the source page (for a `[[wikilink]]`).

---

## Step 3 — Assign a priority to every item

Label every item — Asana, meeting, wiki, and carried-over alike — with exactly one of:

| Label | Meaning |
|---|---|
| 🔴 High | Overdue, due today, explicitly urgent/blocking, or flagged high-priority in Asana |
| 🟡 Medium | Due this week, a normal meeting/wiki action item, or Asana priority "Medium" (default when nothing else signals priority) |
| 🟢 Low | No due date, exploratory/nice-to-have language ("consider", "eventually", "if time allows"), or Asana priority "Low" |

Rules for assigning it:
- **Asana tasks** — use the task's own Asana `priority` custom field if set (High/Medium/Low
  map directly). If not set, derive from the due-date bucket: Overdue → 🔴 High, Due Today →
  🔴 High, Due This Week → 🟡 Medium, no due date → 🟢 Low.
- **Meeting action items** — 🔴 High if the surrounding text signals urgency or a blocker
  ("before Thursday", "blocking", "ASAP", "urgent"); 🟢 Low if it reads as exploratory or
  optional; otherwise 🟡 Medium.
- **Wiki open items** — 🟡 Medium by default; 🔴 High only if the page itself is tagged
  urgent/blocking or the item blocks a near-term deliverable; 🟢 Low for open questions with
  no concrete deadline pressure.
- **Carried-over items** — keep their original priority label from the previous list. If a
  carried item is now overdue relative to its original context, bump it to 🔴 High.

Within each section, sort items 🔴 High → 🟡 Medium → 🟢 Low.

---

## Step 4 — Load carryover from the previous list

Both lists live at a **fixed filename** that gets overwritten every run (see Step 7) — there is
no dated filename to look for. Instead, use each file's own frontmatter `date` to tell whether
its contents are stale (the previous period's list) or already refreshed today:

**Daily:** Read `Level Playbook/planning/daily.md` if it exists.
- If its frontmatter `date` is **before** `today`, it's the previous day's list — extract every
  unchecked `- [ ]` line (keeping its priority label and source attribution) as carryover. This
  file is about to be overwritten with today's list.
- If its frontmatter `date` **equals** `today`, the skill already ran today — treat this as a
  same-day refresh instead of a carryover: fold its unchecked items in as ordinary items to
  preserve (no separate "Carried Over" section needed) rather than duplicating them.

**Weekly:** Same logic against `Level Playbook/planning/weekly.md`, comparing its frontmatter
`date` to `weekStart` instead of `today`.

In both cases, drop any carried item that's a near-duplicate (case-insensitive substring match)
of an item freshly gathered in Step 2 — keep the fresher version instead.

If the file doesn't exist yet (first run), skip carryover — the section is simply omitted.

---

## Step 5 — Build the daily note

```markdown
---
type: todo
scope: daily
date: YYYY-MM-DD
tags:
  - todo
  - daily
---

# Daily To-Do — Month DD, YYYY

*Generated YYYY-MM-DD from Asana, recent meeting/wiki action items, and carried-over tasks.*

---

## 🔁 Carried Over

- [ ] 🔴 Item text — *carried over from yesterday*

*(omit this section entirely if there's nothing to carry over)*

## Asana

- [ ] 🔴 Task Title — [Open in Asana](<permalink_url>) *(overdue X days)*
- [ ] 🔴 Task Title — [Open in Asana](<permalink_url>) *(due today)*

*(or "No Asana tasks due today.")*

## Meeting Action Items

- [ ] 🟡 Item text — *from [[meeting-filename]]*

*(omit if none found)*

## Open Items from Wiki

- [ ] 🟢 Item text — *from [[wiki-page]]*

*(omit if none found)*

---

*Check items off as you go — anything left unchecked rolls into tomorrow's list.*
```

Within each section, list items sorted by priority (🔴 → 🟡 → 🟢) as established in Step 3.

---

## Step 6 — Build the weekly note

Same structure, with these differences:

- Frontmatter: `scope: weekly`, `date: <weekStart>`, `tags: [todo, weekly]`
- Title: `# Weekly To-Do — Week of Month DD, YYYY` (using `weekStart`)
- Carried Over section pulls from the previous week's contents of `weekly.md` (Step 4)
- Asana section is titled **Asana (this week)** and includes overdue + due-this-week tasks
  together, each still labeled 🔴/🟡/🟢 and tagged with its due date or "overdue X days"
- Meeting/wiki sections use the 7-day trailing window from Step 2

---

## Step 7 — Save both files

Both files use a **fixed filename** — never date-stamped — so the folder always holds exactly
one daily file and one weekly file, refreshed in place:
- `Level Playbook/planning/daily.md`
- `Level Playbook/planning/weekly.md`

Always overwrite, regardless of whether the existing file is today's/this week's or stale from
a previous period — staleness only matters for the carryover read in Step 4, which happens
*before* this overwrite.

Write using the Obsidian MCP:
```
obsidian vault="<vault name>" create path="Level Playbook/planning/daily.md" content="..."
obsidian vault="<vault name>" create path="Level Playbook/planning/weekly.md" content="..."
```

---

## Step 8 — Confirm and display

Tell the user:

> Daily to-do saved to `Level Playbook/planning/daily.md` (**X** items — **A** high · **B** medium · **C** low, **Y** carried over).
> Weekly to-do saved to `Level Playbook/planning/weekly.md` (**X** items — **A** high · **B** medium · **C** low, **Y** carried over).

Then display both lists inline in chat so the user can review without opening the files.
