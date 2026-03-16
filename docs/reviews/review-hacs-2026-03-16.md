# HACS Review: Baseline — 2026-03-16

**Reviewer:** Claude Opus 4.6
**Mode:** Baseline
**Scope:** All source files under `custom_components/carelink/`
**Integration:** carelink

## Summary

| Category | Critical | High | Medium | Low | OK |
|----------|----------|------|--------|-----|----|
| HACS Structure | 0 | 1 | 1 | 1 | 8 |
| Strings & Translations | 0 | 0 | 0 | 0 | 5 (T-5 N/A, T-6 N/A, T-7 N/A) |
| Async Safety | 0 | 2 | 0 | 0 | 4 |
| Coordinator | 0 | 0 | 0 | 0 | 7 |
| Config Flow & Lifecycle | 0 | 3 | 1 | 0 | 6 |
| Unload & Cleanup | 0 | 0 | 0 | 0 | 6 |
| Entity Best Practices | 0 | 0 | 0 | 1 | 9 |
| Device Registry | 0 | 0 | 0 | 0 | 4 |
| Error Handling | 0 | 0 | 0 | 0 | 5 |
| Scope Drift | — | — | — | — | N/A (baseline) |
| **Total** | **0** | **6** | **2** | **2** | **49** |

**Verdict:** PASS WITH NOTES

## Findings

### HACS Structure

#### H-4: Requirements not pinned to exact versions [HIGH]
**Location:** `custom_components/carelink/manifest.json:12`
**Issue:** Requirements use `>=` minimum bounds (`aiofiles>=0.8.0`, `certifi>=2023.0.0`, `httpx>=0.23.0`) instead of exact pins (`==x.y.z`). HACS and HA strongly prefer pinned versions to prevent breakage from upstream changes.
**Fix:** Pin to exact versions currently in use, e.g. `aiofiles==24.1.0`, `certifi==2024.12.14`, `httpx==0.28.1` (adjust to actual versions deployed).

#### H-9: Missing `loggers` list for third-party libraries [LOW]
**Location:** `custom_components/carelink/manifest.json`
**Issue:** The integration uses `httpx`, `aiofiles`, and `certifi` but does not declare a `loggers` list in manifest.json. This means users cannot enable debug logging for these libraries via the HA logger configuration without knowing the logger names.
**Fix:** Add `"loggers": ["httpx"]` to manifest.json (httpx is the most likely to need debug logging).

#### H-11: Missing `integration_type` in manifest.json [MEDIUM]
**Location:** `custom_components/carelink/manifest.json`
**Issue:** The `integration_type` key is absent. While not strictly required for HACS submission, it is a best practice and will be required for HA core submissions. The value should be `"hub"` since this integration provides devices with multiple entities.
**Fix:** Add `"integration_type": "hub"` to manifest.json.

### Async Safety

#### A-4a: Own httpx.AsyncClient instead of HA shared session [HIGH]
**Location:** `custom_components/carelink/api.py:116`, `tandem_api.py:542`, `nightscout_uploader.py:57`
**Issue:** All three API clients create their own `httpx.AsyncClient()` instances instead of using HA's `async_get_clientsession(hass)`. HA's shared session handles SSL, connection pooling, and lifecycle management. Custom clients risk connection leaks and bypass HA's proxy settings.
**Mitigating factor:** All three clients implement explicit `close()` methods and the coordinator calls them on unload. However, using httpx instead of aiohttp means the HA helper cannot be used directly (HA's session is aiohttp-based). This is an architectural choice that predates the current review.
**Fix:** This is a significant refactor (switching from httpx to aiohttp). Flag for future work but not blocking for HACS submission since clients are properly lifecycle-managed.

#### A-6: Sync file I/O in async setup path [HIGH]
**Location:** `custom_components/carelink/__init__.py:282-331`
**Issue:** `_migrate_legacy_logindata()` uses `os.path.exists()` (lines 298, 306, 320) and `shutil.copy()` (lines 308, 322) — both synchronous blocking operations — called directly from `_async_setup_carelink_entry()` (line 350) which runs on the event loop. These will block the event loop during setup.
**Fix:** Wrap in `await hass.async_add_executor_job(...)` or use `pathlib.Path` with `asyncio.to_thread()`. Note: the `api.py` client uses `aiofiles` for its own file operations which is correct; this migration function is the only sync file I/O in the async path.

### Config Flow & Lifecycle

#### F-1: No unique ID set in config flow [HIGH]
**Location:** `custom_components/carelink/config_flow.py:189-209` (carelink step), `config_flow.py:254-274` (tandem step)
**Issue:** Neither `async_step_carelink` nor `async_step_tandem` calls `async_set_unique_id()` or `self._abort_if_unique_id_configured()`. This means HA cannot detect duplicate entries for the same pump/account, and users can accidentally create multiple entries.
**Fix:** In `async_step_carelink`, call `await self.async_set_unique_id(user_input.get("patientId") or user_input.get("cl_client_id"))` then `self._abort_if_unique_id_configured()`. In `async_step_tandem`, use `await self.async_set_unique_id(user_input["tandem_email"])` then `self._abort_if_unique_id_configured()`.

#### F-7: No reauth flow implemented [MEDIUM]
**Location:** `custom_components/carelink/config_flow.py`
**Issue:** There is no `async_step_reauth()` method. When credentials expire (especially the Carelink token flow), HA cannot prompt the user to re-authenticate. The coordinator will keep failing with UpdateFailed until the user manually reconfigures.
**Fix:** Implement `async_step_reauth()` and `async_step_reauth_confirm()`. Raise `ConfigEntryAuthFailed` in the coordinator when auth errors are detected.

#### F-8: Setup failures do not raise ConfigEntryNotReady [HIGH]
**Location:** `custom_components/carelink/__init__.py:374` (carelink), `__init__.py:594` (tandem)
**Issue:** Both setup paths call `coordinator.async_config_entry_first_refresh()` which will raise `ConfigEntryNotReady` if `_async_update_data` raises `UpdateFailed` — this is correct for the coordinator path. However, the Tandem client creation at line 577 could fail (e.g., invalid config) and the bare exception would propagate as a generic error rather than `ConfigEntryNotReady`.
**Fix:** Wrap the client creation and initial login in a try/except that raises `ConfigEntryNotReady` for transient errors. The coordinator already handles this via `UpdateFailed` -> `ConfigEntryNotReady` but pre-coordinator failures are not wrapped.

#### F-9: Auth failures do not raise ConfigEntryAuthFailed [HIGH]
**Location:** `custom_components/carelink/__init__.py:1069-1073`
**Issue:** `TandemAuthError` is caught and re-raised as `UpdateFailed`, not `ConfigEntryAuthFailed`. Similarly, Carelink auth errors (HTTP 401/403) in `api.py` are handled internally without surfacing as `ConfigEntryAuthFailed`. This means HA never triggers the reauth flow automatically.
**Fix:** Import `ConfigEntryAuthFailed` from `homeassistant.exceptions` and raise it instead of `UpdateFailed` when `TandemAuthError` is caught. For Carelink, detect auth-specific response codes and raise `ConfigEntryAuthFailed`.

### Entity Best Practices

#### E-8: suggested_display_precision not set on all numeric sensors [LOW]
**Location:** `custom_components/carelink/const.py`
**Issue:** Per review-findings.md (S-5), `suggested_display_precision` was added to 25 Tandem sensors. However, the Carelink (Medtronic) sensor definitions in the `SENSORS` tuple (starting line 107) do not set `suggested_display_precision` for glucose readings (mmol: 2 decimal places, mg/dL: 0 decimal places) or other numeric sensors. This causes default rounding in the HA frontend.
**Fix:** Add `suggested_display_precision=2` to mmol sensors, `suggested_display_precision=0` to mg/dL sensors, and appropriate precision to other numeric Carelink sensors.

## Checks Passed (no findings)

- **HACS Structure:** H-1 (hacs.json exists with `name`), H-2 (manifest.json has `version`), H-3 (manifest.json has `issue_tracker`), H-5 (`iot_class: cloud_polling` matches behaviour), H-6 (`config_flow: true` matches `config_flow.py`), H-7 (codeowners populated), H-8 (documentation URL present), H-10 (single integration under custom_components)
- **Strings & Translations:** T-1 (strings.json exists), T-2 (all config flow steps have matching entries: user, carelink, tandem, reconfigure), T-3 (all error keys match: cannot_connect, invalid_auth, unknown), T-4 (abort reasons match: already_configured, reconfigure_successful). T-5/T-6/T-7 are N/A (no options flow, no translation_key usage, no placeholders).
- **Async Safety:** A-1 (no `import requests`), A-2 (no `time.sleep`), A-3 (file I/O uses aiofiles in api.py/tandem_api.py), A-5 (no urllib usage)
- **Coordinator:** C-1 (both coordinators subclass DataUpdateCoordinator), C-2 (`_async_update_data` is single fetch point), C-3 (update intervals: Carelink 30-300s, Tandem 60-900s — reasonable), C-4 (`async_config_entry_first_refresh` called in both setup functions), C-5 (entities access `self.coordinator.data`), C-6 (no I/O in entity properties), C-7 (N/A — API responses are dicts, equality check not practical)
- **Unload & Cleanup:** U-1 (`async_unload_entry` implemented), U-2 (platforms unloaded via `async_unload_platforms`), U-3 (services cleaned up), U-4 (all HTTP clients closed), U-5 (`hass.data[DOMAIN]` entry popped), U-6 (setup/unload symmetric)
- **Entity Best Practices:** E-1 (`has_entity_name = True` via PumpEntityMixin), E-2 (unique_id set via mixin), E-3 (entity_category used: DIAGNOSTIC for device info sensors), E-4 (device_class used extensively), E-5 (state_class correctly applied), E-6 (`native_value` used), E-7 (units compatible with device_class), E-9 (extra_state_attributes used for supplementary data, not abuse), E-10 (SensorEntityDescription pattern used)
- **Device Registry:** D-1 (DeviceInfo populated with identifiers, manufacturer, model), D-2 (identifiers format correct: `{(DOMAIN, entry_id)}`), D-3 (sw_version populated from metadata), D-4 (configuration_url set on both coordinators)
- **Error Handling:** R-1 (UpdateFailed raised in coordinators; setup uses first_refresh which converts to ConfigEntryNotReady), R-3 (no bare except that swallows setup errors — broad excepts are in data parsing, not setup), R-4 (coordinators raise UpdateFailed on transient errors), R-5 (no excessive logging on retry)

## Recommended Fix Order

1. **F-1 [HIGH]** — Add `async_set_unique_id` + `_abort_if_unique_id_configured` to config flow steps — prevents duplicate entries
2. **F-9 [HIGH]** — Raise `ConfigEntryAuthFailed` for auth errors — enables automatic reauth
3. **F-8 [HIGH]** — Wrap pre-coordinator setup failures in `ConfigEntryNotReady` — graceful retry on transient errors
4. **A-6 [HIGH]** — Wrap `_migrate_legacy_logindata` sync I/O in `async_add_executor_job` — prevents event loop blocking
5. **A-4a [HIGH]** — Own httpx clients instead of HA session — defer (major refactor, clients are lifecycle-managed)
6. **H-4 [HIGH]** — Pin requirements to exact versions — straightforward manifest change
7. **H-11 [MEDIUM]** — Add `integration_type: hub` to manifest — one-line change
8. **F-7 [MEDIUM]** — Implement reauth flow — pairs with F-9 fix
9. **E-8 [LOW]** — Add `suggested_display_precision` to Carelink sensors — cosmetic improvement
10. **H-9 [LOW]** — Add `loggers` list to manifest — optional quality improvement
