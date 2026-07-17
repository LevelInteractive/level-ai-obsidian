---
name: ob-wiki-update
description: >
  Evidence-reviews a bounded ingestion packet and applies only the approved
  Level Knowledge page changes supported by its sources. Use after
  prepare_ingest_packet.py succeeds.
---

# ob-wiki-update

Review the bounded packet prepared by ingestion, then write only the approved
changes to the affected `Level Knowledge/` pages. This skill is the bounded
evidence reviewer and wiki-page writer: it does not discover sources, sort the
inbox, run QMD, edit operational metadata, or advance source state.

## Input contract

Require a completed packet from `prepare_ingest_packet.py` and its source-state
delta. Before reviewing, confirm it includes:

- explicit source paths and SHA-256 hashes;
- selected and queued candidate pages with reasons;
- taxonomy cues and existing-page scope matches;
- QMD and metadata-preflight status.

If the packet is absent, stale, or failed, stop and return control to ingestion.
Do not scan all of `Data/` as a fallback.

## Review workflow

1. Read each explicit source and only the selected or queued wiki pages needed
   to judge it.
2. Treat selected candidates as hypotheses and queued candidates as ambiguity;
   reject anything the evidence does not materially affect.
3. For supported evidence, classify the outcome:
   - **enrich** an existing page;
   - **correct** a contradicted claim;
   - **create** a page only when the packet's independence check and evidence
     threshold are satisfied;
   - **no wiki change** for one-off, duplicate, unsupported, or
     corroboration-only material.
4. Apply only the supported page edits or independently justified page
   creations. Do not write rejected, queued, or unresolved candidates.
5. Return the changes applied, rejected candidates, unresolved questions,
   required taxonomy changes, and any index/graph/HELP follow-up to ingestion.
   Ingestion validates the writes and accepts the source-state delta only after
   its post-write validation succeeds.

## Domain and scope guide

| Evidence signal | Usual domain |
|---|---|
| Client, account, campaign | `clients` |
| Workflow, SOP, operating practice | `processes` |
| Platform, integration, software | `tools` |
| Metric, model, dataset, SQL | `analytics` |
| Person, role, ownership | `team` |
| Concrete decision | `decisions` |
| Durable personal practice or learning | `interests` |

Existing custom domains are valid targets when they fit the packet's reviewed
scope better. Prefer an existing page when it already covers the subject.

## Evidence and safety rules

- Read an existing page in full before proposing a change.
- Preserve prior knowledge that new evidence does not address.
- Never infer operational facts from conversational filler or a single
  exploratory transcript.
- Agent-session material is corroboration-only unless independently supported.
- Never carry credentials into a wiki result: redact API keys, secret tokens,
  passwords, private-key material, embedded-credential connection strings,
  bearer/basic tokens, and tokenized webhook URLs.
- Keep email addresses, names, ordinary URLs, and hashes unless another policy
  requires redaction.

## Page-review rules

For every approved edit or creation:

- Write only to the affected wiki page or independently justified new wiki
  page. Do not write operational files.
- Never modify `## Notes`; read it only for confirming, contradicting, or
  new-information signals.
- Preserve sections that the reviewed sources do not address.
- Merge evidence into the relevant section; do not blind-append.
- Keep `last_updated`, `confidence`, tags, `## References`, and the
  confidence footnote internally consistent.
- Add only raw sources actually read and used to `## References`.
- Use internal wikilinks for known entities; do not over-link repeated mentions.
- Add relevant attachments or a team profile image when the reviewed evidence
  identifies one; do not add empty attachment sections.

## Confidence and decay

Use source count/consistency, recency, and protected `## Notes` together:

- **high**: 3+ consistent, recent raw sources with no contradicting note;
- **medium**: 1–2 sources, partial evidence, or a contradiction needing review;
- **low**: stale evidence, uncorroborated session material, or unresolved
  conflict.

A confirming user note can prevent full decay but cannot make a page high
without raw-source evidence. Decisions are point-in-time records and do not
decay. Flag genuinely stale claims for the linter/contradiction workflow rather
than deleting history during a bounded ingest review.

## Taxonomy guardrail

Follow `.config/tagging.md` as the canonical vocabulary and taxonomy policy.

- Update an existing page if it already covers the reviewed subject.
- A new page requires an independent scope and the required independent-source
  evidence.
- A new folder requires three genuinely separate child-page scopes, not merely
  several sources about one topic.
- When scope is uncertain, return a review cue; do not create a page or folder.
- New theme tags require substantive recurrence across three distinct reviewed
  sources.

## Review result

After applying the approved page changes, return a concise result to ingestion:

```text
Sources reviewed: N
Applied changes: page — evidence summary
Rejected candidates: page — reason
New-page/folder decisions: approved | rejected | needs review
Operational follow-up: index | graph | HELP | source move/delete maintenance
Open questions: ...
```

The skill may update approved `Level Knowledge/` content pages, but never
updates `index.md`, `HELP.md`, `Level Knowledge/log.md`, the dependency
graph, or `.kb-indexer/metadata/state/source-state.json`.
