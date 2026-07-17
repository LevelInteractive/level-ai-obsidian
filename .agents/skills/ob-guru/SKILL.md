---
name: ob-guru
description: >
  Fetch one or more Guru cards using the Guru MCP and save a formatted summary with a link
  to each card in Data/Resources/Guru/ in the Obsidian vault. Use when the user invokes
  /ob-guru or does anything involving Guru cards — including but not limited to: "save this
  Guru card", "pull a Guru card to Obsidian", "log a Guru resource", "save Guru cards",
  "search Guru for X", "look up X in Guru", "find X in Guru", "check Guru for X". Trigger
  on any request that mentions Guru and involves searching, retrieving, saving, or capturing
  card content.
---

# ob-guru

Fetch the requested Guru card(s) and save a formatted summary file to `Data/Resources/Guru/`
in the Obsidian vault.

## User context

- **Vault path**: `the vault root (derive dynamically from cwd -- never hardcode)`
- **Target folder**: `Data/Resources/Guru/`
- **Today's date**: available from `currentDate` context (format: YYYY-MM-DD)

---

## Step 1 — Identify the card(s)

The user may provide:
- A search query ("search Guru for signal operations", "look up GCLID in Guru")
- A Guru card URL (e.g., `https://app.getguru.com/card/...`)
- A card title or search phrase
- A Guru card ID directly

**If a search query is given**, use
`mcp__808278ff-2df2-49c1-90c4-e3a0e7da490b__guru_search_documents` with the user's query.
Display the search results to the user (title, collection, one-line description) and ask
which card(s) to save — or save all if the user said "save all" or "all results".

**If a URL or ID is given**, use `mcp__808278ff-2df2-49c1-90c4-e3a0e7da490b__guru_get_card_by_id`
directly with the extracted card ID.

**If a title or ambiguous phrase is given**, run a search first and confirm with the user
before saving.

---

## Step 2 — Fetch card content

For each card, call `mcp__808278ff-2df2-49c1-90c4-e3a0e7da490b__guru_get_card_by_id`.

Extract from the response:
- `id` — card ID
- `preferredPhrase` — card title
- `content` — card body (may be HTML or markdown)
- `collection.name` — collection the card belongs to
- `boards` — board names if present
- `tags` — any tags on the card
- `lastModified` — last updated date
- `slug` or card URL — construct the public link:
  `https://app.getguru.com/card/<id>`

If fetching multiple cards, run the `guru_get_card_by_id` calls in parallel.

---

## Step 3 — Determine the output filename

Use the card's title (`preferredPhrase`) to derive a kebab-case filename:
- Lowercase, spaces → hyphens, strip special characters
- Example: `"Signal Operations Overview"` → `signal-operations-overview.md`

If saving multiple cards, each gets its own file.

Target path: `Data/Resources/Guru/<kebab-case-title>.md`

---

## Step 4 — Build the note

For each card, produce a note using this template:

```markdown
---
title: <preferredPhrase>
type: resource
source: guru
guru_id: <id>
collection: <collection.name>
tags:
  - guru
  - <any tags from the card, kebab-cased>
created: <today's date YYYY-MM-DD>
updated: <lastModified date YYYY-MM-DD, or today if unavailable>
---

# <preferredPhrase>

**Source:** [View in Guru](https://app.getguru.com/card/<id>)
**Collection:** <collection.name>
**Last modified:** <lastModified>

---

## Summary

<2–4 sentence plain-English summary of what the card covers and why it matters.
Synthesize from the card content — do not just copy the first paragraph.>

---

## Content

<Card body content, cleaned up:
- Convert HTML to markdown if needed
- Preserve headers, lists, and tables
- Remove decorative or layout-only HTML
- Keep all substantive text, code blocks, and links>

---

## References

- [[<kebab-case-title>]] (this note)
- [<preferredPhrase> on Guru](https://app.getguru.com/card/<id>)
```

If the card body is very short (< 100 words), skip the `## Content` / `## Summary` split
and just use `## Content` with the full text.

---

## Step 5 — Save to the vault

Check if `Data/Resources/Guru/` exists by attempting to read any file in it. If the folder
doesn't exist, it will be created implicitly when writing the first file.

For each card, write the note using the Obsidian MCP write tool:

```
obsidian vault="<vault-name>" create path="Data/Resources/Guru/<filename>.md" content="..."
```

If a file with that name already exists, read it first and check whether the `guru_id`
matches. If it matches, overwrite (the card was updated). If it doesn't match (different
card, name collision), append a numeric suffix: `signal-operations-overview-2.md`.

---

## Step 6 — Confirm to the user

After saving, tell the user:

> Saved **<N>** Guru card(s) to `Data/Resources/Guru/` in your vault.

For each card, show a one-line entry:
```
- **<Card Title>** → Data/Resources/Guru/<filename>.md — [View in Guru](https://app.getguru.com/card/<id>)
```

Then display the summary section of each saved note inline so the user can review without
opening the file.
