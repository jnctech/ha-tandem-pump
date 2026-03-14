#!/bin/bash
# =============================================================================
# Notification Hook - Catches API errors and logs them
# =============================================================================
# This script can be called manually or piped error output to capture
# tool_use corruption errors from Claude Code stderr.
#
# Usage: echo "API Error: 400 ..." | ./hooks-on-error.sh [session_id]
# =============================================================================

set -uo pipefail

MONITOR_DIR="${HOME}/.claude/session-monitor"
EVENT_LOG="${MONITOR_DIR}/events.jsonl"

mkdir -p "${MONITOR_DIR}"

session_id="${1:-manual}"

# Read error from stdin or first argument
if [[ -t 0 ]]; then
    error_message="${2:-no message}"
else
    error_message=$(cat)
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

# Check if this is a corruption error
corruption=false
if echo "${error_message}" | grep -q "tool_use ids must be unique"; then
    corruption=true
fi

# Extract request_id if present
request_id=$(echo "${error_message}" | grep -o '"request_id":"[^"]*"' | head -1 | cut -d'"' -f4)

# Truncate message for logging
short_message=$(echo "${error_message}" | head -c 500)

echo "{\"ts\":\"$(date -Is)\",\"event\":\"error\",\"env\":\"${env}\",\"session_id\":\"${session_id}\",\"message\":\"${short_message}\",\"request_id\":\"${request_id:-none}\",\"corruption\":${corruption}}" >> "${EVENT_LOG}"

if [[ "${corruption}" == "true" ]]; then
    echo "" >&2
    echo "=== SESSION CORRUPTION DETECTED ===" >&2
    echo "Environment: ${env}" >&2
    echo "Session: ${session_id}" >&2
    echo "Time: $(date -Is)" >&2
    echo "This session cannot recover. Start a new session." >&2
    echo "Request ID: ${request_id:-none}" >&2
    echo "===================================" >&2
fi

exit 0
