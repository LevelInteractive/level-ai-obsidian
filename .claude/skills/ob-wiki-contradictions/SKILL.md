# ob-wiki-contradictions

This is an orchestration skill — it does not detect issues itself. It calls `ob-wiki-lint` to detect them, then `wiki-triage` to plan fixes, then applies what the user selects.

Audit the wiki for all issues, produce a prioritized action plan, and implement the corrections the user selects.

## Step 1 — Run the ob-wiki-lint skill

Invoke the `ob-wiki-lint` skill using the Skill tool. **Wait for it to fully complete** before moving to Step 2 — do not proceed until it has finished writing its outputs.

The skill runs the `wiki-lint` subagent, which lints every page in `Level Knowledge/` and writes a full report to `Level Playbook/wiki-lint/wiki-lint-<TODAY>.md`, plus a condensed active-issues list to the fixed path `.claude/linter.md` (overwritten wholesale each run — never stale from a prior run).

## Step 2 — Read the active-issues list

Read `.claude/linter.md` using the Read tool — a fixed path, so there's no need to track the dated report filename from the agent's output.

## Step 3 — Run the wiki-triage subagent

Use the Agent tool with `subagent_type: "wiki-triage"`. Pass the full `.claude/linter.md` content in the prompt:

```
Here is the wiki linter's active-issues list. Produce a prioritized action plan.

<paste full .claude/linter.md content>
```

Capture the triage agent's output — a numbered action plan.

## Step 4 — Present the plan to the user

Display the action plan clearly. Keep all item numbers intact so the user can reference them by number.

Follow the plan with a separator and this prompt to the user:

---

**Which items would you like me to implement?**
Reply with item numbers (`1, 3, 5`), a range (`1–4`), a priority level (`all P1`), or `all`.

---

## Step 5 — Wait for user selection

**Stop here.** Do not implement anything until the user responds with their selection. The user's next message is their answer.

## Step 6 — Implement the selected items

After the user replies, parse their selection and collect the target files for every chosen item.

**Batch the reads up front** — before making any edits, read all distinct target files in one pass instead of one `Read` call per item: use a single shell call (`Get-Content -Raw` per file with a `=== FILE: path ===` delimiter on Windows, `cat` with an `echo` delimiter on Mac/Linux), the same pattern `wiki-lint` uses. If two selected items land on the same file, that file only needs to be read once.

Then, working in priority order (P1 first):
1. Apply the specific fix described in the action plan to the already-read content — make only that change, nothing else
2. Note the change (one line: file path + what changed)

Edits still happen one file at a time via the Edit tool — only the reads are batched. If two items touch the same file, apply both changes in the same edit pass rather than two separate write round-trips.

## Step 7 — Summarize fixes

After all selected items are applied:

```
Fixed N items:
- Level Knowledge/path/file.md — what changed
- Level Knowledge/path/file.md — what changed
...

Skipped: [any items you could not apply, and why]
```

If the user selected items that turn out to be already-fixed, invalid, or unfixable without more information, note them in the Skipped list rather than guessing.

Graph color group syncing is **not** part of this skill — run `/wiki-graph-sync` separately if wiki structure changed as part of the fixes applied here.
