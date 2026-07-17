---
name: ob-similarity-consolidate
description: >
  Reads the similarity graph built by ob-similarity-update, resolves everything it flagged
  (candidate cluster merges, files that may belong to more than one topic, thin single-file
  clusters), then synthesizes/updates Level Knowledge wiki pages from the confirmed clusters using
  its own self-contained page templates, confidence model, and decay rules. This is the only skill
  in the ob-similarity-* pair that writes to Level Knowledge/. Use when the user runs
  /ob-similarity-consolidate, asks to "consolidate the graph", "resolve the flagged connections",
  "sync the wiki from the similarity graph", or after running /ob-similarity-update.
---

# ob-similarity-consolidate

The second half of the qmd-similarity ingestion pipeline. `ob-similarity-update` builds the graph
and flags anything ambiguous rather than guessing; this skill reads those flags, makes the actual
judgment calls with full context, and then writes the wiki. It is the only place in this pipeline
that touches `Level Knowledge/`.

This skill is **self-contained** — its own `references/synthesis.md` holds the page templates, the
three-way confidence model, the decay pass, merge logic, wikilink rules, image linking, and
sensitive-content scrubbing. The only external reference is `.config/tagging.md`, the vault-wide
canonical tag vocabulary shared by every skill.

Run `ob-similarity-update` first if you haven't recently — this skill only resolves and synthesizes
what's already in the graph; it doesn't discover new files or query qmd for new connections itself.

## Vault paths

- **Vault root**: the current working directory (never hardcode a path)
- **Graph state**: `.Codex\similarity-graph.json` — shared with `ob-similarity-update`; that skill
  writes it, this skill reads it, resolves flags, and writes it back
- **Wiki root**: `Level Knowledge\`
- **Wiki index**: `Level Knowledge\index.md`
- **Synthesis spec**: `.Codex\skills\ob-similarity-consolidate\references\synthesis.md`
- **Tag vocabulary**: `.config\tagging.md` (shared vault config, not a dependency on any other skill)

## Step 0 — Load the graph

Read `.Codex\similarity-graph.json`. If it doesn't exist or `flagged` is empty and no cluster is
new/changed since the last consolidation, tell the user there's nothing to consolidate and stop —
suggest running `/ob-similarity-update` first if the file is missing entirely.

## Step 1 — Resolve flagged items

Work through every entry in `flagged`, in the order most likely to affect later entries first:
`candidate-merge` (changes cluster identity) → `multi-topic` (depends on cluster identity being
settled) → `thin-cluster` (independent, do last).

### `candidate-merge`

Read the actual member files of both named clusters (or a representative sample if a cluster is
large — at least 3 members, more if they look inconsistent) plus their existing wiki pages if any
are already mapped. Decide:
- **Genuinely the same topic** → merge: pick the cluster with more members (or an existing page
  mapping) as the surviving id, move all `members` into it, update every moved file's `cluster`
  field, delete the absorbed cluster, and if both had `pages` mapped, note the conflict for manual
  review rather than silently picking one (flag it back into `flagged` as a new `page-conflict` type
  if this happens — rare, but a genuine merge of two already-paged clusters needs a human to decide
  whether one page absorbs the other's content or they stay distinct sections).
- **Not the same topic, just superficially similar** → reject the merge. Remove the `candidate-merge`
  entry. No graph change beyond that — the two clusters simply stay separate, which is the correct
  and common outcome for things like "both are Signal Ops check-ins about different clients."

### `multi-topic`

Read the flagged file in full (if not already fresh in context) and both candidate clusters' recent
members. Decide:
- **Genuinely spans two topics** (e.g., a meeting that substantively covers both a recurring process
  and a specific client's issue) → confirm the secondary membership: add the file to the second
  cluster's `members`, keep it in `files[path].alsoIn`. This file will contribute to synthesis for
  *both* clusters' pages in Step 3 — see the per-cluster content filter there.
- **Not really — one topic just got mentioned in passing** → remove the cluster id from
  `files[path].alsoIn`. The file keeps its single primary `cluster` only.
- Remove the `multi-topic` entry from `flagged` either way once decided.

### `thin-cluster`

A single-member cluster is either a real new topic or a missed connection that Phase A/B simply
didn't surface strongly enough. Re-query qmd once more yourself, deliberately looser than the
original run — `type: "vec"` with the file's summary, `collections: ["data", "level-knowledge"]`,
`limit: 30`, `minScore: 0.05` — and read anything new that turns up.
- **A real connection turns up** → treat like a `candidate-merge`/join, above.
- **Still nothing** → confirmed new topic. Leave the cluster as-is; it proceeds to Step 2 as a
  legitimate single-source cluster (which will likely land at `confidence: low` in the synthesis
  model — that's correct and expected for a one-source topic, not a bug to fix here).
- Remove the `thin-cluster` entry from `flagged` either way once decided.

## Step 2 — Map clusters to wiki domains

For every cluster that is new, gained members, or had its `pages` unset before this run:

Determine the wiki domain (`clients`, `processes`, `tools`, `analytics`, `team`, `decisions`,
`organization`, or a new custom domain) from the cluster's dominant entity, applied to its members
collectively:

| Signal in the cluster's content | Domain |
|---|---|
| Client name, campaign, account | `clients` |
| "how we do X", workflow, SOP | `processes` |
| Software, platform, integration, tool name | `tools` |
| Metric, model, data source, dashboard, SQL | `analytics` |
| Person's name, role, responsibility | `team` |
| "we decided", "going forward", "approach" | `decisions` |
| Culture, values, org structure, policy | `organization` |

Set `clusters[id].domain` accordingly.

## Step 3 — Synthesize wiki pages

For each cluster processed in Step 2:

1. If the cluster already maps to existing pages (`clusters[id].pages`, or check `Level
   Knowledge\index.md` if not yet recorded), **read each of those pages in full** before writing —
   non-negotiable.
2. **Apply `references/synthesis.md`**: page templates, the three-way confidence model, the merge
   logic, the expansion pass, the decay pass, wikilink rules, image linking, `## References` (every
   cluster member that actually contributed content), sensitive-content scrubbing, and the
   Codex-session handling rules for any `Data\Codex\` member.
3. **For a file with `alsoIn` membership** (confirmed in Step 1): it contributes to *both* clusters'
   pages, but only the content genuinely relevant to each — don't copy the whole file's synthesis
   into both pages verbatim. Read it once, extract what's relevant to cluster A's page and what's
   relevant to cluster B's page separately, and cite it in both `## References` sections.
4. If no existing page fits, create one using the closest template in `references/synthesis.md`,
   following its restructuring / new-domain guidance as appropriate.
5. Record every page this cluster touched in `clusters[id].pages`. A single cluster commonly feeds
   more than one page — a client cluster fans out across `overview.md`, `issues.md`, `trends.md`,
   `sentiment.md`, and `wins.md` (route each snippet to the page matching its content per the
   client-page templates) — so append each page written rather than overwriting a single value.

## Step 4 — Update index.md, log, and save graph state

1. **Update `Level Knowledge\index.md`:** for each new page created, add a row to the correct
   domain table (`| [[filename\|Display Name]] | One-line description |` — bare filename, Obsidian
   resolves it). Register any new domain as its own section. Update `index.md`'s `last_updated`
   frontmatter to today. If a new domain was created, also add its graph color group per the
   restructuring/new-domain rules in `references/synthesis.md`.
2. **Refresh `HELP.md`** at the vault root only if this run changed the set of skills/agents/hooks
   (rare — usually skip).
3. Log to `Level Knowledge\log.md`: `| YYYY-MM-DD | ob-similarity-consolidate: R flags resolved, P pages written/updated | |`
4. Write the updated graph back to `.Codex\similarity-graph.json` — `flagged` should now be empty
   (or contain only genuinely new items you couldn't resolve this run; note why in the report if so).

## Step 5 — Report to the user

```
Similarity consolidation — YYYY-MM-DD

Flags resolved: R (M merges confirmed, X merges rejected, T multi-topic confirmed, D dismissed, N new-topic confirmed)
Unresolved flags remaining: [list any, with why]
Pages written/updated: list each, with the cluster(s) that fed it
New domains created: list any
```

## Rules

- **Every flag gets read, not guessed.** A merge or multi-topic decision made on cluster/file names
  alone, without reading actual content, is exactly the mistake the flag-instead-of-force design in
  `ob-similarity-update` was meant to prevent from happening blind.
- **A wiki page being written to is always read in full first** — no exception.
- **Don't leave a flag unresolved without saying so.** If Step 1 genuinely can't decide something
  (rare — usually more reading resolves it), leave it in `flagged` and name it explicitly in the
  Step 5 report rather than silently dropping it.
- **Core synthesis non-negotiables** (detailed in `references/synthesis.md`): never modify
  `## Notes`, never invent facts, scrub credentials per the sensitive-content rules, be conservative
  with Codex session files, prefer incremental edits over full page rewrites.
- **This skill doesn't discover new files or run new qmd self-queries against the whole corpus** —
  only the targeted re-query in the `thin-cluster` flag path. Broader discovery is
  `ob-similarity-update`'s job; running this skill repeatedly without re-running that one first will
  just find nothing new to consolidate.
