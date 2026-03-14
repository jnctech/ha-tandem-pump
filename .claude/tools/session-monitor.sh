#!/bin/bash
# =============================================================================
# Claude Code Session Monitor
# =============================================================================
# Tracks session health across environments (Linux CLI, Remote Control, Windows)
# to help identify tool_use ID corruption patterns.
#
# Usage: Run in a separate terminal to tail session events in real-time.
#   ./session-monitor.sh              # tail live events
#   ./session-monitor.sh --summary    # show session summary report
#   ./session-monitor.sh --check-corruption [session_id]  # scan for duplicate tool_use IDs
#   ./session-monitor.sh --clean      # archive logs older than 7 days
#
# Log location: ~/.claude/session-monitor/
# =============================================================================

set -euo pipefail

MONITOR_DIR="${HOME}/.claude/session-monitor"
EVENT_LOG="${MONITOR_DIR}/events.jsonl"
SUMMARY_LOG="${MONITOR_DIR}/summary.csv"
ARCHIVE_DIR="${MONITOR_DIR}/archive"
SESSION_DIR="${HOME}/.claude/projects"

mkdir -p "${MONITOR_DIR}" "${ARCHIVE_DIR}"

# Initialize summary CSV if missing
if [[ ! -f "${SUMMARY_LOG}" ]]; then
    echo "timestamp,session_id,environment,duration_sec,tool_calls,errors,corrupted,crash_reason" > "${SUMMARY_LOG}"
fi

detect_environment() {
    if [[ -n "${CLAUDE_REMOTE_CONTROL:-}" ]] || [[ -n "${CLAUDE_REMOTE:-}" ]]; then
        echo "remote-control"
    elif [[ "$(uname -s)" == "MINGW"* ]] || [[ "$(uname -s)" == "MSYS"* ]] || [[ -n "${WSLENV:-}" ]]; then
        echo "windows"
    elif [[ "$(uname -s)" == "Linux" ]]; then
        echo "linux-cli"
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        echo "macos-cli"
    else
        echo "unknown"
    fi
}

# =============================================================================
# Command: --summary
# =============================================================================
show_summary() {
    echo "============================================="
    echo "  Claude Code Session Monitor - Summary"
    echo "============================================="
    echo ""

    if [[ ! -f "${EVENT_LOG}" ]]; then
        echo "No events recorded yet."
        exit 0
    fi

    total_sessions=$(grep -c '"event":"session_start"' "${EVENT_LOG}" 2>/dev/null || echo 0)
    total_errors=$(grep -c '"event":"error"' "${EVENT_LOG}" 2>/dev/null || echo 0)
    total_corruption=$(grep -c '"corruption":true' "${EVENT_LOG}" 2>/dev/null || echo 0)
    total_tool_calls=$(grep -c '"event":"tool_use"' "${EVENT_LOG}" 2>/dev/null || echo 0)

    echo "Total sessions:       ${total_sessions}"
    echo "Total tool calls:     ${total_tool_calls}"
    echo "Total errors:         ${total_errors}"
    echo "Corruption events:    ${total_corruption}"
    echo ""

    echo "--- By Environment ---"
    for env in linux-cli remote-control windows; do
        local env_lines
        env_lines=$(grep "\"env\":\"${env}\"" "${EVENT_LOG}" 2>/dev/null || true)
        if [[ -z "${env_lines}" ]]; then
            printf "  %-20s sessions=%-5s errors=%-5s corrupted=%-5s\n" "${env}" "0" "0" "0"
            continue
        fi
        env_sessions=$(echo "${env_lines}" | grep -c '"event":"session_start"' || true)
        env_errors=$(echo "${env_lines}" | grep -c '"event":"error"' || true)
        env_corruption=$(echo "${env_lines}" | grep -c '"corruption":true' || true)
        printf "  %-20s sessions=%-5s errors=%-5s corrupted=%-5s\n" "${env}" "${env_sessions}" "${env_errors}" "${env_corruption}"
    done

    echo ""
    echo "--- Recent Errors (last 10) ---"
    grep '"event":"error"' "${EVENT_LOG}" 2>/dev/null | tail -10 | while IFS= read -r line; do
        ts=$(echo "${line}" | jq -r '.ts // "?"')
        env=$(echo "${line}" | jq -r '.env // "?"')
        msg=$(echo "${line}" | jq -r '.message // "?"' | head -c 100)
        printf "  [%s] %-16s %s\n" "${ts}" "${env}" "${msg}"
    done

    echo ""
    echo "--- Corruption Events ---"
    grep '"corruption":true' "${EVENT_LOG}" 2>/dev/null | while IFS= read -r line; do
        ts=$(echo "${line}" | jq -r '.ts // "?"')
        env=$(echo "${line}" | jq -r '.env // "?"')
        sid=$(echo "${line}" | jq -r '.session_id // "?"' | head -c 12)
        printf "  [%s] %-16s session=%s\n" "${ts}" "${env}" "${sid}"
    done

    if [[ -f "${SUMMARY_LOG}" ]]; then
        echo ""
        echo "--- Session History (last 10) ---"
        tail -10 "${SUMMARY_LOG}"
    fi
}

# =============================================================================
# Command: --check-corruption [session_id]
# =============================================================================
check_corruption() {
    local target_session="${1:-}"

    echo "Scanning for duplicate tool_use IDs..."
    echo ""

    local found_corruption=false

    if [[ -n "${target_session}" ]]; then
        # Scan specific session
        local session_files
        session_files=$(find "${SESSION_DIR}" -name "${target_session}*" -name "*.jsonl" 2>/dev/null)
        if [[ -z "${session_files}" ]]; then
            echo "Session not found: ${target_session}"
            echo "Available sessions:"
            find "${SESSION_DIR}" -name "*.jsonl" -printf "  %f\n" 2>/dev/null | sort -r | head -10
            exit 1
        fi
        for f in ${session_files}; do
            scan_file_for_corruption "${f}"
        done
    else
        # Scan all recent sessions
        find "${SESSION_DIR}" -name "*.jsonl" -mtime -7 2>/dev/null | while IFS= read -r f; do
            scan_file_for_corruption "${f}"
        done
    fi

    if [[ "${found_corruption}" == "false" ]]; then
        echo "No duplicate tool_use IDs found."
    fi
}

scan_file_for_corruption() {
    local file="$1"
    local filename
    filename=$(basename "${file}" .jsonl)

    # Extract tool_use IDs and find duplicates
    local dupes
    dupes=$(grep -o '"id":"toolu_[^"]*"' "${file}" 2>/dev/null | sort | uniq -d)

    if [[ -n "${dupes}" ]]; then
        found_corruption=true
        echo "CORRUPTION DETECTED in session: ${filename}"
        echo "  File: ${file}"
        echo "  Duplicate IDs:"
        echo "${dupes}" | while IFS= read -r dup; do
            count=$(grep -c "${dup}" "${file}")
            echo "    ${dup} (appears ${count} times)"
        done
        echo ""

        # Log the corruption event
        local env
        env=$(detect_environment)
        echo "{\"ts\":\"$(date -Is)\",\"event\":\"corruption_scan\",\"env\":\"${env}\",\"session_id\":\"${filename}\",\"corruption\":true,\"file\":\"${file}\"}" >> "${EVENT_LOG}"
    fi
}

# =============================================================================
# Command: --clean
# =============================================================================
clean_logs() {
    echo "Archiving logs older than 7 days..."
    local archive_name="events-$(date +%Y%m%d).jsonl"

    if [[ -f "${EVENT_LOG}" ]]; then
        local line_count
        line_count=$(wc -l < "${EVENT_LOG}")
        if [[ "${line_count}" -gt 1000 ]]; then
            head -n -500 "${EVENT_LOG}" >> "${ARCHIVE_DIR}/${archive_name}"
            tail -500 "${EVENT_LOG}" > "${EVENT_LOG}.tmp"
            mv "${EVENT_LOG}.tmp" "${EVENT_LOG}"
            echo "Archived $(( line_count - 500 )) lines to ${ARCHIVE_DIR}/${archive_name}"
        else
            echo "Log has only ${line_count} lines, no archiving needed."
        fi
    fi
}

# =============================================================================
# Command: (default) -- tail live events
# =============================================================================
tail_events() {
    echo "============================================="
    echo "  Claude Code Session Monitor - Live"
    echo "============================================="
    echo "  Log: ${EVENT_LOG}"
    echo "  Ctrl+C to stop"
    echo "============================================="
    echo ""

    if [[ ! -f "${EVENT_LOG}" ]]; then
        echo "Waiting for first event..."
        touch "${EVENT_LOG}"
    fi

    tail -f "${EVENT_LOG}" | while IFS= read -r line; do
        event=$(echo "${line}" | jq -r '.event // "?"' 2>/dev/null)
        ts=$(echo "${line}" | jq -r '.ts // "?"' 2>/dev/null)
        env=$(echo "${line}" | jq -r '.env // "?"' 2>/dev/null)
        tool=$(echo "${line}" | jq -r '.tool // ""' 2>/dev/null)
        corruption=$(echo "${line}" | jq -r '.corruption // false' 2>/dev/null)

        # Color coding
        local color="\033[0m"
        case "${event}" in
            session_start) color="\033[1;32m" ;;  # green
            session_end)   color="\033[1;34m" ;;  # blue
            tool_use)      color="\033[0;37m" ;;  # gray
            error)         color="\033[1;31m" ;;  # red
            compact)       color="\033[1;33m" ;;  # yellow
        esac

        if [[ "${corruption}" == "true" ]]; then
            color="\033[1;31m"  # red for corruption
            printf "${color}[%s] %-16s %-15s *** CORRUPTION DETECTED ***\033[0m\n" "${ts}" "${env}" "${event}"
        elif [[ -n "${tool}" ]]; then
            printf "${color}[%s] %-16s %-15s tool=%s\033[0m\n" "${ts}" "${env}" "${event}" "${tool}"
        else
            printf "${color}[%s] %-16s %s\033[0m\n" "${ts}" "${env}" "${event}"
        fi
    done
}

# =============================================================================
# Main
# =============================================================================
case "${1:-}" in
    --summary)
        show_summary
        ;;
    --check-corruption)
        check_corruption "${2:-}"
        ;;
    --clean)
        clean_logs
        ;;
    --help|-h)
        head -14 "$0" | tail -10
        ;;
    *)
        tail_events
        ;;
esac
