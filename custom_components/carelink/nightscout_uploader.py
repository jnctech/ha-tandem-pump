import argparse
import asyncio
import certifi
from datetime import datetime
import hashlib
import json
import logging
import ssl

import httpx

from .const import (
    CARELINK_CODE_MAP,
)

NS_USER_AGENT = "Home Assistant Carelink"
DEBUG = False

_LOGGER = logging.getLogger(__name__)


def printdbg(msg):
    """Debug logger/print function"""
    _LOGGER.debug("Nightscout API: %s", msg)

    if DEBUG:
        print(msg)


class NightscoutUploader:
    """Nightscout Uploader library"""

    def __init__(self, nightscout_url, nightscout_secret):

        # Nightscout info
        self.__nightscout_url = nightscout_url.lower().rstrip("/")
        # SHA-1 is required by the Nightscout API specification for the API-SECRET header.
        self.__hashed_secret = hashlib.sha1(  # nosec B324
            nightscout_secret.encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        self.__is_reachable = False

        self._async_client = None
        self.__common_headers = {
            # Common browser headers
            "API-SECRET": self.__hashed_secret,
            "Content-Type": "application/json",
            "User-Agent": NS_USER_AGENT,
            "Accept": "application/json",
        }

    @property
    def async_client(self):
        """Return the httpx client, using a certifi-backed SSL context."""
        if not self._async_client:
            ssl_ctx = ssl.create_default_context(
                cafile=certifi.where()
            )  # NOSONAR S4423 - create_default_context is the recommended secure approach; TLSv1_2 minimum is intentional
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            self._async_client = httpx.AsyncClient(verify=ssl_ctx, timeout=30.0)
        return self._async_client

    async def close(self):
        """Close the HTTP client."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    async def fetch_async(self, url, headers, params=None):
        """Perform an async get request."""
        response = await self.async_client.get(
            url,
            headers=headers,
            params=params,
            follow_redirects=True,
            timeout=30,
        )
        return response

    async def post_async(self, url, headers, data=None, params=None):
        """Perform an async post request."""
        response = await self.async_client.post(
            url,
            headers=headers,
            params=params,
            data=data,
            follow_redirects=True,
            timeout=30,
        )
        return response

    def __get_carbs(self, input_insulin, input_meal):
        result = {}
        for marker in input_insulin:
            for entry in marker.items():
                for meal in input_meal:
                    if entry[0] in meal:
                        result[entry[0]] = {"insulin": entry[1], "carb": meal[entry[0]]}
        return result

    def __get_dict_values(self, input, key, value):
        result = []
        for marker in input:
            marker_dict = {}
            if (
                key in marker
                and marker["data"]
                and marker["data"]["dataValues"]
                and value in marker["data"]["dataValues"]
            ):
                marker_dict[marker[key]] = marker["data"]["dataValues"][value]
                result.append(marker_dict)
        return result

    def __traverse(self, value, key=None):
        if isinstance(value, dict):
            for k, v in value.items():
                yield from self.__traverse(v, k)
        else:
            yield key, value

    def __get_treatments(self, input, key, value):
        result = []
        for marker in input:
            marker_dict = {}
            is_type = False
            for k, v in self.__traverse(marker):
                if key == k and v == value:
                    is_type = True
                    break
            if is_type:
                for entry in marker.items():
                    marker_dict[entry[0]] = entry[1]
                result.append(marker_dict)
        return result

    def __getDataStringFromIso(self, time, tz):
        dt = datetime.fromisoformat(time.replace(".000-00:00", ""))
        dt = dt.replace(tzinfo=tz)
        dt = dt.astimezone(tz)
        timestamp = dt.timestamp()
        date = int(timestamp * 1000)
        date_string = dt.isoformat()
        return date, date_string

    async def __upload_section(self, section_name: str, getter, data_type: str, *args) -> bool:
        """Prepare data via getter and upload to Nightscout.

        Logs failures at WARNING level (visible in default HA logging) rather
        than swallowing them silently at DEBUG level.
        """
        try:
            data = getter(*args)
        except Exception as error:
            _LOGGER.warning(
                "Nightscout: Failed to prepare %s for upload: %s",
                section_name,
                error,
                exc_info=True,
            )
            data = []
        return await self.__set_data(self.__nightscout_url, data, data_type)

    async def __set_data(self, host, data, data_type):
        printdbg("__set_data()")
        if not data:
            return False
        success = True
        url = f"{host}/api/v1/{data_type}"
        try:
            for entry in data:
                response = await self.post_async(url, headers=self.__common_headers, data=json.dumps(entry))
                if response.status_code != 200:
                    raise ValueError(f"__set_data() session response is not OK: {response.status_code}")
        except httpx.TimeoutException as error:
            printdbg(f"__set_data() failed: request timeout - {error}")
            success = False
        except httpx.RequestError as error:
            printdbg(f"__set_data() failed: network error - {error}")
            success = False
        except ValueError as error:
            printdbg(f"__set_data() failed: {error}")
            success = False
        return success

    def __getMsgs(self, rawdata, tz):
        msgs = self.__get_treatments(rawdata.get("clearedNotifications", []), "type", "MESSAGE")
        return self.__getMsgEntries(msgs, tz)

    def __getAlarms(self, rawdata, tz):
        alarms = self.__get_treatments(rawdata.get("clearedNotifications", []), "type", "ALARM")
        return self.__getMsgEntries(alarms, tz)

    def __getAlerts(self, rawdata, tz):
        alerts = self.__get_treatments(rawdata.get("clearedNotifications", []), "type", "ALERT")
        return self.__getMsgEntries(alerts, tz)

    def __getMsgEntries(self, raw, tz):
        result = []
        for msg in raw:
            date, date_string = self.__getDataStringFromIso(msg["dateTime"], tz)
            # Handle both numeric and string faultId values (Simplera sensor uses strings)
            fault_id = msg.get("faultId")
            try:
                message_id = CARELINK_CODE_MAP.get(int(fault_id), "Unknown") if fault_id is not None else "Unknown"
            except (ValueError, TypeError):
                message_id = str(fault_id) if fault_id else "Unknown"

            if "additionalInfo" in msg and "sg" in msg["additionalInfo"] and int(msg["additionalInfo"]["sg"]) < 400:
                result.append(
                    {
                        "timestamp": date,
                        "enteredBy": NS_USER_AGENT,
                        "created_at": date_string,
                        "eventType": "Note",
                        "glucoseType": "sensor",
                        "glucose": float(msg["additionalInfo"]["sg"]),
                        "notes": self.__getNote(message_id),
                    }
                )
            else:
                result.append(
                    {
                        "timestamp": date,
                        "enteredBy": NS_USER_AGENT,
                        "created_at": date_string,
                        "eventType": "Note",
                        "notes": self.__getNote(message_id),
                    }
                )
        return result

    def __getNote(self, msg):
        return msg.replace("BC_SID_", "").replace("BC_MESSAGE_", "")

    def __getBolus(self, raw, tz):
        meal = self.__get_treatments(raw, "type", "MEAL")
        meal_carbs = self.__get_dict_values(meal, "timestamp", "amount")
        insulin = self.__get_treatments(raw, "type", "INSULIN")
        recomm = self.__get_treatments(insulin, "activationType", "RECOMMENDED")
        recomm_insulin = self.__get_dict_values(recomm, "timestamp", "deliveredFastAmount")
        bolus_carbs = self.__get_carbs(recomm_insulin, meal_carbs)
        return self.__getMealEntries(bolus_carbs, tz)

    def __getAutoBolus(self, raw, tz):
        insulin = self.__get_treatments(raw, "type", "INSULIN")
        autocorr = self.__get_treatments(insulin, "activationType", "AUTOCORRECTION")
        return self.__getAutoBolusEntries(autocorr, tz)

    def __getBasal(self, raw, tz):
        basal = self.__get_treatments(raw, "type", "AUTO_BASAL_DELIVERY")
        return self.__getBasalEntries(basal, tz)

    def __getSGS(self, raw, tz):
        sgs = self.__get_treatments(raw, "sensorState", "NO_ERROR_MESSAGE")
        return self.__getSGSEntries(sgs, tz)

    def __getBasalEntries(self, raw, tz):
        result = []
        for basal in raw:
            _, date_string = self.__getDataStringFromIso(basal["timestamp"], tz)
            result.append(
                {
                    "enteredBy": NS_USER_AGENT,
                    "eventType": "Temp Basal",
                    "duration": 5,
                    "absolute": basal["data"]["dataValues"]["bolusAmount"],
                    "created_at": date_string,
                }
            )
        return result

    def __getAutoBolusEntries(self, raw, tz):
        result = []
        for corr in raw:
            date, date_string = self.__getDataStringFromIso(corr["timestamp"], tz)
            result.append(
                {
                    "device": NS_USER_AGENT,
                    "timestamp": date,
                    "enteredBy": NS_USER_AGENT,
                    "created_at": date_string,
                    "eventType": "Correction Bolus",
                    "insulin": corr["data"]["dataValues"]["deliveredFastAmount"],
                }
            )
        return result

    def __getMealEntries(self, meals, tz):
        result = []
        for time, info in meals.items():
            date, date_string = self.__getDataStringFromIso(time, tz)
            result.append(
                {
                    "timestamp": date,
                    "enteredBy": NS_USER_AGENT,
                    "created_at": date_string,
                    "eventType": "Meal",
                    "glucoseType": "sensor",
                    "carbs": info["carb"],
                    "insulin": info["insulin"],
                }
            )
        return result

    def __ns_trend(self, present, past):
        if present["sg"] == 0 or past["sg"] == 0:
            return "null", "null"
        delta = present["sg"] - past["sg"]
        if delta == 0:
            trend = "Flat"
        elif delta < -30:
            trend = "TripleDown"
        elif delta < -15:
            trend = "DoubleDown"
        elif delta < -5:
            trend = "SingleDown"
        elif delta < 0:
            trend = "FortyFiveDown"
        elif delta > 30:
            trend = "TripleUp"
        elif delta > 15:
            trend = "DoubleUp"
        elif delta > 5:
            trend = "SingleUp"
        elif delta > 0:
            trend = "FortyFiveUp"
        else:
            trend = "NOT COMPUTABLE"
        return trend, delta

    def __getDeviceStatus(self, rawdata):
        return [
            {
                "device": rawdata["medicalDeviceInformation"]["modelNumber"],
                "pump": {
                    "battery": {"status": rawdata["conduitBatteryStatus"], "voltage": rawdata["conduitBatteryLevel"]},
                    "reservoir": rawdata["activeInsulin"]["amount"],
                    "status": {"status": rawdata["systemStatusMessage"], "suspended": rawdata["pumpSuspended"]},
                },
            }
        ]

    def __getSGSEntries(self, sgs, tz):
        result = []
        trend, delta = "null", "null"
        for count, sg in enumerate(sgs):
            if count == 0:
                # No previous reading available for the first entry.
                trend, delta = "null", "null"
            else:
                try:
                    trend, delta = self.__ns_trend(sgs[count], sgs[count - 1])
                except Exception as error:
                    _LOGGER.warning(
                        "Nightscout: Failed to compute trend for SGS entry %d: %s",
                        count,
                        error,
                    )
                    trend, delta = "null", "null"
            date, date_string = self.__getDataStringFromIso(sg["timestamp"], tz)
            result.append(
                {
                    "device": NS_USER_AGENT,
                    "direction": trend,
                    "delta": delta,
                    "type": "sgv",
                    "sgv": float(sg["sg"]),
                    "date": date,
                    "dateString": date_string,
                    "noise": 1,
                }
            )
        return result

    async def __slice_recent_data_for_transmission(self, recent_data, tz):
        # Device status
        if await self.__upload_section("device status", self.__getDeviceStatus, "devicestatus", recent_data):
            printdbg("sending device status was ok")

        # SGS entries
        sgs = recent_data.get("sgs")
        if sgs is not None:
            if await self.__upload_section("SGS entries", self.__getSGS, "entries", sgs, tz):
                printdbg("sending SGS entries was ok")
        else:
            printdbg("No SGS data available, skipping upload")

        # Basal, Bolus, Auto-Bolus (markers block)
        markers = recent_data.get("markers")
        if markers is not None:
            if await self.__upload_section("basal", self.__getBasal, "treatments", markers, tz):
                printdbg("sending basal was ok")
            if await self.__upload_section("meal bolus", self.__getBolus, "treatments", markers, tz):
                printdbg("sending meal bolus was ok")
            if await self.__upload_section("auto bolus", self.__getAutoBolus, "treatments", markers, tz):
                printdbg("sending auto bolus was ok")
        else:
            printdbg("No markers data available, skipping basal/bolus upload")

        # Notifications (notificationHistory block)
        notification_history = recent_data.get("notificationHistory")
        if notification_history is not None:
            if await self.__upload_section("alarms", self.__getAlarms, "treatments", notification_history, tz):
                printdbg("sending alarm notifications was ok")
            if await self.__upload_section("messages", self.__getMsgs, "treatments", notification_history, tz):
                printdbg("sending message notifications was ok")
            if await self.__upload_section("alerts", self.__getAlerts, "treatments", notification_history, tz):
                printdbg("sending alert notifications was ok")
        else:
            printdbg("No notification history available, skipping notifications upload")

    # Periodic upload to Nightscout
    async def send_recent_data(self, recent_data, timezone):
        printdbg("__send_recent_data()")
        await self.__slice_recent_data_for_transmission(recent_data, timezone)

    async def __test_server_connection(self):
        url = f"{self.__nightscout_url}/api/v1/devicestatus.json"
        try:
            response = await self.fetch_async(url, headers=self.__common_headers, params={})
            if response.status_code == 200:
                self.__is_reachable = True
            elif response.status_code == 401:
                _LOGGER.warning("Nightscout: Server reachable but API secret was rejected (HTTP 401)")
            else:
                _LOGGER.warning("Nightscout: Server returned unexpected HTTP %s", response.status_code)
        except httpx.TimeoutException:
            _LOGGER.warning("Nightscout: Connection timed out to %s", self.__nightscout_url)
        except httpx.ConnectError as error:
            _LOGGER.warning("Nightscout: Cannot reach server at %s: %s", self.__nightscout_url, error)
        except httpx.RequestError as error:
            _LOGGER.warning("Nightscout: Network error connecting to %s: %s", self.__nightscout_url, error)

    # verify connection
    async def reachServer(self):
        """perform reach server check"""
        if not self.__is_reachable:
            await self.__test_server_connection()
        return self.__is_reachable

    def run_in_console(self, data, timezone):
        """If running this module directly"""
        print("Sending...")
        asyncio.run(self.reachServer())
        if self.__is_reachable:
            asyncio.run(
                self.send_recent_data(data, timezone)
            )  # NOSONAR S930 - signature is (self, data, timezone); SonarCloud false positive


if __name__ == "__main__":
    from zoneinfo import ZoneInfo

    test_data = {
        # fill me
    }
    parser = argparse.ArgumentParser(description="Simulate upload process to Nightscout with testdata")
    parser.add_argument("-u", "--url", dest="url", help="Nightscout URL")
    parser.add_argument("-s", "--secret", dest="secret", help="Nightscout API Secret")
    parser.add_argument("-t", "--timezone", dest="timezone", default="UTC", help="Timezone name (e.g. Europe/London)")

    args = parser.parse_args()

    if args.url is None:
        raise ValueError("URL is required")

    if args.secret is None:
        raise ValueError("Secret is required")

    TESTAPI = NightscoutUploader(nightscout_url=args.url, nightscout_secret=args.secret)

    TESTAPI.run_in_console(test_data, ZoneInfo(args.timezone))
