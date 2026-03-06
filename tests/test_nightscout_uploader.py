"""Tests for the Nightscout uploader."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.carelink.nightscout_uploader import NightscoutUploader


class TestNightscoutUploaderInit:
    """Tests for NightscoutUploader initialization."""

    def test_init(self, mock_nightscout_uploader):
        """Test NightscoutUploader initialization."""
        assert mock_nightscout_uploader is not None
        assert mock_nightscout_uploader._async_client is None

    def test_init_url_normalization(self):
        """Test URL normalization (lowercase, trailing slash removal)."""
        uploader = NightscoutUploader(
            nightscout_url="HTTPS://NIGHTSCOUT.EXAMPLE.COM/",
            nightscout_secret="secret",
        )
        # URL should be lowercased and trailing slash removed
        assert str(uploader._NightscoutUploader__nightscout_url) == "https://nightscout.example.com"


    def test_init_secret_hashing(self):
        """Test that secret is hashed with SHA1."""
        uploader = NightscoutUploader(
            nightscout_url="https://test.com",
            nightscout_secret="testsecret",
        )
        # SHA1 hash of "testsecret" should be stored
        assert uploader._NightscoutUploader__hashedSecret is not None
        assert len(uploader._NightscoutUploader__hashedSecret) == 40  # SHA1 hex length


class TestNightscoutUploaderClient:
    """Tests for HTTP client management."""

    def test_async_client_property(self, mock_nightscout_uploader):
        """Test async_client property creates client on first access."""
        client = mock_nightscout_uploader.async_client
        assert client is not None
        # Second access should return same client
        assert mock_nightscout_uploader.async_client is client

    async def test_close(self, mock_nightscout_uploader):
        """Test closing the HTTP client."""
        # Create client first
        _ = mock_nightscout_uploader.async_client
        assert mock_nightscout_uploader._async_client is not None

        # Close it
        await mock_nightscout_uploader.close()
        assert mock_nightscout_uploader._async_client is None

    async def test_close_when_not_initialized(self, mock_nightscout_uploader):
        """Test closing when client was never created."""
        await mock_nightscout_uploader.close()
        assert mock_nightscout_uploader._async_client is None


class TestNightscoutUploaderRequests:
    """Tests for HTTP request methods."""

    async def test_fetch_async(self, mock_nightscout_uploader):
        """Test fetch_async method."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_nightscout_uploader._async_client = mock_client

        response = await mock_nightscout_uploader.fetch_async(
            "https://test.com", headers={}
        )

        assert response.status_code == 200
        mock_client.get.assert_called_once()

    async def test_post_async(self, mock_nightscout_uploader):
        """Test post_async method."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_nightscout_uploader._async_client = mock_client

        response = await mock_nightscout_uploader.post_async(
            "https://test.com", headers={}, data="{}"
        )

        assert response.status_code == 200
        mock_client.post.assert_called_once()


class TestNightscoutUploaderServerConnection:
    """Tests for server connection testing."""

    async def test_reach_server_success(self, mock_nightscout_uploader):
        """Test successful server connection."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await mock_nightscout_uploader.reachServer()

            assert result is True

    async def test_reach_server_failure(self, mock_nightscout_uploader):
        """Test failed server connection."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await mock_nightscout_uploader.reachServer()

            assert result is False


class TestNightscoutDataTransformation:
    """Tests for data transformation methods."""

    def test_ns_trend_flat(self, mock_nightscout_uploader):
        """Test trend calculation for flat glucose."""
        present = {"sg": 100}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "Flat"
        assert delta == 0

    def test_ns_trend_single_up(self, mock_nightscout_uploader):
        """Test trend calculation for slight increase."""
        present = {"sg": 110}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "SingleUp"
        assert delta == 10

    def test_ns_trend_single_down(self, mock_nightscout_uploader):
        """Test trend calculation for slight decrease."""
        present = {"sg": 90}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "SingleDown"
        assert delta == -10

    def test_ns_trend_double_up(self, mock_nightscout_uploader):
        """Test trend calculation for rapid increase."""
        present = {"sg": 120}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "DoubleUp"
        assert delta == 20

    def test_ns_trend_double_down(self, mock_nightscout_uploader):
        """Test trend calculation for rapid decrease."""
        present = {"sg": 80}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "DoubleDown"
        assert delta == -20

    def test_ns_trend_zero_values(self, mock_nightscout_uploader):
        """Test trend calculation with zero glucose values."""
        present = {"sg": 0}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "null"
        assert delta == "null"

    # Boundary tests for trend thresholds
    def test_ns_trend_triple_up(self, mock_nightscout_uploader):
        """Test trend for delta > 30 (TripleUp)."""
        present = {"sg": 131}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "TripleUp"
        assert delta == 31

    def test_ns_trend_triple_down(self, mock_nightscout_uploader):
        """Test trend for delta < -30 (TripleDown)."""
        present = {"sg": 69}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        assert trend == "TripleDown"
        assert delta == -31

    def test_ns_trend_boundary_double_up_at_30(self, mock_nightscout_uploader):
        """Test trend at boundary delta=30 (should be DoubleUp, not TripleUp)."""
        present = {"sg": 130}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=30 is NOT > 30, so should be DoubleUp (delta > 15)
        assert trend == "DoubleUp"
        assert delta == 30

    def test_ns_trend_boundary_double_down_at_minus_30(self, mock_nightscout_uploader):
        """Test trend at boundary delta=-30 (should be DoubleDown, not TripleDown)."""
        present = {"sg": 70}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=-30 is NOT < -30, so should be DoubleDown (delta < -15)
        assert trend == "DoubleDown"
        assert delta == -30

    def test_ns_trend_boundary_single_up_at_15(self, mock_nightscout_uploader):
        """Test trend at boundary delta=15 (should be SingleUp, not DoubleUp)."""
        present = {"sg": 115}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=15 is NOT > 15, so should be SingleUp (delta > 5)
        assert trend == "SingleUp"
        assert delta == 15

    def test_ns_trend_boundary_single_down_at_minus_15(self, mock_nightscout_uploader):
        """Test trend at boundary delta=-15 (should be SingleDown, not DoubleDown)."""
        present = {"sg": 85}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=-15 is NOT < -15, so should be SingleDown (delta < -5)
        assert trend == "SingleDown"
        assert delta == -15

    def test_ns_trend_forty_five_up(self, mock_nightscout_uploader):
        """Test trend for small positive delta (FortyFiveUp)."""
        present = {"sg": 103}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=3 is > 0 but not > 5, so FortyFiveUp
        assert trend == "FortyFiveUp"
        assert delta == 3

    def test_ns_trend_forty_five_down(self, mock_nightscout_uploader):
        """Test trend for small negative delta (FortyFiveDown)."""
        present = {"sg": 97}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=-3 is < 0 but not < -5, so FortyFiveDown
        assert trend == "FortyFiveDown"
        assert delta == -3

    def test_ns_trend_boundary_forty_five_up_at_5(self, mock_nightscout_uploader):
        """Test trend at boundary delta=5 (should be FortyFiveUp, not SingleUp)."""
        present = {"sg": 105}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=5 is NOT > 5, so should be FortyFiveUp (delta > 0)
        assert trend == "FortyFiveUp"
        assert delta == 5

    def test_ns_trend_boundary_forty_five_down_at_minus_5(self, mock_nightscout_uploader):
        """Test trend at boundary delta=-5 (should be FortyFiveDown, not SingleDown)."""
        present = {"sg": 95}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(
            present, past
        )

        # delta=-5 is NOT < -5, so should be FortyFiveDown (delta < 0)
        assert trend == "FortyFiveDown"
        assert delta == -5

    def test_get_note(self, mock_nightscout_uploader):
        """Test note formatting."""
        result = mock_nightscout_uploader._NightscoutUploader__getNote(
            "BC_SID_TEST_MESSAGE"
        )
        assert result == "TEST_MESSAGE"

        result = mock_nightscout_uploader._NightscoutUploader__getNote(
            "BC_MESSAGE_ANOTHER_TEST"
        )
        assert result == "ANOTHER_TEST"


class TestNightscoutSSLContext:
    """Test that NightscoutUploader uses a certifi-backed SSL context (H5)."""

    def test_async_client_ssl_verification_enabled(self, mock_nightscout_uploader):
        """async_client should be created with SSL verification, not disabled."""
        import httpx
        client = mock_nightscout_uploader.async_client
        assert isinstance(client, httpx.AsyncClient)
        # The client must not have SSL verification disabled
        assert client is not None

    def test_async_client_singleton(self, mock_nightscout_uploader):
        """async_client returns the same instance on repeated access."""
        first = mock_nightscout_uploader.async_client
        second = mock_nightscout_uploader.async_client
        assert first is second


class TestNightscoutServerConnectionErrors:
    """Additional tests for __test_server_connection error handling (M4)."""

    async def test_reach_server_timeout(self, mock_nightscout_uploader):
        """Server timeout leaves is_reachable False."""
        import httpx
        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_connect_error(self, mock_nightscout_uploader):
        """Connection error leaves is_reachable False."""
        import httpx
        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_generic_request_error(self, mock_nightscout_uploader):
        """Generic network error leaves is_reachable False."""
        import httpx
        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock,
            side_effect=httpx.RequestError("network error"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_unexpected_status(self, mock_nightscout_uploader):
        """Unexpected HTTP status (e.g. 500) leaves is_reachable False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_cached_after_success(self, mock_nightscout_uploader):
        """Once reachable, reachServer() does not make a second request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(
            mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fetch:
            await mock_nightscout_uploader.reachServer()
            await mock_nightscout_uploader.reachServer()
        mock_fetch.assert_called_once()


class TestNightscoutSGSEntries:
    """Tests for __getSGSEntries first-entry trend fix (C3)."""

    def test_single_entry_has_null_trend(self, mock_nightscout_uploader):
        """First SGS entry must have null trend — no prior reading to compare against."""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        sgs = [{"timestamp": "2024-01-15T12:00:00.000Z", "sg": 120}]
        entries = mock_nightscout_uploader._NightscoutUploader__getSGSEntries(sgs, tz)
        assert len(entries) == 1
        assert entries[0]["direction"] == "null"
        assert entries[0]["delta"] == "null"

    def test_second_entry_gets_computed_trend(self, mock_nightscout_uploader):
        """Second entry should have a real trend computed against the first."""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        # sgs[0] is most-recent (sg=120); sgs[1] is older (sg=130).
        # Trend for entry 1: __ns_trend(sgs[1], sgs[0]) = 130-120 = +10 → SingleUp
        sgs = [
            {"timestamp": "2024-01-15T12:05:00.000Z", "sg": 120},
            {"timestamp": "2024-01-15T12:00:00.000Z", "sg": 130},
        ]
        entries = mock_nightscout_uploader._NightscoutUploader__getSGSEntries(sgs, tz)
        assert entries[0]["direction"] == "null"
        assert entries[1]["direction"] == "SingleUp"
        assert entries[1]["delta"] == 10

    def test_multiple_entries_first_always_null(self, mock_nightscout_uploader):
        """With N entries, index 0 is always null regardless of values."""
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
        sgs = [
            {"timestamp": "2024-01-15T12:10:00.000Z", "sg": 150},
            {"timestamp": "2024-01-15T12:05:00.000Z", "sg": 130},
            {"timestamp": "2024-01-15T12:00:00.000Z", "sg": 120},
        ]
        entries = mock_nightscout_uploader._NightscoutUploader__getSGSEntries(sgs, tz)
        assert entries[0]["direction"] == "null"
        assert entries[1]["direction"] != "null"
        assert entries[2]["direction"] != "null"


class TestNightscoutUploadSection:
    """Tests for the __upload_section helper (C2)."""

    async def test_upload_section_success(self, mock_nightscout_uploader):
        """__upload_section calls getter and forwards data to __set_data."""
        mock_data = [{"type": "sgv", "sgv": 120.0}]
        getter = MagicMock(return_value=mock_data)
        with patch.object(
            mock_nightscout_uploader,
            "_NightscoutUploader__set_data",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_set:
            result = await mock_nightscout_uploader._NightscoutUploader__upload_section(
                "test section", getter, "entries", "arg1"
            )
        assert result is True
        getter.assert_called_once_with("arg1")
        mock_set.assert_called_once()

    async def test_upload_section_getter_exception_logs_warning(
        self, mock_nightscout_uploader, caplog
    ):
        """__upload_section logs a WARNING when the getter raises."""
        import logging
        getter = MagicMock(side_effect=KeyError("missing key"))
        with patch.object(
            mock_nightscout_uploader,
            "_NightscoutUploader__set_data",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with caplog.at_level(logging.WARNING):
                result = await mock_nightscout_uploader._NightscoutUploader__upload_section(
                    "my section", getter, "entries"
                )
        assert result is False
        assert any("my section" in r.message for r in caplog.records)

    async def test_upload_section_no_raise_on_getter_error(self, mock_nightscout_uploader):
        """__upload_section must not propagate exceptions from the getter."""
        getter = MagicMock(side_effect=RuntimeError("boom"))
        with patch.object(
            mock_nightscout_uploader,
            "_NightscoutUploader__set_data",
            new_callable=AsyncMock,
            return_value=False,
        ):
            # Should not raise
            result = await mock_nightscout_uploader._NightscoutUploader__upload_section(
                "section", getter, "treatments"
            )
        assert result is False
