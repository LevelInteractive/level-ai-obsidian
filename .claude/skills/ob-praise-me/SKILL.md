---
name: ob-praise-me
description: >
  Looks back over a user-specified time window (default: 1 week) and finds wins, accomplishments,
  and moments of excellence from across the vault — Slack activity, meetings, Claude sessions, and
  the wiki. Surfaces improvements, client wins, process gains, productivity boosts, and demonstrations
  of key behaviors or core values, with measurement metrics wherever possible. Saves a celebratory
  report to Level Playbook/insights/. Use this skill whenever the user says "praise me", "what did I
  do well", "celebrate my wins", "show my accomplishments", "what went well this week", "highlight my
  achievements", "give me a win report", or anything similar asking to reflect on personal performance
  or positive contributions. Also trigger on /ob-praise-me. Trigger even if the request is casual
  or self-deprecating ("I need some good news", "remind me I'm doing okay").
---

# ob-praise-me

Find and celebrate wins from a specified time window. Start with the wiki to get a synthesized picture quickly, then dive into raw sources to fill gaps and find wins the wiki hasn't captured yet. Every win gets a citation.

## Vault paths

- **Vault root**: the current working directory (the folder containing `CLAUDE.md`) - never hardcode a path; other users run this vault from a different location
- **Wiki root**: `Level Knowledge\`
- **Wiki index**: `Level Knowledge\index.md`
- **Slack activity**: `Data\Work\Slack Activity\` (monthly files, e.g. `2026-06.md`)
- **Meeting notes**: `Data\Meetings\`
- **Claude sessions**: `Data\Claude\`
- **Daily notes**: `Data\Daily\`
- **Core Values**: `Level Knowledge\organization\core-values.md`
- **Key Behaviors**: `Level Knowledge\organization\key-behaviors.md`
- **Output**: `Level Playbook\insights\praise\`
- **Hub (latest)**: `Level Playbook\Hub\Praises.md`
- **History**: `Level Playbook\insights\Praises History.md`

## Step 0 — Parse the time window

Read the user's args to determine the window. Supported formats:

| Input | Interpretation |
|---|---|
| `last week` / *(no args)* | 7 days ending today |
| `last 2 weeks` | 14 days ending today |
| `last month` / `June` / `June 2026` | Calendar month |
| `last N days` | N days ending today |
| `YYYY-MM-DD to YYYY-MM-DD` | Explicit range |

Derive `window_start` and `window_end` (both inclusive, `YYYY-MM-DD`). Default is 7 days.

Announce the window before proceeding:
> Scanning for wins from **{window_start} → {window_end}**...

## Step 1 — Load the evaluation framework

Before reading any evidence, read both:
- `Level Knowledge\organization\core-values.md` — the 4 Core Values
- `Level Knowledge\organization\key-behaviors.md` — the 26 Key Behaviors

Keep these as a positive lens throughout everything you read. The question you're always asking is: *did this moment embody a Core Value or Key Behavior?* Wins that connect to a named value or behavior are especially worth surfacing — they're the easiest to articulate in a performance review, a rocks update, or a conversation with a manager.

**Core Values (for quick reference):**
1. No Ego, All In — stay humble, lift others, "Can Do Will Do Happy To"
2. Better Every Day — progress over perfection, embrace curiosity
3. Relentless for Results — results over activity, do what you say, biased toward action
4. Driven by Truth — speak up, facts over assumptions, no sugarcoating

**Key Behaviors most likely to show up as wins:**
- **#1 Embrace Curiosity** — explored something new, asked the better question
- **#5 Keep Your Promises** — committed and delivered
- **#9 Own the Outcome** — saw something through without being asked
- **#12 Be Coachable** — incorporated feedback and improved
- **#13 Say the Real Thing** — named the honest truth when it was hard
- **#17 See the Whole Board** — connected work to the bigger picture
- **#18 Respond with Precision** — clear, fast, complete communication
- **#22 Share Information** — knowledge shared made someone else better
- **#25 Automate the Repeatable** — built something that removes future toil

## Step 3 — Read the wiki first

The wiki is the fastest way to get oriented. Start here before touching raw sources.

Read `Level Knowledge\index.md` to identify all pages with `last_updated` on or after `window_start`. Read each of those pages in full. As you read, note:
- Client situations that improved, were resolved, or moved in a positive direction
- Confidence levels that went up (low → medium, medium → high)
- New pages created — something was documented that wasn't before
- Process or tool pages that were updated with improvements or fixes
- Decisions recorded — something was decided and owned
- Any win mentioned in page content, even briefly

Also read at least one overview page per active client and one page per domain even if not updated in the window — you need baseline context to recognize what "better" means.

After this pass, you'll have a working list of candidate wins drawn from the synthesized layer. Many wins will be fully captured here. Move to Step 2 to fill the gaps.

## Step 4 — Dive into raw sources for what the wiki missed

The wiki captures synthesis, not texture. Raw sources surface wins that haven't been written up yet — individual moments in Slack, specific meeting contributions, Claude sessions that built something new. Go here to deepen and expand.

**Scan in this order, reading files modified on or after `window_start`:**

### 2a. Slack Activity
Read all monthly Slack files that overlap the window (`Data\Work\Slack Activity\`). Look for:
- Messages where the user helped a colleague solve a problem
- Positive reactions, thank-yous, or explicit acknowledgments received
- Threads where the user took initiative, drove a decision, or unblocked someone
- Any moment that reflects Level's key behaviors: ownership, curiosity, care, precision, initiative

### 2b. Meeting notes
List and read files in `Data\Meetings\`. Look for:
- Problems the user diagnosed or resolved
- Sharp questions or reframes that moved a conversation forward
- Client situations where the user's input made a difference
- Positive feedback, compliments, or shout-outs from colleagues or clients
- Decisions proposed or owned

### 2c. Claude sessions
List and read files in `Data\Claude\`. Look for:
- New skills, workflows, automations, or systems built
- Complex problems worked through to a solution
- Improvements to vault structure, processes, or knowledge organization
- Evidence of sustained analytical or creative output

For each raw source, add any wins not already captured from the wiki to your working list.

## Step 5 — Classify wins

Group your collected wins into categories that reflect what actually happened. Don't force wins into a fixed list — let the content drive the buckets.

**Seed categories** (use these if relevant; add, rename, or split as needed):
- **Client Wins** — improved health, resolved issues, metrics that moved, positive interactions
- **Process Improvements** — workflows that got faster, manual steps automated, recurring problems fixed
- **Knowledge & Learning** — something new understood, documented for the first time, a skill built
- **Productivity Gains** — more done in less time, a bottleneck cleared, a system that now runs itself
- **Team & Collaboration** — helped a colleague, shared knowledge, proactively communicated
- **Core Values in Action** — ownership, curiosity, care, precision, initiative visibly demonstrated
- **Creative & Analytical Output** — a novel analysis, a well-crafted deliverable, an insight that changed understanding
- **Systems & Tooling** — new automations, vault infrastructure improvements, integrations built
- **Communication & Visibility** — a message that landed well, knowledge shared broadly, something surfaced that others needed

**Create new categories freely** when wins cluster around something not on the list. For example, if there were three separate mentorship moments, create a "Mentorship" bucket rather than scattering them. The goal is a structure that reflects *this* window's actual shape, not a generic template.

A single event can appear in multiple buckets if genuinely warranted — but don't pad.

**Measurement metrics** — for every win, try to attach a number:
- Before/after comparison ("match rate went from 74% → 82%")
- Count ("resolved 3 open client issues")
- Time saved ("automated X, saving ~N hours/week")
- Recency ("first time this was documented")
- Volume ("N new skills built", "N meetings processed")

If no hard metric exists, use a qualitative signal: "first time this came up without escalating", "client signed off without revisions", "colleague replied 'this is exactly what I needed'".

## Step 6 — Tag each win

For every win, identify the most relevant Core Value or Key Behavior it demonstrates. This turns a win from "something good happened" into "evidence of how the user works."

- Tag with the Core Value if the win reflects a broad pattern (e.g., "Relentless for Results")
- Tag with a specific Key Behavior if the win is a precise match (e.g., "#9 Own the Outcome")
- A win can have both a value and a behavior tag if genuinely warranted — keep it to the most salient one of each
- If a win doesn't clearly connect to any value or behavior, it can go untagged — don't force it

Tags appear inline in the report next to each win's rating.

## Step 7 — Assess magnitude

For each win, rate it:

- **⭐ Notable** — a good contribution; solid execution
- **⭐⭐ Significant** — meaningfully moved something; above expectations
- **⭐⭐⭐ Exceptional** — rare, high-impact, or exemplary of values at their best

Be honest and calibrated. Most wins are ⭐ or ⭐⭐. Reserve ⭐⭐⭐ for things that would make someone proud to share in a team meeting.

## Step 8 — Write the report

Save to:
```
Level Playbook\insights\praise\praise-me-{window_end}.md
```

**Report structure:**

```markdown
---
type: praise-me
window: YYYY-MM-DD to YYYY-MM-DD
generated: YYYY-MM-DD
win_count: N
---

# Win Report — {window_start} to {window_end}

*{N} wins found across {window_start} → {window_end}. Here's what you accomplished.*

## Highlight Reel
[2–4 sentences of genuine, specific praise for the most significant things.
Reference real events. No fluff — specificity is the point.]

## Wins by Category

### [Category Name]
- ⭐⭐ **[Short title]** · *[Core Value or #N Key Behavior]* — [What happened. What the impact was. Metric if available.] → *[[source]]*
- ...

### [Next Category]
...

*Categories are determined by the content — use as many as the wins warrant. Omit any with nothing real to say.*

## By the Numbers
[A tight list of any quantitative signals found, e.g.:]
- X client issues resolved
- Y new wiki pages created or updated
- Z meetings processed and documented
- N automations or skills built
- [Metric] improved from A → B

## What to Carry Forward
[1–3 sentences: the strongest pattern or theme from the window.
What does this window reveal about how the user works best, or what's worth doubling down on?]

## Sources
### Wiki pages consulted
- [[page-slug|Page Title]]

### Raw sources
- [[filename]] *(meeting / slack / session)*
```

After saving the dated report, update both hub files:

**Latest Praises** — overwrite with the current report:

Write the full report content to `Level Playbook\Hub\Praises.md`, prefixed with:
```markdown
> *Last updated: {window_start} → {window_end} (generated {today})*
```

**Praises History** — append a summary entry to `Level Playbook\insights\Praises History.md`.

If the file doesn't exist yet, create it with this header first:
```markdown
# Praises History

A running log of every ob-praise-me report. Most recent entry at the top.

---
```

Then prepend a new entry at the top of the log (after the header, before any existing entries):

```markdown
## {window_start} → {window_end} · {win_count} wins · generated {today}

**Highlight:** [The 2–4 sentence Highlight Reel from the report, verbatim.]

**Top wins:**
- ⭐⭐⭐ [Short title] *(category)*
- ⭐⭐⭐ [Short title] *(category)*  ← include only ⭐⭐⭐ wins; if fewer than 2, include the top ⭐⭐ wins

**Carry forward:** [The "What to Carry Forward" paragraph, verbatim.]

→ Full report: [[praise-me-{window_end}]]

---
```

Tell the user:
> Win report saved → `Level Playbook\insights\praise\praise-me-{window_end}.md`
> Hub updated → `Level Playbook\Hub\Praises.md`
> History updated → `Level Playbook\insights\Praises History.md`

Then print the full report inline.

## Rules

- **History is append-only** — never delete or rewrite existing entries in `Praises History.md`; only prepend new ones.
- **Evidence only** — every win must trace back to a specific file. No fabrication, no "probably did well at X."
- **Be specific** — "resolved the CSU GCLID deduplication issue that had been open for 3 weeks" beats "helped with a client issue."
- **Be generous but honest** — this skill is designed to surface real wins that might go unnoticed, not to flatter. If it was a quiet week, say so clearly rather than padding.
- **No fluff** — skip the congratulatory filler phrases. The specificity of the win is the celebration.
- **Omit empty categories** — don't include a section header with nothing under it.
- **Respect `## Notes`** — read user notes for context but never include their content in the output.
- **Read the sources, don't skim** — Slack files and meeting notes are where the actual evidence lives. Spend time there.
