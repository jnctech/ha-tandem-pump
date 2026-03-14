#!/bin/bash
# =============================================================================
# Stop Hook - Logs session end and captures any error state
# =============================================================================

set -uo pipefail

MONITOR_DIR="${HOME}/.claude/session-monitor"
EVENT_LOG="${MONITOR_DIR}/events.jsonl"

mkdir -p "${MONITOR_DIR}"

# Read hook input from stdin
input=$(cat)

session_id=$(echo "${input}" | jq -r '.session_id // "unknown"' 2>/dev/null)
stop_hook_active=$(echo "${input}" | jq -r '.stop_hook_active // false' 2>/dev/null)

# Prevent recursion from existing stop hook
if [[ "${stop_hook_active}" == "true" ]]; then
    exit 0
fi

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

# Count tool calls for this session
tool_count=0
if [[ -f "${EVENT_LOG}" ]]; then
    tool_count=$(grep "\"session_id\":\"${session_id}\"" "${EVENT_LOG}" 2>/dev/null | grep -c '"event":"tool_use"' || echo 0)
fi

# Check for corruption during this session
corruption_count=0
if [[ -f "${EVENT_LOG}" ]]; then
    corruption_count=$(grep "\"session_id\":\"${session_id}\"" "${EVENT_LOG}" 2>/dev/null | grep -c '"corruption":true' || echo 0)
fi

# Calculate session duration
start_ts=""
if [[ -f "${EVENT_LOG}" ]]; then
    start_ts=$(grep "\"session_id\":\"${session_id}\"" "${EVENT_LOG}" 2>/dev/null | grep '"event":"session_start"' | head -1 | jq -r '.ts // ""' 2>/dev/null)
fi

duration="unknown"
if [[ -n "${start_ts}" ]]; then
    start_epoch=$(date -d "${start_ts}" +%s 2>/dev/null || echo 0)
    now_epoch=$(date +%s)
    if [[ "${start_epoch}" -gt 0 ]]; then
        duration=$(( now_epoch - start_epoch ))
    fi
fi

corrupted="false"
if [[ "${corruption_count}" -gt 0 ]]; then
    corrupted="true"
fi

echo "{\"ts\":\"$(date -Is)\",\"event\":\"session_end\",\"env\":\"${env}\",\"session_id\":\"${session_id}\",\"tool_calls\":${tool_count},\"duration_sec\":\"${duration}\",\"corruption\":${corrupted},\"corruption_count\":${corruption_count}}" >> "${EVENT_LOG}"

# Append to summary CSV
SUMMARY_LOG="${MONITOR_DIR}/summary.csv"
if [[ ! -f "${SUMMARY_LOG}" ]]; then
    echo "timestamp,session_id,environment,duration_sec,tool_calls,errors,corrupted,crash_reason" > "${SUMMARY_LOG}"
fi
echo "$(date -Is),${session_id},${env},${duration},${tool_count},${corruption_count},${corrupted}," >> "${SUMMARY_LOG}"

# Clean up ID tracker for this session
rm -f "${MONITOR_DIR}/ids-${session_id}.tmp"

# Exit 0 - don't block the stop hook chain
exit 0
