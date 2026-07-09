---
name: ob-inbox
description: >
  Sorts miscellaneous files from Data/Inbox/ into the appropriate Data/ subfolder,
  creating new subfolders when needed. Use when the user invokes /ob-inbox, asks to
  "sort the inbox", "process inbox files", "triage the inbox", or anything similar
  about clearing or organizing items dropped in Data/Inbox/, or when the user asks to
  "sort raw data" or "organize raw data".
model: claude-haiku-4-5-20251001
tools:
  - Bash
  - Glob
  - Read
  - Write
  - Edit
---

Triage every file in `Data/Inbox/`, move each to the right place inside `Data/`, and leave the inbox empty.

**If invoked as a subagent** (e.g., from ob-wiki-update): skip user confirmation and proceed automatically through all steps.

## Shell commands

Use Bash (POSIX) commands for all file operations — the `Bash` tool runs Git Bash on Windows and native bash on Mac/Linux, so POSIX syntax works on all platforms. Do not use PowerShell commands.

## Vault context

- **Vault path**: Derive from the current working directory — it is the repository root (the folder containing `CLAUDE.md`). Do not hardcode any path.
- **Inbox path**: `Data/Inbox/` relative to the vault root
- **Today's date**: available from `currentDate` context (format: YYYY-MM-DD)

## Existing Data/ subfolders (authoritative list)

| Folder | What belongs here |
|---|---|
| `Data/Claude/` | Claude session transcripts |
| `Data/Daily/` | Daily notes and journal entries |
| `Data/Meetings/` | Zoom meeting exports and meeting notes |
| `Data/Work/Slack Activity/` | Daily Slack activity captures |
| `Data/Knowledge/` | Reference material, guides, external articles saved for future use |
| `Data/Resources/` | Templates, assets, reusable reference files |
| `Data/Personal/` | Personal notes, thoughts, non-work captures |
| `Data/Assets/team/` | Profile photos and avatars for team members |
| `Data/Assets/attachments/` | Screenshots and diagrams linked from notes |
| `Data/Assets/processed/` | Original images that have been vision-extracted (companion .md exists in Data/) |

## Step 1 — List the inbox

List all files in `Data/Inbox/` using the Glob tool or a shell command:

```bash
find "<vault_root>/Data/Inbox" -type f
```

If the inbox is empty, tell the user and stop.

## Step 2 — Classify each file

Files fall into two broad categories: **markdown/text** and **images**. Handle each differently.

---

### Markdown / text files

Read the content (first 30–50 lines is sufficient). Then determine the destination:

1. **Meeting notes / Zoom exports** → `Data/Meetings/`
2. **Slack activity logs** → `Data/Work/Slack Activity/`
3. **Claude session transcripts** → `Data/Claude/`
4. **Daily journal / daily note** → `Data/Daily/`
5. **External reference material, articles, guides, wikis, links** → `Data/Knowledge/`
6. **Templates, assets, reusable resources** → `Data/Resources/`
7. **Personal notes, thoughts, reflections** → `Data/Personal/`
8. **Anything work-related that doesn't fit above** → create a descriptive new subfolder under `Data/Work/`
9. **Anything else** → create a new descriptive subfolder under `Data/`

Use the filename, frontmatter, and file content together to classify. When uncertain between two categories, pick the more specific one.

---

### Image files (.jpg, .jpeg, .png, .gif, .webp, .heic, .svg, .pdf)

Images are classified into one of three types. Use the filename and any companion `.md` file (same name, `.md` extension) to guide classification:

| Type | Signal | Destination |
|---|---|---|
| **Profile photo** | Filename contains a team member's name, "headshot", "photo", "avatar", or "profile" | `Data/Assets/team/` |
| **Content image** | Whiteboard, chart, slide, diagram, screenshot with meaningful text or data | `Data/Assets/processed/` + vision extraction (see below) |
| **Attachment** | Screenshot, UI capture, reference image with no extractable text content | `Data/Assets/attachments/` |

**Vision extraction for content images:**

When an image is classified as a content image:

1. Read the image using your vision capability
2. Generate a markdown summary capturing:
   - What the image shows (type: whiteboard, chart, slide, etc.)
   - All readable text, labels, and data points
   - Key takeaways or structure if it's a diagram
3. Save the summary as a `.md` file in the most appropriate `Data/` subfolder (e.g., `Data/Meetings/` for a meeting whiteboard, `Data/Knowledge/` for a reference chart). Use the same base filename as the image.
4. Add a wikilink to the original image at the top of the markdown file:
   ```markdown
   ![[original-filename.png]]
   ```
5. Move the original image to `Data/Assets/processed/`

**Attachment images:**

Move directly to `Data/Assets/attachments/` — no vision extraction needed. These are meant to be linked manually from notes.

**Profile photos:**

Move directly to `Data/Assets/team/` — no processing needed. The wiki update skill will link them from the relevant team page.

## Step 3 — Scrub sensitive content from text files

Before moving any markdown or text file, read its full content and scan for sensitive material. Redact in place **in the destination copy** — never modify the original in `Data/Inbox/`.

### What to redact (replace with `[REDACTED]`)

| Pattern | Examples |
|---|---|
| API keys and secrets | Strings matching `sk-...`, `pk_...`, `AIza...`, `AKIA[A-Z0-9]{16}`, `xoxb-...`, `xoxp-...` |
| Passwords in config or `.env` style | Lines like `password=abc123`, `passwd = secret`, `SECRET_KEY=...`, `DB_PASSWORD=...` |
| Private key blocks | `-----BEGIN RSA PRIVATE KEY-----` ... `-----END RSA PRIVATE KEY-----` (any key type) |
| Connection strings with credentials | `postgresql://user:password@host`, `mongodb+srv://user:pass@`, `mysql://user:pass@` |
| Bearer / Basic auth tokens | `Authorization: Bearer eyJ...`, `Authorization: Basic abc123==` |
| Webhook URLs with embedded tokens | `https://hooks.slack.com/services/T.../B.../[token]` — keep the domain, redact the token segment |
| Generic credential assignments | Lines where a key name contains `api_key`, `api_secret`, `access_token`, `auth_token`, `client_secret`, `private_key` and is followed by `=` or `:` and a non-empty value |

### What to keep (do NOT redact)

- Email addresses
- Phone numbers
- Names, titles, physical addresses
- URLs without embedded credentials
- Hashed values (bcrypt, SHA) — these are not usable secrets

### How to apply

1. Read the full file content
2. Identify any matching patterns above
3. If **no matches**: proceed normally — move the file as-is
4. If **matches found**:
   - Write the cleaned content (redacted) to the destination path instead of doing a plain file move
   - Delete the original from `Data/Inbox/` after writing the cleaned version
   - Note in your Step 6 summary: `filename.md → Data/Knowledge/ (2 values redacted)`

If you are uncertain whether a string is a real secret or just an example/placeholder (e.g., `api_key = "your_key_here"`), leave it — only redact values that look like real credentials.

## Step 4 — Execute moves

For each file:

1. Create the destination folder if it doesn't exist:

   ```bash
   mkdir -p "<vault_root>/Data/<subfolder>"
   ```

2. Move the file to its destination:

   ```bash
   mv "<vault_root>/Data/Inbox/<filename>" "<vault_root>/Data/<subfolder>/<filename>"
   ```

3. Verify the file exists at the destination before declaring success.

## Step 5 — Update CLAUDE.md if a new subfolder was created

If you created a new `Data/` subfolder, add a row for it in the **Project structure** table in `CLAUDE.md` so future sessions know it exists. Use the same format as existing rows.

## Step 6 — Confirm to the user

After all moves are complete, summarize:

> Inbox cleared. Moved X file(s):
> - `filename.md` → `Data/Knowledge/`

If any file could not be moved (e.g., a name conflict), explain the issue and ask how to resolve it.

## Rules

- **Never delete files** — only move them.
- **Never overwrite** an existing file without asking the user.
- **Never touch files outside `Data/`** during this operation.
- Preserve the original filename exactly unless the user asks to rename.
- If the inbox is already empty, say so and stop — do not touch anything else.
