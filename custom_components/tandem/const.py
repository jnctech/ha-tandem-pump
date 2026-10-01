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

# ── CGM sensor session keys (Phase 7 — G6 212/213/214, G7 394/447) ────
TANDEM_SENSOR_KEY_CGM_SESSION_START = "tandem_cgm_session_start"
TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY = "tandem_cgm_session_expiry"
TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING = "tandem_cgm_sensor_days_remaining"

# ── CGM alerts + sensor lifecycle keys (from events 171/172, 369/370/371, 214/447, 399) ─
# CGM alerts ("Failed Sensor", "Sensor Expired", "Out Of Range", …) are logged by the
# pump as their own event family, separate from pump alerts (4/26).
TANDEM_SENSOR_KEY_LAST_CGM_ALERT = "tandem_last_cgm_alert"
# G7 sensor algorithm state from the latest event 399 (Warmup / In session …). Note the
# pump keeps logging "In Session" right up to a failure; the "Failed Sensor" cause is
# carried on the CGM Sensor Failed alert (369, param1), not on the data stream.
TANDEM_SENSOR_KEY_CGM_SENSOR_STATE = "tandem_cgm_sensor_state"
# Wall-clock time of the most recent CGM session stop (214 / 447), with the stop
# reason and the wear duration of the sensor that ended.
TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END = "tandem_last_cgm_session_end"

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

# CGM session start/join/stop reason → name (tconnectsync events.json DEXBLES_REASON_*
# enum on events 213/214). Reserved members (2, 7) fall back to "Reason {id}".
CGM_SESSION_REASON_MAP: dict[int, str] = {
    0: "User",
    1: "Unknown",
    3: "Transmitter End of Life",
    4: "Transmitter Error",
    5: "Session Stop Success",
    6: "Transmitter Not In Session",
    8: "New Session Started",
    9: "Session Start In Progress",
    10: "Transmitter In Session",
    11: "BLE Stack Invalid",
    12: "New Autocal Session Started",
    13: "No Autocal Session In Progress",
}

# CGM sensor algorithm state (``algorithmState`` on the CGM data event) → name.
# The enum is sensor-specific (tconnectsync events.json): G7 (399) and Libre 2 (372)
# define one; G6 (256) does not, so it is not decoded (null-not-guess). The G7
# "Session Stopped (…)" members are the pump-side cause of a sensor ending — 35 is
# what Tandem Source shows as "Failed Sensor".
CGM_ALGORITHM_STATE_MAP_G7: dict[int, str] = {
    2: "Warmup",
    30: "Electronics Wakeup",
    31: "Detecting Deployment",
    32: "In Session",
    33: "In Session (Invalid Reading)",
    34: "Session Stopped (End of Session)",
    35: "Session Stopped (Sensor Failed)",
    36: "Session Stopped (Manual Stop)",
    37: "Session Stopped (Transmitter Failure)",
    38: "Session Stopped (SIV Failure)",
    39: "Session Stopped (Out of Range / Environmental)",
}
CGM_ALGORITHM_STATE_MAP_FSL2: dict[int, str] = {
    2: "Warmup",
    100: "OK",
    101: "RF Error",
    102: "Sensor Signal Low",
    103: "Temperature High",
    104: "Temperature Low",
    105: "Invalid Data",
    106: "Other",
}
# Dexcom replaces a sensor that fails before this many days of wear, whatever its
# rated life (a 15-day G7 is still only covered below 10 days).
DEXCOM_REPLACEMENT_THRESHOLD_DAYS = 10
# Post-expiry grace window during which the sensor keeps reading, by sensor model.
# G7 has 12 h; G6 has none. The rated life comes from the session event
# (``sessionDuration``) where one carries it: the G6 start/join (212/213) and the G7
# stop (447). The G7 join (394) has no duration, so an active G7 session uses the
# latest G7 stop's duration, else the standard 10-day G7 rating.
CGM_GRACE_PERIOD_HOURS: dict[str, int] = {"G6": 0, "G7": 12}
CGM_G7_DEFAULT_SESSION_DAYS = 10

# The G6 transmitter is separate from the 10-day sensor and moves to each new sensor;
# it is rated (and warrantied) for 3 months. Its session-event clock counts from
# transmitter activation, so its age is known from any G6 session event. The G7 is
# an integrated sensor-transmitter, so this does not apply to it.
CGM_G6_TRANSMITTER_LIFE_DAYS = 90

# CGM alert ids (``dalertId``) that announce a sensor session ending, used to name the
# cause of a session stop: 11 Sensor Failed, 13 Sensor Expired, 20 Transmitter Error,
# 25 Replace Sensor, 39 Transmitter Expired.
CGM_SESSION_END_ALERT_IDS = frozenset({11, 13, 20, 25, 39})
CGM_ALERT_SENSOR_FAILED = 11

# G7 algorithm states that mean the sensor session has ended.
CGM_ALGORITHM_STATES_SESSION_STOPPED_G7 = frozenset(range(34, 40))

# CGM alert ID (``dalertId`` on events 171/172 and 369/370/371) → name.
# Sourced from tconnectsync static_dicts.CGM_ALERTS_DICT ("verified from pump display")
# and filled in from pumpX2 CGMAlertStatusResponse.CGMAlert. Unlisted IDs fall back
# to "CGM Alert {id}" — the raw id is always exposed in the attributes.
TANDEM_CGM_ALERT_MAP: dict[int, str] = {
    1: "CGM Urgent Low",
    2: "CGM High",
    3: "CGM Low",
    4: "CGM Calibration Request",
    5: "CGM Rise",
    6: "CGM Rapid Rise",
    7: "CGM Fall",
    8: "CGM Rapid Fall",
    9: "CGM Low Calibration Error",
    10: "CGM High Calibration Error",
    11: "CGM Sensor Failed",
    12: "CGM Sensor Expiring Soon",
    13: "CGM Sensor Expired",
    14: "CGM Out Of Range",
    16: "CGM First Start Calibration",
    17: "CGM Second Start Calibration",
    18: "CGM Calibration Required",
    19: "CGM Low Transmitter",
    20: "CGM Transmitter Error",
    22: "CGM Sensor Expiring",
    25: "CGM Replace Sensor",
    26: "CGM Temperature",
    27: "CGM Failed Connection",
    39: "CGM Transmitter Expired",
    40: "Pump Bluetooth Error",
    45: "CGM Transmitter Expiring Soon",
    46: "CGM Transmitter Expiring",
    48: "CGM Unavailable",
}

# CGM sensor type on the Dex CGM alert events (369/370/371, field ``sensorType``).
CGM_ALERT_SENSOR_TYPE_MAP: dict[int, str] = {1: "G6", 3: "G7"}

# Pump alert and alarm ID → human-readable name maps (events 4/26 and 5/6/28).
# Sourced from tconnectsync static_dicts.ALERTS_DICT / ALARMS_DICT (jwoglom/tconnectsync),
# which match pumpX2's AlertStatusResponse enum. IDs upstream only names DEFAULT_* are
# omitted so they surface as "Alert {id}" / "Alarm {id}" rather than a guessed name.
# NOTE: CGM alerts ("Sensor Failed", "Sensor Expired", …) are NOT in this family —
# they have their own events and IDs; see TANDEM_CGM_ALERT_MAP.
TANDEM_ALERT_MAP: dict[int, str] = {
    0: "Low Insulin",
    1: "USB Connection",
    2: "Low Power",
    3: "Low Power (Critical)",
    4: "Data Error",
    5: "Auto Off",
    6: "Max Basal Rate",
    7: "Power Source",
    8: "Min Basal",
    9: "Connection Error",
    10: "Connection Error (2)",
    11: "Incomplete Bolus",
    12: "Incomplete Temp Rate",
    13: "Incomplete Cartridge Change",
    14: "Incomplete Fill Tubing",
    15: "Incomplete Fill Cannula",
    16: "Incomplete Setting",
    17: "Low Insulin (2nd)",
    18: "Max Basal",
    19: "Low Transmitter",
    20: "Transmitter",
    22: "Sensor Expiring",
    23: "Pump Rebooting",
    24: "Device Connection Error",
    25: "CGM Graph Removed",
    26: "Min Basal (2)",
    27: "Incomplete Calibration",
    28: "Calibration Timeout",
    29: "Invalid Transmitter ID",
    33: "Button",
    34: "Quick Bolus",
    35: "Basal-IQ",
    39: "Transmitter End of Life",
    40: "CGM Error",
    41: "CGM Error (2)",
    42: "CGM Error (3)",
    44: "Transmitter Expiring",
    45: "Transmitter Expiring (2)",
    46: "Transmitter Expiring (3)",
    48: "CGM Unavailable",
    51: "Control-IQ Low",
    54: "Device Paired",
}

TANDEM_ALARM_MAP: dict[int, str] = {
    0: "Cartridge Alarm",
    1: "Cartridge Alarm (2)",
    2: "Occlusion",
    3: "Pump Reset",
    5: "Cartridge Alarm (3)",
    6: "Cartridge Alarm (4)",
    7: "Auto Off",
    8: "Empty Cartridge",
    9: "Cartridge Alarm (5)",
    10: "Temperature",
    11: "Temperature (2)",
    12: "Battery Shutdown",
    14: "Invalid Date",
    15: "Temperature (3)",
    16: "Cartridge Alarm (6)",
    18: "Resume Pump",
    20: "Cartridge Alarm (7)",
    21: "Altitude",
    22: "Stuck Button",
    23: "Resume Pump (2)",
    24: "Atmospheric Pressure Out Of Range",
    25: "Cartridge Removed",
    26: "Occlusion (2)",
    29: "Cartridge Alarm (10)",
    30: "Cartridge Alarm (11)",
    31: "Cartridge Alarm (12)",
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
