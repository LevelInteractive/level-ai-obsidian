---
last_updated: 
last_full_rerun: 

---


# Level Knowledge

Synthesized, living knowledge about the organization. Claude maintains this wiki by reading raw sources in `Data/` and updating pages in place — never appending. Each page covers one topic and gets rewritten as understanding improves.

## How this wiki works

- **Raw sources** → `Data/Meetings`, `Data/Work/Slack Activity`, `Data/Daily`, `Data/Inbox`
- **Wiki pages** → here in `Level Knowledge/` — clients get sub-folders; other domains are flat files
- **Update trigger** → run `/ob-wiki-update` to push new learnings from raw sources into the wiki
- **Rule** → update existing pages in place; create a new page only if the topic has no page yet

---

## Graph color legend

Colors assigned to each domain in the Obsidian graph view. When a new domain is created, the next color is added here and to `.obsidian/graph.json`. See `.claude/tagging.md` for the canonical color table.

| Color | Hex | Domain |
|---|---|---|
| 🔵 | #4d8fcc | clients |
| 🟢 | #5ca65c | team |
| 🟣 | #9a5cbf | decisions |
| 🩵 | #5ca6a6 | tools |
| 🔴 | #c4607a | analytics |
| 🟡 | #c4a060 | processes |
| 🟠 | #cc7a4d | organization |

---

## Clients

Each client has its own sub-folder with focused pages: `overview`, `issues`, `trends`, `sentiment`, `wins`.

_No client pages yet — created automatically as `/ob-wiki-update` ingests raw sources._

## Processes

_No process pages yet._

## Tools

_No tool pages yet._

## Analytics

_No analytics pages yet._

## Team

_No team pages yet._

## Decisions

_No decision pages yet._

## Organization

_No organization pages yet._
