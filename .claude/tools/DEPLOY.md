# Claude Code Session Monitor - Deployment & Usage Guide

## Overview

Tracks session health across all your Claude Code environments to identify
`tool_use ids must be unique` corruption patterns. Logs every tool call,
detects duplicate IDs in real-time, and provides summary reports.

## Files

```
.claude/tools/
├── session-monitor.sh        # Main monitor CLI (run in separate terminal)
├── hooks-session-start.sh    # Hook: logs session start + environment
├── hooks-post-tool.sh        # Hook: logs tool calls + detects duplicate IDs
├── hooks-session-stop.sh     # Hook: logs session end + summary stats
├── hooks-on-error.sh         # Manual: log API errors for tracking
├── settings-hooks-snippet.json  # Reference: hook config to merge
└── DEPLOY.md                 # This file
```

Data is written to: `~/.claude/session-monitor/`

---

## Deployment

### Step 1: Copy tools to your home directory

The hooks reference `~/.claude/tools/` so they work from any project directory.

```bash
# On each machine (Linux and Windows/WSL):
mkdir -p ~/.claude/tools
cp .claude/tools/*.sh ~/.claude/tools/
chmod +x ~/.claude/tools/*.sh
```

### Step 2: Add hooks to your settings

Edit `~/.claude/settings.json` on **each machine**. Merge the hooks with your
existing config. Your current settings likely look like this:

```json
{
    "hooks": {
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/stop-hook-git-check.sh"
                    }
                ]
            }
        ]
    }
}
```

Add the monitoring hooks so it becomes:

```json
{
    "hooks": {
        "SessionStart": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/tools/hooks-session-start.sh"
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/tools/hooks-post-tool.sh"
                    }
                ]
            }
        ],
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/tools/hooks-session-stop.sh"
                    },
                    {
                        "type": "command",
                        "command": "~/.claude/stop-hook-git-check.sh"
                    }
                ]
            }
        ]
    }
}
```

> **Note**: The Stop hook chains both the monitor AND your existing git-check
> hook. Order matters — monitor runs first so it always logs, even if
> git-check blocks the stop.

### Step 3: Verify installation

```bash
# Check scripts are executable
ls -la ~/.claude/tools/

# Run a quick test
echo '{"session_id":"test","tool_name":"bash"}' | ~/.claude/tools/hooks-post-tool.sh
cat ~/.claude/session-monitor/events.jsonl
```

---

## Usage

### Live Monitoring (run in a separate terminal)

```bash
# Tail events in real-time with color coding
~/.claude/tools/session-monitor.sh

# Green  = session start
# Blue   = session end
# Gray   = tool call
# Yellow = compact
# Red    = error / corruption
```

### Summary Report

```bash
~/.claude/tools/session-monitor.sh --summary
```

Shows:
- Total sessions, tool calls, errors, corruption events
- Breakdown by environment (linux-cli, remote-control, windows)
- Last 10 errors with timestamps
- All corruption events

### Scan for Corruption

```bash
# Scan all sessions from last 7 days
~/.claude/tools/session-monitor.sh --check-corruption

# Scan a specific session
~/.claude/tools/session-monitor.sh --check-corruption abc123-session-id
```

### Log an API Error Manually

When you see a `tool_use ids must be unique` error, capture it:

```bash
echo "API Error: 400 tool_use ids must be unique req_xxx" | \
    ~/.claude/tools/hooks-on-error.sh my-session-id
```

### Clean Up Old Logs

```bash
~/.claude/tools/session-monitor.sh --clean
```

---

## Environment-Specific Workflow

### Linux CLI (local terminal)

```bash
# Terminal 1: Start monitor
~/.claude/tools/session-monitor.sh

# Terminal 2: Work normally
claude

# Best practices:
# - Run /compact when you see tool call count climbing in monitor
# - Use /cost to check token usage periodically
# - Commit early and often (your stop hook enforces this)
# - If monitor shows corruption warning, stop immediately and start new session
```

### Linux + Remote Control

```bash
# Terminal 1: Start monitor
~/.claude/tools/session-monitor.sh

# Terminal 2: Start remote control
claude --remote-control

# Best practices:
# - Monitor is especially important here (highest corruption risk)
# - Keep remote control sessions SHORT (under 30 min of active work)
# - Phase work: plan → execute → commit → new session
# - If network drops, DON'T reconnect to same session — start fresh
# - Watch monitor for rapid tool_use events (may indicate sync issues)
# - Run /compact after every major phase of work
```

### Windows Desktop

```powershell
# PowerShell/Git Bash: Copy tools (one-time setup)
mkdir -p ~/.claude/tools
cp .claude/tools/*.sh ~/.claude/tools/
chmod +x ~/.claude/tools/*.sh

# Terminal 1 (Git Bash or WSL): Start monitor
~/.claude/tools/session-monitor.sh

# Terminal 2: Work normally in Claude Code
claude

# Best practices:
# - Same as Linux CLI
# - If using WSL, monitor detects "windows" environment via WSLENV
# - Ensure jq is installed: winget install jqlang.jq (or via WSL apt)
```

---

## Reading the Data

### Quick Checks

```bash
# How many sessions today?
grep "session_start" ~/.claude/session-monitor/events.jsonl | \
    grep "$(date +%Y-%m-%d)" | wc -l

# Any corruption today?
grep "corruption.*true" ~/.claude/session-monitor/events.jsonl | \
    grep "$(date +%Y-%m-%d)"

# Which environment has most errors?
grep '"event":"error"' ~/.claude/session-monitor/events.jsonl | \
    jq -r '.env' | sort | uniq -c | sort -rn

# Average tool calls per session
grep '"event":"session_end"' ~/.claude/session-monitor/events.jsonl | \
    jq '.tool_calls' | awk '{sum+=$1; n++} END {print sum/n}'
```

### Session Summary CSV

The file `~/.claude/session-monitor/summary.csv` can be opened in any
spreadsheet tool for analysis. Columns:

| Column | Description |
|--------|-------------|
| timestamp | Session end time |
| session_id | Claude session identifier |
| environment | linux-cli, remote-control, or windows |
| duration_sec | Session duration in seconds |
| tool_calls | Number of tool calls in session |
| errors | Number of errors logged |
| corrupted | true/false |
| crash_reason | Manual annotation field |

---

## Troubleshooting

### Hooks not firing
- Check `claude --version` is 2.1.51+ (hooks require this)
- Verify settings.json syntax: `jq . ~/.claude/settings.json`
- Check permissions: `ls -la ~/.claude/tools/`

### jq not found
- Linux: `sudo apt install jq`
- Windows (WSL): `sudo apt install jq`
- Windows (native): `winget install jqlang.jq`
- macOS: `brew install jq`

### Monitor shows no events
- Start a new session after installing hooks (existing sessions won't pick up changes)
- Check if events.jsonl exists: `ls -la ~/.claude/session-monitor/`

### Want to report corruption to Anthropic
Gather this and file at https://github.com/anthropics/claude-code/issues:
```bash
~/.claude/tools/session-monitor.sh --summary
# Include: version, environment, summary output, and request_ids from errors
```

---

## Recommended Session Workflow (All Environments)

1. **Start monitor** in a separate terminal
2. **Plan phase**: Define what you want to accomplish
3. **Execute phase**: Do the work, watching monitor for warnings
4. **Checkpoint**: Run `/compact`, commit work
5. **Evaluate**: Check `/cost`, review monitor for anomalies
6. **Handoff or continue**: Start new session if context is high

**Golden rule**: If the monitor shows any `CORRUPTION DETECTED` — stop
immediately, commit what you have, and start a new session. Do not try to
recover.
