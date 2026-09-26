"""Constants for the Tandem t:slim integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform, UnitOfTime

UNAVAILABLE = None

DOMAIN = "tandem"
ATTRIBUTION = "Data provided by Tandem Source"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Config-entry data keys.
SCAN_INTERVAL = "scan_interval"
CONF_EMAIL = "tandem_email"
CONF_PASSWORD = "tandem_password"
CONF_REGION = "tandem_region"

# Retained for config-entry compatibility with the single Tandem platform.
PLATFORM_TYPE = "platform_type"
PLATFORM_TANDEM = "tandem"

# Fields redacted from diagnostics output (credentials + PII).
TO_REDACT = {
    "tandem_email",
    "tandem_password",
    "email",
    "emailAddress",
    "username",
    "firstName",
    "lastName",
    "name",
    "birthdate",
    "dateOfBirth",
    "patientId",
    "medicalDeviceSerialNumber",
    "deviceSerialNumber",
    "systemId",
    "phone",
    "phoneNumber",
    "address",
}

# ── Device identity keys ────────────────────────────────────────────────
DEVICE_PUMP_SERIAL = "pump serial"
DEVICE_PUMP_NAME = "pump name"
DEVICE_PUMP_MODEL = "pump model"
DEVICE_PUMP_MANUFACTURER = "pump manufacturer"

MMOL = "mmol/L"
MGDL = "mg/dL"
DATETIME = "date/time"
PERCENT = "%"
DURATION_HOUR = UnitOfTime.HOURS
DURATION_MINUTE = UnitOfTime.MINUTES
UNITS = "units"

# ═══════════════════════════════════════════════════════════════════════
# Tandem sensor keys, lookup maps, and staleness threshold
# ═══════════════════════════════════════════════════════════════════════
# ── Tandem t:slim sensor keys ────────────────────────────────────────────

TANDEM_SENSOR_KEY_LASTSG_MMOL = "tandem_last_sg_mmol"
TANDEM_SENSOR_KEY_LASTSG_MGDL = "tandem_last_sg_mgdl"
TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP = "tandem_last_sg_timestamp"
TANDEM_SENSOR_KEY_SG_DELTA = "tandem_last_sg_delta"
TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS = "tandem_last_bolus_units"
TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP = "tandem_last_bolus_timestamp"
TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS = "tandem_last_bolus_attributes"
TANDEM_SENSOR_KEY_BASAL_RATE = "tandem_basal_rate"
TANDEM_SENSOR_KEY_ACTIVE_INSULIN = "tandem_active_insulin"
TANDEM_SENSOR_KEY_LAST_UPLOAD = "tandem_last_upload"
TANDEM_SENSOR_KEY_SOFTWARE_VERSION = "tandem_software_version"
TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO = "tandem_pump_serial_info"
TANDEM_SENSOR_KEY_PUMP_MODEL_INFO = "tandem_pump_model_info"
TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL = "tandem_average_glucose_mmol"
TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL = "tandem_average_glucose_mgdl"
TANDEM_SENSOR_KEY_TIME_IN_RANGE = "tandem_time_in_range"
TANDEM_SENSOR_KEY_CGM_USAGE = "tandem_cgm_usage"
TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS = "tandem_control_iq_status"
TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP = "tandem_last_update_timestamp"
TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS = "tandem_last_meal_bolus"
TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS = "tandem_last_meal_bolus_attributes"

# ── Computed CGM summary keys ──────────────────────────────────────────
TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV = "tandem_glucose_std_dev"
TANDEM_SENSOR_KEY_GLUCOSE_CV = "tandem_glucose_cv"
TANDEM_SENSOR_KEY_GMI = "tandem_gmi"
TANDEM_SENSOR_KEY_TIME_BELOW_RANGE = "tandem_time_below_range"
TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE = "tandem_time_above_range"

# ── New event-derived sensor keys ──────────────────────────────────────
TANDEM_SENSOR_KEY_ACTIVITY_MODE = "tandem_activity_mode"
TANDEM_SENSOR_KEY_CONTROL_IQ_MODE = "tandem_control_iq_mode"
TANDEM_SENSOR_KEY_PUMP_SUSPENDED = "tandem_pump_suspended"
TANDEM_SENSOR_KEY_LAST_CARBS = "tandem_last_carbs"
TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP = "tandem_last_carbs_timestamp"
TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE = "tandem_last_cartridge_change"
TANDEM_SENSOR_KEY_LAST_SITE_CHANGE = "tandem_last_site_change"
TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE = "tandem_last_tubing_change"
TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN = "tandem_cartridge_insulin"
TANDEM_SENSOR_KEY_LAST_BG_READING = "tandem_last_bg_reading"
TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE = "tandem_cgm_rate_of_change"
TANDEM_SENSOR_KEY_CGM_STATUS = "tandem_cgm_status"
TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL = "tandem_last_cartridge_fill_amount"
TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON = "tandem_pump_suspend_reason"

# ── Alerts & Alarms keys (Phase 2 — from events 4, 5, 6, 26, 28) ──────
TANDEM_SENSOR_KEY_LAST_ALERT = "tandem_last_alert"
TANDEM_SENSOR_KEY_LAST_ALARM = "tandem_last_alarm"
TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT = "tandem_active_alerts_count"

# ── CGM sensor type key (Phase 3 — from event 313) ────────────────────
TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE = "tandem_cgm_sensor_type"

# ── CGM sensor session keys (Phase 7 — from events 212, 213, 214) ─────
TANDEM_SENSOR_KEY_CGM_SESSION_START = "tandem_cgm_session_start"
TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY = "tandem_cgm_session_expiry"
TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING = "tandem_cgm_sensor_days_remaining"

# ── Bolus Calculator keys (Phase 4 — from events 64, 65, 66) ─────────
TANDEM_SENSOR_KEY_LAST_BOLUS_BG = "tandem_last_bolus_bg"
TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS = "tandem_last_bolus_carbs_entered"
TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION = "tandem_last_bolus_correction"
TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD = "tandem_last_bolus_food_portion"
TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS = "tandem_last_bolus_bg_attributes"

# ── PLGS & Daily Status keys (Phase 5 — from events 140, 90) ──────────
TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE = "tandem_predicted_glucose"

# ── Estimated Remaining Insulin key (Phase 6 — computed) ──────────────
TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING = "tandem_estimated_insulin_remaining"

# ── Battery monitoring key (Phase 1 — from events 9, 34, 35) ────
TANDEM_SENSOR_KEY_BATTERY_PERCENT = "tandem_battery_percent"

# ── Cheap-win keys (one-line reads of fields already on existing events) ──
# CGM transmitter signal strength (event 256 / 399, field `rssi`).
TANDEM_SENSOR_KEY_RSSI = "tandem_rssi"
# Insulin-on-board duration (event 9 status, fields `iobHours` / `iobMinutes`).
TANDEM_SENSOR_KEY_IOB_HOURS = "tandem_iob_hours"
TANDEM_SENSOR_KEY_IOB_MINUTES = "tandem_iob_minutes"
# Control-IQ closed-loop-preferred setting (event 230 PCM, field `closedLoopPreferred`).
TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED = "tandem_closed_loop_preferred"

# ── Lookup maps for event-derived sensor values ───────────────────────
CGM_STATUS_MAP: dict[int, str] = {0: "Normal", 1: "High", 2: "Low"}

# glucoseValueStatus codes (from CGM_STATUS_MAP) used to gate the numeric reading.
CGM_STATUS_HIGH = 1
CGM_STATUS_LOW = 2

# Dexcom G6/G7 reportable range (mg/dL). Above/below this the sensor reports HIGH/LOW
# rather than a number, and the BFF's ``currentGlucoseDisplayValue`` then carries an
# out-of-range placeholder that differs by sensor: G6 sends a ~0 sentinel, but G7 (event
# 399) sends a LARGE raw estimate (observed 400–1200 mg/dL when glucoseValueStatus=High).
# When the status is High/Low we clamp the reading to these bounds so a fabricated extreme
# is never surfaced as a decision-input (see ADR-008 fail-visible / null-not-guess).
# Confirmed 2026-09-08 via live event-399 probe (G7 High → 33–66 mmol/L before the clamp).
CGM_GLUCOSE_MGDL_MAX = 400
CGM_GLUCOSE_MGDL_MIN = 40

# CGM session start/join/stop reason → name (tconnectsync DexblesReason enum).
# Only the confirmed members are listed; others fall back to "Reason {id}".
CGM_SESSION_REASON_MAP: dict[int, str] = {
    0: "User",
    1: "Unknown",
    3: "Transmitter End of Life",
    4: "Transmitter Error",
    5: "Session Stop Success",
}

# Alert and alarm ID → human-readable name maps.
# Sourced from tconnectsync static_dicts.py (jwoglom/tconnectsync).
TANDEM_ALERT_MAP: dict[int, str] = {
    0: "Low Insulin",
    1: "USB Connection",
    2: "Low Power",
    3: "Low Power (Critical)",
    5: "Auto Off",
    7: "Power Source",
    11: "Incomplete Bolus",
    12: "Incomplete Temp Rate",
    13: "Incomplete Cartridge Change",
    17: "Low Insulin (2nd)",
    19: "Low Transmitter",
    22: "Sensor Expiring",
    23: "Sensor Expired",
    24: "Sensor Failed",
    25: "Sensor Warmup",
    26: "Sensor Out Of Range",
    27: "Sensor High",
    28: "Sensor Low",
    29: "CGM Calibration",
    30: "CGM Cal Due",
    31: "CGM Cal Error",
    32: "CGM Trend",
    33: "CGM Rise",
    34: "CGM Fall",
    36: "Sensor Change",
    38: "Transmitter Low Battery",
    39: "Transmitter End of Life",
    40: "Pump Bluetooth Error",
    42: "CGM High Alert",
    43: "CGM Low Alert",
    44: "CGM Urgent Low Alert",
    45: "CGM Very High Alert",
    46: "Predicted High Alert",
    47: "Predicted Low Alert",
    48: "CGM Unavailable",
    50: "Feature Activation",
    52: "Suspend Before Low",
    53: "Suspend On Low",
    54: "Resume From Suspend",
}

TANDEM_ALARM_MAP: dict[int, str] = {
    0: "Cartridge Alarm",
    2: "Occlusion",
    3: "Pump Reset",
    4: "Motor Error",
    5: "Infusion Complete",
    6: "Basal Rate Not Set",
    7: "Auto Off",
    8: "Empty Cartridge",
    9: "Delivery Error",
    10: "Temperature",
    11: "Hardware Error",
    12: "Battery Shutdown",
    13: "Low Battery",
    14: "Software Error",
    15: "Memory Error",
    16: "Clock Error",
    17: "Calibration Error",
    18: "Resume Pump",
    19: "Cartridge Error",
    20: "Pressure Error",
    21: "Altitude",
    22: "Insulin Expired",
    23: "Max Daily Insulin",
    24: "Max Bolus",
    25: "Cartridge Removed",
    26: "Priming Error",
    27: "Plunger Error",
    28: "Fill Timeout",
}

# ── Shared icon strings (S1192: avoid duplicating literals 3+ times) ──
ICON_ALERT_CIRCLE_OUTLINE = "mdi:alert-circle-outline"

# ── Computed insulin summary keys ──────────────────────────────────────
TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN = "tandem_total_daily_insulin"
TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL = "tandem_daily_bolus_total"
TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL = "tandem_daily_basal_total"
TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT = "tandem_basal_bolus_split"
TANDEM_SENSOR_KEY_DAILY_CARBS = "tandem_daily_carbs"
TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT = "tandem_daily_bolus_count"

# ── Pump settings keys (from metadata.lastUpload.settings) ───────────────
TANDEM_SENSOR_KEY_ACTIVE_PROFILE = "tandem_active_profile"
TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS = "tandem_active_profile_attributes"
TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED = "tandem_control_iq_enabled"
TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT = "tandem_control_iq_weight"
TANDEM_SENSOR_KEY_CONTROL_IQ_TDI = "tandem_control_iq_tdi"
TANDEM_SENSOR_KEY_MAX_BOLUS = "tandem_max_bolus"
TANDEM_SENSOR_KEY_BASAL_LIMIT = "tandem_basal_limit"
TANDEM_SENSOR_KEY_CGM_HIGH_ALERT = "tandem_cgm_high_alert"
TANDEM_SENSOR_KEY_CGM_LOW_ALERT = "tandem_cgm_low_alert"
TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD = "tandem_low_bg_threshold"
TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD = "tandem_high_bg_threshold"
TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT = "tandem_low_insulin_alert"

# ── Staleness detection (Issue #11) ─────────────────────────────────────
# Tandem Reports API is historical — pump uploads periodically, not in real-time.
# When data is older than this threshold, sensors are marked unavailable so HA
# stops recording stale values (which would create misleading flat lines in graphs).
# 6 hours: covers real-world gaps (exercise, phone away, brief BT drops)
# while still catching genuine sync failures within a reasonable window.
TANDEM_DATA_STALE_MINUTES = 360
TANDEM_DATA_STALE_TIMEDELTA = timedelta(minutes=TANDEM_DATA_STALE_MINUTES)
