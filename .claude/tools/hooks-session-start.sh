#!/bin/bash
# =============================================================================
# SessionStart Hook - Logs session start with environment detection
# =============================================================================

set -uo pipefail

MONITOR_DIR="${HOME}/.claude/session-monitor"
EVENT_LOG="${MONITOR_DIR}/events.jsonl"

mkdir -p "${MONITOR_DIR}"

# Read hook input from stdin
input=$(cat)

session_id=$(echo "${input}" | jq -r '.session_id // "unknown"' 2>/dev/null)

# Detect environment
if [[ -n "${CLAUDE_REMOTE_CONTROL:-}" ]] || [[ -n "${CLAUDE_REMOTE:-}" ]]; then
    env="remote-control"
elif [[ "$(uname -s)" == "MINGW"* ]] || [[ "$(uname -s)" == "MSYS"* ]] || [[ -n "${WSLENV:-}" ]]; then
    env="windows"
elif [[ "$(uname -s)" == "Linux" ]]; then
    env="linux-cli"
else
    env="unknown"
fi

# Capture system context
claude_version=$(claude --version 2>/dev/null || echo "unknown")
working_dir=$(pwd)

echo "{\"ts\":\"$(date -Is)\",\"event\":\"session_start\",\"env\":\"${env}\",\"session_id\":\"${session_id}\",\"claude_version\":\"${claude_version}\",\"working_dir\":\"${working_dir}\"}" >> "${EVENT_LOG}"

exit 0
