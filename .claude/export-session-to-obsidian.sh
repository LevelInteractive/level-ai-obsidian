#!/usr/bin/env bash
# Reads a Claude Code session transcript and appends new turns to an Obsidian note.
# Vault path is derived from the script location so this works for any user.

input_json=$(cat)
session_id=$(echo "$input_json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

# Resolve vault root from script location (.claude/ -> vault root)
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vault_root="$(dirname "$script_dir")"
vault="$vault_root/Data/Claude"
state_dir="$vault/.state"
user_label="${USER:-$(whoami)}"

mkdir -p "$vault" "$state_dir"

# Find the transcript file for this session
transcript_dir="$HOME/.claude/projects"
transcript_file=$(find "$transcript_dir" -name "*.jsonl" 2>/dev/null | xargs grep -l "$session_id" 2>/dev/null | head -1)

if [ -z "$transcript_file" ]; then exit 0; fi

# Get ai-title for filename
ai_title=$(python3 - "$transcript_file" <<'PYEOF'
import sys, json
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    for line in f:
        try:
            e = json.loads(line)
            if e.get("type") == "ai-title" and e.get("aiTitle"):
                print(e["aiTitle"])
                break
        except Exception:
            pass
PYEOF
)

if [ -n "$ai_title" ]; then
    safe_title=$(echo "$ai_title" | tr '\\/:*?"<>|' '-' | sed 's/^ *//;s/ *$//')
else
    safe_title="${session_id:0:8}"
fi

filename="$vault/$safe_title.md"
state_file="$state_dir/$session_id.json"
date=$(date +%Y-%m-%d)

# Load already-exported UUIDs
exported=""
if [ -f "$state_file" ]; then
    exported=$(cat "$state_file")
fi

# Parse transcript and collect new turns
new_turns=$(python3 - "$transcript_file" "$session_id" "$exported" "$user_label" <<'PYEOF'
import sys, json

transcript_path = sys.argv[1]
session_id      = sys.argv[2]
exported_raw    = sys.argv[3]
user_label      = sys.argv[4]

try:
    exported = set(json.loads(exported_raw)) if exported_raw.strip() else set()
except Exception:
    exported = set()

new_turns  = []
seen_leaf  = set()
seen_text  = set()
all_uuids  = []

with open(transcript_path, encoding="utf-8") as f:
    for line in f:
        try:
            entry = json.loads(line)

            if entry.get("type") == "last-prompt" and entry.get("lastPrompt"):
                key  = entry.get("leafUuid", "")
                text = entry["lastPrompt"].strip()
                if key not in seen_leaf and f"u:{text}" not in seen_text:
                    seen_leaf.add(key)
                    seen_text.add(f"u:{text}")
                    all_uuids.append(key)
                    if key not in exported:
                        new_turns.append({"role": "user", "text": text, "uuid": key})

            if entry.get("type") == "assistant" and entry.get("message", {}).get("role") == "assistant":
                for block in entry["message"].get("content", []):
                    if block.get("type") == "text" and block.get("text", "").strip():
                        text = block["text"].strip()
                        key  = entry.get("uuid", "")
                        if key not in seen_leaf and f"a:{text}" not in seen_text:
                            seen_leaf.add(key)
                            seen_text.add(f"a:{text}")
                            all_uuids.append(key)
                            if key not in exported:
                                new_turns.append({"role": "assistant", "text": text, "uuid": key})
        except Exception:
            pass

if not new_turns:
    sys.exit(0)

lines = []
for t in new_turns:
    label = user_label if t["role"] == "user" else "Claude"
    lines.append(f"**{label}:** {t['text']}")

print(json.dumps({"turns": lines, "all_uuids": all_uuids}))
PYEOF
)

if [ -z "$new_turns" ]; then exit 0; fi

# Extract turns and uuids from python output
turns_block=$(python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
print('\n\n---\n\n'.join(data['turns']))
" <<< "$new_turns")

all_uuids=$(python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
print(json.dumps(data['all_uuids']))
" <<< "$new_turns")

if [ ! -f "$filename" ]; then
    cat > "$filename" <<EOF
---
date: $date
session_id: $session_id
tags: [claude, session]
---

# Claude Session — $safe_title

## Conversation

$turns_block

## Notes

<!-- Add your own notes here -->
EOF
else
    python3 - "$filename" "$turns_block" <<'PYEOF'
import sys

path       = sys.argv[1]
new_block  = sys.argv[2]

with open(path, encoding="utf-8") as f:
    existing = f.read()

marker = "\n## Notes"
idx    = existing.find(marker)
if idx == -1:
    existing += f"\n\n---\n\n{new_block}"
else:
    existing = existing[:idx] + f"\n\n---\n\n{new_block}" + existing[idx:]

with open(path, "w", encoding="utf-8") as f:
    f.write(existing)
PYEOF
fi

# Save updated state
echo "$all_uuids" > "$state_file"
