---
name: ob-similarity-update
description: >
  Builds and maintains a similarity graph over Data/ using qmd semantic search — queries qmd for
  each file's k-nearest neighbors (wiki-first, then raw data if no confident wiki fit), has Codex
  judge which candidates are genuinely related, and groups related files into clusters. Makes as
  many confident connections as it can and flags anything ambiguous (candidate cluster merges,
  files that may belong to more than one topic, thin single-file clusters) for the separate
  ob-similarity-consolidate skill to resolve. Does not write to Level Knowledge/ itself. Use when
  the user runs /ob-similarity-update, asks to "build the knowledge graph", "find connections qmd
  can see", or "update the similarity graph".
---

# ob-similarity-update

Builds and maintains a similarity graph over `Data/` — this skill's only job is finding and
recording connections between files, not writing wiki pages. It asks qmd "what else in the vault
is similar to this file?" for every new or stale file, lets Codex judge which candidates are
genuinely the same topic, and groups them into clusters. It is deliberately liberal: where a
judgment is clear, it resolves it and moves on; where it's genuinely ambiguous (a file might belong
to two topics, two clusters might actually be the same thing, a cluster has only one member and
might be a false new-domain signal), it records the ambiguity as a flag rather than guessing or
silently dropping it.

**This skill never touches `Level Knowledge/`.** Consolidating flagged ambiguities and synthesizing
wiki pages from confirmed clusters is a separate skill: `ob-similarity-consolidate`. Run this skill
first to build/update the graph, then run that one to resolve flags and write pages. This split
mirrors the vault's existing `ob-wiki-lint` (detect) → `ob-wiki-contradictions` (resolve) pattern.

`ob-wiki-update` is a separate, older ingestion path this pair of skills is meant to replace; it is
not modified by this skill.

## Vault paths

- **Vault root**: the current working directory (never hardcode a path)
- **Raw sources**: `Data\` — scanned recursively
- **Graph state**: `.Codex\similarity-graph.json` — shared with `ob-similarity-consolidate`; this
  skill writes it, that skill reads and resolves it, and also writes back to it after consolidating

## Step 0 — Sort the inbox

Invoke the `ob-inbox` agent (Agent tool, `subagent_type: "ob-inbox"`) to sort any unsorted files
from `Data/Inbox/` into the correct `Data/` subfolders before discovery runs. Wait for it to finish.

This is not optional: qmd's collections only index `**/*.md` files. A raw image or misfiled document
sitting in `Data/Inbox/` is invisible to every step below — Step 3's Glob won't find it, and it can
never surface as anyone's neighbor. `ob-inbox` is what turns a dropped image into a searchable `.md`
file (via vision extraction) or moves a misfiled note into a folder this pipeline will actually scan.

If `Data/Inbox/` is empty or has nothing sortable, the agent reports that and you continue.

## Step 1 — Check the qmd index is current

Call `mcp__qmd__status`. If `needsEmbedding` is greater than 0, run `qmd embed` via Bash before
proceeding — a file that isn't embedded yet can't surface as anyone's neighbor, and won't find its
own neighbors either. This matters especially right after Step 0, since any file `ob-inbox` just
moved or vision-extracted is brand new to the index. If the `qmd embed` command isn't available in
this environment, proceed anyway and note the gap in the Step 6 report; a file that's merely
un-embedded will simply generate a thin neighbor list this run and get retried next run once it's
embedded.

## Step 2 — Load or initialize the similarity graph

Read `.Codex\similarity-graph.json`.

If it doesn't exist, initialize it:
```json
{
  "version": 2,
  "lastRun": null,
  "files": {},
  "clusters": {},
  "flagged": []
}
```

**Schema:**
```json
{
  "version": 2,
  "lastRun": "YYYY-MM-DD",
  "files": {
    "<data file path>": {
      "mtime": "<file mtime, ISO 8601>",
      "summary": "<2-3 sentence AI-written summary used as the qmd query>",
      "keyTerms": ["<entity names, tool names, client names pulled from the file>"],
      "neighbors": [
        {"file": "<path>", "score": 0.0},
        {"file": "level-knowledge/<page>.md", "score": 0.0}
      ],
      "cluster": "<primary cluster id, or null if unresolved>",
      "alsoIn": ["<secondary cluster id>", "..."],
      "lastChecked": "YYYY-MM-DD"
    }
  },
  "clusters": {
    "<cluster id>": {
      "domain": "clients | processes | tools | analytics | team | decisions | organization | <custom> | null",
      "pages": ["<wiki page path this cluster feeds>", "..."],
      "members": ["<data file path>", "..."]
    }
  },
  "flagged": [
    {
      "type": "candidate-merge | multi-topic | thin-cluster",
      "clusters": ["<cluster id>", "..."],
      "file": "<data file path, for multi-topic flags>",
      "reason": "<one sentence: why this needs a human/consolidator judgment call>",
      "flaggedOn": "YYYY-MM-DD"
    }
  ]
}
```

`alsoIn` and the `flagged` array are new in this version — they exist so this skill never has to
force a clean single-cluster answer when the evidence is genuinely ambiguous. `domain`/`pages` on a
cluster may be `null`/empty until `ob-similarity-consolidate` assigns them; this skill never writes
`domain` or `pages` itself.

## Step 3 — Discover files needing (re)processing

Glob `Data\**\*.md`. A file needs processing this run if any of these are true:
- Its path isn't yet a key in `files` (never processed — bootstrap case)
- Its key exists but current mtime is newer than the stored `mtime` (content changed since last
  check — the stored summary/neighbors are stale)
- Its `lastChecked` is **30+ days old**, even with unchanged mtime and content (see below)

For the first two cases, run the full Step 4 (Phase A then, if needed, Phase B). For the third case
(pure staleness recheck, content unchanged) — **skip Phase A and go straight to Phase B.** The
cluster from last time is already known; the only reason to recheck a stable file at all is to look
for new connections the broader corpus may have grown since it was last processed, and Phase A
would just re-confirm the same wiki match and stop there, defeating the point of rechecking.

**Why the 30-day rule exists:** two files can each be processed once, at different times, without
ever being strong matches for each other *at that time* — but the corpus keeps growing, and months
later there may be files connecting them that didn't exist yet. Neither file's mtime ever changes,
so without this rule neither would ever be reprocessed and the connection would never surface. This
is what replaces the purpose `ob-wiki-update`'s periodic full rerun served, at the cost of a cheap
re-query per stale file rather than a full reread of the entire corpus. 30 days is a starting
default; tune it if it re-queries too much or too little in practice.

If nothing needs processing, tell the user the graph is current and stop.

## Step 4 — Self-query each file (two-phase)

For each file needing processing, in any order:

1. **Read the file in full.** This cannot be skipped or shortened — everything downstream depends
   on knowing what's actually in it.
2. **Write a 2-3 sentence summary** capturing its topic, entities involved, and key facts. This
   summary is the qmd query, not the raw file content — keeps the query focused on meaning rather
   than incidental phrasing. **For files under `Data\Codex\`**, summarize what was actively worked
   on or explored, not what was "decided" — these are conversation transcripts revealing intent and
   focus, not established facts; don't let exploratory framing read as a settled claim. Skip
   sessions that are purely infrastructure/tooling (setting up git, configuring hooks, building this
   vault's own skills) — flag them as `no-wiki-value` in `keyTerms` rather than forcing a summary
   that has nothing to connect to.
3. **Extract 3-6 key terms** — proper nouns worth an exact-match pass: client names, tool names,
   people, decision titles.

**Phase A — check existing wiki fit first** (full processing only; staleness rechecks skip to Phase B):

4. Query qmd against the wiki only:
   ```
   searches: [
     { type: "hyde", query: "<the 2-3 sentence summary>" },
     { type: "lex",  query: "<key terms, space-separated>" }
   ]
   collections: ["level-knowledge"]
   limit: 10
   minScore: 0.2
   intent: "finding existing wiki pages this file's content belongs to"
   ```
5. Read the top candidate page(s) in full and judge on content, same as any neighbor judgment (see
   Step 5). If one is a confident, genuine fit:
   - Assign `files[path].cluster` to that page's cluster id directly.
   - Populate this file's `neighbors` from `clusters[id].members` (already known — no query needed)
     plus the matched page itself. **Skip Phase B entirely for this file.**
   - Store the summary/key terms/`lastChecked` as usual and move to the next file.

**Phase B — broaden to raw data** (runs whenever Phase A found no confident fit, or on a staleness recheck):

6. Query qmd across both collections:
   ```
   searches: [
     { type: "hyde", query: "<the same 2-3 sentence summary>" },
     { type: "lex",  query: "<the same key terms>" }
   ]
   collections: ["data", "level-knowledge"]
   limit: 20
   minScore: 0.15
   intent: "finding files and wiki pages related to <one-line description> for wiki clustering"
   ```
   The raised `limit` (20, not the default) and low `minScore` floor are deliberate — this phase is
   about generating a broad candidate set for Codex to judge, not finding the single best answer.
   A tighter default would silently exclude real-but-weaker connections before Codex ever sees them.
7. Drop the file's own docid if qmd returns a self-match.
8. Store the summary, key terms, neighbor list (file + score), and today's date as `lastChecked`
   under this file's entry in `files`. Update `mtime` to the file's current mtime.

## Step 5 — Judge candidates, assign clusters, and flag ambiguity

This step applies to files that went through Phase B (Phase A matches already resolved in Step 4.5).
For staleness rechecks specifically, it also applies to files that already had a `cluster` assigned
— here the goal is to find *additional* connections, not replace the existing one.

1. For every candidate neighbor, pull enough context to judge it — `mcp__qmd__get(file, fromLine=max(1, line-20), maxLines=100)` for a raw `data/` neighbor, or the full page for a `level-knowledge/` neighbor (short enough to read whole, and you need full context to judge fit anyway).
2. **Judge each candidate on content, not score.** A high qmd score means "textually/semantically
   similar," not "the same topic." Reject a neighbor if it's superficially similar (e.g., both are
   Signal Ops check-ins, but about different clients) — read enough to be sure. Confirm a neighbor
   if it's genuinely the same entity, thread, or topic even if its score is middling.
3. **Resolve the unambiguous cases directly:**
   - File has no `cluster` yet, and every confirmed neighbor shares one existing cluster → join it.
   - File has no `cluster` yet, no confirmed neighbor has one → mint a new cluster id (short slug
     from the dominant topic). If this file also has **zero confirmed neighbors at all**, the new
     cluster has exactly one member — do not treat this as an error; it's the "new domain candidate"
     signal a keyword-routing approach would have to infer indirectly. Still, add a `thin-cluster`
     flag for the consolidator to confirm it's a real new topic rather than a missed connection.
4. **Flag, don't force, the ambiguous cases:**
   - A file already has a `cluster` (from a prior run or Phase A) but a Phase B neighbor confirms a
     genuine connection to a *different* cluster → do not overwrite the primary `cluster`, do not
     merge the clusters yourself. Add the candidate cluster id to `files[path].alsoIn` and push a
     `multi-topic` entry to `flagged` with a one-sentence reason. Let the consolidator decide
     whether this becomes real dual membership or gets dismissed.
   - Confirmed neighbors span two or more *different* existing clusters and this file has no prior
     cluster of its own → don't pick one arbitrarily and don't merge them yourself. Assign the file
     provisionally to whichever cluster its strongest confirmed neighbor belongs to, and push a
     `candidate-merge` entry to `flagged` naming both clusters, so the consolidator can read across
     them and decide if they're really the same topic.
5. Update `files[path].cluster`, `files[path].alsoIn`, and `clusters[id].members` accordingly. Never
   delete or overwrite an existing flagged entry that's still unresolved from a prior run — only
   the consolidator clears entries from `flagged`.

## Step 6 — Save graph state and report

1. Write the updated graph back to `.Codex\similarity-graph.json`, with `lastRun` set to today.
   Leave `domain` and `pages` on any cluster exactly as they were — this skill never sets them.
2. Log to `Level Knowledge\log.md`: `| YYYY-MM-DD | ob-similarity-update: N files processed, M clusters touched, K new clusters, F newly flagged | |`
3. Report to the user:
   ```
   Similarity graph update — YYYY-MM-DD

   Inbox: [N files sorted by ob-inbox, or "nothing to sort"]
   Files processed: N (B bootstrap, I incremental, S re-checked for staleness)
   Clusters touched: M
   New clusters (candidate new topics): K — list each with its member file(s)
   Newly flagged for consolidation: F — list each with its type and reason
   qmd embedding gap: [note if Step 1 found un-embedded files still pending]

   Run /ob-similarity-consolidate to resolve flags and write wiki pages.
   ```

## Rules

- **Check the wiki before broadening to raw data.** Phase A (`level-knowledge` only) runs first for
  every newly/changed file; Phase B (`data` + `level-knowledge`) only runs if Phase A found no
  confident match, or this is a staleness recheck (which always goes straight to Phase B).
- **Never resolve genuine ambiguity yourself — flag it.** A candidate cluster merge or a possible
  second topic for a file is exactly the kind of decision `ob-similarity-consolidate` exists to
  make with fuller context. Forcing a decision here to avoid a flag defeats the purpose of the split.
- **qmd supplies candidates; Codex decides membership.** Never confirm a neighbor, or resolve a
  flag, on similarity score alone — always read before deciding.
- **A file's own content always gets read in full.** Only *neighbor* context is windowed.
- **The graph is a cache, not a source of truth.** If a stored cluster assignment looks wrong on
  re-reading, correct the unambiguous parts directly and flag the rest — don't preserve a stale
  grouping just because it's already recorded.
- **Don't re-embed or re-query files that are neither changed nor 30+ days stale.** Step 3's checks
  exist purely to bound how much gets re-queried — this is the efficiency payoff of persisting the
  graph.
- **Never skip Step 0.** Anything dropped in `Data/Inbox/` and never sorted is invisible to every
  later step.
- **This skill never writes to `Level Knowledge/`, never sets `cluster.domain`/`cluster.pages`, and
  never clears an entry from `flagged`.** That's `ob-similarity-consolidate`'s job entirely.
