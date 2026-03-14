#!/bin/bash
# =============================================================================
# PostToolUse Hook - Logs every tool call for session monitoring
# =============================================================================
# Called automatically by Claude Code after each tool use.
# Receives JSON on stdin with tool details.
# =============================================================================

set -uo pipefail

MONITOR_DIR="${HOME}/.claude/session-monitor"
EVENT_LOG="${MONITOR_DIR}/events.jsonl"

mkdir -p "${MONITOR_DIR}"

# Read hook input from stdin
input=$(cat)

# Extract fields from hook input
tool_name=$(echo "${input}" | jq -r '.tool_name // .tool // "unknown"' 2>/dev/null)
session_id=$(echo "${input}" | jq -r '.session_id // "unknown"' 2>/dev/null)
tool_use_id=$(echo "${input}" | jq -r '.tool_use_id // "none"' 2>/dev/null)

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

# Log the tool use event
echo "{\"ts\":\"$(date -Is)\",\"event\":\"tool_use\",\"env\":\"${env}\",\"session_id\":\"${session_id}\",\"tool\":\"${tool_name}\",\"tool_use_id\":\"${tool_use_id}\"}" >> "${EVENT_LOG}"

# Track tool_use_id for corruption detection
# Maintain a rolling set of recent IDs per session
ID_TRACKER="${MONITOR_DIR}/ids-${session_id}.tmp"
if [[ "${tool_use_id}" != "none" ]]; then
    # Check if this ID was already seen (corruption indicator)
    if [[ -f "${ID_TRACKER}" ]] && grep -qF "${tool_use_id}" "${ID_TRACKER}" 2>/dev/null; then
        echo "{\"ts\":\"$(date -Is)\",\"event\":\"error\",\"env\":\"${env}\",\"session_id\":\"${session_id}\",\"message\":\"DUPLICATE tool_use_id detected: ${tool_use_id}\",\"corruption\":true}" >> "${EVENT_LOG}"
        # Write to stderr so it appears in Claude Code output
        echo "WARNING: Duplicate tool_use_id detected (${tool_use_id}). Session may be corrupted. Consider starting a new session." >&2
    else
        echo "${tool_use_id}" >> "${ID_TRACKER}"
        # Keep only last 500 IDs to prevent file bloat
        if [[ -f "${ID_TRACKER}" ]]; then
            line_count=$(wc -l < "${ID_TRACKER}")
            if [[ "${line_count}" -gt 500 ]]; then
                tail -250 "${ID_TRACKER}" > "${ID_TRACKER}.tmp"
                mv "${ID_TRACKER}.tmp" "${ID_TRACKER}"
            fi
        fi
    fi
fi

exit 0
