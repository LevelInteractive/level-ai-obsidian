---
name: ob-slack-activity
description: >
  Pulls a daily Slack activity summary for the current user and saves it to their Obsidian vault.
  Use this skill whenever the user invokes /ob-slack-activity, asks to "log today's Slack activity",
  "save my Slack summary", "pull my Slack messages to Obsidian", or anything similar about
  capturing/logging daily Slack activity into the vault. Searches for messages sent, mentions
  received, and @here/@channel pings — then appends a formatted daily entry to a monthly file
  under Data/Work/Slack Activity/ in the vault.
---

# ob-slack-activity

Fetch today's Slack activity for the current user and save a formatted daily entry to the Obsidian vault.

## User context

- **Slack user ID**: Read from the `mcp__d760c211-5049-4da3-923c-4089d577be42__slack_search_public_and_private` tool description — it contains the phrase `"Current logged in user's user_id is UXXXXXXXXX"`. Extract that ID and use it for all queries. Do not hardcode any user ID.
- **Vault path**: the current working directory (the folder containing `CLAUDE.md`) - never hardcode a path; other users run this vault from a different location
- **Obsidian CLI format**: `obsidian vault="<vault name>" <command>` (vault name = the folder name of this vault; never hardcode)
- **Timezone**: US Eastern
- **Today's date**: available from `currentDate` context (format: YYYY-MM-DD)

## Step 1 — Run nine Slack searches in parallel

Use `mcp__d760c211-5049-4da3-923c-4089d577be42__slack_search_public_and_private` for all nine searches. Run them at the same time (parallel tool calls in a single response). Replace `UID` below with the current user's ID extracted from the tool description.

**Search A — Messages sent by the current user:**
```
query: "from:<@UID> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: true
```

**Search B — Mentions of the current user:**
```
query: "<@UID> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search C — Channel-wide pings (@here / @channel):**
```
query: "@here OR @channel on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search D — #staff channel:**
```
query: "in:<#C03RPQG5C> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search E — #all-company-announcements channel:**
```
query: "in:<#C06D0V5GGFN> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search F — #sd-signal-operations channel:**
```
query: "in:<#C0A6R2DU5RV> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search G — #ai channel:**
```
query: "in:<#C05EGLGUY3Y> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search H — #del-crm-data-team-internal channel:**
```
query: "in:<#C0356R91Q1E> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

**Search I — #data-strength-program-ops channel:**
```
query: "in:<#C0AS3UNFXHB> on:YYYY-MM-DD"
sort: timestamp
sort_dir: asc
limit: 20
include_context: false
```

Replace `YYYY-MM-DD` with today's actual date from `currentDate`.

## Step 2 — Synthesize the summary

Group results into three sections. Be concise but informative — each bullet should give the reader enough context to know what happened without re-reading the original message.

### Messages Sent
List each conversation thread the user participated in. Group related messages into one bullet per thread/channel rather than listing every individual message. Include:
- Channel or DM partner name
- Time (HH:MM AM/PM ET)
- Brief summary of what was discussed or communicated

### Mentions
List each message where the user was @mentioned. Include:
- Who mentioned him
- Channel
- Time
- What they said/asked

If no mentions, write: *No mentions today.*

### Channel-wide Pings
List any @here or @channel messages from channels the user is in. Include:
- Who sent it
- Channel
- Time
- Brief content summary

If none, write: *No @here or @channel pings today.*

### Staff Channel
List all messages posted in #staff today. Include sender, time, and a one-line summary of each message.

If none, write: *No activity in #staff today.*

### Company Announcements
List all messages posted in #all-company-announcements today. Include sender, time, and a one-line summary.

If none, write: *No announcements today.*

### Signal Operations
List all messages posted in #sd-signal-operations today. Include sender, time, and a one-line summary of each message.

If none, write: *No activity in #sd-signal-operations today.*

### AI Channel
List all messages posted in #ai today. Include sender, time, and a one-line summary of each message.

If none, write: *No activity in #ai today.*

### CRM Data Team Internal
List all messages posted in #del-crm-data-team-internal today. Include sender, time, and a one-line summary of each message.

If none, write: *No activity in #del-crm-data-team-internal today.*

### Data Strength Program Ops
List all messages posted in #data-strength-program-ops today. Include sender, time, and a one-line summary of each message.

If none, write: *No activity in #data-strength-program-ops today.*

## Step 3 — Determine the target file

From `currentDate` (e.g., `2026-06-25`):
- **File name**: `Data/Work/Slack Activity/Slack Messages YYYY-MM` (no `.md` extension in CLI commands)
- **H1 heading**: `# Slack Activity — June 2026`
- **Day heading**: `## June 25, 2026`

## Step 4 — Save to Obsidian

### Check if the monthly file exists

Run:
```
obsidian vault="<vault name>" read file="Data/Work/Slack Activity/Slack Messages YYYY-MM"
```

**If the file does NOT exist**, create it with the full content (use `path=` not `name=` for nested paths):
```
obsidian vault="<vault name>" create path="Data/Work/Slack Activity/Slack Messages YYYY-MM.md" content="# Slack Activity — Month YYYY\n\n## Month DD, YYYY\n\n### Messages Sent\n...\n\n### Mentions\n...\n\n### Channel-wide Pings\n..."
```

**If the file EXISTS**, check whether today's heading (`## Month DD, YYYY`) is already present:
- If **not present**: append today's entry
  ```
  obsidian vault="<vault name>" append file="Data/Work/Slack Activity/Slack Messages YYYY-MM" content="\n## Month DD, YYYY\n\n### Messages Sent\n...\n\n### Mentions\n...\n\n### Channel-wide Pings\n..."
  ```
- If **already present**: tell the user the entry for today already exists and ask if they want to overwrite or skip.

## Step 5 — Confirm to the user

After saving, tell the user:

> Saved today's Slack activity to **Data/Work/Slack Activity/Slack Messages YYYY-MM.md** in your vault.
> - X messages sent across Y conversations
> - X mentions
> - X channel-wide pings
> - X staff channel messages
> - X company announcements
> - X #sd-signal-operations messages
> - X #ai messages
> - X #del-crm-data-team-internal messages
> - X #data-strength-program-ops messages

Then display the formatted summary in the chat as well so they can review it inline.

## Format template

Use this exact markdown structure for the daily entry:

```markdown
## June 25, 2026

### Messages Sent

- **#sd-signal-operations** (7:00 AM ET) — Announced CSU ensemble modeling MVP complete; noted codebase needs debugging. Shared raw performance metrics.
- **DM with Jordan Grace** (3:08–7:22 PM ET) — Discussed MSC HubSpot dbt model staging setup; shared Q3 Rocks draft.

### Mentions

- **Kyle Taljan** in #sd-signal-operations (10:34 AM ET) — Asked for clarification on whether the CSU model uses the 2-stage predict-to-enroll setup.

### Channel-wide Pings

*No @here or @channel pings today.*

### Staff Channel

- **Matt Rose** (9:15 AM ET) — Shared updated PTO policy for Q3.

### Company Announcements

*No announcements today.*

### Signal Operations

- **Kyle Taljan** (9:30 AM ET) — Praised the new 2-stage model PR.

### AI Channel

*No activity in #ai today.*

### CRM Data Team Internal

*No activity in #del-crm-data-team-internal today.*

### Data Strength Program Ops

*No activity in #data-strength-program-ops today.*
```

Keep entries tight. One bullet per thread, not per message. Prioritize signal over noise.
