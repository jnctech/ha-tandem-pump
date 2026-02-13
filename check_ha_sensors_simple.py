#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Home Assistant sensor checker using only built-in libraries.
"""

import json
import urllib.request
import urllib.error
import sys
from pathlib import Path

# Force UTF-8 encoding for output
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

HA_URL = "http://192.168.88.43:8123"


def load_token():
    """Load HA token from credentials file."""
    creds_file = Path(__file__).parent / "test_credentials.json"
    if not creds_file.exists():
        print("ERROR: test_credentials.json not found!")
        print("Please create it with your ha_token")
        return None

    try:
        with open(creds_file, 'r') as f:
            creds = json.load(f)
            return creds.get("ha_token")
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def get_states(token):
    """Get all entity states from Home Assistant."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        f"{HA_URL}/api/states",
        headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            return json.loads(data)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        if e.code == 401:
            print("Authentication failed. Check your ha_token in test_credentials.json")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    print("\n" + "="*70)
    print("Home Assistant Tandem Sensor Status Check")
    print(f"Connecting to: {HA_URL}")
    print("="*70 + "\n")

    token = load_token()
    if not token:
        return

    print("Fetching sensor states...")
    states = get_states(token)
    if not states:
        print("Failed to fetch states from Home Assistant")
        return

    # Filter for carelink sensors
    carelink_sensors = [
        entity for entity in states
        if entity.get("entity_id", "").startswith("sensor.carelink_")
    ]

    if not carelink_sensors:
        print("❌ No carelink sensors found!")
        print("\nPossible reasons:")
        print("  - Integration not configured")
        print("  - Integration failed to load")
        print("  - Sensors use different entity_id pattern")

        # Show all sensor entity IDs for debugging
        all_sensors = [e for e in states if e.get("entity_id", "").startswith("sensor.")]
        print(f"\nFound {len(all_sensors)} total sensors in HA")
        print("First 10 sensor entity_ids:")
        for sensor in all_sensors[:10]:
            print(f"  - {sensor.get('entity_id')}")
        return

    print(f"Found {len(carelink_sensors)} carelink sensors\n")

    # Categorize sensors
    unknown = []
    unavailable = []
    working = []

    for sensor in carelink_sensors:
        entity_id = sensor.get("entity_id")
        state = sensor.get("state")
        name = sensor.get("attributes", {}).get("friendly_name", entity_id)

        if state == "unknown":
            unknown.append((entity_id, name))
        elif state == "unavailable":
            unavailable.append((entity_id, name))
        else:
            working.append((entity_id, name, state))

    # Print results
    if unknown:
        print(f"❌ Sensors in UNKNOWN state ({len(unknown)}):")
        for entity_id, name in unknown:
            print(f"  - {name}")
            print(f"    Entity: {entity_id}")
        print()

    if unavailable:
        print(f"⚠️  Sensors UNAVAILABLE ({len(unavailable)}):")
        for entity_id, name in unavailable:
            print(f"  - {name}")
            print(f"    Entity: {entity_id}")
        print()

    if working:
        print(f"✅ Sensors with values ({len(working)}):")
        for entity_id, name, state in working[:10]:  # Limit to first 10
            print(f"  - {name}: {state}")
        if len(working) > 10:
            print(f"  ... and {len(working) - 10} more")
        print()

    # Summary
    print("-" * 70)
    print("Summary:")
    print(f"  Total carelink sensors: {len(carelink_sensors)}")
    print(f"  Unknown: {len(unknown)}")
    print(f"  Unavailable: {len(unavailable)}")
    print(f"  Working: {len(working)}")
    print("-" * 70)

    # Show details of one unknown sensor if any
    if unknown:
        print("\n📋 Sample unknown sensor details:")
        entity_id = unknown[0][0]
        sensor = next(s for s in carelink_sensors if s["entity_id"] == entity_id)

        print(f"\nEntity ID: {sensor.get('entity_id')}")
        print(f"State: {sensor.get('state')}")
        print(f"Attributes:")
        for key, value in sensor.get('attributes', {}).items():
            if key not in ['friendly_name']:  # Skip friendly_name as we already showed it
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
