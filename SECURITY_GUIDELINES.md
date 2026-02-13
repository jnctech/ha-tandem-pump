# Security Guidelines - Handling Credentials

This document outlines best practices for handling credentials during development and testing.

## ⚠️ CRITICAL: Never Commit Secrets

**Files that should NEVER be committed:**
- `test_credentials.json` - Contains your actual credentials
- `secrets.json`, `credentials.json` - Any file with actual secrets
- `tandem_api_response.json` - May contain personal health data
- Any file with API tokens, passwords, or personal information

## ✅ Safe Practices

### 1. Use the Template File

**Template File** (Safe to commit):
- `test_credentials.json.template` - Example format, no real credentials

**Your Credentials File** (NEVER commit):
- `test_credentials.json` - Your actual credentials (gitignored)

### 2. Creating Your Credentials File

```bash
# Copy the template
cp test_credentials.json.template test_credentials.json

# Edit with your credentials
nano test_credentials.json  # or use your preferred editor
```

**Format**:
```json
{
  "tandem_email": "your-actual-email@example.com",
  "tandem_password": "your-actual-password",
  "tandem_region": "EU"
}
```

### 3. Verify Files Are Ignored

Before committing, always check:

```bash
# Check git status
git status

# Verify your credentials file is NOT listed
# If it appears, DO NOT COMMIT!

# Check what would be committed
git diff --staged
```

**✅ Safe to see in `git status`**:
- `test_credentials.json.template`
- `SECURITY_GUIDELINES.md`
- `diagnostic_tandem.py`

**❌ NEVER should appear in `git status`**:
- `test_credentials.json`
- `secrets.json`
- `tandem_api_response.json`

## Protected by .gitignore

The following patterns are automatically ignored:

```gitignore
# Credentials files
secrets.json
credentials.json
test_credentials.json
tandem_credentials.json
*_credentials.json
*_secrets.json

# API responses (may contain PHI)
tandem_api_response.json
*_api_response.json

# Local testing
local_test_*.py
```

## Using the Diagnostic Script

### Option 1: With Credentials File (Recommended)

```bash
# 1. Create credentials file from template
cp test_credentials.json.template test_credentials.json

# 2. Edit with your credentials
nano test_credentials.json

# 3. Run diagnostic (will auto-load credentials)
python diagnostic_tandem.py
```

### Option 2: Interactive Input

```bash
# Run without credentials file
# Script will prompt for credentials
python diagnostic_tandem.py
```

**Note**: Credentials entered interactively are not saved to disk.

## Data Sanitization

The diagnostic script automatically sanitizes sensitive data before saving:

**Redacted Fields**:
- `firstName`, `lastName`
- `email`, `username`
- `serialNumber`, `patientId`
- `phone`, `address`
- `password`

**Output File**: `tandem_api_response.json`
- Contains API structure with PII redacted
- Still gitignored as a safety measure
- Safe to share for debugging (verify before sharing)

## Best Practices Checklist

Before committing ANY changes:

- [ ] Run `git status` and verify no credential files are staged
- [ ] Run `git diff --staged` and scan for any hardcoded credentials
- [ ] Check that only template files (`.template`) are being committed
- [ ] Verify `.gitignore` is working: `git check-ignore test_credentials.json` should output the filename
- [ ] If in doubt, DON'T commit - ask for review first

## What to Do If You Accidentally Commit Secrets

**STOP IMMEDIATELY!**

1. **Do NOT push to GitHub**
2. Undo the commit:
   ```bash
   git reset --soft HEAD~1
   ```
3. Remove the file from staging:
   ```bash
   git restore --staged test_credentials.json
   ```
4. Verify the file is gitignored:
   ```bash
   git check-ignore test_credentials.json
   ```

**If already pushed to GitHub:**
1. Immediately change your passwords
2. Revoke any API tokens
3. Contact repository maintainer
4. Consider the repository compromised

## Sharing Credentials Securely

**For local development:**
- Use `test_credentials.json` (gitignored)
- Never share via git/email
- Use encrypted channels if needed

**For CI/CD:**
- Use GitHub Secrets
- Use environment variables
- Never hardcode in workflows

## Questions?

If you're unsure whether a file is safe to commit:
1. Check if it's in `.gitignore`
2. Run `git check-ignore <filename>`
3. Ask in the issue or PR before committing

---

**Remember**: It's better to be overly cautious than to leak credentials!
