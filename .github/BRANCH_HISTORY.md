# Branch History and Context

This document preserves the context of deprecated branches for future reference.

## v0.1.0.beta - DEPRECATED (Do Not Use)

**Status**: Failed attempts - superseded by v0.1.3-beta
**Created**: 2026-02-XX
**Deprecated**: 2026-02-11
**Contains**: 2 failed SSL fix attempts
**Root Issue**: Blocking SSL call in TandemSourceClient

### Problem Statement

The Tandem integration failed to load with error:
```
Detected blocking call to load_verify_locations with args (<ssl.SSLContext object>,
'/usr/local/lib/python3.13/site-packages/certifi/cacert.pem', None, None)
inside the event loop by custom integration 'carelink'
```

### Failed Attempt #1 (Commit 56ef0ce)

**Approach**: Use Home Assistant's `create_async_httpx_client` helper

**Changes**:
- Modified `tandem_api.py` to accept `hass` parameter in `__init__`
- Changed `_get_client()` to use `create_async_httpx_client(self.hass, timeout=30)`

**Result**: FAILED
- Caused "Invalid handler specified" error
- Integration completely broken
- Config flow would not load

**Why It Failed**:
Home Assistant's `create_async_httpx_client` creates a client with pre-configured settings that conflicted with the custom headers and follow_redirects needed for Tandem's OIDC flow.

### Failed Attempt #2 (Commits 6756f33, c4139aa)

**Approach**: Refactor client initialization with data dictionary

**Changes**:
- Attempted to restructure how client was initialized
- Added data dictionary pattern

**Result**: FAILED
- Still encountered the same SSL blocking issue
- Did not address root cause

**Why It Failed**:
Did not actually move SSL context creation out of the event loop. The blocking call to `load_verify_locations` still occurred synchronously.

### Successful Fix (v0.1.3-beta, Commit d028aab)

**Approach**: Use executor to offload SSL context creation

**Changes**:
```python
async def _get_client(self) -> httpx.AsyncClient:
    """Get or create the async HTTP client."""
    if self._client is None or self._client.is_closed:
        loop = asyncio.get_running_loop()
        ssl_ctx = await loop.run_in_executor(
            None,
            lambda: ssl.create_default_context(cafile=certifi.where()),
        )
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
            verify=ssl_ctx,
        )
    return self._client
```

**Result**: SUCCESS
- SSL context creation offloaded to thread pool executor
- No blocking in event loop
- Maintains full control over httpx.AsyncClient configuration
- OIDC flow works correctly

### Lessons Learned

1. **Don't use Home Assistant helpers blindly**
   - `create_async_httpx_client` is useful for simple cases
   - Custom OAuth flows need manual client configuration

2. **Executor pattern for blocking I/O**
   - `asyncio.run_in_executor()` is the correct solution for unavoidable blocking calls
   - SSL context creation from disk is inherently blocking

3. **Test thoroughly before tagging**
   - v0.1.0.beta was tagged without full integration testing
   - v0.1.2.beta tag was on the broken branch

4. **Keep detailed logs**
   - ISSUES.MD in v0.1.0.beta branch documents the problem clearly
   - Helps future developers understand what went wrong

### Branch Commits (for reference)

```
v0.1.0.beta branch:
1d1aacb - Update ISSUES.MD (documents the problem)
c4139aa - Revise testing summary and analyze SSL error (tag: v0.1.2.beta)
6756f33 - Refactor client initialization with data dictionary (failed attempt #2)
56ef0ce - bug fix attempt #1 tandem_api to use Home Assistant's HTTP client (failed attempt #1)
1c3b584 - Results of initial testing (discovered the issue)
```

### Preservation

This branch is preserved in the repository for historical reference but should never be merged. The ISSUES.MD file in this branch contains valuable troubleshooting information.

**To view**:
```bash
git checkout v0.1.0.beta
cat ISSUES.MD
git checkout develop
```

## bugfix/sensor-population-unknown-state - ACTIVE

**Status**: Fix verified, PR #4 open against develop
**Created**: 2026-02-11
**Issue**: #3 - Tandem sensors stuck in Unknown state
**PR**: #4

### Problem Statement

After the SSL fix (v0.1.3-beta), the integration loaded successfully but all Tandem sensors remained in "Unknown" state. No visible errors in logs - the integration appeared to be working but wasn't populating data.

### Investigation Path

1. **Added debug logging** (commit f9e44ce) - Confirmed API auth works, pump_metadata and pumper_info fetch correctly
2. **Discovered ControlIQ 404s** - therapy_timeline, therapy_events, and dashboard_summary all returned HTTP 404 from `tdcservices.eu.tandemdiabetes.com`
3. **Added therapy_events fallback** (commit e1f6e12) - therapy_events endpoint also returned 404
4. **Inspected web UI network traffic** - Discovered the Tandem Source web UI uses a completely different endpoint: `/api/reports/reportsfacade/pumpevents/{userId}/{deviceId}`
5. **Discovered binary format** - The pumpevents API returns base64-encoded binary data, NOT JSON
6. **Researched tconnectsync** - Found binary format documentation in [tconnectsync](https://github.com/jwoglom/tconnectsync) project
7. **Implemented binary decoder** (commit d7ea0da) - Decodes 26-byte records with event-specific payloads
8. **Verified on production** - 3376 events decoded, sensors populating with real data

### Key Technical Discovery: Tandem Binary Event Format

The pumpevents API returns base64-encoded binary data. Each record is exactly 26 bytes:

```
Bytes 0-1:   Source (4 bits) + Event ID (12 bits) [big-endian uint16]
Bytes 2-5:   Timestamp [big-endian uint32, seconds since 2008-01-01 00:00:00 UTC]
Bytes 6-9:   Sequence number [big-endian uint32]
Bytes 10-25: Payload [16 bytes, event-specific format]
```

**Tandem Epoch**: January 1, 2008 (Unix timestamp 1199145600)

**Event payloads decoded**:
- **CGM (256)**: uint16 glucose at offset +4, int8 rate_of_change at +0, uint16 status at +2
- **BolusCompleted (20)**: uint16 bolus_id at +0, uint16 completion at +2, float32 iob at +4, float32 delivered at +8, float32 requested at +12
- **BolusDelivery (280)**: uint8 bolus_type at +0, uint8 status at +1, uint16 bolus_id at +2, uint16 requested_mu at +4, uint16 correction_mu at +8, uint16 delivered_mu at +12
- **BasalRateChange (3)**: float32 commanded at +0, float32 base_rate at +4, float32 max_rate at +8, uint8 change_type at +13
- **BasalDelivery (279)**: uint16 commanded_source at +2, uint16 profile_rate_mu at +4, uint16 commanded_rate_mu at +6

### API Endpoints Map

| Endpoint | Base URL | Status | Used For |
|----------|----------|--------|----------|
| `/api/reports/reportsfacade/pumpevents/{userId}/{deviceId}` | source.eu.tandemdiabetes.com | **WORKS** | CGM, bolus, basal events (binary) |
| `/api/source/pumps/metadata` | source.eu.tandemdiabetes.com | **WORKS** | Device info, settings, upload timestamps |
| `/api/source/pumpers/{pumperId}` | source.eu.tandemdiabetes.com | **WORKS** | User/patient info |
| `/tconnect/controliq/api/TherapyTimeline/...` | tdcservices.eu.tandemdiabetes.com | **404** | Therapy timeline (ControlIQ) |
| `/tconnect/controliq/api/DashboardSummary/...` | tdcservices.eu.tandemdiabetes.com | **404** | Dashboard stats |
| `/tconnect/therapyevents/api/TherapyEvents/...` | tdcservices.eu.tandemdiabetes.com | **404** | Therapy events |

### Lessons Learned

1. **Inspect the web UI first** - The browser's Network tab shows exactly which endpoints the official UI uses. Don't assume the API structure based on code or documentation alone.

2. **Binary formats exist in modern APIs** - Not everything is JSON. The Tandem pumpevents API returns base64-encoded binary, which is efficient for large event datasets (87KB for 3376 events vs potentially 500KB+ in JSON).

3. **tconnect vs Tandem Source** - The tconnect service was retired and replaced by Tandem Source, but the underlying binary event format remains the same. The tconnectsync project's event parser was invaluable for understanding the binary layout.

4. **ControlIQ API may require separate authentication** - The ControlIQ API at `tdcservices.eu.tandemdiabetes.com` appears to require different credentials than the Source OIDC tokens. This may be a separate API with its own auth flow, or it may have been decommissioned.

5. **Deploy and test incrementally** - First deployment revealed the response was a base64 string (not JSON objects), which redirected the investigation toward binary decoding.

6. **Pump metadata contains rich settings data** - The `lastUpload.settings` object contains pump profiles, CGM alert thresholds, Control-IQ settings, and more. These can be used to compute derived sensors locally.

### Branch Commits

```
bugfix/sensor-population-unknown-state:
ead41e9 - docs: Update CHANGELOG with binary pump events decoder fix
d7ea0da - fix(tandem): Decode binary pump events from Source Reports API (THE FIX)
e1f6e12 - fix(tandem): Add fallback to therapy_events API when ControlIQ fails
12ef1ce - docs: Add diagnostic findings and additional helper scripts
2709da7 - feat: Add Home Assistant sensor diagnostic script
59b3b9a - chore: Add security guidelines and credential handling for testing
f9e44ce - fix(tandem): Add comprehensive debug logging for sensor population issue
```

---

## Future Branch Management

When a feature branch fails:
1. Document the failure in this file
2. Keep the branch in the repository (do not delete)
3. Mark as deprecated in branch description
4. Create new feature branch with lessons learned
5. Reference failed attempts in successful PR
