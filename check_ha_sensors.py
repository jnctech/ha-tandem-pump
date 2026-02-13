#!/usr/bin/env python3
"""
Check Home Assistant Tandem sensor states.

Usage:
    python check_ha_sensors.py [--token YOUR_TOKEN]
"""

import argparse
import json
import requests
from pathlib import Path

HA_URL = "http://192.168.88.43:8123"


def load_token_from_file():
    """Try to load HA token from credentials file."""
    creds_file = Path(__file__).parent / "test_credentials.json"
    if creds_file.exists():
        try:
            with open(creds_file, 'r') as f:
                creds = json.load(f)
                return creds.get("ha_token")
        except Exception as e:
            print(f"Warning: Could not load token from file: {e}")
    return None


def get_states(token):
    """Get all entity states from Home Assistant."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(f"{HA_URL}/api/states", headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching states: {e}")
        return None


def check_tandem_sensors(token):
    """Check status of all Tandem sensors."""
    print("\n" + "="*70)
    print("Home Assistant Tandem Sensor Status Check")
    print(f"Connecting to: {HA_URL}")
    print("="*70 + "\n")

    states = get_states(token)
    if not states:
        print("Failed to fetch states from Home Assistant")
        return

    # Filter for carelink/tandem sensors
    tandem_sensors = [
        entity for entity in states
        if entity.get("entity_id", "").startswith("sensor.carelink_")
    ]

    if not tandem_sensors:
        print("❌ No carelink sensors found!")
        print("\nPossible reasons:")
        print("  - Integration not configured")
        print("  - Integration failed to load")
        print("  - Sensors use different entity_id pattern")
        return

    print(f"Found {len(tandem_sensors)} carelink sensors\n")

    # Categorize sensors by state
    unknown_sensors = []
    unavailable_sensors = []
    ok_sensors = []

    for sensor in tandem_sensors:
        entity_id = sensor.get("entity_id")
        state = sensor.get("state")
        friendly_name = sensor.get("attributes", {}).get("friendly_name", entity_id)

        if state == "unknown":
            unknown_sensors.append((entity_id, friendly_name))
        elif state == "unavailable":
            unavailable_sensors.append((entity_id, friendly_name))
        else:
            ok_sensors.append((entity_id, friendly_name, state))

    # Print results
    if unknown_sensors:
        print(f"❌ Sensors in UNKNOWN state ({len(unknown_sensors)}):")
        for entity_id, name in unknown_sensors:
            print(f"  - {name}")
            print(f"    Entity: {entity_id}")
        print()

    if unavailable_sensors:
        print(f"⚠️  Sensors UNAVAILABLE ({len(unavailable_sensors)}):")
        for entity_id, name in unavailable_sensors:
            print(f"  - {name}")
            print(f"    Entity: {entity_id}")
        print()

    if ok_sensors:
        print(f"✅ Sensors with values ({len(ok_sensors)}):")
        for entity_id, name, state in ok_sensors:
            print(f"  - {name}: {state}")
            print(f"    Entity: {entity_id}")
        print()

    # Summary
    print("-" * 70)
    print("Summary:")
    print(f"  Total sensors: {len(tandem_sensors)}")
    print(f"  Unknown: {len(unknown_sensors)}")
    print(f"  Unavailable: {len(unavailable_sensors)}")
    print(f"  Working: {len(ok_sensors)}")
    print("-" * 70)

    # Detailed view of one unknown sensor
    if unknown_sensors:
        print("\nDetailed view of first unknown sensor:")
        entity_id = unknown_sensors[0][0]
        sensor = next(s for s in tandem_sensors if s["entity_id"] == entity_id)
        print(json.dumps(sensor, indent=2))


def check_system_log(token):
    """Try to fetch recent errors from system log."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print("\n" + "="*70)
    print("Checking System Log for Carelink Errors")
    print("="*70 + "\n")

    try:
        response = requests.get(
            f"{HA_URL}/api/error_log",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            log_content = response.text
            # Look for carelink-related errors
            carelink_lines = [
                line for line in log_content.split('\n')
                if 'carelink' in line.lower() or 'tandem' in line.lower()
            ]

            if carelink_lines:
                print(f"Found {len(carelink_lines)} carelink-related log entries (last 50):")
                for line in carelink_lines[-50:]:
                    print(line)
            else:
                print("No carelink-related errors in recent logs")
        else:
            print(f"Could not fetch error log (status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching log: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Home Assistant Tandem sensors")
    parser.add_argument("--token", help="Home Assistant long-lived access token")
    args = parser.parse_args()

    # Get token from args or file
    token = args.token or load_token_from_file()

    if not token:
        print("ERROR: No Home Assistant token provided!")
        print("\nOptions:")
        print("  1. Pass via command line: --token YOUR_TOKEN")
        print("  2. Add to test_credentials.json:")
        print('     {"ha_token": "YOUR_TOKEN", ...}')
        print("\nTo create a long-lived token:")
        print(f"  1. Go to {HA_URL}/profile")
        print("  2. Scroll to 'Long-Lived Access Tokens'")
        print("  3. Click 'Create Token'")
        exit(1)

    check_tandem_sensors(token)
    check_system_log(token)
