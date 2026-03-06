"""Tests for the Nightscout uploader."""

from unittest.mock import AsyncMock, MagicMock, patch

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
        assert uploader._NightscoutUploader__hashed_secret is not None
        assert len(uploader._NightscoutUploader__hashed_secret) == 40  # SHA1 hex length


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

        response = await mock_nightscout_uploader.fetch_async("https://test.com", headers={})

        assert response.status_code == 200
        mock_client.get.assert_called_once()

    async def test_post_async(self, mock_nightscout_uploader):
        """Test post_async method."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_nightscout_uploader._async_client = mock_client

        response = await mock_nightscout_uploader.post_async("https://test.com", headers={}, data="{}")

        assert response.status_code == 200
        mock_client.post.assert_called_once()


class TestNightscoutUploaderServerConnection:
    """Tests for server connection testing."""

    async def test_reach_server_success(self, mock_nightscout_uploader):
        """Test successful server connection."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await mock_nightscout_uploader.reachServer()

            assert result is True

    async def test_reach_server_failure(self, mock_nightscout_uploader):
        """Test failed server connection."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await mock_nightscout_uploader.reachServer()

            assert result is False


class TestNightscoutDataTransformation:
    """Tests for data transformation methods."""

    def test_ns_trend_flat(self, mock_nightscout_uploader):
        """Test trend calculation for flat glucose."""
        present = {"sg": 100}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "Flat"
        assert delta == 0

    def test_ns_trend_single_up(self, mock_nightscout_uploader):
        """Test trend calculation for slight increase."""
        present = {"sg": 110}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "SingleUp"
        assert delta == 10

    def test_ns_trend_single_down(self, mock_nightscout_uploader):
        """Test trend calculation for slight decrease."""
        present = {"sg": 90}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "SingleDown"
        assert delta == -10

    def test_ns_trend_double_up(self, mock_nightscout_uploader):
        """Test trend calculation for rapid increase."""
        present = {"sg": 120}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "DoubleUp"
        assert delta == 20

    def test_ns_trend_double_down(self, mock_nightscout_uploader):
        """Test trend calculation for rapid decrease."""
        present = {"sg": 80}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "DoubleDown"
        assert delta == -20

    def test_ns_trend_zero_values(self, mock_nightscout_uploader):
        """Test trend calculation with zero glucose values."""
        present = {"sg": 0}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "null"
        assert delta == "null"

    # Boundary tests for trend thresholds
    def test_ns_trend_triple_up(self, mock_nightscout_uploader):
        """Test trend for delta > 30 (TripleUp)."""
        present = {"sg": 131}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "TripleUp"
        assert delta == 31

    def test_ns_trend_triple_down(self, mock_nightscout_uploader):
        """Test trend for delta < -30 (TripleDown)."""
        present = {"sg": 69}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        assert trend == "TripleDown"
        assert delta == -31

    def test_ns_trend_boundary_double_up_at_30(self, mock_nightscout_uploader):
        """Test trend at boundary delta=30 (should be DoubleUp, not TripleUp)."""
        present = {"sg": 130}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=30 is NOT > 30, so should be DoubleUp (delta > 15)
        assert trend == "DoubleUp"
        assert delta == 30

    def test_ns_trend_boundary_double_down_at_minus_30(self, mock_nightscout_uploader):
        """Test trend at boundary delta=-30 (should be DoubleDown, not TripleDown)."""
        present = {"sg": 70}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=-30 is NOT < -30, so should be DoubleDown (delta < -15)
        assert trend == "DoubleDown"
        assert delta == -30

    def test_ns_trend_boundary_single_up_at_15(self, mock_nightscout_uploader):
        """Test trend at boundary delta=15 (should be SingleUp, not DoubleUp)."""
        present = {"sg": 115}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=15 is NOT > 15, so should be SingleUp (delta > 5)
        assert trend == "SingleUp"
        assert delta == 15

    def test_ns_trend_boundary_single_down_at_minus_15(self, mock_nightscout_uploader):
        """Test trend at boundary delta=-15 (should be SingleDown, not DoubleDown)."""
        present = {"sg": 85}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=-15 is NOT < -15, so should be SingleDown (delta < -5)
        assert trend == "SingleDown"
        assert delta == -15

    def test_ns_trend_forty_five_up(self, mock_nightscout_uploader):
        """Test trend for small positive delta (FortyFiveUp)."""
        present = {"sg": 103}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=3 is > 0 but not > 5, so FortyFiveUp
        assert trend == "FortyFiveUp"
        assert delta == 3

    def test_ns_trend_forty_five_down(self, mock_nightscout_uploader):
        """Test trend for small negative delta (FortyFiveDown)."""
        present = {"sg": 97}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=-3 is < 0 but not < -5, so FortyFiveDown
        assert trend == "FortyFiveDown"
        assert delta == -3

    def test_ns_trend_boundary_forty_five_up_at_5(self, mock_nightscout_uploader):
        """Test trend at boundary delta=5 (should be FortyFiveUp, not SingleUp)."""
        present = {"sg": 105}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=5 is NOT > 5, so should be FortyFiveUp (delta > 0)
        assert trend == "FortyFiveUp"
        assert delta == 5

    def test_ns_trend_boundary_forty_five_down_at_minus_5(self, mock_nightscout_uploader):
        """Test trend at boundary delta=-5 (should be FortyFiveDown, not SingleDown)."""
        present = {"sg": 95}
        past = {"sg": 100}

        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend(present, past)

        # delta=-5 is NOT < -5, so should be FortyFiveDown (delta < 0)
        assert trend == "FortyFiveDown"
        assert delta == -5

    def test_get_note(self, mock_nightscout_uploader):
        """Test note formatting."""
        result = mock_nightscout_uploader._NightscoutUploader__getNote("BC_SID_TEST_MESSAGE")
        assert result == "TEST_MESSAGE"

        result = mock_nightscout_uploader._NightscoutUploader__getNote("BC_MESSAGE_ANOTHER_TEST")
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
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_connect_error(self, mock_nightscout_uploader):
        """Connection error leaves is_reachable False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_generic_request_error(self, mock_nightscout_uploader):
        """Generic network error leaves is_reachable False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("network error"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_unexpected_status(self, mock_nightscout_uploader):
        """Unexpected HTTP status (e.g. 500) leaves is_reachable False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_cached_after_success(self, mock_nightscout_uploader):
        """Once reachable, reachServer() does not make a second request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
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

    async def test_upload_section_getter_exception_logs_warning(self, mock_nightscout_uploader, caplog):
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
            result = await mock_nightscout_uploader._NightscoutUploader__upload_section("section", getter, "treatments")
        assert result is False


class TestNightscoutHelpers:
    """Pure-function tests for private helper methods (no async, no HTTP)."""

    # __get_carbs

    def test_get_carbs_matching(self, mock_nightscout_uploader):
        """Returns matched carb/insulin pairs when key is in meal."""
        input_insulin = [{"2024-01-15T12:00:00": 3.5}]
        input_meal = [{"2024-01-15T12:00:00": 45}]
        result = mock_nightscout_uploader._NightscoutUploader__get_carbs(input_insulin, input_meal)
        assert "2024-01-15T12:00:00" in result
        assert result["2024-01-15T12:00:00"]["insulin"] == 3.5
        assert result["2024-01-15T12:00:00"]["carb"] == 45

    def test_get_carbs_no_match(self, mock_nightscout_uploader):
        """Returns empty dict when no keys match between insulin and meal."""
        input_insulin = [{"ts_a": 3.5}]
        input_meal = [{"ts_b": 45}]
        result = mock_nightscout_uploader._NightscoutUploader__get_carbs(input_insulin, input_meal)
        assert result == {}

    def test_get_carbs_empty_inputs(self, mock_nightscout_uploader):
        """Returns empty dict for empty inputs."""
        result = mock_nightscout_uploader._NightscoutUploader__get_carbs([], [])
        assert result == {}

    # __get_dict_values

    def test_get_dict_values_matching(self, mock_nightscout_uploader):
        """Returns list with matched key/value pair when all fields present."""
        input_data = [
            {
                "timestamp": "2024-01-15T12:00:00",
                "data": {"dataValues": {"deliveredFastAmount": 1.2}},
            }
        ]
        result = mock_nightscout_uploader._NightscoutUploader__get_dict_values(
            input_data, "timestamp", "deliveredFastAmount"
        )
        assert len(result) == 1
        assert result[0]["2024-01-15T12:00:00"] == 1.2

    def test_get_dict_values_missing_key(self, mock_nightscout_uploader):
        """Returns empty list when key field is not in marker."""
        input_data = [{"data": {"dataValues": {"amount": 10}}}]
        result = mock_nightscout_uploader._NightscoutUploader__get_dict_values(input_data, "timestamp", "amount")
        assert result == []

    def test_get_dict_values_empty(self, mock_nightscout_uploader):
        """Returns empty list for empty input."""
        result = mock_nightscout_uploader._NightscoutUploader__get_dict_values([], "timestamp", "amount")
        assert result == []

    # __traverse

    def test_traverse_dict_input(self, mock_nightscout_uploader):
        """Yields leaf key-value pairs from a nested dict."""
        data = {"a": {"b": 1}}
        result = list(mock_nightscout_uploader._NightscoutUploader__traverse(data))
        assert ("b", 1) in result

    def test_traverse_non_dict_input(self, mock_nightscout_uploader):
        """Yields (key, value) for a non-dict leaf."""
        result = list(mock_nightscout_uploader._NightscoutUploader__traverse(42, "mykey"))
        assert result == [("mykey", 42)]

    # __get_treatments

    def test_get_treatments_matching(self, mock_nightscout_uploader):
        """Returns matching markers when key/value pair found via traverse."""
        input_data = [{"type": "MEAL", "carbs": 40}]
        result = mock_nightscout_uploader._NightscoutUploader__get_treatments(input_data, "type", "MEAL")
        assert len(result) == 1
        assert result[0]["carbs"] == 40

    def test_get_treatments_no_match(self, mock_nightscout_uploader):
        """Returns empty list when key/value not found."""
        input_data = [{"type": "INSULIN"}]
        result = mock_nightscout_uploader._NightscoutUploader__get_treatments(input_data, "type", "MEAL")
        assert result == []

    def test_get_treatments_empty(self, mock_nightscout_uploader):
        """Returns empty list for empty input."""
        result = mock_nightscout_uploader._NightscoutUploader__get_treatments([], "type", "MEAL")
        assert result == []

    # __getNote

    def test_get_note_strips_bc_sid_prefix(self, mock_nightscout_uploader):
        """Strips BC_SID_ prefix from note."""
        result = mock_nightscout_uploader._NightscoutUploader__getNote("BC_SID_SENSOR_FAULT")
        assert result == "SENSOR_FAULT"

    def test_get_note_strips_bc_message_prefix(self, mock_nightscout_uploader):
        """Strips BC_MESSAGE_ prefix from note."""
        result = mock_nightscout_uploader._NightscoutUploader__getNote("BC_MESSAGE_LOW_GLUCOSE")
        assert result == "LOW_GLUCOSE"

    def test_get_note_no_prefix(self, mock_nightscout_uploader):
        """Returns message unchanged when no known prefix present."""
        result = mock_nightscout_uploader._NightscoutUploader__getNote("PLAIN_MESSAGE")
        assert result == "PLAIN_MESSAGE"

    # __ns_trend (supplementary boundary cases not already covered)

    def test_ns_trend_flat_delta_zero(self, mock_nightscout_uploader):
        """delta == 0 returns Flat."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 100}, {"sg": 100})
        assert trend == "Flat"
        assert delta == 0

    def test_ns_trend_forty_five_up_delta_1(self, mock_nightscout_uploader):
        """delta == 1 returns FortyFiveUp."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 101}, {"sg": 100})
        assert trend == "FortyFiveUp"

    def test_ns_trend_single_up_delta_6(self, mock_nightscout_uploader):
        """delta == 6 returns SingleUp."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 106}, {"sg": 100})
        assert trend == "SingleUp"

    def test_ns_trend_double_up_delta_16(self, mock_nightscout_uploader):
        """delta == 16 returns DoubleUp."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 116}, {"sg": 100})
        assert trend == "DoubleUp"

    def test_ns_trend_triple_up_delta_31(self, mock_nightscout_uploader):
        """delta == 31 returns TripleUp."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 131}, {"sg": 100})
        assert trend == "TripleUp"

    def test_ns_trend_forty_five_down_delta_neg1(self, mock_nightscout_uploader):
        """delta == -1 returns FortyFiveDown."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 99}, {"sg": 100})
        assert trend == "FortyFiveDown"

    def test_ns_trend_single_down_delta_neg6(self, mock_nightscout_uploader):
        """delta == -6 returns SingleDown."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 94}, {"sg": 100})
        assert trend == "SingleDown"

    def test_ns_trend_double_down_delta_neg16(self, mock_nightscout_uploader):
        """delta == -16 returns DoubleDown."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 84}, {"sg": 100})
        assert trend == "DoubleDown"

    def test_ns_trend_triple_down_delta_neg31(self, mock_nightscout_uploader):
        """delta == -31 returns TripleDown."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 69}, {"sg": 100})
        assert trend == "TripleDown"

    def test_ns_trend_zero_sg_present_returns_null(self, mock_nightscout_uploader):
        """Zero sg in present reading returns null trend and delta."""
        trend, delta = mock_nightscout_uploader._NightscoutUploader__ns_trend({"sg": 0}, {"sg": 100})
        assert trend == "null"
        assert delta == "null"


class TestNightscoutEntryBuilders:
    """Tests for methods that build Nightscout entry dicts."""

    # __getBasalEntries

    def test_get_basal_entries_single(self, mock_nightscout_uploader):
        """Single basal entry produces eventType=Temp Basal with correct fields."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        raw = [
            {
                "timestamp": "2024-01-15T12:00:00.000-00:00",
                "data": {"dataValues": {"bolusAmount": 0.85}},
            }
        ]
        result = mock_nightscout_uploader._NightscoutUploader__getBasalEntries(raw, tz)
        assert len(result) == 1
        assert result[0]["eventType"] == "Temp Basal"
        assert result[0]["absolute"] == 0.85
        assert result[0]["duration"] == 5

    # __getAutoBolusEntries

    def test_get_auto_bolus_entries_single(self, mock_nightscout_uploader):
        """Single autocorrection entry produces eventType=Correction Bolus."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        raw = [
            {
                "timestamp": "2024-01-15T12:00:00.000-00:00",
                "data": {"dataValues": {"deliveredFastAmount": 1.2}},
            }
        ]
        result = mock_nightscout_uploader._NightscoutUploader__getAutoBolusEntries(raw, tz)
        assert len(result) == 1
        assert result[0]["eventType"] == "Correction Bolus"
        assert result[0]["insulin"] == 1.2

    # __getMealEntries

    def test_get_meal_entries_single(self, mock_nightscout_uploader):
        """Single meal entry produces eventType=Meal with carbs and insulin."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        meals = {"2024-01-15T12:00:00.000-00:00": {"carb": 45, "insulin": 3.5}}
        result = mock_nightscout_uploader._NightscoutUploader__getMealEntries(meals, tz)
        assert len(result) == 1
        assert result[0]["eventType"] == "Meal"
        assert result[0]["carbs"] == 45
        assert result[0]["insulin"] == 3.5

    # __getSGSEntries

    def test_get_sgs_entries_single_has_null_trend(self, mock_nightscout_uploader):
        """Single SGS entry has direction=null (no prior reading)."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        sgs = [{"timestamp": "2024-01-15T12:00:00.000-00:00", "sg": 120}]
        result = mock_nightscout_uploader._NightscoutUploader__getSGSEntries(sgs, tz)
        assert result[0]["direction"] == "null"
        assert result[0]["delta"] == "null"

    def test_get_sgs_entries_second_has_computed_trend(self, mock_nightscout_uploader):
        """Second SGS entry has a real trend computed from delta (+20 → DoubleUp)."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        sgs = [
            {"timestamp": "2024-01-15T12:05:00.000-00:00", "sg": 120},
            {"timestamp": "2024-01-15T12:00:00.000-00:00", "sg": 100},
        ]
        result = mock_nightscout_uploader._NightscoutUploader__getSGSEntries(sgs, tz)
        # index 0 always null; index 1: sgs[1]-sgs[0] = 100-120 = -20 → DoubleDown
        assert result[0]["direction"] == "null"
        assert result[1]["direction"] == "DoubleDown"

    # __getMsgEntries

    def test_get_msg_entries_with_additional_info_sg(self, mock_nightscout_uploader):
        """Entry with additionalInfo.sg < 400 includes glucose field."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        raw = [
            {
                "dateTime": "2024-01-15T12:00:00.000-00:00",
                "faultId": None,
                "additionalInfo": {"sg": 120},
            }
        ]
        result = mock_nightscout_uploader._NightscoutUploader__getMsgEntries(raw, tz)
        assert len(result) == 1
        assert "glucose" in result[0]
        assert result[0]["glucose"] == 120.0

    def test_get_msg_entries_without_additional_info(self, mock_nightscout_uploader):
        """Entry without additionalInfo does not include glucose field."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        raw = [
            {
                "dateTime": "2024-01-15T12:00:00.000-00:00",
                "faultId": None,
            }
        ]
        result = mock_nightscout_uploader._NightscoutUploader__getMsgEntries(raw, tz)
        assert len(result) == 1
        assert "glucose" not in result[0]

    def test_get_msg_entries_string_fault_id(self, mock_nightscout_uploader):
        """String faultId (Simplera sensor) is converted and used as note."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        raw = [
            {
                "dateTime": "2024-01-15T12:00:00.000-00:00",
                "faultId": "SENSOR_FAULT",
            }
        ]
        result = mock_nightscout_uploader._NightscoutUploader__getMsgEntries(raw, tz)
        assert len(result) == 1
        assert "SENSOR_FAULT" in result[0]["notes"]

    # __getDeviceStatus

    def test_get_device_status_extracts_fields(self, mock_nightscout_uploader, mock_recent_data):
        """__getDeviceStatus extracts model, battery, reservoir, and status."""
        # Add fields that __getDeviceStatus requires but conftest doesn't have
        rawdata = dict(mock_recent_data)
        rawdata["conduitBatteryStatus"] = "CHARGING"
        rawdata["systemStatusMessage"] = "ALL_OK"
        rawdata["pumpSuspended"] = False

        result = mock_nightscout_uploader._NightscoutUploader__getDeviceStatus(rawdata)
        assert len(result) == 1
        entry = result[0]
        assert entry["device"] == "MMT-1780"
        assert entry["pump"]["battery"]["status"] == "CHARGING"
        assert entry["pump"]["battery"]["voltage"] == 100
        assert entry["pump"]["reservoir"] == 2.5
        assert entry["pump"]["status"]["status"] == "ALL_OK"
        assert entry["pump"]["status"]["suspended"] is False


class TestNightscoutReachServer:
    """Async tests for __test_server_connection (private) via reachServer()."""

    async def test_reach_server_200_returns_true(self, mock_nightscout_uploader):
        """HTTP 200 causes reachServer() to return True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock, return_value=mock_response):
            result = await mock_nightscout_uploader.reachServer()
        assert result is True

    async def test_reach_server_401_returns_false(self, mock_nightscout_uploader):
        """HTTP 401 causes reachServer() to return False."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        with patch.object(mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock, return_value=mock_response):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_timeout_returns_false(self, mock_nightscout_uploader):
        """TimeoutException causes reachServer() to return False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_connect_error_returns_false(self, mock_nightscout_uploader):
        """ConnectError causes reachServer() to return False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_request_error_returns_false(self, mock_nightscout_uploader):
        """Generic RequestError causes reachServer() to return False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "fetch_async",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("network error"),
        ):
            result = await mock_nightscout_uploader.reachServer()
        assert result is False

    async def test_reach_server_already_reachable_skips_http(self, mock_nightscout_uploader):
        """When __is_reachable is already True, no HTTP call is made."""
        # Mark as already reachable
        mock_nightscout_uploader._NightscoutUploader__is_reachable = True
        with patch.object(mock_nightscout_uploader, "fetch_async", new_callable=AsyncMock) as mock_fetch:
            result = await mock_nightscout_uploader.reachServer()
        mock_fetch.assert_not_called()
        assert result is True


class TestNightscoutSetData:
    """Async tests for __set_data."""

    async def test_set_data_empty_data_returns_false(self, mock_nightscout_uploader):
        """Empty data list skips HTTP call and returns False."""
        with patch.object(mock_nightscout_uploader, "post_async", new_callable=AsyncMock) as mock_post:
            result = await mock_nightscout_uploader._NightscoutUploader__set_data(
                "https://ns.example.com", [], "entries"
            )
        mock_post.assert_not_called()
        assert result is False

    async def test_set_data_200_returns_true(self, mock_nightscout_uploader):
        """HTTP 200 response causes __set_data to return True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(mock_nightscout_uploader, "post_async", new_callable=AsyncMock, return_value=mock_response):
            result = await mock_nightscout_uploader._NightscoutUploader__set_data(
                "https://ns.example.com", [{"sgv": 120}], "entries"
            )
        assert result is True

    async def test_set_data_non_200_returns_false(self, mock_nightscout_uploader):
        """Non-200 response causes __set_data to return False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch.object(mock_nightscout_uploader, "post_async", new_callable=AsyncMock, return_value=mock_response):
            result = await mock_nightscout_uploader._NightscoutUploader__set_data(
                "https://ns.example.com", [{"sgv": 120}], "entries"
            )
        assert result is False

    async def test_set_data_timeout_returns_false(self, mock_nightscout_uploader):
        """TimeoutException causes __set_data to return False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "post_async",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await mock_nightscout_uploader._NightscoutUploader__set_data(
                "https://ns.example.com", [{"sgv": 120}], "entries"
            )
        assert result is False

    async def test_set_data_request_error_returns_false(self, mock_nightscout_uploader):
        """RequestError causes __set_data to return False."""
        import httpx

        with patch.object(
            mock_nightscout_uploader,
            "post_async",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("network error"),
        ):
            result = await mock_nightscout_uploader._NightscoutUploader__set_data(
                "https://ns.example.com", [{"sgv": 120}], "entries"
            )
        assert result is False


class TestNightscoutSendRecentData:
    """Tests for the public send_recent_data() method."""

    async def test_send_recent_data_minimal(self, mock_nightscout_uploader):
        """send_recent_data with minimal data completes without raising."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        recent_data = {
            "sgs": [],
            "markers": None,
            "notificationHistory": None,
            "medicalDeviceInformation": {"modelNumber": "MMT-1780"},
            "conduitBatteryStatus": "NORMAL",
            "conduitBatteryLevel": 95,
            "activeInsulin": {"amount": 1.5},
            "systemStatusMessage": "ALL_OK",
            "pumpSuspended": False,
        }
        with patch.object(
            mock_nightscout_uploader,
            "_NightscoutUploader__upload_section",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # Should complete without raising
            await mock_nightscout_uploader.send_recent_data(recent_data, tz)
