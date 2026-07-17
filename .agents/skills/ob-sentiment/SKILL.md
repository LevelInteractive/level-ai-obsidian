---
name: ob-sentiment
description: >
  Predicts how a client, person, or group feels about Level Agency's performance by mining
  vault sources (meeting notes, Slack activity, wiki pages) for sentiment signals — then
  producing a structured report with an overall health label, evidence quotes, confidence,
  trend direction, and recommended actions. Optionally saves the result as a wiki sentiment
  page. Use this skill whenever the user asks about client sentiment, relationship health,
  how a client or stakeholder feels, whether a relationship is at risk, mood check, or
  anything like "how is [client/person] feeling about us", "what's the vibe with [X]",
  "are we at risk of losing [client]", "sentiment check on [X]", or "predict [X]'s mood".
  Also use when the user invokes /ob-sentiment or asks to update a sentiment page.
---

# ob-sentiment

Analyze vault sources to predict how a client, person, or group feels about Level Agency's
performance, then surface a structured sentiment report.

## Target resolution

The user will pass a name — usually a client (e.g., "CSU", "NBU", "AIM", "Country Financial"),
a person (e.g., "Bill"), or a group (e.g., "the CSU stakeholders"). Resolve this to:

- **Client folder**: `Level Knowledge/clients/<client-slug>/` — contains overview, issues,
  trends, wins, sentiment pages
- **Relevant meetings**: files in `Data/Meetings/` whose names reference the client or person
- **Slack signals**: `Data/Work/Slack Activity/` — search for the client/person name

If the target is ambiguous (e.g., a first name that could match multiple people), surface the
ambiguity and ask the user to confirm before proceeding.

## Step 1 — Gather sources

Read these directly first (small, targeted files — no need for search):

1. All existing wiki pages for the target under `Level Knowledge/clients/<slug>/` — especially
   `issues.md`, `trends.md`, `wins.md`, `overview.md`, and any existing `sentiment.md`
2. `Level Knowledge/index.md` — to confirm which client folder exists and catch aliases

Then use the `qmd` MCP to find raw signals about the target in `Data/`. This catches mentions in
meetings and Slack even when the client/person isn't in the filename, and avoids reading full
monthly Slack exports or every meeting transcript end-to-end:

```
mcp__qmd__query(
  searches=[
    {type:"lex", query:"\"<target name>\""},
    {type:"vec", query:"how does <target> feel about Level's performance — complaints, praise, escalation, or churn risk"}
  ],
  intent="client/relationship sentiment signals from meetings and Slack",
  collections=["data"],
  limit=15
)
```

For each result, pull just the surrounding context instead of the whole file — use the `line`
field from the hit: `mcp__qmd__get(file=hit.file, fromLine=max(1, line-20), maxLines=80)`. Only
fall back to reading a full file when a snippet doesn't give enough context to judge tone.

If fewer than ~4 solid signals come back, run a second pass (drop the exact-phrase lex query,
broaden the vec query) before falling back to the old approach: Glob `Data/Meetings/` for
filename matches and read the most recent 6, plus the latest `Data/Work/Slack Activity/` file.

Reading widely is more valuable than reading deeply. Better to have 8 well-targeted snippets than
read 2 files exhaustively — breadth reveals patterns that single sources hide.

## Step 2 — Extract sentiment signals

For each source, extract signals. Signals fall into three categories:

**Positive signals** — the relationship is healthy and they value the work:
- Explicit praise or compliments about Level's work
- Client expanding scope, adding services, or asking for more
- Enthusiastic tone in meetings or messages
- Client acting on Level's recommendations
- Timely responses and high engagement
- Wins acknowledged internally (meeting notes, Slack)

**Negative signals** — friction, risk, or dissatisfaction:
- Complaints about results, communication, or responsiveness
- Missed expectations or surprises (client "didn't know" about something)
- Escalations — issues raised to senior stakeholders
- Silence or reduced engagement (fewer check-ins, delayed responses)
- Budget cuts, scope reductions, or contract questions
- Internal discussion of risk or "managing optics"
- Language around churn: "alternatives", "reconsidering", "frustrated"

**Neutral/mixed signals** — present but not strongly directional:
- Routine check-ins with no strong tone
- Questions that could be curious or skeptical
- Mixed results (some good, some bad)

For each signal, note:
- The source it came from (file name and approximate date)
- A short quote or paraphrase (keep it verbatim where possible)
- Its category (positive / negative / neutral)
- Its recency (how recent is this relative to today: `<2 weeks`, `1–3 months`, `3+ months`)

Recency matters: a negative signal from last week outweighs a positive signal from 3 months ago.

## Step 3 — Synthesize sentiment

With signals in hand, make a holistic judgment:

**Overall label** (pick one):
- `Healthy` — relationship is strong; client is engaged and satisfied
- `Stable` — no major issues; routine engagement; nothing alarming
- `Watch` — some friction or ambiguity; not at risk yet but worth monitoring
- `At Risk` — clear signs of dissatisfaction, disengagement, or escalation
- `Critical` — active churn risk; needs immediate attention

**Trend direction** (pick one):
- `Improving` — signals are getting better over time
- `Stable` — no clear directional shift
- `Declining` — signals are getting worse over time
- `Unknown` — insufficient historical data to judge

**Confidence** (use AGENTS.md definitions):
- `high` — 3+ consistent, recent sources
- `medium` — 1–2 sources, or some inference required
- `low` — single source, or all sources are old (3+ months)

When evidence conflicts (e.g., a recent win but also a recent complaint), hold both. Don't
average them into blandness — the tension itself is the insight. Name the conflicting signals
explicitly in the report.

## Step 4 — Recommended actions

Based on the label and trend, suggest 2–4 concrete next steps. These should be specific, not
generic. Good examples:
- "Schedule a direct briefing with Bill and Sarah before the next results review"
- "Lead the next check-in with wins before addressing model limitations"
- "Ask the account team whether Steph has heard any feedback from the client side in the last 2 weeks"

Avoid vague advice like "improve communication" or "monitor closely" — these are not actionable.

## Step 5 — Format and save the report

Always show the report in chat first. Use this structure:

```
## Sentiment: [Target Name]
**As of**: [today's date]

### Overall: [Label] | Trend: [Direction] | Confidence: [Level]

### Key Signals

**Positive**
- [quote or paraphrase] — *[source], [date]*

**Negative**
- [quote or paraphrase] — *[source], [date]*

**Neutral / Mixed**
- [quote or paraphrase] — *[source], [date]*

### Assessment
[2–3 sentences synthesizing what the signals mean together. Name the dominant theme.]

### Recommended Actions
1. [Specific action]
2. [Specific action]
3. [Specific action]

### Sources Used
- [file names]
```

If there are no signals in a category, omit that category heading rather than writing "None."

**Always save the report** to `Level Playbook/sentiment/<slug>-sentiment.md` — no need to
ask. Use `<slug>` as the lowercase hyphenated client/target name (e.g., `csu`, `nbu`, `aim`).
If a file already exists for that target, overwrite it in place. The file content is the full
report exactly as shown in chat, with a simple H1 title at the top:

```markdown
# Sentiment Report: [Target Name] — YYYY-MM-DD

[report body — same as chat output]
```

After saving, log to `Level Knowledge/log.md`:
```
[date] ob-sentiment: [target] sentiment analysis — [label], [confidence] confidence, [N] sources
```
