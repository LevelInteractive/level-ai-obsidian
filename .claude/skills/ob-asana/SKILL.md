---
name: ob-asana
description: >
  Generates a daily Asana task report for the current user and saves it to Data/Work/Asana/
  in the Obsidian vault. Use when the user invokes /ob-asana, asks for "my Asana report",
  "what's on my plate in Asana", "Asana daily briefing", "what tasks are due today", or
  anything similar about getting a status overview of their Asana workload.
---

# ob-asana

Generate a daily Asana task briefing for the current user — overdue, due today, upcoming,
recently completed, and anything noteworthy — and save it as an immutable snapshot to
`Data/Work/Asana/` in the Obsidian vault.

## User context

- **Vault path**: the current working directory (the folder containing `CLAUDE.md`) - never hardcode a path; other users run this vault from a different location
- **Target folder**: `Data/Work/Asana/`
- **Today's date**: available from `currentDate` context (format: YYYY-MM-DD)

---

## Step 1 — Identify the current user

Call `mcp__6af4a118-cca0-4888-af60-81bf3ae19f1f__get_me` to get the current user's Asana
GID and display name. Store both — the GID is needed for searches, the name for the report.

---

## Step 2 — Fetch task data in parallel

Run all three fetches at the same time:

**A — Open tasks assigned to me:**
Call `mcp__6af4a118-cca0-4888-af60-81bf3ae19f1f__get_my_tasks` to retrieve all incomplete
tasks currently assigned to the user.

**B — Tasks recently completed by me (last 14 days):**
Call `mcp__6af4a118-cca0-4888-af60-81bf3ae19f1f__search_tasks` filtering by:
- `completed_by.any`: current user GID
- `completed_since`: 14 days before today (YYYY-MM-DD)
- `completed`: true

This captures tasks you finished that may have since been reassigned to a reviewer or
unassigned entirely — they would no longer appear in `get_my_tasks`.

**C — Task detail enrichment:**
For any tasks from A or B missing `due_on`, `projects`, or `notes`, call
`mcp__6af4a118-cca0-4888-af60-81bf3ae19f1f__get_task` in parallel to fill in the gaps.

---

## Step 3 — Classify open tasks

Using today's date from `currentDate`, bucket each open task from fetch A:

| Bucket | Condition |
|---|---|
| **Overdue** | `due_on` is set and is before today |
| **Due Today** | `due_on` equals today |
| **Due This Week** | `due_on` is within the next 7 days (not today) |
| **Upcoming** | `due_on` is more than 7 days out |
| **No Due Date** | `due_on` is null or absent |

Within each bucket, sort by `due_on` ascending (no-due-date tasks sorted by task name).

---

## Step 4 — Identify noteworthy items

Flag tasks as noteworthy if any of the following are true — include a short reason tag:

- **Overdue by 3+ days** → tag `⚠️ significantly overdue`
- **Blocked** — task has unmet dependencies → tag `🔒 blocked`
- **High priority** — marked Priority: High or Urgent in Asana → tag `🔴 high priority`
- **Recently reassigned to reviewer** — appears in completed search (B) but not in assigned
  search (A), meaning it moved to someone else after your completion → tag `✅ pending review`

Collect all flagged tasks into an **Attention** section at the top of the report.

---

## Step 5 — Build the report

Use this exact markdown structure:

```markdown
---
title: Asana Daily Report — YYYY-MM-DD
type: work-snapshot
source: asana
created: YYYY-MM-DD
tags:
  - asana
  - daily-report
---

# Asana Daily Report — Month DD, YYYY

*Generated YYYY-MM-DD. Open tasks assigned to me + tasks completed by me in the last 14 days.*

---

## ⚡ Attention

> Items that need eyes on them today.

- **Task Title** — [Open in Asana](<permalink_url>) `⚠️ significantly overdue` `🔴 high priority`
  - **Project:** Project Name | **Due:** YYYY-MM-DD

*(omit this section entirely if nothing is flagged)*

---

## 🔴 Overdue

- **Task Title** — [Open in Asana](<permalink_url>)
  - **Project:** Project Name | **Due:** YYYY-MM-DD | **X days overdue**

*(or: "No overdue tasks.")*

---

## 📅 Due Today

- **Task Title** — [Open in Asana](<permalink_url>)
  - **Project:** Project Name

*(or: "Nothing due today.")*

---

## 📆 Due This Week

- **Task Title** — [Open in Asana](<permalink_url>)
  - **Project:** Project Name | **Due:** YYYY-MM-DD

*(or: "Nothing due this week.")*

---

## 🗓️ Upcoming

- **Task Title** — [Open in Asana](<permalink_url>)
  - **Project:** Project Name | **Due:** YYYY-MM-DD

*(or: "No upcoming tasks with due dates.")*

---

## 📋 No Due Date

- **Task Title** — [Open in Asana](<permalink_url>)
  - **Project:** Project Name

*(omit this section if empty)*

---

## ✅ Recently Completed (last 14 days)

- **Task Title** — [Open in Asana](<permalink_url>) `✅ pending review`
  - **Project:** Project Name | **Completed:** YYYY-MM-DD

*(or: "No tasks completed in the last 14 days.")*

---

*Summary: X overdue · X due today · X due this week · X upcoming · X no due date · X recently completed*
```

Rules:
- Omit **Attention** entirely if nothing is flagged.
- Omit **No Due Date** entirely if empty.
- The `⚠️ significantly overdue` tag should include the count: `⚠️ 5 days overdue`.
- If a task belongs to multiple projects, list them comma-separated.
- Truncate `notes` — do not include task notes in the report; the report is a status view, not a detail dump.

---

## Step 6 — Save to the vault

Filename: `Data/Work/Asana/asana-YYYY-MM-DD.md` (today's date from `currentDate`).

If a file with that name already exists, overwrite it — re-running the skill refreshes today's snapshot.

Write using the Obsidian MCP:
```
obsidian vault="<vault name>" create path="Data/Work/Asana/asana-YYYY-MM-DD.md" content="..."
```

---

## Step 7 — Confirm and display

After saving, tell the user:

> Asana daily report saved to `Data/Work/Asana/asana-YYYY-MM-DD.md`.
> **X overdue · X due today · X due this week · X upcoming · X recently completed**

Then display the full report inline in chat so the user can review it without opening the file.
If there are overdue tasks or high-priority flagged items, call those out explicitly before
showing the report.
