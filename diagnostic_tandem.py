#!/usr/bin/env python3
"""
Diagnostic script for Tandem Source API integration.

This script tests the Tandem API connection independently from Home Assistant
to help identify where the sensor population issue occurs.

Usage:
    python diagnostic_tandem.py

You will be prompted for your Tandem credentials.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the custom_components directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from custom_components.carelink.tandem_api import TandemSourceClient, parse_dotnet_date

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

_LOGGER = logging.getLogger(__name__)


async def test_tandem_api():
    """Test Tandem API connection and data retrieval."""

    print("\n" + "="*70)
    print("Tandem Source API Diagnostic Tool")
    print("="*70 + "\n")

    # Get credentials from user
    email = input("Enter Tandem email: ").strip()
    password = input("Enter Tandem password: ").strip()
    region = input("Enter region (US/EU) [default: EU]: ").strip() or "EU"

    print("\n" + "-"*70)
    print("Step 1: Creating Tandem client")
    print("-"*70)

    try:
        client = TandemSourceClient(
            email=email,
            password=password,
            region=region
        )
        print(f"✓ Tandem client created successfully (Region: {region})")
    except Exception as e:
        print(f"✗ FAILED to create Tandem client: {e}")
        return

    print("\n" + "-"*70)
    print("Step 2: Testing API login")
    print("-"*70)

    try:
        await client.login()
        print("✓ Login successful!")
    except Exception as e:
        print(f"✗ Login FAILED: {e}")
        _LOGGER.error("Login failed", exc_info=True)
        await client.close()
        return

    print("\n" + "-"*70)
    print("Step 3: Fetching recent data")
    print("-"*70)

    try:
        recent_data = await client.get_recent_data()

        if recent_data is None:
            print("✗ CRITICAL: get_recent_data() returned None!")
            await client.close()
            return

        if not isinstance(recent_data, dict):
            print(f"✗ CRITICAL: get_recent_data() returned {type(recent_data)} instead of dict!")
            await client.close()
            return

        print(f"✓ Data fetched successfully (type: {type(recent_data)})")

    except Exception as e:
        print(f"✗ Data fetch FAILED: {e}")
        _LOGGER.error("Data fetch failed", exc_info=True)
        await client.close()
        return

    print("\n" + "-"*70)
    print("Step 4: Analyzing data structure")
    print("-"*70)

    # Check for expected data sources
    data_sources = {
        "pump_metadata": recent_data.get("pump_metadata"),
        "pumper_info": recent_data.get("pumper_info"),
        "therapy_timeline": recent_data.get("therapy_timeline"),
        "dashboard_summary": recent_data.get("dashboard_summary"),
    }

    print("\nData sources present:")
    for source_name, source_data in data_sources.items():
        status = "✓ PRESENT" if source_data else "✗ MISSING"
        print(f"  {source_name}: {status}")
        if source_data and isinstance(source_data, dict):
            print(f"    Keys: {list(source_data.keys())[:10]}")  # Show first 10 keys

    print("\n" + "-"*70)
    print("Step 5: Testing sensor data extraction")
    print("-"*70)

    sensors_data = {}

    # Test metadata extraction
    metadata = recent_data.get("pump_metadata")
    if metadata:
        print("\n✓ Pump metadata found:")
        print(f"  Serial: {metadata.get('serialNumber', 'N/A')}")
        print(f"  Model: {metadata.get('modelNumber', 'N/A')}")
        print(f"  Software: {metadata.get('softwareVersion', 'N/A')}")
        print(f"  Last upload: {metadata.get('lastUpload', 'N/A')}")

        sensors_data["pump_serial"] = metadata.get("serialNumber")
        sensors_data["pump_model"] = metadata.get("modelNumber")
        sensors_data["software_version"] = metadata.get("softwareVersion")
    else:
        print("\n✗ No pump metadata found")

    # Test therapy timeline extraction
    timeline = recent_data.get("therapy_timeline")
    if timeline:
        print("\n✓ Therapy timeline found:")

        # CGM data
        cgm_entries = timeline.get("cgm", [])
        print(f"  CGM entries: {len(cgm_entries)}")
        if cgm_entries:
            latest_cgm = cgm_entries[0]
            readings = latest_cgm.get("Readings", [])
            print(f"    Readings in latest entry: {len(readings)}")
            if readings:
                for reading in readings[:3]:  # Show first 3
                    print(f"      Value: {reading.get('Value')}, Type: {reading.get('Type')}")

        # Bolus data
        bolus_entries = timeline.get("bolus", [])
        print(f"  Bolus entries: {len(bolus_entries)}")
        if bolus_entries:
            latest_bolus = bolus_entries[0]
            print(f"    Latest insulin: {latest_bolus.get('InsulinDelivered', 'N/A')} units")
            print(f"    IOB: {latest_bolus.get('IOB', 'N/A')}")

        # Basal data
        basal_entries = timeline.get("basal", [])
        print(f"  Basal entries: {len(basal_entries)}")
        if basal_entries:
            latest_basal = basal_entries[0]
            print(f"    Latest rate: {latest_basal.get('BasalRate', 'N/A')} U/hr")
            print(f"    Type: {latest_basal.get('Type', 'N/A')}")
    else:
        print("\n✗ No therapy timeline found")

    # Test dashboard summary extraction
    summary = recent_data.get("dashboard_summary")
    if summary:
        print("\n✓ Dashboard summary found:")
        print(f"  Average reading: {summary.get('averageReading', 'N/A')} mg/dL")
        print(f"  Time in range: {summary.get('timeInRangePercent', 'N/A')}%")
        print(f"  CGM inactive: {summary.get('cgmInactivePercent', 'N/A')}%")

        sensors_data["avg_glucose"] = summary.get("averageReading")
        sensors_data["time_in_range"] = summary.get("timeInRangePercent")
    else:
        print("\n✗ No dashboard summary found")

    print("\n" + "-"*70)
    print("Step 6: Summary")
    print("-"*70)

    print(f"\nTotal top-level keys in API response: {len(recent_data.keys())}")
    print(f"All keys: {list(recent_data.keys())}")

    print(f"\nExtractable sensor values found: {len(sensors_data)}")
    for key, value in sensors_data.items():
        print(f"  {key}: {value}")

    # Save full response to file for analysis
    output_file = Path(__file__).parent / "tandem_api_response.json"
    try:
        # Sanitize data before saving (remove sensitive info)
        sanitized_data = sanitize_data(recent_data)
        with open(output_file, 'w') as f:
            json.dump(sanitized_data, f, indent=2, default=str)
        print(f"\n✓ Full API response saved to: {output_file}")
        print("  (Sensitive data has been redacted)")
    except Exception as e:
        print(f"\n✗ Failed to save response: {e}")

    print("\n" + "="*70)
    print("Diagnostic complete!")
    print("="*70 + "\n")

    # Close the client
    await client.close()


def sanitize_data(data, depth=0):
    """Remove sensitive information from data for safe logging."""
    if depth > 10:  # Prevent infinite recursion
        return "[MAX_DEPTH]"

    pii_fields = {
        "firstName", "lastName", "username", "email", "password",
        "serialNumber", "patientId", "patientName", "phone", "address"
    }

    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k in pii_fields else sanitize_data(v, depth + 1)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [sanitize_data(item, depth + 1) for item in data]
    return data


if __name__ == "__main__":
    try:
        asyncio.run(test_tandem_api())
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        _LOGGER.error("Unexpected error", exc_info=True)
