#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find any tandem/carelink related sensors."""

import json
import urllib.request
from pathlib import Path

HA_URL = "http://192.168.88.43:8123"

def load_token():
    creds_file = Path(__file__).parent / "test_credentials.json"
    with open(creds_file, 'r') as f:
        return json.load(f).get("ha_token")

def get_states(token):
    req = urllib.request.Request(
        f"{HA_URL}/api/states",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())

token = load_token()
states = get_states(token)

print("Searching for tandem/carelink related entities...\n")

# Search for any entity containing tandem, carelink, glucose, insulin, etc.
keywords = ['tandem', 'carelink', 'glucose', 'insulin', 'pump', 'cgm', 'blood', 'sugar']

found = []
for entity in states:
    entity_id = entity.get("entity_id", "").lower()
    name = entity.get("attributes", {}).get("friendly_name", "").lower()

    for keyword in keywords:
        if keyword in entity_id or keyword in name:
            found.append({
                'entity_id': entity.get("entity_id"),
                'name': entity.get("attributes", {}).get("friendly_name"),
                'state': entity.get("state"),
                'domain': entity.get("entity_id").split('.')[0]
            })
            break

if found:
    print(f"Found {len(found)} potentially related entities:\n")
    for item in found[:20]:  # Show first 20
        print(f"  {item['entity_id']}")
        print(f"    Name: {item['name']}")
        print(f"    State: {item['state']}")
        print()
else:
    print("No tandem/carelink related entities found!")
    print("\nThis suggests:")
    print("  - The integration is not loaded")
    print("  - The integration failed during setup")
    print("  - The integration is configured but sensors weren't created")
    print("\nNext steps:")
    print("  1. Check Home Assistant logs for errors")
    print("  2. Check if integration appears in Settings > Devices & Services")
    print("  3. Verify the integration is installed in custom_components/carelink/")
