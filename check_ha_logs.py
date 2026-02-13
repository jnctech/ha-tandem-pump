#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check Home Assistant logs for carelink/tandem errors."""

import json
import urllib.request
from pathlib import Path

HA_URL = "http://192.168.88.43:8123"

def load_token():
    creds_file = Path(__file__).parent / "test_credentials.json"
    with open(creds_file, 'r') as f:
        return json.load(f).get("ha_token")

def get_error_log(token):
    req = urllib.request.Request(
        f"{HA_URL}/api/error_log",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode('utf-8')

token = load_token()
print("Fetching Home Assistant error log...\n")
log = get_error_log(token)

# Filter for carelink/tandem related entries
relevant_lines = []
for line in log.split('\n'):
    lower_line = line.lower()
    if any(keyword in lower_line for keyword in ['carelink', 'tandem', 'coordinator']):
        relevant_lines.append(line)

if relevant_lines:
    print(f"Found {len(relevant_lines)} carelink/tandem related log entries:\n")
    print("="*70)
    for line in relevant_lines[-50:]:  # Last 50 entries
        print(line)
    print("="*70)
else:
    print("No carelink/tandem related errors in logs")
    print("\nThis could mean:")
    print("  - Integration is running but silently failing")
    print("  - Debug logging is not enabled")
    print("  - Errors are being suppressed")
    print("\nNext step: Enable debug logging in Home Assistant")
