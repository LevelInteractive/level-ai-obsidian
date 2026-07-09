# Reads a Claude Code session transcript and appends new turns to an Obsidian note.
# Vault path is derived from $PSScriptRoot so this works for any user who opens this vault.

$input_json = $input | Out-String
$data = $input_json | ConvertFrom-Json -ErrorAction SilentlyContinue
$session_id = $data.session_id

# Resolve vault root from script location (.claude/ -> vault root)
$vault_root = (Resolve-Path "$PSScriptRoot\..").Path
$vault      = "$vault_root\Data\Claude"
$state_dir  = "$vault\.state"
$user_label = $env:USERNAME

if (-not (Test-Path $vault))     { New-Item -ItemType Directory -Force -Path $vault     | Out-Null }
if (-not (Test-Path $state_dir)) { New-Item -ItemType Directory -Force -Path $state_dir | Out-Null }

# Find the transcript file for this session
$transcript_dir  = "$env:USERPROFILE\.claude\projects"
$transcript_file = Get-ChildItem -Path $transcript_dir -Recurse -Filter "*.jsonl" |
    Where-Object { $_.Name -like "*$session_id*" -or $_.FullName -like "*$session_id*" } |
    Select-Object -First 1

# Get ai-title for filename
$ai_title = $null
if ($transcript_file) {
    Get-Content $transcript_file.FullName -Encoding UTF8 | ForEach-Object {
        try {
            $e = $_ | ConvertFrom-Json
            if ($e.type -eq "ai-title" -and $e.aiTitle -and -not $ai_title) {
                $ai_title = $e.aiTitle
            }
        } catch {}
    }
}
$safe_title = if ($ai_title) {
    ($ai_title -replace '[\\/:*?"<>|]', '-').Trim()
} else {
    $session_id.Substring(0, [Math]::Min(8, $session_id.Length))
}
$filename   = "$vault\$safe_title.md"
$state_file = "$state_dir\$session_id.json"
$date       = Get-Date -Format "yyyy-MM-dd"

# Load already-exported UUIDs from state file
$exported = @{}
if (Test-Path $state_file) {
    (Get-Content $state_file -Encoding UTF8 | ConvertFrom-Json) | ForEach-Object { $exported[$_] = $true }
}

# Read transcript and collect only new turns
$new_turns = @()
$seen_leaf = @{}
$seen_text = @{}
$all_uuids = @()

if ($transcript_file) {
    Get-Content $transcript_file.FullName -Encoding UTF8 | ForEach-Object {
        try {
            $entry = $_ | ConvertFrom-Json

            if ($entry.type -eq "last-prompt" -and $entry.lastPrompt) {
                $key  = $entry.leafUuid
                $text = $entry.lastPrompt.Trim()
                if (-not $seen_leaf[$key] -and -not $seen_text["u:$text"]) {
                    $seen_leaf[$key]      = $true
                    $seen_text["u:$text"] = $true
                    $all_uuids += $key
                    if (-not $exported[$key]) {
                        $new_turns += [PSCustomObject]@{ role = "user"; text = $text; uuid = $key }
                    }
                }
            }

            if ($entry.type -eq "assistant" -and $entry.message.role -eq "assistant") {
                foreach ($block in $entry.message.content) {
                    if ($block.type -eq "text" -and $block.text.Length -gt 0) {
                        $text = $block.text.Trim()
                        $key  = $entry.uuid
                        if (-not $seen_leaf[$key] -and -not $seen_text["a:$text"]) {
                            $seen_leaf[$key]      = $true
                            $seen_text["a:$text"] = $true
                            $all_uuids += $key
                            if (-not $exported[$key]) {
                                $new_turns += [PSCustomObject]@{ role = "assistant"; text = $text; uuid = $key }
                            }
                        }
                    }
                }
            }
        } catch {}
    }
}

if ($new_turns.Count -eq 0) { exit 0 }

# Render new turns as markdown
$new_block = ($new_turns | ForEach-Object {
    if ($_.role -eq "user") { "**${user_label}:** $($_.text)" } else { "**Claude:** $($_.text)" }
}) -join "`n`n---`n`n"

if (-not (Test-Path $filename)) {
    $note = @"
---
date: $date
session_id: $session_id
tags: [claude, session]
---

# Claude Session — $safe_title

## Conversation

$new_block

## Notes

<!-- Add your own notes here -->
"@
    [System.IO.File]::WriteAllText($filename, $note, [System.Text.UTF8Encoding]::new($false))
} else {
    $existing    = [System.IO.File]::ReadAllText($filename, [System.Text.UTF8Encoding]::new($false))
    $notes_index = $existing.IndexOf("`n## Notes")
    $insert      = "`n`n---`n`n$new_block"
    $updated     = $existing.Substring(0, $notes_index) + $insert + $existing.Substring($notes_index)
    [System.IO.File]::WriteAllText($filename, $updated, [System.Text.UTF8Encoding]::new($false))
}

# Save updated state
$all_uuids | ConvertTo-Json | Set-Content $state_file -Encoding UTF8
