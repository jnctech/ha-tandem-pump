# HA Integration Rules — HACS Compliance

Rules the AI assistant MUST follow when writing or modifying integration code.
Violations will be caught by `/hacs-review` but should be prevented at write time.

## Async Safety (non-negotiable)
- NEVER use `requests`, `urllib`, `time.sleep`, or bare `open()` in async code
- Use `async_get_clientsession(hass)` for HTTP — do not create own `aiohttp.ClientSession`
- Sync I/O must be wrapped in `hass.async_add_executor_job()`

## Coordinator
- `_async_update_data` is the single fetch point — no API calls anywhere else
- Entity properties return cached `self.coordinator.data` only — no I/O
- Raise `UpdateFailed` on transient fetch errors (HA auto-retries)
- Call `async_config_entry_first_refresh()` in `async_setup_entry`

## Entities
- `has_entity_name = True` on all entities
- `unique_id` on every entity — must be stable (device serial, not IP/hostname)
- `native_value` (not deprecated `state` property)
- `state_class`: MEASUREMENT for instantaneous, TOTAL_INCREASING for cumulative, None for discrete events
- `device_class` and `native_unit_of_measurement` must be compatible when both set
- `entity_category`: CONFIG for settings, DIAGNOSTIC for read-only diagnostics
- Use `EntityDescription` dataclass pattern (already in `const.py`)

## Config Flow
- Call `async_set_unique_id()` + `_abort_if_unique_id_configured()` to prevent duplicates
- Test connection/auth before creating entry
- Never mutate `entry.data` directly — use `hass.config_entries.async_update_entry()`
- Bump `VERSION` and add `async_migrate_entry` when changing config schema

## Lifecycle (setup/unload symmetry)
- Everything registered in `async_setup_entry` must be cleaned up in `async_unload_entry`
- Forward platforms with `async_forward_entry_setups`, unload with `async_unload_platforms`
- Clean up `hass.data[DOMAIN]` on unload

## Error Handling
- `ConfigEntryNotReady` for temporary setup failures (HA auto-retries)
- `ConfigEntryAuthFailed` for auth failures (triggers reauth flow)
- Always chain exceptions: `raise ConfigEntryNotReady("msg") from ex`
- Never swallow exceptions silently in setup or coordinator

## Strings
- Every `async_step_*` needs a matching entry in `strings.json` under `config.step`
- All error/abort keys referenced in config flow must exist in `strings.json`
- Entities using `translation_key` need entries under `entity.<platform>.<key>.name`
