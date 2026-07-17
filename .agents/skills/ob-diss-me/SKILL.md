---
name: ob-diss-me
description: >
  Looks back over a user-specified time window (default: 1 week) and surfaces honest, specific areas
  for improvement — missed commitments, over-promising, time management gaps, delivery delays,
  communication lapses, and anything else that fell short. Anchors findings against Level's 4 Core
  Values and 26 Key Behaviors as the primary evaluation framework. Reads wiki first, then raw sources.
  Saves a candid improvement report to Level Playbook/insights/ and appends a summary entry to a
  running history file. Use this skill whenever the user says "critique me", "what should I improve",
  "where did I fall short", "be honest with me", "what did I miss", "give me feedback", "what could I
  do better", "roast me", "diss me", or anything similar asking for constructive criticism or honest
  self-assessment. Also trigger on /ob-diss-me.
---

# ob-diss-me

Surface honest, evidence-based areas for improvement from a specified time window. The goal is not to be harsh — it's to be useful. Every finding must be grounded in something that actually happened, anchored to a specific Level Core Value or Key Behavior where applicable, and actionable enough to act on.

## Vault paths

- **Vault root**: `the vault root (derive dynamically from cwd -- never hardcode)`
- **Wiki root**: `Level Knowledge\`
- **Wiki index**: `Level Knowledge\index.md`
- **Core Values**: `Level Knowledge\organization\core-values.md`
- **Key Behaviors**: `Level Knowledge\organization\key-behaviors.md`
- **Slack activity**: `Data\Work\Slack Activity\` (monthly files, e.g. `2026-06.md`)
- **Meeting notes**: `Data\Meetings\`
- **Codex sessions**: `Data\Codex\`
- **Daily notes**: `Data\Daily\`
- **Output**: `Level Playbook\insights\critique\`
- **Hub (latest)**: `Level Playbook\Hub\Critiques.md`
- **History**: `Level Playbook\insights\Critique History.md`

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
> Looking for improvement areas from **{window_start} → {window_end}**...

## Step 1 — Load the evaluation framework

Before reading any evidence, read both:
- `Level Knowledge\organization\core-values.md` — the 4 Core Values
- `Level Knowledge\organization\key-behaviors.md` — the 26 Key Behaviors

Keep these in mind as your primary evaluation lens for everything you read. The question you're always asking is: *did this moment reflect or fall short of the Level Way?*

## Step 2 — Read the wiki first

Read `Level Knowledge\index.md` to identify all pages with `last_updated` on or after `window_start`. Read each in full. As you read, look for:
- Open issues or blockers that haven't been resolved or followed up on
- Commitments assigned to Nick in meeting notes or wiki pages that show no closure
- Client situations that got worse, stalled, or were flagged as at-risk
- Decisions deferred or left unresolved
- Confidence levels that are still low despite available source material
- Any explicit mention of a missed deadline, unmet expectation, or communication gap

Also read the overview page for each active client and at least one page per domain — you need baseline context to recognize what "worse" or "missed" looks like.

## Step 3 — Dive into raw sources

The wiki captures synthesis; raw sources reveal texture. Go here to find what hasn't been written up.

Instead of reading every Slack export, meeting note, and Codex session in the window end-to-end,
use `qmd` to find the highest-signal passages first, then pull only the context around each hit.
This is the efficient path — full reads are the fallback, not the default.

**Run targeted queries** (scope `collections: ["data"]`, one call per lens below):

| Lens | lex query | vec query |
|---|---|---|
| Missed commitments | `"I'll have that" OR "I'll take care of" OR overdue OR "follow up"` | `Nick committed to something and it wasn't delivered, or closed out late without notice` |
| Communication gaps | `"any update" OR "circling back" OR "still waiting"` | `someone asked Nick a direct question and got no response or a much later response` |
| Scope / rework | `rework OR "scope creep" OR rabbit hole OR "walking back"` | `Nick promised a scope or timeline that later had to be walked back, or redid work that was just built` |

For each result:
1. Check the file's path/date (most `Data/` files are named or dated `YYYY-MM-DD`) falls within
   `[window_start, window_end]` — discard hits outside the window.
2. Pull context with `mcp__qmd__get(file=hit.file, fromLine=max(1, line-15), maxLines=60)` rather
   than reading the whole file.
3. Note which source folder it came from (Slack / Meetings / Codex) so you can still write the
   `*(meeting / slack / session)*` tag in the final Sources section.

**Fall back to a full scan** only if the queries return fewer than ~6 in-window hits total —
in that case, Glob `Data\Work\Slack Activity\`, `Data\Meetings\`, and `Data\Codex\` for files
modified on or after `window_start` and read them directly, as before.

For each raw source, add any improvement areas not already captured from the wiki to your working list.

## Step 4 — Classify improvement areas

Group findings into categories that reflect what actually happened. Let the content drive the buckets — don't pad.

**Seed categories** (use, rename, split, or skip as content warrants):
- **Missed Commitments** — said it would happen, didn't happen (or happened late without communication)
- **Over-Promising / Scope Creep** — committed to more than was realistic; stretched too thin
- **Time Management** — things deprioritized, delayed, or deferred that shouldn't have been
- **Communication Gaps** — slow response, missing update, someone had to chase for information
- **Delivery Quality** — work shipped with known issues, bugs not caught, testing skipped
- **Proactivity Gaps** — reactive when proactive behavior was called for; could have flagged sooner
- **Key Behavior Misses** — specific moments that fell short of a named Level Key Behavior
- **Core Value Gaps** — patterns across the window that don't fully reflect a Core Value

Create new categories freely when findings cluster around something else. A single finding can appear in multiple buckets if genuinely warranted — but don't double-count to inflate the list.

## Step 5 — Anchor to Core Values and Key Behaviors

For every finding, ask: which Core Value or Key Behavior is most relevant here?

**Core Values:**
1. No Ego, All In — stay humble, lift others, "Can Do Will Do Happy To"
2. Better Every Day — progress over perfection, embrace curiosity
3. Relentless for Results — results over activity, do what you say, biased toward action
4. Driven by Truth — speak up, facts over assumptions, no sugarcoating

**Key Behaviors most likely to surface in a critique:**
- **#5 Keep Your Promises** — if you say you'll do it, make it happen; communicate early when things change
- **#6 Get Clear from the Start** — define goals, owners, dates upfront
- **#8 Make Quality a Habit** — always ask: is this my best work?
- **#9 Own the Outcome** — care about the result, not just the activity; see projects through
- **#10 Maintain to Sustain** — protect work-life balance; sustainable pace over heroics
- **#13 Say the Real Thing** — be honest and transparent; address issues directly
- **#17 See the Whole Board** — connect work to the bigger picture
- **#18 Respond with Precision** — be quick and clear; a simple "got it" keeps people informed
- **#22 Share Information** — shared knowledge makes everyone stronger
- **#25 Automate the Repeatable** — if a tool can do the boring work, let it

Tag each finding with the relevant value or behavior. If a finding connects to multiple, pick the most salient one.

## Step 6 — Assess priority

Rate each finding:

- **P1 — High** — directly affected a client, a deadline, or a colleague's ability to do their job; likely to recur if not addressed
- **P2 — Medium** — affected quality or efficiency; worth addressing but not urgent
- **P3 — Low** — minor friction; good to know but low stakes

Most findings will be P2. Reserve P1 for things with real downstream impact.

## Step 7 — Write the report

Save to:
```
Level Playbook\insights\critique\critique-{window_end}.md
```

**Report structure:**

```markdown
---
type: critique
window: YYYY-MM-DD to YYYY-MM-DD
generated: YYYY-MM-DD
finding_count: N
---

# Critique Report — {window_start} to {window_end}

*{N} improvement areas found across {window_start} → {window_end}. This is meant to be useful, not harsh.*

## Summary

[2–3 sentences. What's the overall pattern? What's the one or two things most worth addressing?
Be direct. Don't soften this into meaninglessness.]

## Findings

### [Category Name]

**P1 · [Short title]** · *Core Value: Relentless for Results / Key Behavior: #5 Keep Your Promises*
[What happened. What the impact or risk was. What the better behavior looks like.] → *[[source]]*

**P2 · [Short title]** · *Key Behavior: #18 Respond with Precision*
[What happened.] → *[[source]]*

...

*Omit any category with no real findings — don't pad.*

## Pattern Analysis

[1–3 sentences. What do these findings have in common? Is there a root cause — overextension,
unclear ownership, reactive vs. proactive posture, something else? This is the most actionable
part of the report.]

## Suggested Focus for Next Week

[Numbered list of 2–4 specific, concrete things to do differently. Not "be better at X" —
instead: "before committing to a timeline, check what's already in flight" or
"close open action items from the previous week's meetings before the next check-in."]

## Sources
### Wiki pages consulted
- [[page-slug|Page Title]]

### Raw sources
- [[filename]] *(meeting / slack / session)*
```

## Step 8 — Update the hub files

**Latest Critique** — overwrite with the current report:

Write the full report content to `Level Playbook\Hub\Critiques.md`, prefixed with:
```markdown
> *Last updated: {window_start} → {window_end} (generated {today})*
```

**Critique History** — append a summary entry to `Level Playbook\Hub\Critique History.md`.

If the file doesn't exist yet, create it with this header first:
```markdown
# Critique History

A running log of every ob-diss-me report. Most recent entry at the top.

---
```

Then prepend a new entry at the top of the log (after the header, before any existing entries):

```markdown
## {window_start} → {window_end} · {finding_count} findings · generated {today}

**Summary:** [The 2–3 sentence summary from the report, verbatim.]

**Top findings:**
- P[N] · [Short title] · *[Key Behavior or Core Value]*
- P[N] · [Short title] · *[Key Behavior or Core Value]*
- P[N] · [Short title] · *[Key Behavior or Core Value]*

**Suggested focus:** [First item from the Suggested Focus list.]

→ Full report: [[critique-{window_end}]]

---
```

Include up to 3 top findings in the history entry — the highest-priority ones. This keeps the history scannable without duplicating the full report.

Tell the user:
> Critique report saved → `Level Playbook\insights\critique\critique-{window_end}.md`
> Hub updated → `Level Playbook\Hub\Critiques.md`
> History updated → `Level Playbook\Hub\Critique History.md`

Then print the full report inline.

## Rules

- **Evidence only** — every finding must trace back to a specific file. No speculation, no "probably."
- **Be specific** — "committed to fixing Brian's bucket access on June 25; no follow-up visible by June 29" beats "sometimes slow to follow through."
- **Be fair** — this isn't a pile-on. If context explains a gap (sick day, explicit reprioritization, team agreed to defer), note it and lower the priority.
- **Anchor everything** — every finding should connect to a Core Value or Key Behavior. If it doesn't, ask whether it's actually worth raising.
- **No fluff** — don't pad with generic advice. If it was a strong week with only minor gaps, say so.
- **Omit empty categories** — don't include a section header with nothing real under it.
- **Respect `## Notes`** — read user notes for context; never include their content in the output.
- **History is append-only** — never delete or rewrite existing entries in `Critique History.md`; only prepend new ones.
- **Balance with ob-praise-me** — this skill and ob-praise-me are a pair. The critique should be honest but calibrated to the same window's reality. If it was a high-output week, the findings should reflect that most things went well.
