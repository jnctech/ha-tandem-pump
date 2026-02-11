#!/usr/bin/env python3
"""
Validate test_credentials.json file.
"""

import json
from pathlib import Path

creds_file = Path("test_credentials.json")

if not creds_file.exists():
    print("❌ test_credentials.json not found!")
    print("\nCreate it by copying the template:")
    print("  cp test_credentials.json.template test_credentials.json")
    exit(1)

print("Checking test_credentials.json...")
print(f"File location: {creds_file.absolute()}\n")

try:
    with open(creds_file, 'r') as f:
        content = f.read()
        print("File contents:")
        print("-" * 50)
        # Show with line numbers
        for i, line in enumerate(content.split('\n'), 1):
            print(f"{i:2}: {line}")
        print("-" * 50)

    print("\nAttempting to parse JSON...")
    with open(creds_file, 'r') as f:
        creds = json.load(f)

    print("✅ JSON is valid!\n")
    print("Found fields:")
    for key in creds.keys():
        value = creds[key]
        if key in ['tandem_password', 'ha_token']:
            # Mask sensitive values
            if value and len(value) > 10:
                display = value[:8] + "..." + value[-4:]
            else:
                display = "***" if value else "(empty)"
        else:
            display = value
        print(f"  ✓ {key}: {display}")

    # Check for required fields
    required = ['tandem_email', 'tandem_password', 'tandem_region', 'ha_token']
    missing = [field for field in required if field not in creds]

    if missing:
        print(f"\n⚠️  Missing optional fields: {', '.join(missing)}")
    else:
        print("\n✅ All required fields present!")

    # Check for common issues
    issues = []
    if creds.get('ha_token') == 'your-home-assistant-long-lived-token':
        issues.append("ha_token is still the template value")
    if creds.get('tandem_email') == 'your-tandem-email@example.com':
        issues.append("tandem_email is still the template value")

    if issues:
        print("\n⚠️  Potential issues:")
        for issue in issues:
            print(f"  - {issue}")

except json.JSONDecodeError as e:
    print(f"❌ JSON parsing error!")
    print(f"\nError details:")
    print(f"  Line {e.lineno}, Column {e.colno}")
    print(f"  {e.msg}")
    print(f"\n💡 Common JSON errors:")
    print("  - Missing comma between fields")
    print("  - Extra comma after last field")
    print("  - Unescaped quotes in values")
    print("  - Missing closing brace")
    print("\n📝 Correct format:")
    print('{')
    print('  "field1": "value1",')
    print('  "field2": "value2",')
    print('  "field3": "value3"')
    print('}')
except Exception as e:
    print(f"❌ Error: {e}")
