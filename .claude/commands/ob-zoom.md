Search for today's Zoom meetings that have AI summaries available. Detect the user's local timezone dynamically.

Steps:
1. Run this Python 3 snippet in bash to get today's local date, timezone name, and UTC search bounds:

```
python3 -c "
from datetime import datetime, timezone
now = datetime.now().astimezone()
tz_name = now.strftime('%Z')
local_date = now.strftime('%Y-%m-%d')
start = now.replace(hour=0, minute=0, second=0, microsecond=0)
end = now.replace(hour=23, minute=59, second=59, microsecond=0)
print('DATE=' + local_date)
print('TZ=' + tz_name)
print('FROM=' + start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
print('TO=' + end.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
"
```

Use the FROM and TO values as the search range. Use the Zoom search_meetings MCP tool to find meetings in that range. Filter for ones where has_summary is true and has_summary_permission is true. Use TZ_NAME when displaying times to the user and in the written notes.

2. If no meetings with summaries are found, tell the user and stop.

3. Present the list of meetings with summaries to the user using AskUserQuestion, showing the topic and start time for each. Allow multi-select so they can pick one or more to export. Include a "None" option to cancel.

4. For each selected meeting, call get_meeting_assets using the meeting_uuid, then write a markdown note to Data\Meetings\ (relative to the vault root - the current working directory) using this format:

```
---
date: YYYY-MM-DD
topic: <topic>
attendees: [name1, name2, ...]
tags: [zoom, meeting]
---

# <topic> — YYYY-MM-DD

**Time:** HH:MM – HH:MM <TZ_NAME>
**Attendees:** name1, name2, ...

## Summary

<quick_recap text from meeting_summary>

## Full Notes

<summary_markdown or full summary text>

## Next Steps

<next_steps as bullet list>
```

Name the file: YYYY-MM-DD <topic>.md using the meeting's actual start_time date (not today's UTC date). Sanitize any special characters in the topic for the filename.
Create the Data\Meetings folder if it doesn't exist.

5. Tell the user which files were created and their paths in the vault.
