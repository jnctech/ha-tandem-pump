"""Tests for NightscoutUploader — edge cases and None-data branches."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.carelink.nightscout_uploader import NightscoutUploader


UTC = ZoneInfo("UTC")


@pytest.fixture
def uploader() -> NightscoutUploader:
    return NightscoutUploader(
        nightscout_url="https://nightscout.example.com",
        nightscout_secret="testsecret",
    )


# -- __ns_trend ----------------------------------------------------------------


class TestNsTrend:
    """Tests for the __ns_trend private method."""

    def test_flat_when_delta_zero(self, uploader):
        trend, delta = uploader._NightscoutUploader__ns_trend({"sg": 100}, {"sg": 100})
        assert trend == "Flat"
        assert delta == 0

    def test_not_computable_when_sg_zero(self, uploader):
        trend, delta = uploader._NightscoutUploader__ns_trend({"sg": 0}, {"sg": 100})
        assert trend == "null"

    def test_triple_up(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 180}, {"sg": 140})
        assert trend == "TripleUp"

    def test_double_up(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 140}, {"sg": 120})
        assert trend == "DoubleUp"

    def test_single_up(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 115}, {"sg": 108})
        assert trend == "SingleUp"

    def test_forty_five_up(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 102}, {"sg": 100})
        assert trend == "FortyFiveUp"

    def test_forty_five_down(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 98}, {"sg": 100})
        assert trend == "FortyFiveDown"

    def test_single_down(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 93}, {"sg": 100})
        assert trend == "SingleDown"

    def test_double_down(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 80}, {"sg": 100})
        assert trend == "DoubleDown"

    def test_triple_down(self, uploader):
        trend, _ = uploader._NightscoutUploader__ns_trend({"sg": 60}, {"sg": 100})
        assert trend == "TripleDown"


# -- send_recent_data None-branch paths ----------------------------------------


class TestSendRecentDataNoneBranches:
    """send_recent_data skips sections whose data key is None."""

    def _minimal(self):
        return {
            "medicalDeviceInformation": {"modelNumber": "MMT-1780"},
            "conduitBatteryStatus": "NORMAL",
            "conduitBatteryLevel": 100,
            "activeInsulin": {"amount": 2.5},
            "systemStatusMessage": "OK",
            "pumpSuspended": False,
            "sgs": None,
            "markers": None,
            "notificationHistory": None,
        }

    async def test_none_sgs_not_uploaded(self, uploader):
        with patch.object(uploader, "_NightscoutUploader__upload_section", new=AsyncMock(return_value=True)) as mock_up:
            await uploader.send_recent_data(self._minimal(), UTC)
        calls = [c.args[0] for c in mock_up.call_args_list]
        assert "SGS entries" not in calls

    async def test_none_markers_not_uploaded(self, uploader):
        with patch.object(uploader, "_NightscoutUploader__upload_section", new=AsyncMock(return_value=True)) as mock_up:
            await uploader.send_recent_data(self._minimal(), UTC)
        calls = [c.args[0] for c in mock_up.call_args_list]
        assert "basal" not in calls
        assert "meal bolus" not in calls

    async def test_none_notifications_not_uploaded(self, uploader):
        with patch.object(uploader, "_NightscoutUploader__upload_section", new=AsyncMock(return_value=True)) as mock_up:
            await uploader.send_recent_data(self._minimal(), UTC)
        calls = [c.args[0] for c in mock_up.call_args_list]
        assert "alarms" not in calls

    async def test_device_status_always_sent(self, uploader):
        with patch.object(uploader, "_NightscoutUploader__upload_section", new=AsyncMock(return_value=True)) as mock_up:
            await uploader.send_recent_data(self._minimal(), UTC)
        calls = [c.args[0] for c in mock_up.call_args_list]
        assert "device status" in calls


# -- __getSGSEntries trend exception recovery ----------------------------------


class TestSGSEntriesTrendException:
    def test_trend_exception_falls_back_to_null(self, uploader):
        sgs = [
            {"sg": 100, "timestamp": "2024-01-15T12:00:00.000Z"},
            {"sg": 110, "timestamp": "2024-01-15T12:05:00.000Z"},
        ]
        with patch.object(uploader, "_NightscoutUploader__ns_trend", side_effect=Exception("fail")):
            result = uploader._NightscoutUploader__getSGSEntries(sgs, UTC)
        assert result[1]["direction"] == "null"


# -- __getMsgEntries string/None faultId ---------------------------------------


class TestGetMsgEntriesEdgeCases:
    def test_string_fault_id_does_not_raise(self, uploader):
        msgs = [{"dateTime": "2024-01-15T12:00:00.000Z", "faultId": "ABC_CODE"}]
        result = uploader._NightscoutUploader__getMsgEntries(msgs, UTC)
        assert len(result) == 1

    def test_none_fault_id_handled(self, uploader):
        msgs = [{"dateTime": "2024-01-15T12:00:00.000Z", "faultId": None}]
        result = uploader._NightscoutUploader__getMsgEntries(msgs, UTC)
        assert len(result) == 1

    def test_additional_info_sg_included(self, uploader):
        msgs = [
            {
                "dateTime": "2024-01-15T12:00:00.000Z",
                "faultId": None,
                "additionalInfo": {"sg": 120},
            }
        ]
        result = uploader._NightscoutUploader__getMsgEntries(msgs, UTC)
        assert result[0]["glucose"] == 120.0
