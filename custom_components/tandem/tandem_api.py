"""Tandem Diabetes Source API client.

Implements OIDC/PKCE authentication against source.tandemdiabetes.com (US)
and source.eu.tandemdiabetes.com (EU) to fetch pump data for Tandem t:slim
insulin pumps.

Authentication flow:
1. POST credentials to login API
2. GET authorization endpoint with PKCE challenge (follows redirects to get code)
3. POST code + verifier to token endpoint (gets access_token + id_token)
4. Decode JWT id_token to extract pumperId and accountId

Data sources:
- Tandem Source API: pump metadata (serial, model, last upload)
- ControlIQ API: therapy timeline (CGM, bolus, basal) and summary statistics
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
import re
import ssl
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from urllib.parse import urlencode, urlparse, parse_qs

import certifi
import httpx

from .exceptions import TandemApiError, TandemAuthError  # noqa: F401  (re-exported for callers)

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

# Per-request timeout (seconds). Applied on every call so behaviour is identical
# whether we own the client or reuse Home Assistant's managed httpx client, whose
# default timeout (5 s) is too short for the Tandem Source OIDC/report calls.
REQUEST_TIMEOUT = 30.0


# ── Binary pump event decoder ────────────────────────────────────────
# The Tandem Source pumpevents API returns base64-encoded binary data.
# Each record is 26 bytes (big-endian). Format based on tconnectsync
# event parser (https://github.com/jwoglom/tconnectsync).

EVENT_LEN = 26
TANDEM_EPOCH = 1199145600  # 2008-01-01 00:00:00 (local pump time)

# Event type IDs we care about
EVT_BASAL_RATE_CHANGE = 3
EVT_PUMPING_SUSPENDED = 11
EVT_PUMPING_RESUMED = 12
EVT_BG_READING_TAKEN = 16
EVT_BOLUS_COMPLETED = 20
EVT_BOLEX_COMPLETED = 21
EVT_CARTRIDGE_FILLED = 33
EVT_CARBS_ENTERED = 48
EVT_CANNULA_FILLED = 61
EVT_TUBING_FILLED = 63
EVT_ALERT_ACTIVATED = 4
EVT_ALARM_ACTIVATED = 5
EVT_MALFUNCTION_ACTIVATED = 6
EVT_USB_CONNECTED = 36
EVT_USB_DISCONNECTED = 37
EVT_SHELF_MODE = 53
EVT_STATUS = 9  # LID_STATUS — periodic pump status, carries battery charge (abc)
EVT_BATTERY_1 = 34  # LID battery detail (carries abc battery charge)
EVT_BATTERY_2 = 35  # LID battery detail (carries abc battery charge)
EVT_ALERT_CLEARED = 26
EVT_ALARM_CLEARED = 28
EVT_DAILY_BASAL = 81
EVT_AA_USER_MODE_CHANGE = 229
EVT_AA_PCM_CHANGE = 230
EVT_CGM_DATA_GXB = 256
EVT_BASAL_DELIVERY = 279
EVT_BOLUS_DELIVERY = 280
EVT_BOLUS_REQUESTED_MSG1 = 64
EVT_BOLUS_REQUESTED_MSG2 = 65
EVT_BOLUS_REQUESTED_MSG3 = 66
EVT_NEW_DAY = 90
EVT_PLGS_PERIODIC = 140
EVT_AA_DAILY_STATUS = 313
EVT_CGM_DATA_FSL2 = 372
EVT_CGM_DATA_G7 = 399
EVT_CGM_SESSION_START = 212  # LID_CGM_START_SESSION_GX
EVT_CGM_SESSION_JOIN = 213  # LID_CGM_JOIN_SESSION_GX
EVT_CGM_SESSION_STOP = 214  # LID_CGM_STOP_SESSION_GX


def _decode_cgm_gxb_layout(evt: dict[str, Any], payload: bytes) -> None:
    """Decode GXB-style CGM payload (shared by events 256 and 399)."""
    evt["event_name"] = "CGM"
    evt["glucose_mgdl"] = struct.unpack_from(">H", payload, 4)[0]
    rate_raw = struct.unpack_from(">b", payload, 0)[0]
    evt["rate_of_change"] = round(rate_raw * 0.1, 1)
    evt["status"] = struct.unpack_from(">H", payload, 2)[0]


def decode_pump_events(raw_b64: str) -> list[dict[str, Any]]:
    """Decode base64-encoded binary pump events into a list of dicts.

    Each returned dict contains:
        event_id: int - event type identifier
        event_name: str - human-readable event name
        timestamp: datetime - event timestamp (UTC)
        seq: int - sequence number
        ... event-specific fields
    """
    try:
        raw_bytes = base64.b64decode(raw_b64)
    except (ValueError, binascii.Error) as e:
        _LOGGER.error("Failed to base64-decode pump events: %s", e)
        return []

    num_events = len(raw_bytes) // EVENT_LEN
    _LOGGER.debug("Decoding %d pump events (%d bytes)", num_events, len(raw_bytes))

    events: list[dict[str, Any]] = []
    event_id_counts: dict[int, int] = {}
    for i in range(num_events):
        chunk = raw_bytes[i * EVENT_LEN : (i + 1) * EVENT_LEN]
        if len(chunk) < EVENT_LEN:
            break

        # Header (bytes 0-9)
        source_and_id = struct.unpack_from(">H", chunk, 0)[0]
        event_id = source_and_id & 0x0FFF
        ts_raw = struct.unpack_from(">I", chunk, 2)[0]
        seq = struct.unpack_from(">I", chunk, 6)[0]
        payload = chunk[10:26]  # 16-byte data payload

        # Tandem timestamps are LOCAL pump time (seconds since 2008-01-01
        # midnight local).  Create a naive datetime so the coordinator can
        # attach the correct pump timezone via .replace(tzinfo=tz).
        ts = datetime.fromtimestamp(TANDEM_EPOCH + ts_raw, tz=timezone.utc).replace(tzinfo=None)
        event_id_counts[event_id] = event_id_counts.get(event_id, 0) + 1

        evt: dict[str, Any] = {
            "event_id": event_id,
            "timestamp": ts,
            "seq": seq,
        }

        # Parse event-specific payload fields
        if event_id == EVT_CGM_DATA_GXB:
            _decode_cgm_gxb_layout(evt, payload)

        elif event_id == EVT_BOLUS_COMPLETED:
            evt["event_name"] = "BolusCompleted"
            bolus_id = struct.unpack_from(">H", payload, 0)[0]
            completion = struct.unpack_from(">H", payload, 2)[0]
            iob = struct.unpack_from(">f", payload, 4)[0]
            delivered = struct.unpack_from(">f", payload, 8)[0]
            requested = struct.unpack_from(">f", payload, 12)[0]
            evt["bolus_id"] = bolus_id
            evt["completion_status"] = completion  # 3=completed
            evt["iob"] = round(iob, 2)
            evt["insulin_delivered"] = round(delivered, 2)
            evt["insulin_requested"] = round(requested, 2)

        elif event_id == EVT_BOLUS_DELIVERY:
            evt["event_name"] = "BolusDelivery"
            bolus_type = struct.unpack_from(">B", payload, 0)[0]
            status = struct.unpack_from(">B", payload, 1)[0]
            bolus_id = struct.unpack_from(">H", payload, 2)[0]
            requested_now = struct.unpack_from(">H", payload, 4)[0]
            correction = struct.unpack_from(">H", payload, 8)[0]
            delivered_total = struct.unpack_from(">H", payload, 12)[0]
            evt["bolus_type"] = bolus_type
            evt["delivery_status"] = status  # 0=completed, 1=started
            evt["bolus_id"] = bolus_id
            evt["requested_now_mu"] = requested_now  # milliunits
            evt["correction_mu"] = correction
            evt["delivered_total_mu"] = delivered_total
            evt["insulin_delivered"] = round(delivered_total / 1000.0, 3)

        elif event_id == EVT_BASAL_RATE_CHANGE:
            evt["event_name"] = "BasalRateChange"
            commanded = struct.unpack_from(">f", payload, 0)[0]
            base_rate = struct.unpack_from(">f", payload, 4)[0]
            max_rate = struct.unpack_from(">f", payload, 8)[0]
            change_type = struct.unpack_from(">B", payload, 13)[0]
            evt["commanded_rate"] = round(commanded, 3)
            evt["base_rate"] = round(base_rate, 3)
            evt["max_rate"] = round(max_rate, 3)
            evt["change_type"] = change_type

        elif event_id == EVT_BASAL_DELIVERY:
            evt["event_name"] = "BasalDelivery"
            commanded_source = struct.unpack_from(">H", payload, 2)[0]
            profile_rate = struct.unpack_from(">H", payload, 4)[0]
            commanded_rate = struct.unpack_from(">H", payload, 6)[0]
            evt["commanded_source"] = commanded_source
            evt["profile_rate_mu"] = profile_rate  # milliunits/hr
            evt["commanded_rate_mu"] = commanded_rate
            evt["commanded_rate"] = round(commanded_rate / 1000.0, 3)

        elif event_id == EVT_PUMPING_SUSPENDED:
            evt["event_name"] = "PumpingSuspended"
            suspend_reason = struct.unpack_from(">B", payload, 0)[0]
            insulin_amount = struct.unpack_from(">f", payload, 4)[0]
            reason_map = {
                0: "User",
                1: "Alarm",
                2: "Malfunction",
                3: "Auto-PLGS",
            }
            evt["suspend_reason"] = reason_map.get(suspend_reason, f"Unknown ({suspend_reason})")
            evt["suspend_reason_id"] = suspend_reason
            evt["insulin_amount"] = round(insulin_amount, 2)

        elif event_id == EVT_PUMPING_RESUMED:
            evt["event_name"] = "PumpingResumed"
            pre_resume_state = struct.unpack_from(">B", payload, 0)[0]
            insulin_amount = struct.unpack_from(">f", payload, 4)[0]
            evt["pre_resume_state"] = pre_resume_state
            evt["insulin_amount"] = round(insulin_amount, 2)

        elif event_id == EVT_BG_READING_TAKEN:
            evt["event_name"] = "BGReading"
            bg = struct.unpack_from(">H", payload, 0)[0]
            iob = struct.unpack_from(">f", payload, 4)[0]
            entry_type = struct.unpack_from(">B", payload, 8)[0]
            type_map = {0: "Manual", 1: "Dexcom EGV"}
            evt["bg_mgdl"] = bg
            evt["iob"] = round(iob, 2)
            evt["entry_type"] = type_map.get(entry_type, f"Type_{entry_type}")

        elif event_id == EVT_BOLEX_COMPLETED:
            evt["event_name"] = "BolexCompleted"
            # Same structure as BOLUS_COMPLETED
            bolus_id = struct.unpack_from(">H", payload, 0)[0]
            completion = struct.unpack_from(">H", payload, 2)[0]
            iob = struct.unpack_from(">f", payload, 4)[0]
            delivered = struct.unpack_from(">f", payload, 8)[0]
            requested = struct.unpack_from(">f", payload, 12)[0]
            evt["bolus_id"] = bolus_id
            evt["completion_status"] = completion
            evt["iob"] = round(iob, 2)
            evt["insulin_delivered"] = round(delivered, 2)
            evt["insulin_requested"] = round(requested, 2)

        elif event_id == EVT_CARTRIDGE_FILLED:
            evt["event_name"] = "CartridgeFilled"
            insulin_volume = struct.unpack_from(">f", payload, 4)[0]
            evt["insulin_volume"] = round(insulin_volume, 1)

        elif event_id == EVT_CARBS_ENTERED:
            evt["event_name"] = "CarbsEntered"
            carbs = struct.unpack_from(">f", payload, 0)[0]
            evt["carbs"] = round(carbs)

        elif event_id == EVT_CANNULA_FILLED:
            evt["event_name"] = "CannulaFilled"
            prime_size = struct.unpack_from(">f", payload, 0)[0]
            completion = struct.unpack_from(">H", payload, 4)[0]
            evt["prime_size"] = round(prime_size, 2)
            evt["completion_status"] = completion

        elif event_id == EVT_TUBING_FILLED:
            evt["event_name"] = "TubingFilled"
            prime_size = struct.unpack_from(">f", payload, 0)[0]
            completion = struct.unpack_from(">H", payload, 4)[0]
            evt["prime_size"] = round(prime_size, 2)
            evt["completion_status"] = completion

        elif event_id == EVT_AA_USER_MODE_CHANGE:
            evt["event_name"] = "UserModeChange"
            current_mode = struct.unpack_from(">B", payload, 0)[0]
            previous_mode = struct.unpack_from(">B", payload, 1)[0]
            mode_map = {
                0: "Normal",
                1: "Sleep",
                2: "Exercise",
                3: "Eating Soon",
            }
            evt["current_mode"] = mode_map.get(current_mode, f"Mode_{current_mode}")
            evt["previous_mode"] = mode_map.get(previous_mode, f"Mode_{previous_mode}")
            evt["current_mode_id"] = current_mode
            evt["previous_mode_id"] = previous_mode

        elif event_id == EVT_AA_PCM_CHANGE:
            evt["event_name"] = "PCMChange"
            current_pcm = struct.unpack_from(">B", payload, 0)[0]
            previous_pcm = struct.unpack_from(">B", payload, 1)[0]
            pcm_map = {
                0: "No Control",
                1: "Open Loop",
                2: "Pining",
                3: "Closed Loop",
            }
            evt["current_pcm"] = pcm_map.get(current_pcm, f"PCM_{current_pcm}")
            evt["previous_pcm"] = pcm_map.get(previous_pcm, f"PCM_{previous_pcm}")

        elif event_id == EVT_USB_CONNECTED:
            evt["event_name"] = "USBConnected"
            negotiated_current = struct.unpack_from(">f", payload, 0)[0]
            evt["negotiated_current_ma"] = round(negotiated_current, 1)

        elif event_id == EVT_USB_DISCONNECTED:
            evt["event_name"] = "USBDisconnected"
            negotiated_current = struct.unpack_from(">f", payload, 0)[0]
            evt["negotiated_current_ma"] = round(negotiated_current, 1)

        elif event_id == EVT_SHELF_MODE:
            evt["event_name"] = "ShelfMode"
            # Battery detail from LID_SHELF_MODE event
            msec_since_reset = struct.unpack_from(">I", payload, 0)[0]
            lipo_ibc = struct.unpack_from(">B", payload, 4)[0]  # battery % (display)
            lipo_abc = struct.unpack_from(">B", payload, 5)[0]  # alternate battery %
            lipo_current = struct.unpack_from(">h", payload, 6)[0]  # mA (signed)
            lipo_rem_cap = struct.unpack_from(">I", payload, 8)[0]  # mAh
            lipo_mv = struct.unpack_from(">I", payload, 12)[0]  # mV
            evt["msec_since_reset"] = msec_since_reset
            evt["battery_percent"] = lipo_ibc
            evt["battery_percent_alt"] = lipo_abc
            evt["battery_current_ma"] = lipo_current
            evt["battery_remaining_mah"] = lipo_rem_cap
            evt["battery_voltage_mv"] = lipo_mv

        elif event_id in (EVT_ALERT_ACTIVATED, EVT_ALARM_ACTIVATED, EVT_MALFUNCTION_ACTIVATED):
            # payload is always 16 bytes (chunk[10:26], guaranteed by EVENT_LEN guard above).
            # Struct reads at offsets 0/4/8/12 are fully within bounds.
            name_map = {
                EVT_ALERT_ACTIVATED: "AlertActivated",
                EVT_ALARM_ACTIVATED: "AlarmActivated",
                EVT_MALFUNCTION_ACTIVATED: "MalfunctionActivated",
            }
            evt["event_name"] = name_map[event_id]
            alert_id = struct.unpack_from(">I", payload, 0)[0]
            fault_locator = struct.unpack_from(">I", payload, 4)[0]
            param1 = struct.unpack_from(">I", payload, 8)[0]
            param2 = struct.unpack_from(">f", payload, 12)[0]
            evt["alert_id"] = alert_id
            evt["fault_locator"] = fault_locator
            evt["param1"] = param1
            evt["param2"] = round(param2, 3)

        elif event_id == EVT_ALERT_CLEARED:
            evt["event_name"] = "AlertCleared"
            alert_id = struct.unpack_from(">I", payload, 0)[0]
            evt["alert_id"] = alert_id

        elif event_id == EVT_ALARM_CLEARED:
            # Event 28 clears both AlarmActivated (5) and MalfunctionActivated (6) events.
            # The pump does not emit a separate MalfunctionCleared event.
            evt["event_name"] = "AlarmCleared"
            alert_id = struct.unpack_from(">I", payload, 0)[0]
            evt["alert_id"] = alert_id

        elif event_id == EVT_DAILY_BASAL:
            evt["event_name"] = "DailyBasal"
            # LID_DAILY_BASAL: daily totals + battery data
            daily_total_basal = struct.unpack_from(">f", payload, 0)[0]
            last_basal_rate = struct.unpack_from(">f", payload, 4)[0]
            iob = struct.unpack_from(">f", payload, 8)[0]
            battery_msb_raw = struct.unpack_from(">B", payload, 12)[0]
            battery_lsb_raw = struct.unpack_from(">B", payload, 13)[0]
            # Bytes 14-15 are NOT millivolts in DailyBasal — raw value is
            # unreliable (e.g. 25344 vs ShelfMode's 3722 mV). Omit voltage;
            # ShelfMode provides the accurate reading.
            # Battery % formula from tconnectsync transforms.py
            battery_pct = min(100, max(0, round((256 * (battery_msb_raw - 14) + battery_lsb_raw) / (3 * 256) * 100, 1)))
            evt["daily_total_basal"] = round(daily_total_basal, 2)
            evt["last_basal_rate"] = round(last_basal_rate, 3)
            evt["iob"] = round(iob, 2)
            evt["battery_percent"] = battery_pct

        elif event_id == EVT_CGM_DATA_G7:
            _decode_cgm_gxb_layout(evt, payload)

        elif event_id == EVT_CGM_DATA_FSL2:
            # Libre 2: int16 rate (not int8), uint8 status (not uint16)
            evt["event_name"] = "CGM"
            glucose = struct.unpack_from(">H", payload, 4)[0]
            rate_raw = struct.unpack_from(">h", payload, 0)[0]  # int16
            status = struct.unpack_from(">B", payload, 2)[0]  # uint8
            evt["glucose_mgdl"] = glucose
            evt["rate_of_change"] = round(rate_raw * 0.1, 1)
            evt["status"] = status

        elif event_id == EVT_AA_DAILY_STATUS:
            evt["event_name"] = "AADailyStatus"
            sensor_type = struct.unpack_from(">B", payload, 1)[0]
            user_mode = struct.unpack_from(">B", payload, 2)[0]
            pump_control_state = struct.unpack_from(">B", payload, 3)[0]
            sensor_type_map = {0: "No CGM", 1: "G6", 2: "Libre 2", 3: "G7"}
            evt["sensor_type"] = sensor_type_map.get(sensor_type, f"Unknown ({sensor_type})")
            evt["sensor_type_id"] = sensor_type
            evt["user_mode"] = user_mode
            evt["pump_control_state"] = pump_control_state

        elif event_id == EVT_NEW_DAY:
            evt["event_name"] = "NewDay"
            commanded_basal_rate = struct.unpack_from(">f", payload, 0)[0]
            features_bitmask = struct.unpack_from(">I", payload, 4)[0]
            evt["commanded_basal_rate"] = round(commanded_basal_rate, 3)
            evt["features_bitmask"] = features_bitmask

        elif event_id == EVT_PLGS_PERIODIC:
            evt["event_name"] = "PLGSPeriodic"
            homin_state = struct.unpack_from(">B", payload, 4)[0]
            rule_state = struct.unpack_from(">B", payload, 5)[0]
            pgv = struct.unpack_from(">H", payload, 10)[0]
            fmr = struct.unpack_from(">H", payload, 12)[0]
            homin_state_map = {
                0: "No Prediction",
                1: "BG Rising",
                2: "BG Falling Mildly",
                3: "BG Falling Rapidly",
                4: "BG Falling - Suspend",
            }
            evt["homin_state"] = homin_state_map.get(homin_state, f"State_{homin_state}")
            evt["homin_state_id"] = homin_state
            evt["rule_state"] = rule_state
            evt["predicted_glucose_mgdl"] = pgv
            evt["fmr_mgdl"] = fmr

        elif event_id == EVT_BOLUS_REQUESTED_MSG1:
            evt["event_name"] = "BolusRequestedMsg1"
            correction_included = struct.unpack_from(">B", payload, 0)[0]
            bolus_type = struct.unpack_from(">B", payload, 1)[0]
            bolus_id = struct.unpack_from(">H", payload, 2)[0]
            bg = struct.unpack_from(">H", payload, 4)[0]
            iob = struct.unpack_from(">f", payload, 6)[0]
            carb_amount = struct.unpack_from(">H", payload, 10)[0]
            carb_ratio_raw = struct.unpack_from(">I", payload, 12)[0]
            evt["correction_included"] = bool(correction_included)
            evt["bolus_type"] = bolus_type
            evt["bolus_id"] = bolus_id
            evt["bg_mgdl"] = bg
            evt["iob"] = round(iob, 2)
            evt["carb_amount"] = carb_amount
            # Carb ratio is stored as fixed-point g/u * 1000
            evt["carb_ratio"] = round(carb_ratio_raw / 1000.0, 1)

        elif event_id == EVT_BOLUS_REQUESTED_MSG2:
            evt["event_name"] = "BolusRequestedMsg2"
            standard_percent = struct.unpack_from(">B", payload, 0)[0]
            bolus_id = struct.unpack_from(">H", payload, 2)[0]
            target_bg = struct.unpack_from(">H", payload, 4)[0]
            isf = struct.unpack_from(">H", payload, 6)[0]
            duration = struct.unpack_from(">H", payload, 8)[0]
            declined_correction = struct.unpack_from(">B", payload, 10)[0]
            user_override = struct.unpack_from(">B", payload, 11)[0]
            evt["standard_percent"] = standard_percent
            evt["bolus_id"] = bolus_id
            evt["target_bg"] = target_bg
            evt["isf"] = isf
            evt["duration_minutes"] = duration
            evt["declined_correction"] = bool(declined_correction)
            evt["user_override"] = bool(user_override)

        elif event_id == EVT_BOLUS_REQUESTED_MSG3:
            evt["event_name"] = "BolusRequestedMsg3"
            bolus_id = struct.unpack_from(">H", payload, 0)[0]
            food_bolus = struct.unpack_from(">f", payload, 2)[0]
            correction_bolus = struct.unpack_from(">f", payload, 6)[0]
            total_bolus = struct.unpack_from(">f", payload, 10)[0]
            evt["bolus_id"] = bolus_id
            evt["food_bolus_size"] = round(food_bolus, 2)
            evt["correction_bolus_size"] = round(correction_bolus, 2)
            evt["total_bolus_size"] = round(total_bolus, 2)

        else:
            evt["event_name"] = f"Event_{event_id}"
            continue  # Skip events we don't need

        events.append(evt)

    # Log event ID distribution for diagnostics
    _LOGGER.debug("Tandem: Raw event ID counts: %s", dict(sorted(event_id_counts.items())))

    return events


# ═══════════════════════════════════════════════════════════════════════════
# Tandem Source BFF adapters
#
# Tandem migrated the Source Reports API from ``api/reports/reportsfacade/*`` to
# ``api/reports/bff/*`` (~June 2026). The BFF returns pre-decoded JSON instead of
# the base64 binary blob ``decode_pump_events`` parsed, and renames the device id
# (``tconnectDeviceId`` → ``assignmentId``). These helpers translate the new BFF
# shapes back into the legacy dicts the coordinator already consumes, so the
# migration is contained to the API client and no coordinator/sensor code changes.
#
# eventProperties key names below are the server's camelCase keys, matched
# case-insensitively via ``_norm`` and confirmed against a live EU account
# (2026-09-06). CGM events 256 (GXB/G6), 372 (FSL2) and 399 (G7) share identical
# properties, so all three map the same — important when a user swaps sensors.
# ═══════════════════════════════════════════════════════════════════════════

# Typed dict[Any, str] because the lookup key comes from eventProperties as
# ``Any | None`` (a missing/None code falls through to the default).
_SUSPEND_REASON_MAP: dict[Any, str] = {0: "User", 1: "Alarm", 2: "Malfunction", 3: "Auto-PLGS"}
_USER_MODE_MAP: dict[Any, str] = {0: "Normal", 1: "Sleep", 2: "Exercise", 3: "Eating Soon"}
_PCM_MAP: dict[Any, str] = {0: "No Control", 1: "Open Loop", 2: "Pining", 3: "Closed Loop"}
_BG_ENTRY_TYPE_MAP: dict[Any, str] = {0: "Manual", 1: "Dexcom EGV"}
_CGM_SENSOR_TYPE_MAP: dict[Any, str] = {0: "No CGM", 1: "G6", 2: "Libre 2", 3: "G7"}


def _as_bool(value: Any) -> Any:
    """Coerce a BFF flag to bool, preserving None (absent → None, not False)."""
    return bool(value) if value is not None else None


# CGM event codes that share the GXB eventProperties layout (G6, FSL2, G7).
_CGM_EVENT_IDS = (EVT_CGM_DATA_GXB, EVT_CGM_DATA_FSL2, EVT_CGM_DATA_G7)


def _norm(key: str) -> str:
    """Normalise an eventProperties key for robust lookup (lowercase, alnum)."""
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _round(value: Any, ndigits: int) -> Any:
    """Round a numeric value, tolerating None (returns None unchanged)."""
    return round(value, ndigits) if isinstance(value, (int, float)) else value


def _bitmask_to_int(value: Any) -> Any:
    """Convert a BFF bitmask field to the int the coordinator expects.

    Bitmask eventProperties (bolusType, changeType, cgmDataType, …) arrive from
    the BFF as arrays of set-bit indices, e.g. ``[4]`` meaning bit 4 is set
    (= 0x10). The old binary decoder produced a plain int, and the coordinator
    still does integer bit tests on these (``bolus_type & 0x10``), so an array
    here raises ``TypeError``. Convert ``[i, j, …]`` → ``sum(1 << i)``; pass an
    int through unchanged and None → None.
    """
    if isinstance(value, (list, tuple)):
        result = 0
        for bit in value:
            try:
                result |= 1 << int(bit)
            except (TypeError, ValueError):
                continue
        return result
    return value


def _parse_pump_datetime(value: str | None) -> datetime | None:
    """Parse a BFF ``pumpDateTime`` into a NAIVE datetime in pump-local time.

    The BFF sends pump-local wall-clock timestamps (e.g. "2026-09-05T14:22:33").
    The coordinator attaches the real pump timezone afterwards, exactly as it did
    for the old binary decoder, so we return a naive datetime carrying the same
    wall-clock and never shift it. (``estimatedDateTime`` is the UTC form and must
    NOT be used here — it would double-shift.)
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def map_pump_log_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map one BFF ``pump-logs`` JSON event to the legacy decoded-event dict.

    Returns the same shape ``decode_pump_events`` produced (``event_id``,
    ``timestamp`` naive-local, ``event_name`` + per-type payload fields), or
    ``None`` for event types the coordinator does not consume from this path.

    NOTE (staged): core event types plus the bolus-calculator (64/65/66),
    Control-IQ daily status (313, CGM sensor type), pump-status/battery
    (9/34/35, battery level from ``abc``), alerts/alarms (4/5/6/26/28) and
    CGM session (212/213/214) are mapped. Still unmapped — their sensors read
    unavailable (null-not-guess) until added: ShelfMode (53), USB charging
    (36/37), daily basal (81), new day (90), PLGS (140). Codes 8 and 27 appear
    live but are absent from the tconnectsync event catalog, so they stay
    unmapped pending identification. Live eventProperties keys are recorded in
    .remember/BFF-LIVE-VALIDATION-2026-09-06.md.
    """
    event_id = event.get("eventCode")
    ts = _parse_pump_datetime(event.get("pumpDateTime"))
    if event_id is None or ts is None:
        return None

    props = {_norm(k): v for k, v in (event.get("eventProperties") or {}).items()}
    g = props.get
    evt: dict[str, Any] = {"event_id": event_id, "timestamp": ts, "seq": event.get("sequenceNumber")}

    if event_id in _CGM_EVENT_IDS:
        evt["event_name"] = "CGM"
        evt["glucose_mgdl"] = g("currentglucosedisplayvalue")
        rate = g("rate")
        evt["rate_of_change"] = round(rate * 0.1, 1) if isinstance(rate, (int, float)) else None
        evt["status"] = g("glucosevaluestatus")
        # CGM transmitter signal strength. Confirmed present on event 256 (G6/GXB)
        # in live validation; not confirmed on 399 (G7) — absent -> None (null-not-guess).
        evt["rssi"] = g("rssi")

    elif event_id in (EVT_BOLUS_COMPLETED, EVT_BOLEX_COMPLETED):
        evt["event_name"] = "BolusCompleted" if event_id == EVT_BOLUS_COMPLETED else "BolexCompleted"
        evt["bolus_id"] = g("bolusid")
        evt["completion_status"] = g("completionstatus")
        evt["iob"] = _round(g("iob"), 2)
        evt["insulin_delivered"] = _round(g("insulindelivered"), 2)
        evt["insulin_requested"] = _round(g("insulinrequested"), 2)

    elif event_id == EVT_BOLUS_DELIVERY:
        evt["event_name"] = "BolusDelivery"
        # bolusType is a bitmask array from the BFF; the coordinator bit-tests it
        # (``bolus_type & 0x10`` for meal-bolus detection), so coerce to int.
        evt["bolus_type"] = _bitmask_to_int(g("bolustype"))
        evt["delivery_status"] = g("bolusdeliverystatus")  # 0=completed, 1=started
        evt["bolus_id"] = g("bolusid")
        evt["requested_now_mu"] = g("requestednow")
        evt["correction_mu"] = g("correction")
        delivered_total = g("deliveredtotal")
        evt["delivered_total_mu"] = delivered_total
        evt["insulin_delivered"] = (
            round(delivered_total / 1000.0, 3) if isinstance(delivered_total, (int, float)) else None
        )

    elif event_id == EVT_BASAL_RATE_CHANGE:
        evt["event_name"] = "BasalRateChange"
        evt["commanded_rate"] = _round(g("commandedbasalrate"), 3)
        evt["base_rate"] = _round(g("basebasalrate"), 3)
        evt["max_rate"] = _round(g("maxbasalrate"), 3)
        evt["change_type"] = _bitmask_to_int(g("changetype"))

    elif event_id == EVT_BASAL_DELIVERY:
        evt["event_name"] = "BasalDelivery"
        evt["commanded_source"] = g("commandedratesource")
        evt["profile_rate_mu"] = g("profilebasalrate")
        commanded_rate_mu = g("commandedrate")
        evt["commanded_rate_mu"] = commanded_rate_mu
        evt["commanded_rate"] = (
            round(commanded_rate_mu / 1000.0, 3) if isinstance(commanded_rate_mu, (int, float)) else None
        )

    elif event_id == EVT_PUMPING_SUSPENDED:
        evt["event_name"] = "PumpingSuspended"
        reason = g("suspendreason")
        evt["suspend_reason_id"] = reason
        evt["suspend_reason"] = _SUSPEND_REASON_MAP.get(reason, f"Unknown ({reason})")
        evt["insulin_amount"] = _round(g("insulinamount"), 2)

    elif event_id == EVT_PUMPING_RESUMED:
        evt["event_name"] = "PumpingResumed"
        evt["pre_resume_state"] = g("preresumestate")
        evt["insulin_amount"] = _round(g("insulinamount"), 2)

    elif event_id == EVT_BG_READING_TAKEN:
        evt["event_name"] = "BGReading"
        evt["bg_mgdl"] = g("bg")
        evt["iob"] = _round(g("iob"), 2)
        entry_type = g("bgentrytype")
        evt["entry_type"] = _BG_ENTRY_TYPE_MAP.get(entry_type, f"Type_{entry_type}")

    elif event_id == EVT_CARTRIDGE_FILLED:
        evt["event_name"] = "CartridgeFilled"
        volume = g("v2volume")
        if volume is None:
            volume = g("insulinvolume")
        evt["insulin_volume"] = _round(volume, 1)

    elif event_id == EVT_CARBS_ENTERED:
        evt["event_name"] = "CarbsEntered"
        carbs = g("carbs")
        evt["carbs"] = round(carbs) if isinstance(carbs, (int, float)) else None

    elif event_id in (EVT_CANNULA_FILLED, EVT_TUBING_FILLED):
        evt["event_name"] = "CannulaFilled" if event_id == EVT_CANNULA_FILLED else "TubingFilled"
        evt["prime_size"] = _round(g("primesize"), 2)
        evt["completion_status"] = g("completionstatus")

    elif event_id == EVT_AA_USER_MODE_CHANGE:
        evt["event_name"] = "UserModeChange"
        current = g("currentusermode")
        previous = g("previoususermode")
        evt["current_mode_id"] = current
        evt["previous_mode_id"] = previous
        evt["current_mode"] = _USER_MODE_MAP.get(current, f"Mode_{current}")
        evt["previous_mode"] = _USER_MODE_MAP.get(previous, f"Mode_{previous}")

    elif event_id == EVT_AA_PCM_CHANGE:
        evt["event_name"] = "PCMChange"
        current = g("currentpcm")
        previous = g("previouspcm")
        evt["current_pcm"] = _PCM_MAP.get(current, f"PCM_{current}")
        evt["previous_pcm"] = _PCM_MAP.get(previous, f"PCM_{previous}")
        # Control-IQ setting: whether the user prefers closed-loop operation.
        evt["closed_loop_preferred"] = _as_bool(g("closedlooppreferred"))

    elif event_id == EVT_BOLUS_REQUESTED_MSG1:
        # Bolus calculator message 1 — carbs/BG/IOB at request time. Joined with
        # msg2/msg3 by bolus_id in the coordinator to build the last-bolus detail.
        evt["event_name"] = "BolusRequestedMsg1"
        evt["bolus_id"] = g("bolusid")
        evt["bg_mgdl"] = g("bg")
        evt["iob"] = _round(g("iob"), 2)
        evt["carb_amount"] = g("carbamount")
        carb_ratio = g("carbratio")
        # Carb ratio is fixed-point g/u * 1000 (matches the binary decoder).
        evt["carb_ratio"] = round(carb_ratio / 1000.0, 1) if isinstance(carb_ratio, (int, float)) else None
        evt["bolus_type"] = _bitmask_to_int(g("bolustype"))
        evt["correction_included"] = _as_bool(g("correctionbolusincluded"))

    elif event_id == EVT_BOLUS_REQUESTED_MSG2:
        evt["event_name"] = "BolusRequestedMsg2"
        evt["bolus_id"] = g("bolusid")
        evt["standard_percent"] = g("standardpercent")
        evt["target_bg"] = g("targetbg")
        evt["isf"] = g("isf")
        evt["duration_minutes"] = g("duration")
        evt["declined_correction"] = _as_bool(g("declinedcorrection"))
        evt["user_override"] = _as_bool(g("useroverride"))

    elif event_id == EVT_BOLUS_REQUESTED_MSG3:
        # Bolus calculator message 3 — the delivered split. Carries the msg3
        # timestamp the coordinator uses to pick the latest complete record.
        evt["event_name"] = "BolusRequestedMsg3"
        evt["bolus_id"] = g("bolusid")
        evt["food_bolus_size"] = _round(g("foodbolussize"), 2)
        evt["correction_bolus_size"] = _round(g("correctionbolussize"), 2)
        evt["total_bolus_size"] = _round(g("totalbolussize"), 2)

    elif event_id == EVT_AA_DAILY_STATUS:
        # Control-IQ daily status — carries the active CGM sensor type.
        evt["event_name"] = "AADailyStatus"
        sensor_type = g("sensortype")
        evt["sensor_type_id"] = sensor_type
        evt["sensor_type"] = _CGM_SENSOR_TYPE_MAP.get(sensor_type, f"Unknown ({sensor_type})")
        evt["user_mode"] = g("usermode")
        evt["pump_control_state"] = g("pumpcontrolstate")

    elif event_id in (EVT_STATUS, EVT_BATTERY_1, EVT_BATTERY_2):
        # Pump status / battery-detail events. `abc` (actual battery charge) is the
        # display battery percentage (0-100) — the value behind the pump's on-screen
        # battery icon. Live validation (2026-09-06, event 9): abc=96 matched the
        # physical charge ratio remainingChargeCapacity/fullChargeCapacity
        # (403/420 = 96%), while the sibling `ibc` read a ceilinged 100. Used
        # directly (no scaling); only the level is surfaced (not voltage/capacity).
        evt["event_name"] = "PumpStatus" if event_id == EVT_STATUS else "Battery"
        evt["battery_percent"] = g("abc")
        # Insulin-on-board remaining duration (hours + minutes). Present on the
        # status event (9) only; the battery-detail events (34/35) carry no IOB,
        # so these read None there (null-not-guess).
        evt["iob_hours"] = g("iobhours")
        evt["iob_minutes"] = g("iobminutes")

    elif event_id in (EVT_ALERT_ACTIVATED, EVT_ALERT_CLEARED):
        # Alert lifecycle (tconnectsync LID_ALERT_ACTIVATED/CLEARED). The
        # coordinator replays activate/clear pairs keyed on evt["alert_id"].
        evt["event_name"] = "AlertActivated" if event_id == EVT_ALERT_ACTIVATED else "AlertCleared"
        evt["alert_id"] = g("alertid")

    elif event_id in (EVT_ALARM_ACTIVATED, EVT_MALFUNCTION_ACTIVATED, EVT_ALARM_CLEARED):
        # Alarm / malfunction lifecycle. The id field name differs per code
        # (alarmId for 5/28, malfId for 6 — tconnectsync events.json); all are
        # stored under evt["alert_id"], the single key the coordinator reads.
        evt["event_name"] = {
            EVT_ALARM_ACTIVATED: "AlarmActivated",
            EVT_MALFUNCTION_ACTIVATED: "MalfunctionActivated",
            EVT_ALARM_CLEARED: "AlarmCleared",
        }[event_id]
        evt["alert_id"] = g("malfid") if event_id == EVT_MALFUNCTION_ACTIVATED else g("alarmid")

    elif event_id in (EVT_CGM_SESSION_START, EVT_CGM_SESSION_JOIN, EVT_CGM_SESSION_STOP):
        # CGM sensor session lifecycle (tconnectsync LID_CGM_{START,JOIN,STOP}_SESSION_GX).
        # Fields (events.json): sessionStartTime / currentTransmitterTime are uint32
        # seconds on the transmitter clock (NOT wall-clock); sessionDuration is a
        # uint8 count of DAYS (10 for a G7 sensor). The coordinator derives the
        # wall-clock start as pumpDateTime - (currentTransmitterTime - sessionStartTime).
        evt["event_name"] = {
            EVT_CGM_SESSION_START: "CGMSessionStart",
            EVT_CGM_SESSION_JOIN: "CGMSessionJoin",
            EVT_CGM_SESSION_STOP: "CGMSessionStop",
        }[event_id]
        evt["current_transmitter_time"] = g("currenttransmittertime")
        evt["session_start_time"] = g("sessionstarttime")
        evt["session_duration_days"] = g("sessionduration")
        evt["session_stop_time"] = g("sessionstoptime")
        # First non-None reason (reason 0 = "User" is falsy — do not use ``or``).
        evt["session_reason"] = next(
            (r for r in (g("sessionstopreason"), g("sessionjoinreason"), g("sessionstartreason")) if r is not None),
            None,
        )

    else:
        return None

    return evt


def _bff_pump_to_legacy(pump: dict[str, Any], pumper: dict[str, Any]) -> dict[str, Any]:
    """Map one BFF ``pumps[]`` entry to the legacy pump-metadata dict shape.

    Preserves the keys the coordinator reads from the old reportsfacade
    ``pumpeventmetadata`` response. ``settings.details`` carries the new
    pump-settings blob (shape differs from the old ``lastUpload.settings``; the
    settings sensors degrade to unavailable rather than fabricate until that
    blob is remapped).
    """
    settings = pump.get("settings") or {}
    settings_details = settings.get("details") if isinstance(settings, dict) else None
    name = pumper.get("name") or " ".join(p for p in (pumper.get("firstName"), pumper.get("lastName")) if p)
    return {
        "tconnectDeviceId": pump.get("assignmentId"),
        "assignmentId": pump.get("assignmentId"),
        "serialNumber": pump.get("serialNumber"),
        "modelNumber": pump.get("modelNumber") or pump.get("modelName"),
        "softwareVersion": pump.get("softwareVersion"),
        "partNumber": pump.get("partNumber"),
        "maxDateWithEvents": pump.get("maxDateOfEvents"),
        "patientName": name or None,
        "lastUpload": {
            "lastUploadedAt": pump.get("lastUploadDate"),
            "settings": settings_details,
        },
        "_bff_pump": pump,
    }


def _select_active_first(legacy_pumps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the pumps ordered with the active (latest-event) pump first.

    Fixes the multi-pump bug (issue #65): Tandem never deletes retired pumps and
    the BFF lists them alongside the active one, so picking ``pumps[0]`` can select
    a years-old pump. Ordering key is ``maxDateWithEvents``; pumps that have never
    uploaded (None) sort last. Mirrors tconnectsync's ChooseDevice.choose().
    """

    def sort_key(p: dict[str, Any]) -> tuple[int, str]:
        max_date = p.get("maxDateWithEvents")
        return (1 if max_date else 0, max_date or "")

    return sorted(legacy_pumps, key=sort_key, reverse=True)


class TandemSourceClient:
    """Async API client for Tandem Diabetes Source platform."""

    LOGIN_PAGE_URL = "https://sso.tandemdiabetes.com/"

    _REGION_URLS = {
        "EU": {
            "LOGIN_API": "https://tdcservices.eu.tandemdiabetes.com/accounts/api/login",
            "AUTHORIZE": "https://tdcservices.eu.tandemdiabetes.com/accounts/api/connect/authorize",
            "TOKEN": "https://tdcservices.eu.tandemdiabetes.com/accounts/api/connect/token",
            "JWKS": "https://tdcservices.eu.tandemdiabetes.com/accounts/api/.well-known/openid-configuration/jwks",
            "ISSUER": "https://tdcservices.eu.tandemdiabetes.com/accounts/api",
            "CLIENT_ID": "1519e414-eeec-492e-8c5e-97bea4815a10",
            "SOURCE_URL": "https://source.eu.tandemdiabetes.com/",
            "REDIRECT_URI": "https://source.eu.tandemdiabetes.com/authorize/callback",
            "TDC_BASE": "https://tdcservices.eu.tandemdiabetes.com/",
        },
        "US": {
            "LOGIN_API": "https://tdcservices.tandemdiabetes.com/accounts/api/login",
            "AUTHORIZE": "https://tdcservices.tandemdiabetes.com/accounts/api/connect/authorize",
            "TOKEN": "https://tdcservices.tandemdiabetes.com/accounts/api/connect/token",
            "JWKS": "https://tdcservices.tandemdiabetes.com/accounts/api/.well-known/openid-configuration/jwks",
            "ISSUER": "https://tdcservices.tandemdiabetes.com/accounts/api",
            "CLIENT_ID": "0oa27ho9tpZE9Arjy4h7",
            "SOURCE_URL": "https://source.tandemdiabetes.com/",
            "REDIRECT_URI": "https://sso.tandemdiabetes.com/auth/callback",
            "TDC_BASE": "https://tdcservices.tandemdiabetes.com/",
        },
    }

    def __init__(
        self,
        email: str,
        password: str,
        region: str = "EU",
        session: httpx.AsyncClient | None = None,
    ):
        self.email = email
        self.password = password
        self.region = region.upper()
        if self.region not in self._REGION_URLS:
            raise ValueError(f"Invalid region '{region}'. Must be 'US' or 'EU'.")
        self.urls = self._REGION_URLS[self.region]

        self.access_token: str | None = None
        self.id_token: str | None = None
        self.pumper_id: str | None = None
        self.account_id: str | None = None
        self.token_expires_at: float = 0

        # When a session is injected (Home Assistant's managed httpx client) we
        # reuse it and never build or close our own — HA owns its lifecycle. Only
        # when constructed standalone (tests, scripts) do we own a self-made client.
        self._client: httpx.AsyncClient | None = session
        self._owns_client: bool = session is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the async HTTP client.

        When Home Assistant's managed client was injected, reuse it verbatim —
        never rebuild or close it. Otherwise lazily build our own, creating the SSL
        context in an executor to avoid blocking the event loop with
        load_verify_locations().
        """
        if not self._owns_client:
            return self._client  # type: ignore[return-value]  # injected, non-None by construction
        if self._client is None or self._client.is_closed:
            loop = asyncio.get_running_loop()

            def _build_ssl_ctx() -> ssl.SSLContext:
                ctx = ssl.create_default_context(cafile=certifi.where())
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                return ctx

            ssl_ctx = await loop.run_in_executor(None, _build_ssl_ctx)
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={"User-Agent": USER_AGENT},
                verify=ssl_ctx,
            )
        return self._client

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a high-entropy PKCE code verifier."""
        return base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8").rstrip("=")

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate S256 code challenge from verifier."""
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def _needs_login(self) -> bool:
        """Return True if authentication is missing or expiring within 5 minutes."""
        return not self.access_token or time.time() >= (self.token_expires_at - 300)

    async def login(self) -> None:
        """Perform OIDC/PKCE authentication.

        Returns on success, raises TandemAuthError on failure.
        """
        if not self._needs_login():
            return

        client = await self._get_client()

        _LOGGER.debug("Tandem: Starting OIDC login for %s region", self.region)

        # Step 1: Initialize session (establish cookies)
        try:
            await client.get(
                self.LOGIN_PAGE_URL,
                headers=self._login_headers(),
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Cannot reach login page: {e}") from e

        # Step 2: POST credentials to login API
        try:
            login_resp = await client.post(
                self.urls["LOGIN_API"],
                json={"username": self.email, "password": self.password},
                headers=self._login_headers({"Referer": self.LOGIN_PAGE_URL}),
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Login request failed: {e}") from e

        if login_resp.status_code != 200:
            raise TandemAuthError(f"Login failed with HTTP {login_resp.status_code}: {login_resp.text[:200]}")

        login_json = login_resp.json()
        if login_json.get("status") != "SUCCESS":
            raise TandemAuthError(f"Login rejected: {login_json.get('message', 'Unknown error')}")

        _LOGGER.debug("Tandem: Login credentials accepted")

        # Step 3: OIDC authorize with PKCE
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)

        auth_params = {
            "client_id": self.urls["CLIENT_ID"],
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": self.urls["REDIRECT_URI"],
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        try:
            # The OAuth authorization code is delivered via a 302 to the
            # redirect_uri (…/callback?code=…). We must follow that redirect to
            # read the code off the final URL. An injected Home Assistant client
            # (get_async_client) defaults to follow_redirects=False, so force it
            # per-request rather than rely on the client's default.
            auth_resp = await client.get(
                self.urls["AUTHORIZE"] + "?" + urlencode(auth_params),
                headers=self._login_headers({"Referer": self.LOGIN_PAGE_URL}),
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Authorization request failed: {e}") from e

        # Extract authorization code from redirect URL
        final_url = str(auth_resp.url)
        parsed = urlparse(final_url)
        query_params = parse_qs(parsed.query)

        if "code" not in query_params:
            raise TandemAuthError(f"No authorization code in redirect URL: {final_url[:200]}")

        auth_code = query_params["code"][0]
        _LOGGER.debug("Tandem: Got authorization code")

        # Step 4: Exchange code for tokens
        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.urls["CLIENT_ID"],
            "code": auth_code,
            "redirect_uri": self.urls["REDIRECT_URI"],
            "code_verifier": code_verifier,
        }

        try:
            token_resp = await client.post(
                self.urls["TOKEN"],
                data=token_data,
                headers=self._login_headers({"Content-Type": "application/x-www-form-urlencoded"}),
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Token exchange failed: {e}") from e

        if token_resp.status_code // 100 != 2:
            raise TandemAuthError(f"Token exchange HTTP {token_resp.status_code}: {token_resp.text[:200]}")

        token_json = token_resp.json()

        if "access_token" not in token_json:
            raise TandemAuthError("Missing access_token in token response")
        if "id_token" not in token_json:
            raise TandemAuthError("Missing id_token in token response")

        self.access_token = token_json["access_token"]
        self.id_token = token_json["id_token"]
        self.token_expires_at = time.time() + token_json.get("expires_in", 3600)

        # Step 5: Decode JWT to get pumperId and accountId
        self._extract_jwt_claims()

        _LOGGER.info(
            "Tandem: Login successful (pumperId=%s, region=%s)",
            self.pumper_id,
            self.region,
        )

    def _extract_jwt_claims(self) -> None:
        """Extract claims from the id_token JWT payload.

        We skip cryptographic verification since we received the token over
        HTTPS directly from the token endpoint.
        """
        if self.id_token is None:
            raise TandemAuthError("No id_token available to decode")
        parts = self.id_token.split(".")
        if len(parts) != 3:
            raise TandemAuthError("Invalid JWT format")

        # Base64url decode the payload (middle part)
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)

        try:
            claims = json.loads(base64.urlsafe_b64decode(payload))
        except ValueError as e:  # json.JSONDecodeError is a subclass of ValueError
            raise TandemAuthError(f"Cannot decode JWT payload: {e}") from e

        self.pumper_id = claims.get("pumperId")
        self.account_id = claims.get("accountId")

        if not self.pumper_id:
            raise TandemAuthError("No pumperId found in JWT claims")

        _LOGGER.debug(
            "Tandem: JWT decoded - pumperId=%s, accountId=%s",
            self.pumper_id,
            self.account_id,
        )

    def _login_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Headers for the unauthenticated OIDC login requests.

        Carries the User-Agent explicitly rather than relying on a client-level
        default, so the login flow behaves identically on Home Assistant's managed
        client (which has no default UA) as on our self-made one.
        """
        headers = {"User-Agent": USER_AGENT}
        if extra:
            headers.update(extra)
        return headers

    def _api_headers(self) -> dict[str, str]:
        """Get headers for authenticated API requests.

        The Tandem Source WAF enforces same-origin on the ``api/reports/bff/*``
        endpoints: ``Origin``/``Referer`` must match SOURCE_URL
        (source.tandemdiabetes.com / source.eu.tandemdiabetes.com) or the
        request is rejected with HTTP 403 ("The request is blocked"). The old
        reportsfacade endpoints did not require this; sending it on every
        request is harmless for endpoints that don't enforce it.
        """
        source_url = self.urls["SOURCE_URL"]
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT,
            "Origin": source_url.rstrip("/"),
            "Referer": source_url,
        }

    async def _api_get(self, url: str, _retries: int = 2) -> Any:
        """Make an authenticated GET request with automatic re-login on 401.

        Retries transient network errors (connection reset, timeout, DNS)
        up to ``_retries`` times with a short back-off.
        """
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(_retries + 1):
            try:
                resp = await client.get(url, headers=self._api_headers(), timeout=REQUEST_TIMEOUT)
                break
            except (
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.PoolTimeout,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
            ) as exc:
                last_exc = exc
                if attempt < _retries:
                    wait = 2 ** (attempt + 1)  # 2s, 4s
                    _LOGGER.debug(
                        "Tandem: transient error on %s (attempt %d/%d), retrying in %ds: %s",
                        url,
                        attempt + 1,
                        _retries + 1,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise TandemApiError(f"API GET {url} failed after {_retries + 1} attempts: {exc}") from last_exc

        if resp.status_code == 401:
            _LOGGER.info("Tandem: Got 401, attempting re-login")
            self.access_token = None
            await self.login()
            if not self.access_token:
                raise TandemAuthError("Re-authentication succeeded but no token obtained")
            resp = await client.get(url, headers=self._api_headers(), timeout=REQUEST_TIMEOUT)

        if resp.status_code != 200:
            raise TandemApiError(f"API GET {url} failed ({resp.status_code}): {resp.text[:300]}")

        return resp.json()

    # ── Tandem Source API endpoints ──────────────────────────────────────

    async def get_pumper_info(self) -> dict[str, Any]:
        """Get user and pump information."""
        return cast(
            "dict[str, Any]", await self._api_get(f"{self.urls['SOURCE_URL']}api/pumpers/pumpers/{self.pumper_id}")
        )

    async def get_pump_event_metadata(self) -> list[dict[str, Any]]:
        """Get pump event metadata (serial, model, last upload, etc.).

        Uses the Tandem Source BFF endpoint ``api/reports/bff/pumper/{pumperId}``
        (the old ``reportsfacade/.../pumpeventmetadata`` path was removed ~June
        2026 and now returns 403/404). The BFF response is
        ``{firstName, lastName, ..., pumps: [...]}``; each pump is mapped back to
        the legacy metadata shape the coordinator expects.

        Returns a list of dicts, one per pump, ordered with the active
        (most-recently-uploaded) pump FIRST so callers that take ``[0]`` select
        the pump actually in use rather than a retired one (issue #65). Each dict
        has: tconnectDeviceId (= BFF assignmentId), serialNumber, modelNumber,
        maxDateWithEvents, lastUpload, patientName, softwareVersion, partNumber.
        """
        response = await self._api_get(f"{self.urls['SOURCE_URL']}api/reports/bff/pumper/{self.pumper_id}")

        pumper = response if isinstance(response, dict) else {}
        raw_pumps = pumper.get("pumps")
        pumps = raw_pumps if isinstance(raw_pumps, list) else []

        legacy_pumps = [_bff_pump_to_legacy(pump, pumper) for pump in pumps]
        return _select_active_first(legacy_pumps)

    # ── ControlIQ API endpoints ──────────────────────────────────────────
    # These use the TDC services base URL and may or may not accept the
    # Tandem Source OIDC access token. Failures are handled gracefully.

    async def get_therapy_timeline(self, start_date: str, end_date: str) -> dict[str, Any] | None:
        """Fetch therapy timeline data (basal, bolus, CGM readings).

        Args:
            start_date: Date in MM-DD-YYYY format
            end_date: Date in MM-DD-YYYY format

        Returns dict with 'basal', 'bolus', 'cgm' keys, or None if unavailable.
        """
        try:
            user_guid = self.account_id or self.pumper_id
            url = (
                f"{self.urls['TDC_BASE']}tconnect/controliq/api/therapytimeline/"
                f"users/{user_guid}?startDate={start_date}&endDate={end_date}"
            )
            return cast("dict[str, Any]", await self._api_get(url))
        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.debug("Therapy timeline not available: %s", e)
            return None

    async def get_dashboard_summary(self, start_date: str, end_date: str) -> dict[str, Any] | None:
        """Fetch dashboard summary statistics.

        Args:
            start_date: Date in MM-DD-YYYY format
            end_date: Date in MM-DD-YYYY format

        Returns dict with averageReading, timeInUsePercent, etc. or None.
        """
        try:
            user_guid = self.account_id or self.pumper_id
            url = (
                f"{self.urls['TDC_BASE']}tconnect/controliq/api/summary/"
                f"users/{user_guid}?startDate={start_date}&endDate={end_date}"
            )
            return cast("dict[str, Any]", await self._api_get(url))
        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.debug("Dashboard summary not available: %s", e)
            return None

    async def get_therapy_events(self, start_date: str, end_date: str) -> dict[str, Any] | None:
        """Fetch therapy events used by the webui Therapy Timeline.

        Args:
            start_date: Date in MM-DD-YYYY format
            end_date: Date in MM-DD-YYYY format
        """
        try:
            user_guid = self.account_id or self.pumper_id
            url = (
                f"{self.urls['TDC_BASE']}tconnect/therapyevents/api/"
                f"TherapyEvents/{start_date}/{end_date}/false?userId={user_guid}"
            )
            _LOGGER.debug("Tandem: Attempting therapy_events API: %s", url)
            result: dict[str, Any] = await self._api_get(url)
            _LOGGER.debug("Tandem: therapy_events returned type=%s", type(result).__name__)
            return result
        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.debug("Therapy events API not available: %s", e)
            return None

    # The BFF pump-logs endpoint caps each request at roughly four weeks, so a
    # longer range must be paged in windows no larger than this.
    _PUMP_LOGS_WINDOW_DAYS = 28

    @staticmethod
    def _pump_log_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
        """Split an inclusive YYYY-MM-DD range into <=28-day (start, end) windows."""
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
        if end < start:
            start, end = end, start

        windows: list[tuple[str, str]] = []
        cur = start
        step = timedelta(days=TandemSourceClient._PUMP_LOGS_WINDOW_DAYS - 1)
        while cur <= end:
            win_end = min(cur + step, end)
            windows.append((cur.isoformat(), win_end.isoformat()))
            cur = win_end + timedelta(days=1)
        return windows

    async def get_pump_events(
        self, device_id: str | int, start_date: str, end_date: str
    ) -> list[dict[str, Any]] | None:
        """Fetch and decode pump events from the Source BFF pump-logs endpoint.

        Uses ``api/reports/bff/pump-logs/{assignmentId}`` (the old base64-binary
        ``reportsfacade/pumpevents`` path was removed ~June 2026). The BFF returns
        pre-decoded JSON (``{events, clockChanges}``) with per-event
        ``eventProperties``; each event is mapped back to the legacy decoded-event
        dict via :func:`map_pump_log_event`, so the coordinator is unchanged.

        The endpoint caps the window at ~4 weeks, so the range is paged in 28-day
        windows and de-duplicated by (sequenceGroup, sequenceNumber).

        Args:
            device_id: assignmentId (UUID) from pump metadata (``tconnectDeviceId``)
            start_date: Date in YYYY-MM-DD format
            end_date: Date in YYYY-MM-DD format

        Returns list of decoded event dicts, or None if unavailable.
        """
        try:
            seen: set[tuple[Any, Any]] = set()
            events: list[dict[str, Any]] = []
            raw_event_count = 0

            for window_start, window_end in self._pump_log_windows(start_date, end_date):
                params = {
                    "pumperId": self.pumper_id,
                    "startDate": f"{window_start}T00:00:00Z",
                    "endDate": f"{window_end}T23:59:59Z",
                }
                url = f"{self.urls['SOURCE_URL']}api/reports/bff/pump-logs/{device_id}?{urlencode(params)}"
                _LOGGER.debug("Tandem: Fetching pump-logs %s → %s", window_start, window_end)

                response = await self._api_get(url)
                if not isinstance(response, dict):
                    _LOGGER.warning("Tandem: Unexpected pump-logs response type: %s", type(response).__name__)
                    continue

                raw_events = response.get("events") or []
                raw_event_count += len(raw_events)
                for raw in raw_events:
                    key = (raw.get("sequenceGroup"), raw.get("sequenceNumber"))
                    if key in seen:
                        continue
                    seen.add(key)
                    mapped = map_pump_log_event(raw)
                    if mapped is not None:
                        events.append(mapped)

            _LOGGER.debug(
                "Tandem: Mapped %d/%d pump-logs events (types we consume)",
                len(events),
                raw_event_count,
            )
            return events if events else None

        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.error("Pump events API failed: %s", e, exc_info=True)
            return None

    # ── Unified data fetch ───────────────────────────────────────────────

    async def get_recent_data(
        self,
        pump_timezone: str | None = None,
        fallback_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch all available recent data from Tandem Source APIs.

        Parallelises independent API calls where possible.

        Args:
            pump_timezone: IANA timezone string (e.g. "Europe/London").
                           Used for the date range so we don't miss recent
                           data when the HA server is in a different zone.
                           Falls back to UTC if not provided.
            fallback_date: ISO date string (e.g. "2026-02-20T21:48:08") of the
                           last known maxDateWithEvents.  When the primary fetch
                           returns no pump_events (pump hasn't synced recently),
                           a second fetch is attempted around this date so the
                           dashboard can show the last-known pump state.

        Returns a unified dict with keys:
            pump_metadata: dict or None
            pumper_info: dict or None
            pump_events: list or None  (from Source Reports API)
            therapy_timeline: dict or None  (from ControlIQ, often unavailable)
            dashboard_summary: dict or None  (from ControlIQ, often unavailable)
        """
        from zoneinfo import ZoneInfo

        try:
            tz = ZoneInfo(pump_timezone) if pump_timezone else ZoneInfo("UTC")
        except (KeyError, TypeError):
            tz = ZoneInfo("UTC")

        now_pump = datetime.now(tz)
        week_ago_pump = now_pump - timedelta(days=7)

        data: dict[str, Any] = {
            "pump_metadata": None,
            "pumper_info": None,
            "pump_events": None,
            "therapy_timeline": None,
            "dashboard_summary": None,
        }

        # ── Phase 1: metadata + pumper_info in parallel ──────────────
        # Pre-declare the unpack targets: mypy cannot infer the tuple element
        # types through asyncio.gather(return_exceptions=True) unpacking.
        metadata_result: dict[str, Any] | None | BaseException
        pumper_result: dict[str, Any] | None | BaseException
        metadata_result, pumper_result = await asyncio.gather(
            self._fetch_pump_metadata(),
            self._fetch_pumper_info(),
            return_exceptions=True,
        )

        if isinstance(metadata_result, BaseException):
            _LOGGER.warning("Failed to fetch pump metadata: %s", metadata_result)
        else:
            data["pump_metadata"] = metadata_result

        if isinstance(pumper_result, BaseException):
            _LOGGER.warning("Failed to fetch pumper info: %s", pumper_result)
        else:
            data["pumper_info"] = pumper_result

        # ── Phase 2: pump_events (needs device_id from metadata) ─────
        device_id = None
        if data["pump_metadata"]:
            device_id = data["pump_metadata"].get("tconnectDeviceId")

        if device_id:
            start_iso = week_ago_pump.strftime("%Y-%m-%d")
            end_iso = now_pump.strftime("%Y-%m-%d")
            try:
                data["pump_events"] = await self.get_pump_events(device_id, start_iso, end_iso)
            except Exception as e:
                _LOGGER.warning("Failed to fetch pump events: %s", e)

            # ── Historical fallback ───────────────────────────────────
            # When the pump hasn't synced recently (e.g. Dexcom sensor
            # expired, Bluetooth gap), the recent date range returns
            # nothing.  Fall back to the last-known event date so the
            # dashboard can show site/cartridge/tubing changes and the
            # last bolus rather than all-unknown.  CGM/IOB sensors will
            # still correctly show as unavailable via staleness detection.
            if not data["pump_events"] and fallback_date:
                try:
                    fallback_dt = datetime.fromisoformat(
                        fallback_date[:10]  # take just YYYY-MM-DD
                    )
                    # Only bother if the fallback date is actually earlier
                    # than the range we already tried.
                    if fallback_dt.strftime("%Y-%m-%d") < start_iso:
                        fb_start = (fallback_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                        fb_end = fallback_dt.strftime("%Y-%m-%d")
                        _LOGGER.info(
                            "Tandem: No recent pump events — fetching last-known "
                            "event range %s to %s for static sensor data",
                            fb_start,
                            fb_end,
                        )
                        data["pump_events"] = await self.get_pump_events(device_id, fb_start, fb_end)
                except Exception as e:
                    _LOGGER.warning("Tandem: Historical event fallback failed: %s", e)
        else:
            _LOGGER.debug("Tandem: No tconnectDeviceId in metadata, skipping pump events")

        # ── Phase 3: ControlIQ fallback (parallel) ───────────────────
        if not data["pump_events"]:
            start_mm = week_ago_pump.strftime("%m-%d-%Y")
            end_mm = now_pump.strftime("%m-%d-%Y")

            _LOGGER.debug(
                "Tandem: No pump_events, trying ControlIQ for %s to %s (tz=%s)",
                start_mm,
                end_mm,
                tz,
            )

            timeline_result: dict[str, Any] | None | BaseException
            summary_result: dict[str, Any] | None | BaseException
            timeline_result, summary_result = await asyncio.gather(
                self.get_therapy_timeline(start_mm, end_mm),
                self.get_dashboard_summary(start_mm, end_mm),
                return_exceptions=True,
            )

            if isinstance(timeline_result, BaseException):
                _LOGGER.debug("Therapy timeline not available: %s", timeline_result)
            else:
                data["therapy_timeline"] = timeline_result

            if isinstance(summary_result, BaseException):
                _LOGGER.debug("Dashboard summary not available: %s", summary_result)
            else:
                data["dashboard_summary"] = summary_result

            if not data["therapy_timeline"]:
                _LOGGER.debug(
                    "Tandem: ControlIQ therapy timeline not available "
                    "(Source OIDC token may not be accepted by ControlIQ API)"
                )

        return data

    async def _fetch_pump_metadata(self) -> dict[str, Any] | None:
        """Fetch and extract first pump metadata entry."""
        metadata_list = await self.get_pump_event_metadata()
        if isinstance(metadata_list, list) and metadata_list:
            return metadata_list[0]
        if isinstance(metadata_list, dict):
            return metadata_list
        return None

    async def _fetch_pumper_info(self) -> dict[str, Any] | None:
        """Fetch pumper info."""
        return await self.get_pumper_info()

    async def close(self) -> None:
        """Close the HTTP client we own.

        A no-op when the client was injected by Home Assistant — closing the
        shared managed client would break every other consumer of it.
        """
        if not self._owns_client:
            return
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


def parse_dotnet_date(date_str: str) -> datetime | None:
    """Parse .NET /Date(epoch_ms)/ or /Date(epoch_ms+offset)/ format.

    Also handles plain ISO 8601 date strings and epoch integers.
    Always returns UTC-aware datetimes so callers can safely use .astimezone().
    """
    if date_str is None:
        return None

    if isinstance(date_str, (int, float)):
        return datetime.fromtimestamp(
            date_str / 1000 if date_str > 1e12 else date_str,
            tz=timezone.utc,
        )

    if isinstance(date_str, str):
        # .NET date format: /Date(1234567890000)/ or /Date(1234567890000+0000)/
        match = re.match(r"/Date\((\d+)([+-]\d+)?\)/", date_str)
        if match:
            epoch_ms = int(match.group(1))
            return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)

        # ISO 8601 format
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            # Convert to UTC and keep timezone-aware
            return dt.astimezone(timezone.utc)
        except (ValueError, AttributeError):
            pass

    return None
