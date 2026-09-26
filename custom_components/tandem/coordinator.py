"""Tandem t:slim Source data update coordinator.

Fetches pump events from the Tandem Source Reports API, replays intermediate
events (CGM, bolus, basal) through the coordinator so HA's recorder captures
the full history between polls, and imports correctly-timestamped long-term
statistics. Moved verbatim from the pre-refactor __init__.py (research preserved).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .helpers import is_data_stale
from .util import sanitize_for_logging
from .const import TANDEM_SENSOR_KEY_TIME_IN_RANGE as TANDEM_TIME_IN_RANGE
from .tandem_api import (
    EVT_AA_DAILY_STATUS,
    EVT_AA_PCM_CHANGE,
    EVT_AA_USER_MODE_CHANGE,
    EVT_ALARM_ACTIVATED,
    EVT_ALARM_CLEARED,
    EVT_ALERT_ACTIVATED,
    EVT_ALERT_CLEARED,
    EVT_BASAL_DELIVERY,
    EVT_BASAL_RATE_CHANGE,
    EVT_BATTERY_1,
    EVT_BATTERY_2,
    EVT_BG_READING_TAKEN,
    EVT_BOLEX_COMPLETED,
    EVT_BOLUS_COMPLETED,
    EVT_BOLUS_DELIVERY,
    EVT_BOLUS_REQUESTED_MSG1,
    EVT_BOLUS_REQUESTED_MSG2,
    EVT_BOLUS_REQUESTED_MSG3,
    EVT_CANNULA_FILLED,
    EVT_CARBS_ENTERED,
    EVT_CARTRIDGE_FILLED,
    EVT_CGM_DATA_FSL2,
    EVT_CGM_DATA_G7,
    EVT_CGM_DATA_GXB,
    EVT_CGM_SESSION_JOIN,
    EVT_CGM_SESSION_START,
    EVT_CGM_SESSION_STOP,
    EVT_DAILY_BASAL,
    EVT_MALFUNCTION_ACTIVATED,
    EVT_NEW_DAY,
    EVT_PLGS_PERIODIC,
    EVT_PUMPING_RESUMED,
    EVT_PUMPING_SUSPENDED,
    EVT_SHELF_MODE,
    EVT_STATUS,
    EVT_TUBING_FILLED,
    TandemSourceClient,
    parse_dotnet_date,
)
from .exceptions import TandemApiError, TandemAuthError
from .const import (
    CGM_SESSION_REASON_MAP,
    CGM_GLUCOSE_MGDL_MAX,
    CGM_GLUCOSE_MGDL_MIN,
    CGM_STATUS_HIGH,
    CGM_STATUS_LOW,
    CGM_STATUS_MAP,
    DEVICE_PUMP_MANUFACTURER,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DOMAIN,
    TANDEM_ALARM_MAP,
    TANDEM_ALERT_MAP,
    TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT,
    TANDEM_SENSOR_KEY_ACTIVE_INSULIN,
    TANDEM_SENSOR_KEY_ACTIVE_PROFILE,
    TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS,
    TANDEM_SENSOR_KEY_ACTIVITY_MODE,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
    TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT,
    TANDEM_SENSOR_KEY_BASAL_LIMIT,
    TANDEM_SENSOR_KEY_BASAL_RATE,
    TANDEM_SENSOR_KEY_BATTERY_PERCENT,
    TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS,
    TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN,
    TANDEM_SENSOR_KEY_CGM_HIGH_ALERT,
    TANDEM_SENSOR_KEY_CGM_LOW_ALERT,
    TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE,
    TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING,
    TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE,
    TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY,
    TANDEM_SENSOR_KEY_CGM_SESSION_START,
    TANDEM_SENSOR_KEY_CGM_STATUS,
    TANDEM_SENSOR_KEY_CGM_USAGE,
    TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED,
    TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED,
    TANDEM_SENSOR_KEY_CONTROL_IQ_MODE,
    TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS,
    TANDEM_SENSOR_KEY_CONTROL_IQ_TDI,
    TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT,
    TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL,
    TANDEM_SENSOR_KEY_DAILY_CARBS,
    TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING,
    TANDEM_SENSOR_KEY_GLUCOSE_CV,
    TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV,
    TANDEM_SENSOR_KEY_GMI,
    TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD,
    TANDEM_SENSOR_KEY_IOB_HOURS,
    TANDEM_SENSOR_KEY_IOB_MINUTES,
    TANDEM_SENSOR_KEY_LASTSG_MGDL,
    TANDEM_SENSOR_KEY_LASTSG_MMOL,
    TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_ALARM,
    TANDEM_SENSOR_KEY_LAST_ALERT,
    TANDEM_SENSOR_KEY_LAST_BG_READING,
    TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS,
    TANDEM_SENSOR_KEY_LAST_BOLUS_BG,
    TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS,
    TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION,
    TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD,
    TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS,
    TANDEM_SENSOR_KEY_LAST_CARBS,
    TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE,
    TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS,
    TANDEM_SENSOR_KEY_LAST_SITE_CHANGE,
    TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE,
    TANDEM_SENSOR_KEY_LAST_UPLOAD,
    TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD,
    TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT,
    TANDEM_SENSOR_KEY_MAX_BOLUS,
    TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE,
    TANDEM_SENSOR_KEY_PUMP_MODEL_INFO,
    TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO,
    TANDEM_SENSOR_KEY_PUMP_SUSPENDED,
    TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON,
    TANDEM_SENSOR_KEY_RSSI,
    TANDEM_SENSOR_KEY_SG_DELTA,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
    TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE,
    TANDEM_SENSOR_KEY_TIME_BELOW_RANGE,
    TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN,
    TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP,
    UNAVAILABLE,
)

_LOGGER = logging.getLogger(__name__)

_CGM_SESSION_TIME_SENTINEL = 0xFFFFFFFF  # uint32 max — "no valid time" marker


def _valid_session_seconds(value: Any) -> bool:
    """True when a CGM-session transmitter-clock field holds a real second count.

    Stop events (214) and absent fields use the uint32 sentinel 0xFFFFFFFF (or
    None), which must not be treated as a real transmitter time.
    """
    return isinstance(value, (int, float)) and 0 <= value < _CGM_SESSION_TIME_SENTINEL


def _clamp_cgm_over_range(evt: dict[str, Any]) -> None:
    """Clamp an out-of-range CGM reading to the sensor's reportable bound, in place.

    When the CGM reports High/Low (``glucoseValueStatus`` 1/2) the numeric
    ``currentGlucoseDisplayValue`` is not a valid display reading: G7 (event 399)
    sends a large raw estimate (observed 400–1200 mg/dL at status=High), while G6
    (event 256) sends a ~0 sentinel. The physical sensor pegs at its reportable
    bound and shows HIGH/LOW, so we clamp ``glucose_mgdl`` to that bound instead of
    surfacing a fabricated extreme as a decision-input (ADR-008 fail-visible /
    null-not-guess). Confirmed 2026-09-08 via a live event-399 probe.

    Applied at the single point every CGM event enters the pipeline, so ALL
    consumers see the bounded value — the latest-glucose sensor, ``_compute_cgm_summary``
    (avg/TIR/GMI/SD), the history attributes, and the LTS statistics import (a
    separate task that reads these same in-place-mutated event dicts). A future
    refactor that deep-copies events before the import would need to clamp there too.

    Trade-off: the summary stats then cannot tell a pegged bound from a genuine
    reading at that bound (mirrors the physical sensor); an over-range counter could
    restore that distinction — see ISS-260908.

    Fail-visible: every clamp is logged with the raw value. A raw value OUTSIDE the
    expected over-range signature (High → large, Low → ~0), or an out-of-band
    magnitude carrying no High/Low status at all, is logged at WARNING — that is the
    signature of a decode fault rather than a legitimately pegged sensor, and is the
    case most worth surfacing. ``CGM_GLUCOSE_MGDL_MAX`` is the Dexcom G6/G7 ceiling; a
    FreeStyle Libre (event 372) ceiling differs, but any clamp still beats a raw extreme.
    """
    raw = evt.get("glucose_mgdl")
    try:
        status = int(evt["status"]) if evt.get("status") is not None else None
    except (TypeError, ValueError):
        status = None

    clamped: int | None = None
    expected = False
    if status == CGM_STATUS_HIGH:
        clamped = CGM_GLUCOSE_MGDL_MAX
        expected = isinstance(raw, (int, float)) and raw >= CGM_GLUCOSE_MGDL_MAX
    elif status == CGM_STATUS_LOW:
        clamped = CGM_GLUCOSE_MGDL_MIN
        expected = isinstance(raw, (int, float)) and 0 <= raw <= CGM_GLUCOSE_MGDL_MIN
    elif isinstance(raw, (int, float)) and raw > CGM_GLUCOSE_MGDL_MAX:
        # Out-of-band magnitude with no High status: missing/malformed status or a
        # decode fault. Never surface it raw; clamp defensively and warn.
        clamped = CGM_GLUCOSE_MGDL_MAX

    if clamped is None or clamped == raw:
        return
    log = _LOGGER.debug if expected else _LOGGER.warning
    log("Tandem: CGM over-range clamp (status=%r raw=%r -> %s mg/dL)", evt.get("status"), raw, clamped)
    evt["glucose_mgdl"] = clamped


@dataclass
class TandemRuntimeData:
    """Per-entry runtime data for the Tandem integration.

    Stored on ``entry.runtime_data`` (the HA-recommended replacement for
    ``hass.data[DOMAIN][entry_id]`` — the quality-scale ``runtime-data`` rule).
    Holds the Source API client and the live coordinator so platforms,
    services, and diagnostics resolve them from the loaded entry.
    """

    client: TandemSourceClient
    coordinator: TandemCoordinator


# Typed config entry whose runtime_data is the TandemRuntimeData above.
type TandemConfigEntry = ConfigEntry[TandemRuntimeData]


class TandemCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tandem Source API.

    Fetches pump events from the Tandem Source Reports API and replays
    ALL intermediate events (CGM, bolus, basal) through the coordinator
    so HA's recorder captures the full history between polls. Also imports
    correctly-timestamped long-term statistics for Statistics Graph cards.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TandemSourceClient,
        update_interval: timedelta,
    ):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval, config_entry=entry)

        self.entry_id = entry.entry_id
        self.configuration_url = "https://source.tandemdiabetes.com"
        self.client = client
        self.timezone = hass.config.time_zone
        self._prev_sg_mgdl: float | None = None

        # Historical data tracking
        self._last_max_date: str | None = None  # maxDateWithEvents from metadata
        self._last_event_seq: int = 0  # Last processed event sequence number

        # Phase 6: Estimated Remaining Insulin — cumulative tracking.
        # Accumulates delivered insulin incrementally using seq numbers to
        # avoid double-counting. Persists across polls so we can compute
        # remaining even when events age out of the 14-day API window.
        # State is lost on HA restart — sensor shows UNAVAILABLE until
        # a new cartridge fill event appears in the window.
        self._last_cartridge_fill_seq: int = 0
        self._last_cartridge_fill_volume: float = 0.0
        self._cumulative_delivered: float = 0.0
        self._last_delivery_seq: int = 0

    async def _async_update_data(self) -> dict[str, Any]:
        _LOGGER.debug("TandemCoordinator: Starting _async_update_data")
        data: dict[str, Any] = {}

        try:
            await self.client.login()
        except TandemAuthError as err:
            raise ConfigEntryAuthFailed(f"Tandem authentication failed: {err}") from err
        except Exception as err:
            _LOGGER.debug("Unexpected error during Tandem login: %s", err, exc_info=True)
            raise UpdateFailed(f"Tandem login error: {err}") from err

        # ── Lightweight metadata check: skip heavy API call if no new data ──
        # The pumpevents endpoint is expensive. Check maxDateWithEvents first
        # and skip the full fetch if nothing has changed since last poll.
        try:
            metadata_list = await self.client.get_pump_event_metadata()
            metadata_entry = None
            if isinstance(metadata_list, list) and metadata_list:
                metadata_entry = metadata_list[0]
            elif isinstance(metadata_list, dict):
                metadata_entry = metadata_list

            max_date_str = metadata_entry.get("maxDateWithEvents") if metadata_entry else None
        except Exception as err:
            _LOGGER.debug("Tandem: Metadata check failed (%s), proceeding with full fetch", err)
            max_date_str = None
            metadata_entry = None

        if max_date_str and self._last_max_date and max_date_str == self._last_max_date and self.data:
            _LOGGER.debug(
                "[Tandem] Poll: no new pump data (maxDate=%s, serving %d cached keys)",
                max_date_str,
                len(self.data),
            )
            return self.data

        _LOGGER.info(
            "[Tandem] New pump data: maxDate %s → %s — fetching events",
            self._last_max_date or "(first poll)",
            max_date_str,
        )

        try:
            recent_data = await self.client.get_recent_data(
                pump_timezone=self.timezone,
                fallback_date=max_date_str,
            )
        except TandemApiError as err:
            raise UpdateFailed(f"Tandem API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Tandem data fetch error: {err}") from err

        if not isinstance(recent_data, dict):
            raise UpdateFailed(f"get_recent_data() returned {type(recent_data)}, expected dict")

        # Save maxDateWithEvents for next poll comparison
        if max_date_str:
            self._last_max_date = max_date_str

        _LOGGER.debug("Tandem before data parsing: %s", sanitize_for_logging(recent_data))

        # Log what data sources are available
        _LOGGER.info(
            "[Tandem] Fetch OK — metadata=%s  pumper=%s  pump_events=%s  therapy=%s  dashboard=%s",
            "OK" if recent_data.get("pump_metadata") else "MISSING",
            "OK" if recent_data.get("pumper_info") else "MISSING",
            "OK" if recent_data.get("pump_events") else "MISSING",
            "OK" if recent_data.get("therapy_timeline") else "MISSING",
            "OK" if recent_data.get("dashboard_summary") else "MISSING",
        )

        # ── Device info from pump metadata ───────────────────────────────
        metadata = recent_data.get("pump_metadata")

        if metadata:
            _LOGGER.debug("Tandem metadata keys: %s", list(metadata.keys()))
            _LOGGER.debug(
                "Tandem metadata values: serialNumber=%s, modelNumber=%s, softwareVersion=%s, partNumber=%s",
                metadata.get("serialNumber"),
                metadata.get("modelNumber"),
                metadata.get("softwareVersion"),
                metadata.get("partNumber"),
            )
            data[DEVICE_PUMP_SERIAL] = metadata.get("serialNumber", "unknown")
            data[DEVICE_PUMP_MODEL] = metadata.get("modelNumber", "t:slim X2")
            data[DEVICE_PUMP_NAME] = metadata.get("patientName", "Tandem Pump")
            data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] = metadata.get("serialNumber")
            data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] = metadata.get("modelNumber")
            sw_version = metadata.get("softwareVersion")
            if not sw_version:
                _LOGGER.debug(
                    "Tandem softwareVersion not in metadata (keys: %s), trying partNumber as fallback",
                    list(metadata.keys()),
                )
                sw_version = metadata.get("partNumber")
            data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] = sw_version or UNAVAILABLE

            # Parse last upload timestamp
            # lastUpload is a dict {uploadId, lastUploadedAt, settings}, not a string
            last_upload_obj = metadata.get("lastUpload")
            last_uploaded_at = None
            if isinstance(last_upload_obj, dict):
                last_uploaded_at = last_upload_obj.get("lastUploadedAt")
            elif isinstance(last_upload_obj, str):
                # Backwards compat: some test fixtures use a bare date string
                last_uploaded_at = last_upload_obj

            if last_uploaded_at:
                upload_dt = parse_dotnet_date(last_uploaded_at)
                if upload_dt:
                    upload_aware = upload_dt.astimezone(ZoneInfo(self.timezone))
                    data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = upload_aware
                    data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = upload_aware
                else:
                    data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE

            # Parse pump settings from lastUpload.settings
            self._parse_pump_settings(last_upload_obj, data)
        else:
            data[DEVICE_PUMP_SERIAL] = "unknown"
            data[DEVICE_PUMP_MODEL] = "t:slim X2"
            data[DEVICE_PUMP_NAME] = "Tandem Pump"
            data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE
            self._parse_pump_settings(None, data)

        data[DEVICE_PUMP_MANUFACTURER] = "Tandem Diabetes Care"

        # ── Therapy data (CGM, bolus, basal) ─────────────────────────────
        pump_events = recent_data.get("pump_events")
        timeline = recent_data.get("therapy_timeline")

        try:
            if pump_events:
                _LOGGER.debug("TandemCoordinator: Parsing pump events (Source Reports API)")
                self._parse_pump_events(pump_events, data)
            elif timeline:
                _LOGGER.debug("TandemCoordinator: Parsing therapy timeline (ControlIQ API)")
                self._parse_therapy_timeline(timeline, data)
            else:
                _LOGGER.debug("TandemCoordinator: No therapy data available")
                self._parse_therapy_timeline(None, data)  # Set all to UNAVAILABLE
        except Exception as e:
            _LOGGER.error("TandemCoordinator: Error parsing therapy data: %s", e, exc_info=True)

        # ── Dashboard summary (fallback only) ──────────────────────────
        # When pump_events are available, _compute_cgm_summary() inside
        # _parse_pump_events() computes avg glucose, TIR, CGM usage locally.
        # Only fall back to the dashboard_summary API if no pump_events.
        if not pump_events:
            summary = recent_data.get("dashboard_summary")
            try:
                self._parse_dashboard_summary(summary, data)
            except Exception as e:
                _LOGGER.error("TandemCoordinator: Error parsing dashboard summary: %s", e, exc_info=True)

        # Diagnostic: show CGM reading, its age, and whether staleness would have fired
        cgm_mgdl = data.get("tandem_last_sg_mgdl")
        cgm_ts = data.get("tandem_last_sg_timestamp")
        try:
            if cgm_ts and hasattr(cgm_ts, "astimezone"):
                age_secs = (datetime.now(timezone.utc) - cgm_ts.astimezone(timezone.utc)).total_seconds()
                age_str = f"{int(age_secs / 60)}min"
            else:
                age_str = "N/A"
        except Exception:
            age_str = "?"
        _LOGGER.info(
            "[Tandem] Parse done: %d keys | CGM=%s mg/dL @ %s (age=%s) | stale_check=%s",
            len(data),
            cgm_mgdl if cgm_mgdl is not None else "N/A",
            cgm_ts.strftime("%H:%M:%S %Z") if cgm_ts and hasattr(cgm_ts, "strftime") else "N/A",
            age_str,
            is_data_stale(data),
        )

        # ── Import long-term statistics with correct timestamps ──────────
        if pump_events:
            self.hass.async_create_task(self._import_statistics(pump_events))

        return data

    def _parse_therapy_timeline(self, timeline: dict[str, Any] | None, data: dict[str, Any]) -> None:
        """Parse therapy timeline data into sensor values."""
        # Keys only populated by _parse_pump_events — always default to UNAVAILABLE
        # when falling back to this path so sensors show unavailable, not unknown.
        data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_RSSI] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_IOB_HOURS] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_IOB_MINUTES] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_ALERT] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_ALARM] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_SESSION_START] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS] = {}
        data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] = UNAVAILABLE

        if not timeline:
            data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
            return

        # ── CGM readings ─────────────────────────────────────────────
        try:
            cgm_entries = timeline.get("cgm", [])
            if cgm_entries:
                # Find the most recent CGM reading
                latest_reading = None
                latest_dt = None
                for entry in cgm_entries:
                    readings = entry.get("Readings", [])
                    entry_dt = parse_dotnet_date(entry.get("EventDateTime"))
                    for reading in readings:
                        val = reading.get("Value")
                        rtype = reading.get("Type", "")
                        if val and val > 0 and rtype == "EGV":
                            if latest_dt is None or (entry_dt and entry_dt > latest_dt):
                                latest_reading = val
                                latest_dt = entry_dt

                if latest_reading is not None:
                    sg_mgdl = float(latest_reading)
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = int(sg_mgdl)
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = round(sg_mgdl * 0.0555, 2)

                    if latest_dt:
                        data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = latest_dt.astimezone(ZoneInfo(self.timezone))

                    # Calculate delta from previous reading
                    if self._prev_sg_mgdl is not None:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = sg_mgdl - self._prev_sg_mgdl
                    else:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                    self._prev_sg_mgdl = sg_mgdl
                else:
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing CGM data: %s", e)
            data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE

        # ── Bolus events ─────────────────────────────────────────────
        try:
            bolus_entries = timeline.get("bolus", [])
            if bolus_entries:
                # Sort by completion time, most recent first
                sorted_boluses = sorted(
                    bolus_entries,
                    key=lambda b: (
                        parse_dotnet_date(b.get("CompletionDateTime") or b.get("RequestDateTime", 0)) or datetime.min
                    ),
                    reverse=True,
                )

                last_bolus = sorted_boluses[0]
                insulin = last_bolus.get("InsulinDelivered", 0)
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = round(float(insulin), 2) if insulin else UNAVAILABLE

                bolus_dt = parse_dotnet_date(last_bolus.get("CompletionDateTime") or last_bolus.get("RequestDateTime"))
                if bolus_dt:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = bolus_dt.astimezone(ZoneInfo(self.timezone))
                else:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE

                # Extra attributes
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {
                    "description": last_bolus.get("Description", ""),
                    "requested_insulin": last_bolus.get("RequestedInsulin"),
                    "carbs": last_bolus.get("CarbSize"),
                    "bg": last_bolus.get("BG"),
                    "iob": last_bolus.get("IOB"),
                    "completion_status": last_bolus.get("CompletionStatusID", ""),
                }

                # IOB from the last bolus entry
                iob = last_bolus.get("IOB")
                if iob is not None:
                    data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = round(float(iob), 2)
                else:
                    data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE

                # Find last meal bolus (with carbs)
                meal_bolus = None
                for b in sorted_boluses:
                    carbs = b.get("CarbSize")
                    if carbs and float(carbs) > 0:
                        meal_bolus = b
                        break

                if meal_bolus:
                    meal_insulin = meal_bolus.get("InsulinDelivered", 0)
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = (
                        round(float(meal_insulin), 2) if meal_insulin else UNAVAILABLE
                    )
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {
                        "carbs": meal_bolus.get("CarbSize"),
                        "bg": meal_bolus.get("BG"),
                        "description": meal_bolus.get("Description", ""),
                    }
                else:
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
            else:
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
                data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
        except Exception as e:
            _LOGGER.warning("Error parsing bolus data: %s", e)
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}

        # ── Basal events ─────────────────────────────────────────────
        try:
            basal_entries = timeline.get("basal", [])
            if basal_entries:
                sorted_basals = sorted(
                    basal_entries,
                    key=lambda b: parse_dotnet_date(b.get("EventDateTime", 0)) or datetime.min,
                    reverse=True,
                )
                last_basal = sorted_basals[0]
                rate = last_basal.get("BasalRate")
                if rate is not None:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = round(float(rate), 3)
                else:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE

                # Determine Control-IQ status from basal type
                basal_type = last_basal.get("Type", "")
                if basal_type:
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = basal_type
                else:
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing basal data: %s", e)
            data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE

    def _parse_pump_events(self, pump_events: list[dict[str, Any]], data: dict[str, Any]) -> None:
        """Parse decoded pump events into sensor values.

        Events are pre-decoded from binary format by decode_pump_events().
        Each event dict has: event_id, event_name, timestamp (datetime),
        and event-specific fields (glucose_mgdl, insulin_delivered, etc.).

        IMPORTANT: Sensor values are ALWAYS populated from the full event
        set (latest of each type), regardless of deduplication. The sequence
        dedup only controls which events get imported as long-term statistics.
        """
        if not pump_events:
            _LOGGER.debug("No pump_events data, setting all to UNAVAILABLE")
            self._parse_therapy_timeline(None, data)
            return

        _LOGGER.debug("Tandem: Parsing %d decoded pump events", len(pump_events))

        # Categorise ALL events by type — sensor values always use full set
        cgm_readings: list[dict[str, Any]] = []
        bolus_completed: list[dict[str, Any]] = []
        bolex_completed: list[dict[str, Any]] = []
        bolus_delivery: list[dict[str, Any]] = []
        basal_rate_changes: list[dict[str, Any]] = []
        basal_delivery: list[dict[str, Any]] = []
        suspend_resume: list[dict[str, Any]] = []
        bg_readings: list[dict[str, Any]] = []
        cartridge_fills: list[dict[str, Any]] = []
        carbs_entered: list[dict[str, Any]] = []
        cannula_fills: list[dict[str, Any]] = []
        tubing_fills: list[dict[str, Any]] = []
        user_mode_changes: list[dict[str, Any]] = []
        pcm_changes: list[dict[str, Any]] = []
        daily_basal_events: list[dict[str, Any]] = []
        shelf_mode_events: list[dict[str, Any]] = []
        battery_status_events: list[dict[str, Any]] = []
        alert_events: list[dict[str, Any]] = []
        alarm_events: list[dict[str, Any]] = []
        daily_status_events: list[dict[str, Any]] = []
        bolus_req_msg1: list[dict[str, Any]] = []
        bolus_req_msg2: list[dict[str, Any]] = []
        bolus_req_msg3: list[dict[str, Any]] = []
        plgs_events: list[dict[str, Any]] = []
        new_day_events: list[dict[str, Any]] = []
        cgm_session_events: list[dict[str, Any]] = []

        for evt in pump_events:
            eid = evt.get("event_id")
            if eid in (EVT_CGM_DATA_GXB, EVT_CGM_DATA_G7, EVT_CGM_DATA_FSL2):
                # Safety: clamp out-of-range readings before ANY consumer sees them
                # (over-range G7 sends a fabricated 400–1200 mg/dL). See helper docstring.
                _clamp_cgm_over_range(evt)
                cgm_readings.append(evt)
            elif eid == EVT_BOLUS_COMPLETED:
                bolus_completed.append(evt)
            elif eid == EVT_BOLEX_COMPLETED:
                bolex_completed.append(evt)
            elif eid == EVT_BOLUS_DELIVERY:
                bolus_delivery.append(evt)
            elif eid == EVT_BASAL_RATE_CHANGE:
                basal_rate_changes.append(evt)
            elif eid == EVT_BASAL_DELIVERY:
                basal_delivery.append(evt)
            elif eid in (EVT_PUMPING_SUSPENDED, EVT_PUMPING_RESUMED):
                suspend_resume.append(evt)
            elif eid == EVT_BG_READING_TAKEN:
                bg_readings.append(evt)
            elif eid == EVT_CARTRIDGE_FILLED:
                cartridge_fills.append(evt)
            elif eid == EVT_CARBS_ENTERED:
                carbs_entered.append(evt)
            elif eid == EVT_CANNULA_FILLED:
                cannula_fills.append(evt)
            elif eid == EVT_TUBING_FILLED:
                tubing_fills.append(evt)
            elif eid == EVT_AA_USER_MODE_CHANGE:
                user_mode_changes.append(evt)
            elif eid == EVT_AA_PCM_CHANGE:
                pcm_changes.append(evt)
            elif eid == EVT_DAILY_BASAL:
                daily_basal_events.append(evt)
            elif eid == EVT_SHELF_MODE:
                shelf_mode_events.append(evt)
            elif eid in (EVT_STATUS, EVT_BATTERY_1, EVT_BATTERY_2):
                battery_status_events.append(evt)
            elif eid in (EVT_ALERT_ACTIVATED, EVT_ALERT_CLEARED):
                alert_events.append(evt)
            elif eid in (EVT_ALARM_ACTIVATED, EVT_MALFUNCTION_ACTIVATED, EVT_ALARM_CLEARED):
                alarm_events.append(evt)
            elif eid == EVT_AA_DAILY_STATUS:
                daily_status_events.append(evt)
            elif eid == EVT_BOLUS_REQUESTED_MSG1:
                bolus_req_msg1.append(evt)
            elif eid == EVT_BOLUS_REQUESTED_MSG2:
                bolus_req_msg2.append(evt)
            elif eid == EVT_BOLUS_REQUESTED_MSG3:
                bolus_req_msg3.append(evt)
            elif eid == EVT_PLGS_PERIODIC:
                plgs_events.append(evt)
            elif eid == EVT_NEW_DAY:
                new_day_events.append(evt)
            elif eid in (EVT_CGM_SESSION_START, EVT_CGM_SESSION_JOIN, EVT_CGM_SESSION_STOP):
                cgm_session_events.append(evt)

        _LOGGER.debug(
            "Tandem: Events - CGM: %d, BolusCompleted: %d, BolexCompleted: %d, "
            "BolusDelivery: %d, BasalChange: %d, BasalDelivery: %d, "
            "Suspend/Resume: %d, BG: %d, Cartridge: %d, Carbs: %d, "
            "Cannula: %d, Tubing: %d, UserMode: %d, PCM: %d, "
            "DailyBasal: %d, ShelfMode: %d, "
            "Alert: %d, Alarm: %d, DailyStatus: %d, "
            "BolusReqMsg1: %d, BolusReqMsg2: %d, BolusReqMsg3: %d, "
            "PLGS: %d, NewDay: %d",
            len(cgm_readings),
            len(bolus_completed),
            len(bolex_completed),
            len(bolus_delivery),
            len(basal_rate_changes),
            len(basal_delivery),
            len(suspend_resume),
            len(bg_readings),
            len(cartridge_fills),
            len(carbs_entered),
            len(cannula_fills),
            len(tubing_fills),
            len(user_mode_changes),
            len(pcm_changes),
            len(daily_basal_events),
            len(shelf_mode_events),
            len(alert_events),
            len(alarm_events),
            len(daily_status_events),
            len(bolus_req_msg1),
            len(bolus_req_msg2),
            len(bolus_req_msg3),
            len(plgs_events),
            len(new_day_events),
        )

        # Update the last-seen sequence number for statistics deduplication
        max_seq = max((evt.get("seq", 0) for evt in pump_events), default=0)
        if max_seq > self._last_event_seq:
            self._last_event_seq = max_seq
            _LOGGER.debug("Tandem: Updated last_event_seq to %d", max_seq)

        # Sort all event lists by timestamp
        cgm_readings.sort(key=lambda e: e["timestamp"])
        bolus_completed.sort(key=lambda e: e["timestamp"])
        bolex_completed.sort(key=lambda e: e["timestamp"])
        bolus_delivery.sort(key=lambda e: e["timestamp"])
        basal_rate_changes.sort(key=lambda e: e["timestamp"])
        basal_delivery.sort(key=lambda e: e["timestamp"])
        suspend_resume.sort(key=lambda e: e["timestamp"])
        bg_readings.sort(key=lambda e: e["timestamp"])
        cartridge_fills.sort(key=lambda e: e["timestamp"])
        carbs_entered.sort(key=lambda e: e["timestamp"])
        cannula_fills.sort(key=lambda e: e["timestamp"])
        tubing_fills.sort(key=lambda e: e["timestamp"])
        user_mode_changes.sort(key=lambda e: e["timestamp"])
        pcm_changes.sort(key=lambda e: e["timestamp"])
        daily_basal_events.sort(key=lambda e: e["timestamp"])
        shelf_mode_events.sort(key=lambda e: e["timestamp"])
        alert_events.sort(key=lambda e: e["timestamp"])
        alarm_events.sort(key=lambda e: e["timestamp"])
        daily_status_events.sort(key=lambda e: e["timestamp"])
        bolus_req_msg1.sort(key=lambda e: e["timestamp"])
        bolus_req_msg2.sort(key=lambda e: e["timestamp"])
        bolus_req_msg3.sort(key=lambda e: e["timestamp"])
        plgs_events.sort(key=lambda e: e["timestamp"])
        # NewDay events decoded for diagnostics logging (Phase 5).
        new_day_events.sort(key=lambda e: e["timestamp"])
        cgm_session_events.sort(key=lambda e: e["timestamp"])

        # ── Populate current sensor values from latest events ────────

        # ── CGM readings ─────────────────────────────────────────────
        try:
            if cgm_readings:
                latest = cgm_readings[-1]
                sg_mgdl = latest.get("glucose_mgdl", 0)

                # Signal strength is independent of glucose validity — surface it
                # whenever a reading exists (absent on some transmitters -> unavailable).
                rssi_val = latest.get("rssi")
                data[TANDEM_SENSOR_KEY_RSSI] = rssi_val if isinstance(rssi_val, (int, float)) else UNAVAILABLE

                if sg_mgdl and sg_mgdl > 0:
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = int(sg_mgdl)
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = round(sg_mgdl * 0.0555, 2)
                    data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = latest["timestamp"].replace(
                        tzinfo=ZoneInfo(self.timezone)
                    )

                    if self._prev_sg_mgdl is not None:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = float(sg_mgdl) - self._prev_sg_mgdl
                    else:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                    self._prev_sg_mgdl = float(sg_mgdl)

                    roc = latest.get("rate_of_change")
                    data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = round(roc, 1) if roc is not None else UNAVAILABLE
                    cgm_status_code = latest.get("status")
                    cgm_status = CGM_STATUS_MAP.get(cgm_status_code) if cgm_status_code is not None else None
                    if cgm_status is None and cgm_status_code is not None:
                        _LOGGER.debug("Tandem: Unknown CGM status code %r — update CGM_STATUS_MAP", cgm_status_code)
                    data[TANDEM_SENSOR_KEY_CGM_STATUS] = cgm_status if cgm_status is not None else UNAVAILABLE
                else:
                    _LOGGER.warning(
                        "Tandem: CGM event has zero/missing glucose: %s",
                        latest,
                    )
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_RSSI] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing CGM: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_RSSI] = UNAVAILABLE

        # ── Store recent readings history as attributes ───────────────
        # Custom Lovelace cards (e.g. ApexCharts) can use these for
        # correctly-timestamped graphs. Limited to most recent entries
        # to stay within HA's 16KB state attribute size limit.
        tz = ZoneInfo(self.timezone)
        _MAX_CGM_HISTORY = 24  # ~2 hours of 5-min readings
        _MAX_BOLUS_HISTORY = 10
        _MAX_BASAL_HISTORY = 10

        # CGM readings history (for glucose graph cards)
        recent_cgm = cgm_readings[-_MAX_CGM_HISTORY:]
        data[f"{TANDEM_SENSOR_KEY_LASTSG_MGDL}_attributes"] = {
            "readings": [
                {
                    "t": r["timestamp"].replace(tzinfo=tz).isoformat(),
                    "v": r.get("glucose_mgdl"),
                }
                for r in recent_cgm
                if r.get("glucose_mgdl")
            ],
        }

        # IOB history (from bolus completed events)
        recent_iob = bolus_completed[-_MAX_BOLUS_HISTORY:]
        data[f"{TANDEM_SENSOR_KEY_ACTIVE_INSULIN}_attributes"] = {
            "readings": [
                {
                    "t": b["timestamp"].replace(tzinfo=tz).isoformat(),
                    "v": round(float(b["iob"]), 2),
                }
                for b in recent_iob
                if b.get("iob") is not None
            ],
        }

        # Basal rate history
        all_basal_sorted = sorted(
            basal_rate_changes + basal_delivery,
            key=lambda e: e["timestamp"],
        )
        recent_basal = all_basal_sorted[-_MAX_BASAL_HISTORY:]
        data[f"{TANDEM_SENSOR_KEY_BASAL_RATE}_attributes"] = {
            "readings": [
                {
                    "t": b["timestamp"].replace(tzinfo=tz).isoformat(),
                    "v": round(float(b["commanded_rate"]), 3),
                }
                for b in recent_basal
                if b.get("commanded_rate") is not None
            ],
        }

        # ── Bolus events ─────────────────────────────────────────────
        try:
            # Prefer BOLUS_COMPLETED (has IOB), fall back to BOLUS_DELIVERY
            latest_bolus_list = bolus_completed or bolus_delivery
            if latest_bolus_list:
                last_bolus = latest_bolus_list[-1]

                insulin = last_bolus.get("insulin_delivered", 0)
                if insulin:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = round(float(insulin), 2)
                else:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE

                data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = last_bolus["timestamp"].replace(
                    tzinfo=ZoneInfo(self.timezone)
                )

                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {
                    "event_type": last_bolus.get("event_name", ""),
                    "insulin_requested": last_bolus.get("insulin_requested"),
                    "bolus_id": last_bolus.get("bolus_id"),
                    "completion_status": last_bolus.get("completion_status"),
                }

                # IOB from BOLUS_COMPLETED event
                iob = last_bolus.get("iob")
                if iob is not None:
                    data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = round(float(iob), 2)
                else:
                    # Try to find IOB from any completed bolus
                    for b in reversed(bolus_completed):
                        if b.get("iob") is not None:
                            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = round(float(b["iob"]), 2)
                            break
                    else:
                        data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE

                # Meal bolus detection (bolus with carb flag)
                # In binary format, bolus_type bitmask bit 4 = Carb bolus
                meal_bolus = None
                for b in reversed(bolus_delivery):
                    btype = b.get("bolus_type", 0)
                    if btype & 0x10:  # bit 4 = Carb
                        meal_bolus = b
                        break

                if meal_bolus:
                    meal_ins = meal_bolus.get("insulin_delivered", 0)
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = round(float(meal_ins), 2) if meal_ins else UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {
                        "bolus_type": meal_bolus.get("bolus_type"),
                        "bolus_id": meal_bolus.get("bolus_id"),
                    }
                else:
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
            else:
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
                data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
        except Exception as e:
            _LOGGER.warning("Error parsing bolus: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}

        # ── Basal events ─────────────────────────────────────────────
        try:
            # Prefer BASAL_RATE_CHANGE (has float rate), fall back to
            # BASAL_DELIVERY (has milliunits rate)
            latest_basal_list = basal_rate_changes or basal_delivery
            if latest_basal_list:
                last_basal = latest_basal_list[-1]

                rate = last_basal.get("commanded_rate")
                if rate is not None:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = round(float(rate), 3)
                else:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE

                # Control-IQ status from basal change type or source
                change_type = last_basal.get("change_type")
                commanded_source = last_basal.get("commanded_source")
                if commanded_source is not None:
                    source_map = {
                        0: "Suspended",
                        1: "Profile",
                        2: "Temp Rate",
                        3: "Algorithm",
                        4: "Temp + Algorithm",
                    }
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = source_map.get(
                        commanded_source, f"Source_{commanded_source}"
                    )
                elif change_type is not None:
                    _LOGGER.debug(
                        "Tandem: BasalRateChange change_type=%d has no commanded_source — "
                        "raw value used as Control-IQ status (add to source_map if known)",
                        change_type,
                    )
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = str(change_type)
                else:
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing basal: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE

        # ── Pump suspend/resume state ──────────────────────────────────
        try:
            if suspend_resume:
                last_sr = suspend_resume[-1]
                is_suspended = last_sr.get("event_id") == 11
                data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] = "Suspended" if is_suspended else "Active"
                suspend_reason = last_sr.get("suspend_reason") if is_suspended else None
                data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = (
                    suspend_reason if suspend_reason is not None else UNAVAILABLE
                )
            else:
                data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing suspend/resume: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = UNAVAILABLE

        # ── Activity mode (sleep/exercise/eating soon) ─────────────────
        if user_mode_changes:
            last_mode = user_mode_changes[-1]
            data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] = last_mode.get("current_mode", UNAVAILABLE)
        else:
            data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] = UNAVAILABLE

        # ── Control-IQ mode (open loop / closed loop) ──────────────────
        if pcm_changes:
            last_pcm = pcm_changes[-1]
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_MODE] = last_pcm.get("current_pcm", UNAVAILABLE)
            clp = last_pcm.get("closed_loop_preferred")
            data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] = clp if isinstance(clp, bool) else UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_MODE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] = UNAVAILABLE

        # ── BG readings ────────────────────────────────────────────────
        if bg_readings:
            last_bg = bg_readings[-1]
            data[TANDEM_SENSOR_KEY_LAST_BG_READING] = last_bg.get("bg_mgdl", UNAVAILABLE)
        else:
            data[TANDEM_SENSOR_KEY_LAST_BG_READING] = UNAVAILABLE

        # ── Carb entries ───────────────────────────────────────────────
        tz = ZoneInfo(self.timezone)
        if carbs_entered:
            last_carb = carbs_entered[-1]
            data[TANDEM_SENSOR_KEY_LAST_CARBS] = last_carb.get("carbs", UNAVAILABLE)
            data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP] = last_carb["timestamp"].replace(tzinfo=tz)
        else:
            data[TANDEM_SENSOR_KEY_LAST_CARBS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP] = UNAVAILABLE

        # ── Cartridge change ───────────────────────────────────────────
        if cartridge_fills:
            last_cart = cartridge_fills[-1]
            data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] = last_cart["timestamp"].replace(tzinfo=tz)
            fill_volume = last_cart.get("insulin_volume")
            if fill_volume and fill_volume > 0:
                data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] = fill_volume
                data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = round(fill_volume, 1)
            else:
                _LOGGER.debug(
                    "Cartridge fill volume is %s — no fill volume in API response",
                    fill_volume,
                )
                data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = UNAVAILABLE

        # ── Estimated remaining insulin (Phase 6) ──────────────────────
        # Accumulates delivered insulin incrementally using seq-based dedup.
        # State persists across polls; lost on HA restart.
        try:
            self._compute_estimated_remaining_insulin(
                cartridge_fills, bolus_completed, bolex_completed, basal_delivery, data
            )
        except (KeyError, TypeError, IndexError, ValueError, AttributeError) as e:
            _LOGGER.warning("Error computing estimated remaining insulin: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] = UNAVAILABLE

        # ── Site change ───────────────────────────────────────────────
        # The Tandem Source API does not return CANNULA_FILLED (event 61)
        # for cartridge/site changes. The web UI shows "Cartridge/Site Change"
        # as a single combined event. We derive site change from the cartridge
        # fill timestamp, falling back to cannula fill if present.
        if cannula_fills:
            data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = cannula_fills[-1]["timestamp"].replace(tzinfo=tz)
        elif cartridge_fills:
            data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = cartridge_fills[-1]["timestamp"].replace(tzinfo=tz)
        else:
            data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = UNAVAILABLE

        # ── Tubing change ──────────────────────────────────────────────
        if tubing_fills:
            data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] = tubing_fills[-1]["timestamp"].replace(tzinfo=tz)
        else:
            data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] = UNAVAILABLE

        # ── Battery level ─────────────────────────────────────────────────
        # The pump's on-screen battery percentage, from the BFF pump-status /
        # battery-detail events (9 / 34 / 35). Their `abc` (actual battery charge)
        # field is the display percentage — validated 2026-09-06 against the physical
        # charge ratio remainingChargeCapacity/fullChargeCapacity. The pre-BFF
        # sources (DailyBasal 81 / ShelfMode 53) carry no battery data under the BFF,
        # so the level comes solely from 9/34/35. Only the level is surfaced —
        # voltage/mAh are not consumed.
        try:
            battery_pct = UNAVAILABLE

            # Most-recent battery-percent-bearing status/battery event.
            battery_pct_events = [e for e in battery_status_events if e.get("battery_percent") is not None]
            if battery_pct_events:
                latest_batt = max(battery_pct_events, key=lambda e: e["timestamp"])
                raw_pct = latest_batt.get("battery_percent")
                # `abc` is a 0-100 integer; guard against an unexpected scale rather
                # than surfacing a misleading value (null-not-guess).
                if isinstance(raw_pct, (int, float)) and 0 <= raw_pct <= 100:
                    battery_pct = round(raw_pct)
                else:
                    _LOGGER.warning(
                        "Tandem: battery_percent out of range (%r) — leaving unavailable",
                        raw_pct,
                    )

            data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] = battery_pct
        except Exception as e:
            _LOGGER.warning("Error parsing battery data: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] = UNAVAILABLE

        # ── Insulin-on-board remaining duration ────────────────────────
        # From the status event (9) only — the battery-detail events (34/35)
        # share the bucket but carry no IOB, so filter on iob_hours presence.
        try:
            iob_hours = UNAVAILABLE
            iob_minutes = UNAVAILABLE
            iob_events = [e for e in battery_status_events if e.get("iob_hours") is not None]
            if iob_events:
                latest_iob = max(iob_events, key=lambda e: e["timestamp"])
                raw_h = latest_iob.get("iob_hours")
                raw_m = latest_iob.get("iob_minutes")
                if isinstance(raw_h, (int, float)) and raw_h >= 0:
                    iob_hours = int(raw_h)
                if isinstance(raw_m, (int, float)) and raw_m >= 0:
                    iob_minutes = int(raw_m)
            data[TANDEM_SENSOR_KEY_IOB_HOURS] = iob_hours
            data[TANDEM_SENSOR_KEY_IOB_MINUTES] = iob_minutes
        except Exception as e:
            _LOGGER.warning("Error parsing IOB duration: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_IOB_HOURS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_IOB_MINUTES] = UNAVAILABLE

        # ── Alerts & Alarms (Phase 2) ─────────────────────────────────
        try:
            self._parse_alert_alarm_events(alert_events, alarm_events, data)
        except Exception as e:
            _LOGGER.error(
                "Error parsing alert/alarm events (%d alert, %d alarm events): %s",
                len(alert_events),
                len(alarm_events),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_LAST_ALERT] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_ALARM] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] = UNAVAILABLE

        # ── CGM Sensor Session / expiry (Phase 7) ─────────────────────
        try:
            self._parse_cgm_session_events(cgm_session_events, data)
        except Exception as e:
            _LOGGER.error(
                "Error parsing %d CGM session event(s): %s",
                len(cgm_session_events),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_CGM_SESSION_START] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] = UNAVAILABLE

        # ── CGM Sensor Type (Phase 3) ────────────────────────────────
        try:
            if daily_status_events:
                latest_status = daily_status_events[-1]
                sensor_type = latest_status.get("sensor_type", UNAVAILABLE)
                if sensor_type != UNAVAILABLE and isinstance(sensor_type, str) and sensor_type.startswith("Unknown"):
                    _LOGGER.info(
                        "Tandem: Unrecognised CGM sensor_type %r from %d daily_status event(s) — update sensor_type_map in tandem_api.py",
                        sensor_type,
                        len(daily_status_events),
                    )
                data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = sensor_type
            else:
                data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = UNAVAILABLE
        except (KeyError, TypeError, IndexError) as e:
            _LOGGER.error(
                "Tandem: Error parsing %d daily status event(s): %s",
                len(daily_status_events),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = UNAVAILABLE

        # ── Bolus Calculator (3-way join on BolusID) ─────────────────────
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS] = {}
        try:
            if bolus_req_msg3:
                tz = ZoneInfo(self.timezone)
                # Build joined records keyed by bolus_id
                bolus_calc: dict[int, dict[str, Any]] = {}
                for msg in bolus_req_msg1:
                    bid = msg.get("bolus_id")
                    if bid is not None:
                        bolus_calc.setdefault(bid, {}).update(
                            {
                                "bg": msg.get("bg_mgdl"),
                                "carbs": msg.get("carb_amount"),
                                "iob_at_request": msg.get("iob"),
                                "bolus_type": msg.get("bolus_type"),
                                "correction_included": msg.get("correction_included"),
                                "carb_ratio": msg.get("carb_ratio"),
                            }
                        )
                for msg in bolus_req_msg2:
                    bid = msg.get("bolus_id")
                    if bid is not None:
                        bolus_calc.setdefault(bid, {}).update(
                            {
                                "target_bg": msg.get("target_bg"),
                                "isf": msg.get("isf"),
                                "declined_correction": msg.get("declined_correction"),
                                "user_override": msg.get("user_override"),
                                "standard_percent": msg.get("standard_percent"),
                                "duration_minutes": msg.get("duration_minutes"),
                            }
                        )
                for msg in bolus_req_msg3:
                    bid = msg.get("bolus_id")
                    if bid is not None:
                        bolus_calc.setdefault(bid, {}).update(
                            {
                                "food_bolus": msg.get("food_bolus_size"),
                                "correction_bolus": msg.get("correction_bolus_size"),
                                "total_bolus": msg.get("total_bolus_size"),
                                "timestamp": msg.get("timestamp"),
                            }
                        )

                # Find latest complete record (has msg3 timestamp and msg1 data)
                complete = [
                    (rec["timestamp"], bid, rec)
                    for bid, rec in bolus_calc.items()
                    if rec.get("timestamp") and rec.get("bg") is not None
                ]
                if complete:
                    complete.sort(key=lambda x: x[0])
                    _, latest_bid, latest = complete[-1]

                    bg = latest.get("bg")
                    if bg is not None and isinstance(bg, (int, float)) and bg > 0:
                        data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] = int(bg)
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] = latest.get("carbs", 0)
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] = round(float(latest.get("correction_bolus", 0)), 2)
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] = round(float(latest.get("food_bolus", 0)), 2)
                    data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS] = {
                        "bolus_id": latest_bid,
                        "total_bolus": latest.get("total_bolus"),
                        "iob_at_request": latest.get("iob_at_request"),
                        "carb_ratio": latest.get("carb_ratio"),
                        "target_bg": latest.get("target_bg"),
                        "isf": latest.get("isf"),
                        "correction_included": latest.get("correction_included"),
                        "declined_correction": latest.get("declined_correction"),
                        "user_override": latest.get("user_override"),
                        "timestamp": latest["timestamp"].replace(tzinfo=tz).isoformat(),
                    }
        except (KeyError, TypeError, IndexError, ValueError) as e:
            _LOGGER.error(
                "Tandem: Error parsing %d bolus calculator event(s): %s",
                len(bolus_req_msg3),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS] = {}

        # ── PLGS Predicted Glucose (Phase 5) ───────────────────────────
        try:
            if plgs_events:
                latest_plgs = plgs_events[-1]
                pgv = latest_plgs.get("predicted_glucose_mgdl")
                if pgv is not None and isinstance(pgv, (int, float)) and pgv > 0:
                    data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] = int(pgv)
                else:
                    data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] = UNAVAILABLE
        except (KeyError, TypeError, IndexError, ValueError) as e:
            _LOGGER.error(
                "Tandem: Error parsing %d PLGS event(s): %s",
                len(plgs_events),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] = UNAVAILABLE

        # ── Computed summaries ─────────────────────────────────────────
        try:
            self._compute_cgm_summary(cgm_readings, data)
        except Exception as e:
            _LOGGER.warning("Error computing CGM summary: %s", e, exc_info=True)

        try:
            self._compute_insulin_summary(
                bolus_completed,
                bolex_completed,
                basal_delivery,
                basal_rate_changes,
                carbs_entered,
                data,
            )
        except Exception as e:
            _LOGGER.warning("Error computing insulin summary: %s", e, exc_info=True)

    def _parse_alert_alarm_events(
        self,
        alert_events: list[dict[str, Any]],
        alarm_events: list[dict[str, Any]],
        data: dict[str, Any],
    ) -> None:
        """Parse alert and alarm events into sensor values.

        alert_events contains events 4 (AlertActivated) and 26 (AlertCleared).
        alarm_events contains events 5 (AlarmActivated), 6 (MalfunctionActivated),
        and 28 (AlarmCleared).

        Active count tracks all uncleared activations across both lists.
        """
        tz = ZoneInfo(self.timezone)

        # ── Alert sensors (events 4 / 26) ────────────────────────────
        # Track which alert IDs are currently active (activated but not cleared).
        # Events are pre-sorted by timestamp so we replay in order.
        active_alerts: dict[int, dict[str, Any]] = {}
        for evt in alert_events:
            if evt["event_name"] == "AlertActivated":
                active_alerts[evt["alert_id"]] = evt
            elif evt["event_name"] == "AlertCleared":
                active_alerts.pop(evt["alert_id"], None)

        last_activated_alert = next(
            (e for e in reversed(alert_events) if e["event_name"] == "AlertActivated"),
            None,
        )
        if last_activated_alert:
            aid = last_activated_alert["alert_id"]
            name = TANDEM_ALERT_MAP.get(aid, f"Alert {aid}")
            ts = last_activated_alert["timestamp"].replace(tzinfo=tz)
            # Last 10 activation events in order; the same alert_id may appear
            # multiple times if it fired and cleared repeatedly.
            recent = [
                {
                    "id": e["alert_id"],
                    "name": TANDEM_ALERT_MAP.get(e["alert_id"], f"Alert {e['alert_id']}"),
                    "timestamp": e["timestamp"].replace(tzinfo=tz).isoformat(),
                }
                for e in alert_events
                if e["event_name"] == "AlertActivated"
            ][-10:]
            data[TANDEM_SENSOR_KEY_LAST_ALERT] = name
            data[f"{TANDEM_SENSOR_KEY_LAST_ALERT}_attributes"] = {
                "alert_id": aid,
                "cleared": aid not in active_alerts,
                "timestamp": ts.isoformat(),
                "recent": recent,
            }
        else:
            data[TANDEM_SENSOR_KEY_LAST_ALERT] = UNAVAILABLE

        # ── Alarm sensors (events 5, 6 / 28) ─────────────────────────
        active_alarms: dict[int, dict[str, Any]] = {}
        for evt in alarm_events:
            if evt["event_name"] in ("AlarmActivated", "MalfunctionActivated"):
                active_alarms[evt["alert_id"]] = evt
            elif evt["event_name"] == "AlarmCleared":
                active_alarms.pop(evt["alert_id"], None)

        last_activated_alarm = next(
            (e for e in reversed(alarm_events) if e["event_name"] in ("AlarmActivated", "MalfunctionActivated")),
            None,
        )
        if last_activated_alarm:
            aid = last_activated_alarm["alert_id"]
            name = TANDEM_ALARM_MAP.get(aid, f"Alarm {aid}")
            ts = last_activated_alarm["timestamp"].replace(tzinfo=tz)
            recent = [
                {
                    "id": e["alert_id"],
                    "name": TANDEM_ALARM_MAP.get(e["alert_id"], f"Alarm {e['alert_id']}"),
                    "timestamp": e["timestamp"].replace(tzinfo=tz).isoformat(),
                }
                for e in alarm_events
                if e["event_name"] in ("AlarmActivated", "MalfunctionActivated")
            ][-10:]
            data[TANDEM_SENSOR_KEY_LAST_ALARM] = name
            data[f"{TANDEM_SENSOR_KEY_LAST_ALARM}_attributes"] = {
                "alert_id": aid,
                "cleared": aid not in active_alarms,
                "timestamp": ts.isoformat(),
                "recent": recent,
            }
        else:
            data[TANDEM_SENSOR_KEY_LAST_ALARM] = UNAVAILABLE

        # ── Active count (alerts + alarms combined) ───────────────────
        data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] = len(active_alerts) + len(active_alarms)

    def _parse_cgm_session_events(
        self,
        cgm_session_events: list[dict[str, Any]],
        data: dict[str, Any],
    ) -> None:
        """Derive CGM sensor session start / expiry from events 212/213/214.

        Events (tconnectsync LID_CGM_{START,JOIN,STOP}_SESSION_GX) carry, on the
        transmitter clock in whole seconds (uint32): ``current_transmitter_time``
        (the clock at the event) and ``session_start_time`` (the clock when the
        session began). ``session_duration_days`` is the session length in whole
        days (10 for a G7 sensor). The wall-clock session start is the event's
        ``timestamp`` minus the transmitter seconds elapsed since the session
        began, so the result needs no epoch assumption::

            start_wall  = pumpDateTime - (current_transmitter_time - session_start_time)
            expiry_wall = start_wall + session_duration_days

        When the most recent session event is a stop (214), there is no active
        sensor session, so the sensors go unavailable rather than report a stale
        one (null-not-guess).
        """
        keys = (
            TANDEM_SENSOR_KEY_CGM_SESSION_START,
            TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY,
            TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING,
        )
        # A session is anchored by a start/join (212/213) that carries a valid
        # transmitter start time. Stop events (214) carry the sentinel
        # 0xFFFFFFFF for sessionStartTime, so they cannot anchor a session.
        starts = [
            e
            for e in cgm_session_events
            if e.get("event_name") in ("CGMSessionStart", "CGMSessionJoin")
            and _valid_session_seconds(e.get("session_start_time"))
            and _valid_session_seconds(e.get("current_transmitter_time"))
            and isinstance(e.get("session_duration_days"), (int, float))
        ]
        if not starts:
            for key in keys:
                data[key] = UNAVAILABLE
            return

        # Most recent valid start/join (list is pre-sorted by timestamp).
        anchor = starts[-1]
        ct = anchor["current_transmitter_time"]
        sst = anchor["session_start_time"]
        duration_days = anchor["session_duration_days"]
        tz = ZoneInfo(self.timezone)
        start_wall = anchor["timestamp"].replace(tzinfo=tz) - timedelta(seconds=ct - sst)
        expiry_wall = start_wall + timedelta(days=duration_days)
        now = datetime.now(tz)

        # If a stop was logged after this start, or the session has already
        # expired, the anchored sensor is no longer current and the current
        # sensor's start has not uploaded yet — report unavailable rather than a
        # stale/expired session (null-not-guess).
        stopped_after = any(
            e.get("event_name") == "CGMSessionStop" and e["timestamp"] > anchor["timestamp"] for e in cgm_session_events
        )
        if stopped_after or expiry_wall <= now:
            for key in keys:
                data[key] = UNAVAILABLE
            return

        reason_id = anchor.get("session_reason")
        data[TANDEM_SENSOR_KEY_CGM_SESSION_START] = start_wall
        data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY] = expiry_wall
        data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] = round((expiry_wall - now).total_seconds() / 86400.0, 2)
        data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"] = {
            "session_duration_days": duration_days,
            "session_started_via": (
                CGM_SESSION_REASON_MAP.get(reason_id, f"Reason {reason_id}") if reason_id is not None else None
            ),
        }

    def _parse_dashboard_summary(self, summary: dict[str, Any] | None, data: dict[str, Any]) -> None:
        """Parse dashboard summary into sensor values."""
        if not summary:
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE
            data[TANDEM_TIME_IN_RANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_USAGE] = UNAVAILABLE
            return

        try:
            avg_reading = summary.get("averageReading")
            if avg_reading is not None:
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = int(avg_reading)
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = round(float(avg_reading) * 0.0555, 2)
            else:
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE

            # Time in range - calculate from CGM data percentages
            tir = summary.get("timeInRangePercent")
            if tir is not None:
                data[TANDEM_TIME_IN_RANGE] = round(float(tir), 1)
            else:
                data[TANDEM_TIME_IN_RANGE] = UNAVAILABLE

            # CGM usage
            cgm_inactive = summary.get("cgmInactivePercent")
            if cgm_inactive is not None:
                data[TANDEM_SENSOR_KEY_CGM_USAGE] = round(100.0 - float(cgm_inactive), 1)
            else:
                time_in_use = summary.get("timeInUsePercent")
                if time_in_use is not None:
                    data[TANDEM_SENSOR_KEY_CGM_USAGE] = round(float(time_in_use), 1)
                else:
                    data[TANDEM_SENSOR_KEY_CGM_USAGE] = UNAVAILABLE

        except Exception as e:
            _LOGGER.warning("Error parsing dashboard summary: %s", e)
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE
            data[TANDEM_TIME_IN_RANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_USAGE] = UNAVAILABLE

    def _parse_pump_settings(self, last_upload_obj: dict[str, Any] | None, data: dict[str, Any]) -> None:
        """Extract pump settings from metadata.lastUpload.settings.

        The lastUpload field is a dict: {uploadId, lastUploadedAt, settings}.
        The Tandem Source BFF migration (~2026-06) renamed several settings
        sub-blocks; the current shape is: profiles, controlIqSettings,
        pumpSettings, globalMaxBolusSettings, basalLimitSettings, cgmSettings,
        reminders, globals, localizationSettings.
        """
        _set_unavailable = [
            TANDEM_SENSOR_KEY_ACTIVE_PROFILE,
            TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED,
            TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT,
            TANDEM_SENSOR_KEY_CONTROL_IQ_TDI,
            TANDEM_SENSOR_KEY_MAX_BOLUS,
            TANDEM_SENSOR_KEY_BASAL_LIMIT,
            TANDEM_SENSOR_KEY_CGM_HIGH_ALERT,
            TANDEM_SENSOR_KEY_CGM_LOW_ALERT,
            TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD,
            TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD,
            TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT,
        ]

        if not isinstance(last_upload_obj, dict):
            for key in _set_unavailable:
                data[key] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}
            return

        settings = last_upload_obj.get("settings")
        if not settings:
            for key in _set_unavailable:
                data[key] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}
            return

        try:
            # ── Active profile ──────────────────────────────────────────
            profiles = settings.get("profiles") or {}
            active_idp = profiles.get("activeIdp")
            profile_list = profiles.get("profile") or []

            active_profile = None
            for prof in profile_list:
                if prof.get("idp") == active_idp:
                    active_profile = prof
                    break

            if active_profile:
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] = active_profile.get("name", "Unknown")

                # Build profile attributes: schedule segments, insulin duration
                segments = active_profile.get("tDependentSegs") or []
                schedule: list[dict[str, Any]] = []
                for seg in segments:
                    rate = seg.get("basalRate", 0)
                    if rate == 0 and seg.get("startTime", 0) == 0 and not schedule:
                        # Skip empty placeholder segments, but keep the first
                        # one if it has a real rate
                        continue
                    if rate == 0 and seg.get("isf", 0) == 0:
                        # Empty trailing slot
                        continue
                    start_mins = seg.get("startTime", 0)
                    hours, mins = divmod(start_mins, 60)
                    schedule.append(
                        {
                            "time": f"{hours:02d}:{mins:02d}",
                            "basal_rate": round(rate / 1000, 3),
                            "isf_mgdl": seg.get("isf"),
                            "carb_ratio": round(seg.get("carbRatio", 0) / 1000, 1),
                            "target_bg_mgdl": seg.get("targetBg"),
                        }
                    )

                insulin_dur_mins = active_profile.get("insulinDuration", 0)
                attrs = {
                    "profile_name": active_profile.get("name"),
                    "insulin_duration_hours": round(insulin_dur_mins / 60, 1) if insulin_dur_mins else None,
                    "carb_entry_enabled": bool(active_profile.get("carbEntry")),
                    "schedule": schedule,
                }
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = attrs
            else:
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}

            # ── Control-IQ settings ─────────────────────────────────────
            # BFF renamed this block controlIQSettings → controlIqSettings and
            # lowercased its field names (ClosedLoop → closedLoop, etc.).
            ciq = settings.get("controlIqSettings") or {}
            closed_loop = ciq.get("closedLoop")
            if closed_loop is not None:
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] = "On" if closed_loop else "Off"
            else:
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] = UNAVAILABLE

            weight = ciq.get("weight")
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT] = weight if weight is not None else UNAVAILABLE

            tdi = ciq.get("totalDailyInsulin")
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_TDI] = tdi if tdi is not None else UNAVAILABLE

            # ── Pump limits ─────────────────────────────────────────────
            # BFF moved these out of pumpSettings into dedicated blocks:
            # maxBolus → globalMaxBolusSettings, basalLimit → basalLimitSettings.
            pump_settings = settings.get("pumpSettings") or {}
            max_bolus_settings = settings.get("globalMaxBolusSettings") or {}
            basal_limit_settings = settings.get("basalLimitSettings") or {}

            max_bolus_raw = max_bolus_settings.get("maxBolus")
            if max_bolus_raw is not None:
                data[TANDEM_SENSOR_KEY_MAX_BOLUS] = round(max_bolus_raw / 1000, 1)
            else:
                data[TANDEM_SENSOR_KEY_MAX_BOLUS] = UNAVAILABLE

            basal_limit_raw = basal_limit_settings.get("basalLimit")
            if basal_limit_raw is not None:
                data[TANDEM_SENSOR_KEY_BASAL_LIMIT] = round(basal_limit_raw / 1000, 1)
            else:
                data[TANDEM_SENSOR_KEY_BASAL_LIMIT] = UNAVAILABLE

            # ── CGM alert thresholds ────────────────────────────────────
            # BFF flattened these: highGlucoseAlert.mgPerDl → highGlucoseAlertMgPerDl.
            cgm_settings = settings.get("cgmSettings") or {}

            high_mgdl = cgm_settings.get("highGlucoseAlertMgPerDl")
            data[TANDEM_SENSOR_KEY_CGM_HIGH_ALERT] = high_mgdl if high_mgdl is not None else UNAVAILABLE

            low_mgdl = cgm_settings.get("lowGlucoseAlertMgPerDl")
            data[TANDEM_SENSOR_KEY_CGM_LOW_ALERT] = low_mgdl if low_mgdl is not None else UNAVAILABLE

            # ── Alert thresholds ────────────────────────────────────────
            # BFF renamed alertsAndReminders → reminders (low/high BG threshold);
            # lowInsulinThreshold moved into pumpSettings.
            reminders = settings.get("reminders") or {}
            low_bg = reminders.get("lowBgThreshold")
            data[TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD] = low_bg if low_bg is not None else UNAVAILABLE

            high_bg = reminders.get("highBgThreshold")
            data[TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD] = high_bg if high_bg is not None else UNAVAILABLE

            low_insulin = pump_settings.get("lowInsulinThreshold")
            data[TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT] = low_insulin if low_insulin is not None else UNAVAILABLE

        except Exception as e:
            _LOGGER.warning("Error parsing pump settings: %s", e, exc_info=True)
            for key in _set_unavailable:
                if key not in data:
                    data[key] = UNAVAILABLE
            if TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS not in data:
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}

    def _compute_cgm_summary(self, cgm_readings: list[dict[str, Any]], data: dict[str, Any]) -> None:
        """Compute CGM summary statistics from raw glucose readings.

        Replaces the broken dashboard_summary API by computing locally:
        avg glucose, SD, CV, GMI, time in/below/above range, CGM usage.
        """
        _unavailable_keys = (
            TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
            TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
            TANDEM_TIME_IN_RANGE,
            TANDEM_SENSOR_KEY_CGM_USAGE,
            TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV,
            TANDEM_SENSOR_KEY_GLUCOSE_CV,
            TANDEM_SENSOR_KEY_GMI,
            TANDEM_SENSOR_KEY_TIME_BELOW_RANGE,
            TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE,
        )

        if not cgm_readings:
            for key in _unavailable_keys:
                data[key] = UNAVAILABLE
            return

        # Extract valid glucose values
        values = [r["glucose_mgdl"] for r in cgm_readings if r.get("glucose_mgdl") and r["glucose_mgdl"] > 0]

        if not values:
            for key in _unavailable_keys:
                data[key] = UNAVAILABLE
            return

        n = len(values)
        mean = sum(values) / n

        # Average glucose
        data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = round(mean)
        data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = round(mean * 0.0555, 1)

        # Standard deviation
        if n >= 2:
            variance = sum((v - mean) ** 2 for v in values) / (n - 1)
            sd = math.sqrt(variance)
            data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] = round(sd, 1)
            data[TANDEM_SENSOR_KEY_GLUCOSE_CV] = round((sd / mean) * 100, 1) if mean > 0 else UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_GLUCOSE_CV] = UNAVAILABLE

        # GMI (Glucose Management Indicator)
        data[TANDEM_SENSOR_KEY_GMI] = round(3.31 + (0.02392 * mean), 1)

        # Time in range (70-180 mg/dL)
        in_range = sum(1 for v in values if 70 <= v <= 180)
        below = sum(1 for v in values if v < 70)
        above = sum(1 for v in values if v > 180)
        data[TANDEM_TIME_IN_RANGE] = round((in_range / n) * 100, 1)
        data[TANDEM_SENSOR_KEY_TIME_BELOW_RANGE] = round((below / n) * 100, 1)
        data[TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE] = round((above / n) * 100, 1)

        # CGM usage (readings per day: 288 at 5-min intervals)
        # Use reading count vs expected for the fetch window
        data[TANDEM_SENSOR_KEY_CGM_USAGE] = round(min((n / 288) * 100, 100.0), 1)

        _LOGGER.debug(
            "CGM summary: avg=%d mg/dL, SD=%.1f, CV=%.1f%%, GMI=%.1f%%, "
            "TIR=%.1f%%, below=%.1f%%, above=%.1f%%, usage=%.1f%% (%d readings)",
            mean,
            data.get(TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV, 0) or 0,
            data.get(TANDEM_SENSOR_KEY_GLUCOSE_CV, 0) or 0,
            data.get(TANDEM_SENSOR_KEY_GMI, 0) or 0,
            data[TANDEM_TIME_IN_RANGE],
            data[TANDEM_SENSOR_KEY_TIME_BELOW_RANGE],
            data[TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE],
            data[TANDEM_SENSOR_KEY_CGM_USAGE],
            n,
        )

    def _compute_insulin_summary(
        self,
        bolus_completed: list[dict[str, Any]],
        bolex_completed: list[dict[str, Any]],
        basal_delivery: list[dict[str, Any]],
        basal_rate_changes: list[dict[str, Any]],
        carbs_entered: list[dict[str, Any]],
        data: dict[str, Any],
    ) -> None:
        """Compute daily insulin summary from bolus and basal events.

        Only events from "today" (in pump timezone) are included so that
        the totals reflect a single calendar day, not the full 2-day
        fetch window.
        """
        _unavailable_keys = (
            TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN,
            TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL,
            TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL,
            TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT,
            TANDEM_SENSOR_KEY_DAILY_CARBS,
            TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT,
        )

        # Filter events to "today" in pump timezone
        tz = ZoneInfo(self.timezone)
        today = datetime.now(tz).date()

        def _today_only(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
            result = []
            for e in events:
                ts = e.get("timestamp")
                if not ts:
                    continue
                if ts.tzinfo is None:
                    # Naive timestamp — local pump time
                    ts = ts.replace(tzinfo=tz)
                if ts.astimezone(tz).date() == today:
                    result.append(e)
            return result

        bolus_completed = _today_only(bolus_completed)
        bolex_completed = _today_only(bolex_completed)
        basal_delivery = _today_only(basal_delivery)
        basal_rate_changes = _today_only(basal_rate_changes)
        carbs_entered = _today_only(carbs_entered)

        # Daily bolus total: sum insulin_delivered from completed boluses
        all_bolus = bolus_completed + bolex_completed
        bolus_total = sum(b.get("insulin_delivered", 0) for b in all_bolus if b.get("insulin_delivered"))
        data[TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL] = round(bolus_total, 2) if all_bolus else UNAVAILABLE
        data[TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT] = len(all_bolus) if all_bolus else UNAVAILABLE

        # Daily basal total: estimate from basal delivery events
        # Each basal_delivery event gives commanded_rate in U/hr.
        # Approximate: sum (rate * interval) for consecutive events.
        basal_total = 0.0
        if basal_delivery:
            sorted_basal = sorted(basal_delivery, key=lambda e: e["timestamp"])
            for i in range(len(sorted_basal) - 1):
                rate = sorted_basal[i].get("commanded_rate", 0) or 0
                dt_hours = (sorted_basal[i + 1]["timestamp"] - sorted_basal[i]["timestamp"]).total_seconds() / 3600.0
                # Cap interval at 1 hour to avoid gaps inflating the total
                dt_hours = min(dt_hours, 1.0)
                basal_total += rate * dt_hours
            # Add last segment (assume 5 min)
            last_rate = sorted_basal[-1].get("commanded_rate", 0) or 0
            basal_total += last_rate * (5.0 / 60.0)
        elif basal_rate_changes:
            sorted_basal = sorted(basal_rate_changes, key=lambda e: e["timestamp"])
            for i in range(len(sorted_basal) - 1):
                rate = sorted_basal[i].get("commanded_rate", 0) or 0
                dt_hours = (sorted_basal[i + 1]["timestamp"] - sorted_basal[i]["timestamp"]).total_seconds() / 3600.0
                dt_hours = min(dt_hours, 1.0)
                basal_total += rate * dt_hours
            last_rate = sorted_basal[-1].get("commanded_rate", 0) or 0
            basal_total += last_rate * (5.0 / 60.0)

        data[TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL] = (
            round(basal_total, 2) if (basal_delivery or basal_rate_changes) else UNAVAILABLE
        )

        # TDI and split
        if bolus_total > 0 or basal_total > 0:
            tdi = bolus_total + basal_total
            data[TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN] = round(tdi, 2)
            data[TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT] = round((basal_total / tdi) * 100, 1) if tdi > 0 else UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT] = UNAVAILABLE

        # Daily carbs
        if carbs_entered:
            total_carbs = sum(c.get("carbs", 0) for c in carbs_entered)
            data[TANDEM_SENSOR_KEY_DAILY_CARBS] = total_carbs
        else:
            data[TANDEM_SENSOR_KEY_DAILY_CARBS] = UNAVAILABLE

        _LOGGER.debug(
            "Insulin summary: TDI=%.2f U, bolus=%.2f U (%d), basal=%.2f U, split=%.1f%%, carbs=%s g",
            data.get(TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN) or 0,
            bolus_total,
            len(all_bolus),
            basal_total,
            data.get(TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT) or 0,
            data.get(TANDEM_SENSOR_KEY_DAILY_CARBS, "N/A"),
        )

    def _compute_estimated_remaining_insulin(
        self,
        cartridge_fills: list[dict[str, Any]],
        bolus_completed: list[dict[str, Any]],
        bolex_completed: list[dict[str, Any]],
        basal_delivery: list[dict[str, Any]],
        data: dict[str, Any],
    ) -> None:
        """Estimate remaining insulin from fill volume minus cumulative deliveries.

        Uses incremental accumulation with seq-based dedup to avoid both
        double-counting (overlapping API windows) and drift (events aging
        out of the 14-day window). A new cartridge fill resets the accumulator.

        All computation uses local variables; self._ state is only committed
        atomically at the end to prevent partial state corruption on exceptions.

        State is lost on HA restart — sensor shows UNAVAILABLE until a
        cartridge fill event appears in the window.
        """
        # Snapshot coordinator state into locals for atomic update
        local_fill_seq = self._last_cartridge_fill_seq
        local_fill_volume = self._last_cartridge_fill_volume
        local_cumulative = self._cumulative_delivered
        local_del_seq = self._last_delivery_seq
        fill_reset = False

        # Check for a new cartridge fill — resets the accumulator
        if cartridge_fills:
            latest_fill = cartridge_fills[-1]
            fill_seq = latest_fill.get("seq", 0)
            fill_volume = latest_fill.get("insulin_volume", 0)
            if fill_seq > local_fill_seq and fill_volume and fill_volume > 0:
                local_fill_seq = fill_seq
                local_fill_volume = float(fill_volume)
                local_cumulative = 0.0
                local_del_seq = fill_seq
                fill_reset = True

        # No fill volume known — cannot compute
        if local_fill_volume <= 0:
            _LOGGER.debug("No cartridge fill volume known — insulin remaining unavailable")
            data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] = UNAVAILABLE
            return

        # Accumulate only NEW deliveries (seq > local_del_seq)
        new_bolus = 0.0
        new_basal = 0.0
        max_new_seq = local_del_seq

        for b in bolus_completed + bolex_completed:
            seq = b.get("seq")
            if seq is None:
                _LOGGER.warning("Bolus event missing seq field, skipping")
                continue
            if seq > local_del_seq:
                delivered = b.get("insulin_delivered")
                if delivered is None:
                    _LOGGER.warning("Bolus seq=%d missing insulin_delivered", seq)
                    delivered = 0
                new_bolus += delivered
                max_new_seq = max(max_new_seq, seq)

        # Basal: only count new delivery events (seq > local_del_seq)
        new_basal_events = [b for b in basal_delivery if (bseq := b.get("seq")) is not None and bseq > local_del_seq]
        if new_basal_events:
            sorted_basal = sorted(new_basal_events, key=lambda e: e.get("seq", 0))
            for i in range(len(sorted_basal) - 1):
                rate = sorted_basal[i].get("commanded_rate", 0) or 0
                ts_a = sorted_basal[i].get("timestamp")
                ts_b = sorted_basal[i + 1].get("timestamp")
                if ts_a and ts_b:
                    dt_hours = (ts_b - ts_a).total_seconds() / 3600.0
                    dt_hours = max(0.0, min(dt_hours, 1.0))
                    new_basal += rate * dt_hours
                else:
                    _LOGGER.debug(
                        "Basal event seq=%s missing timestamp, skipping interval",
                        sorted_basal[i].get("seq"),
                    )
            # Last segment: assume 5 min
            last_rate = sorted_basal[-1].get("commanded_rate", 0) or 0
            new_basal += last_rate * (5.0 / 60.0)
            max_new_seq = max(max_new_seq, sorted_basal[-1].get("seq", 0))

        # Compute result
        local_cumulative += new_bolus + new_basal
        estimated = max(0.0, local_fill_volume - local_cumulative)

        # Atomic commit — only reached if no exception above
        self._last_cartridge_fill_seq = local_fill_seq
        self._last_cartridge_fill_volume = local_fill_volume
        self._cumulative_delivered = local_cumulative
        self._last_delivery_seq = max_new_seq
        data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] = round(estimated, 1)

        if fill_reset:
            _LOGGER.debug(
                "New cartridge fill: %.1f U (seq=%d), reset accumulator",
                local_fill_volume,
                local_fill_seq,
            )

        _LOGGER.debug(
            "Estimated insulin remaining: %.1f U "
            "(fill=%.1f, cumulative=%.2f, new_bolus=%.2f, new_basal=%.2f, last_seq=%d)",
            estimated,
            self._last_cartridge_fill_volume,
            self._cumulative_delivered,
            new_bolus,
            new_basal,
            self._last_delivery_seq,
        )

    # ── Long-term statistics import ──────────────────────────────────

    async def _import_statistics(self, pump_events: list[dict[str, Any]]) -> None:
        """Import pump events as HA long-term statistics.

        Creates correctly-timestamped 5-minute statistics entries so
        Statistics Graph cards show accurate historical data.
        """
        try:
            from homeassistant.components.recorder.statistics import (
                async_import_statistics,
            )
            from homeassistant.components.recorder.models import (
                StatisticData,
                StatisticMeanType,
                StatisticMetaData,
            )
        except ImportError:
            _LOGGER.debug("Tandem: Recorder statistics API not available, skipping")
            return

        tz = ZoneInfo(self.timezone)

        # ── CGM statistics ───────────────────────────────────────────
        cgm_stats: list[StatisticData] = []
        iob_stats: list[StatisticData] = []
        basal_stats: list[StatisticData] = []
        carb_stats: list[StatisticData] = []
        bolus_stats: list[StatisticData] = []
        correction_stats: list[StatisticData] = []

        for evt in pump_events:
            eid = evt.get("event_id")
            ts = evt.get("timestamp")
            if not ts:
                continue

            # null-not-guess: a malformed (non-datetime) timestamp is skipped, not
            # coerced or crashed on — a corrupted event must not abort the whole
            # statistics import for the good events alongside it.
            if not isinstance(ts, datetime):
                _LOGGER.debug("Skipping statistic for event %s: non-datetime timestamp %r", eid, ts)
                continue

            # Pump event timestamps are naive local pump time — label them
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=tz)
            else:
                ts = ts.astimezone(tz)  # already aware (shouldn't happen)

            # Round down to the top of the hour for HA statistics
            # (HA requires timestamps at the top of the hour)
            period_start = ts.replace(minute=0, second=0, microsecond=0)

            if eid in (EVT_CGM_DATA_GXB, EVT_CGM_DATA_G7, EVT_CGM_DATA_FSL2):
                sg = evt.get("glucose_mgdl", 0)
                if sg and sg > 0:
                    mmol = round(sg * 0.0555, 2)
                    cgm_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=mmol,
                            min=mmol,
                            max=mmol,
                            state=mmol,
                        )
                    )

            elif eid in (EVT_BOLUS_COMPLETED, EVT_BOLEX_COMPLETED):
                iob = evt.get("iob")
                if iob is not None:
                    iob_val = round(float(iob), 2)
                    iob_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=iob_val,
                            min=iob_val,
                            max=iob_val,
                            state=iob_val,
                        )
                    )
                # Collect completed bolus delivery for bolus statistics
                if evt.get("completion_status") == 3:
                    delivered = evt.get("insulin_delivered")
                    if delivered is not None and delivered > 0:
                        bolus_val = round(float(delivered), 2)
                        bolus_stats.append(
                            StatisticData(
                                start=period_start,
                                mean=bolus_val,
                                state=bolus_val,
                            )
                        )

            elif eid in (EVT_BASAL_RATE_CHANGE, EVT_BASAL_DELIVERY):
                rate = evt.get("commanded_rate")
                if rate is not None:
                    rate_val = round(float(rate), 3)
                    basal_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=rate_val,
                            min=rate_val,
                            max=rate_val,
                            state=rate_val,
                        )
                    )

            elif eid == EVT_CARBS_ENTERED:
                carbs = evt.get("carbs")
                if carbs is not None and carbs > 0:
                    carbs_val = round(float(carbs), 1)
                    carb_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=carbs_val,
                            state=carbs_val,
                        )
                    )

            elif eid == EVT_BOLUS_DELIVERY:
                if evt.get("delivery_status") == 0:
                    correction_mu = evt.get("correction_mu", 0)
                    if correction_mu and correction_mu > 0:
                        correction_val = round(correction_mu / 1000, 2)
                        correction_stats.append(
                            StatisticData(
                                start=period_start,
                                mean=correction_val,
                                state=correction_val,
                            )
                        )
                else:
                    _LOGGER.debug(
                        "Tandem: Skipping event 280 — delivery_status=%r (expected 0 for completed)",
                        evt.get("delivery_status"),
                    )

        # Import each statistic type — each in its own try/except so a failure
        # in one type does not prevent the others from being recorded.
        entity_prefix = f"sensor.{DOMAIN}"

        stat_types = [
            ("last_glucose_level_mmol", "Last glucose level mmol", "mmol/L", "CGM", cgm_stats),
            ("active_insulin_iob", "Active insulin (IOB)", "units", "IOB", iob_stats),
            ("basal_rate", "Basal rate", "U/hr", "basal", basal_stats),
            ("meal_carbs", "Meal carbs", "g", "carb", carb_stats),
            ("total_bolus", "Total bolus", "units", "bolus", bolus_stats),
            ("correction_bolus", "Correction bolus", "units", "correction", correction_stats),
        ]

        for stat_id_suffix, name, unit, log_label, stats in stat_types:
            if not stats:
                continue
            try:
                meta = StatisticMetaData(
                    has_mean=True,
                    mean_type=StatisticMeanType.ARITHMETIC,
                    has_sum=False,
                    name=name,
                    source="recorder",
                    statistic_id=f"{entity_prefix}_{stat_id_suffix}",
                    unit_of_measurement=unit,
                    unit_class=None,
                )
                async_import_statistics(self.hass, meta, stats)
                _LOGGER.info("[Tandem] Imported %d %s statistics", len(stats), log_label)
            except Exception as e:
                _LOGGER.warning("Tandem: Failed to import %s statistics: %s", log_label, e)


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions (Carelink)
# ═══════════════════════════════════════════════════════════════════════════
