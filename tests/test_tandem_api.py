"""Tests for the Tandem Source API client."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from custom_components.carelink.tandem_api import (
    TandemSourceClient,
    TandemAuthError,
    TandemApiError,
    parse_dotnet_date,
)


# ═══════════════════════════════════════════════════════════════════════════
# parse_dotnet_date
# ═══════════════════════════════════════════════════════════════════════════


class TestParseDotnetDate:
    """Tests for the parse_dotnet_date helper function."""

    def test_basic_dotnet_format(self):
        """Test parsing /Date(epoch_ms)/ format returns UTC-aware datetime."""
        result = parse_dotnet_date("/Date(1705320000000)/")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_dotnet_format_with_positive_offset(self):
        """Test parsing /Date(epoch_ms+0200)/ format returns UTC-aware datetime."""
        result = parse_dotnet_date("/Date(1705320000000+0200)/")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_dotnet_format_with_negative_offset(self):
        """Test parsing /Date(epoch_ms-0500)/ format returns UTC-aware datetime."""
        result = parse_dotnet_date("/Date(1705320000000-0500)/")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_iso8601_format(self):
        """Test parsing ISO 8601 format returns UTC-aware datetime."""
        result = parse_dotnet_date("2024-01-15T12:00:00Z")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_iso8601_with_offset(self):
        """Test parsing ISO 8601 with timezone offset converts to UTC."""
        result = parse_dotnet_date("2024-01-15T12:00:00+02:00")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        # +02:00 means the UTC time is 10:00
        assert result.hour == 10

    def test_none_input(self):
        """Test that None input returns None."""
        assert parse_dotnet_date(None) is None

    def test_empty_string(self):
        """Test that empty string returns None."""
        assert parse_dotnet_date("") is None

    def test_invalid_string(self):
        """Test that garbage input returns None."""
        assert parse_dotnet_date("not-a-date") is None

    def test_zero_epoch(self):
        """Test /Date(0)/ parses as Unix epoch."""
        result = parse_dotnet_date("/Date(0)/")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.year == 1970

    def test_integer_input(self):
        """Test that integer input is treated as epoch seconds."""
        result = parse_dotnet_date(12345)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None


# ═══════════════════════════════════════════════════════════════════════════
# TandemSourceClient construction
# ═══════════════════════════════════════════════════════════════════════════


class TestTandemSourceClientInit:
    """Tests for TandemSourceClient initialization."""

    def test_init_eu_region(self):
        """Test EU region URL configuration."""
        client = TandemSourceClient("user@test.com", "pass", region="EU")
        assert client.region == "EU"
        assert "eu" in client.urls["SOURCE_URL"]
        assert client.email == "user@test.com"

    def test_init_us_region(self):
        """Test US region URL configuration."""
        client = TandemSourceClient("user@test.com", "pass", region="US")
        assert client.region == "US"
        assert "eu" not in client.urls["SOURCE_URL"]

    def test_init_default_region(self):
        """Test default region is EU."""
        client = TandemSourceClient("user@test.com", "pass")
        assert client.region == "EU"

    def test_initial_state(self):
        """Test that client starts with no tokens."""
        client = TandemSourceClient("user@test.com", "pass")
        assert client.access_token is None
        assert client.pumper_id is None
        assert client.account_id is None


# ═══════════════════════════════════════════════════════════════════════════
# TandemSourceClient._get_client (async SSL context creation)
# ═══════════════════════════════════════════════════════════════════════════


class TestTandemSourceClientGetClient:
    """Tests for async HTTP client creation."""

    async def test_get_client_creates_async_client(self):
        """Test that _get_client creates an httpx.AsyncClient."""
        client = TandemSourceClient("user@test.com", "pass")
        http_client = await client._get_client()

        assert isinstance(http_client, httpx.AsyncClient)
        assert not http_client.is_closed

        await client.close()

    async def test_get_client_reuses_existing(self):
        """Test that _get_client returns the same client on repeated calls."""
        client = TandemSourceClient("user@test.com", "pass")
        http_client1 = await client._get_client()
        http_client2 = await client._get_client()

        assert http_client1 is http_client2

        await client.close()

    async def test_get_client_recreates_after_close(self):
        """Test that _get_client creates new client after close."""
        client = TandemSourceClient("user@test.com", "pass")
        http_client1 = await client._get_client()
        await client.close()

        http_client2 = await client._get_client()
        assert http_client1 is not http_client2

        await client.close()


# ═══════════════════════════════════════════════════════════════════════════
# TandemSourceClient.close
# ═══════════════════════════════════════════════════════════════════════════


class TestTandemSourceClientClose:
    """Tests for client cleanup."""

    async def test_close_active_client(self):
        """Test closing an active HTTP client."""
        client = TandemSourceClient("user@test.com", "pass")
        await client._get_client()
        assert client._client is not None

        await client.close()
        assert client._client is None

    async def test_close_no_client(self):
        """Test closing when no client was created."""
        client = TandemSourceClient("user@test.com", "pass")
        await client.close()  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════
# TandemSourceClient PKCE helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestPKCEHelpers:
    """Tests for PKCE code generation."""

    def test_generate_code_verifier_length(self):
        """Test code verifier is proper length."""
        verifier = TandemSourceClient._generate_code_verifier()
        # Base64 of 64 random bytes, stripped of padding
        assert len(verifier) > 40

    def test_generate_code_verifier_uniqueness(self):
        """Test code verifiers are unique."""
        v1 = TandemSourceClient._generate_code_verifier()
        v2 = TandemSourceClient._generate_code_verifier()
        assert v1 != v2

    def test_generate_code_challenge(self):
        """Test code challenge is derived from verifier."""
        verifier = "test_verifier_string"
        challenge = TandemSourceClient._generate_code_challenge(verifier)
        assert isinstance(challenge, str)
        # S256 challenge should be base64url encoded SHA256 hash
        assert len(challenge) > 0
        # Should not contain padding
        assert "=" not in challenge


# ═══════════════════════════════════════════════════════════════════════════
# TandemSourceClient._api_get
# ═══════════════════════════════════════════════════════════════════════════


class TestApiGet:
    """Tests for authenticated API requests."""

    async def test_api_get_success(self):
        """Test successful GET request."""
        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._client = mock_http

        result = await client._api_get("https://api.test.com/data")

        assert result == {"key": "value"}
        mock_http.get.assert_called_once()

    async def test_api_get_401_retries_login(self):
        """Test that 401 triggers re-login and retry."""
        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "expired_token"

        mock_401 = MagicMock()
        mock_401.status_code = 401

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"key": "value"}

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=[mock_401, mock_200])
        mock_http.is_closed = False
        client._client = mock_http

        async def _mock_login():
            client.access_token = "new_token"

        with patch.object(client, "login", new_callable=AsyncMock, side_effect=_mock_login):
            result = await client._api_get("https://api.test.com/data")

        assert result == {"key": "value"}
        assert mock_http.get.call_count == 2

    async def test_api_get_non_200_raises_error(self):
        """Test that non-200/non-401 status raises TandemApiError."""
        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid_token"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemApiError, match="500"):
            await client._api_get("https://api.test.com/data")


# ═══════════════════════════════════════════════════════════════════════════
# TandemSourceClient.get_recent_data
# ═══════════════════════════════════════════════════════════════════════════


class TestGetRecentData:
    """Tests for the get_recent_data aggregation method."""

    async def test_get_recent_data_success(self):
        """Test successful aggregation of all data sources."""
        client = TandemSourceClient("user@test.com", "pass")
        client.pumper_id = "pump-123"
        client.account_id = "acct-456"
        client.access_token = "valid_token"

        with patch.object(
            client, "get_pump_event_metadata", new_callable=AsyncMock,
            return_value=[{"serialNumber": "SN123", "modelNumber": "t:slim X2"}],
        ), patch.object(
            client, "get_pumper_info", new_callable=AsyncMock,
            return_value={"firstName": "Test", "lastName": "User"},
        ), patch.object(
            client, "get_therapy_timeline", new_callable=AsyncMock,
            return_value={"cgm": [], "bolus": [], "basal": []},
        ), patch.object(
            client, "get_dashboard_summary", new_callable=AsyncMock,
            return_value={"averageReading": 120},
        ):
            data = await client.get_recent_data()

        assert data["pump_metadata"] == {"serialNumber": "SN123", "modelNumber": "t:slim X2"}
        assert data["pumper_info"]["firstName"] == "Test"
        assert data["therapy_timeline"] is not None
        assert data["dashboard_summary"]["averageReading"] == 120

    async def test_get_recent_data_metadata_failure(self):
        """Test graceful handling when metadata fetch fails."""
        client = TandemSourceClient("user@test.com", "pass")
        client.pumper_id = "pump-123"
        client.account_id = "acct-456"
        client.access_token = "valid_token"

        with patch.object(
            client, "get_pump_event_metadata", new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ), patch.object(
            client, "get_pumper_info", new_callable=AsyncMock,
            return_value={"firstName": "Test"},
        ), patch.object(
            client, "get_therapy_timeline", new_callable=AsyncMock,
            return_value=None,
        ), patch.object(
            client, "get_dashboard_summary", new_callable=AsyncMock,
            return_value=None,
        ):
            data = await client.get_recent_data()

        # pump_metadata key exists but stays None after failure
        assert data["pump_metadata"] is None
        assert data["pumper_info"]["firstName"] == "Test"

    async def test_get_recent_data_no_pumper_id(self):
        """Test that missing pumper_id results in None metadata/pumper_info."""
        client = TandemSourceClient("user@test.com", "pass")
        client.pumper_id = None
        client.account_id = "acct-456"
        client.access_token = "valid_token"

        with patch.object(
            client, "get_pump_event_metadata", new_callable=AsyncMock,
            side_effect=Exception("No pumper_id"),
        ), patch.object(
            client, "get_pumper_info", new_callable=AsyncMock,
            side_effect=Exception("No pumper_id"),
        ), patch.object(
            client, "get_therapy_timeline", new_callable=AsyncMock,
            return_value=None,
        ), patch.object(
            client, "get_dashboard_summary", new_callable=AsyncMock,
            return_value=None,
        ):
            data = await client.get_recent_data()

        # Keys exist but are None due to failures
        assert data["pump_metadata"] is None
        assert data["pumper_info"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Exception classes
# ═══════════════════════════════════════════════════════════════════════════


class TestExceptions:
    """Tests for custom exception classes."""

    def test_tandem_auth_error(self):
        """Test TandemAuthError can be raised and caught."""
        with pytest.raises(TandemAuthError, match="bad credentials"):
            raise TandemAuthError("bad credentials")

    def test_tandem_api_error(self):
        """Test TandemApiError can be raised and caught."""
        with pytest.raises(TandemApiError, match="server error"):
            raise TandemApiError("server error")


class TestExtractJwtClaims:
    """Tests for _extract_jwt_claims (M2 — narrow exception type)."""

    def _make_client(self):
        return TandemSourceClient("user@test.com", "pass", region="EU")

    def test_invalid_jwt_format_raises(self):
        """JWT with wrong number of parts raises TandemAuthError."""
        client = self._make_client()
        client.id_token = "only.two"
        with pytest.raises(TandemAuthError, match="Invalid JWT format"):
            client._extract_jwt_claims()

    def test_invalid_base64_payload_raises(self):
        """Garbled base64 payload raises TandemAuthError, not bare Exception (M2)."""
        client = self._make_client()
        # Header and signature are irrelevant; payload is invalid base64
        bad_payload = "!!!not-valid-base64!!!"
        client.id_token = f"header.{bad_payload}.signature"
        with pytest.raises(TandemAuthError, match="Cannot decode JWT payload"):
            client._extract_jwt_claims()

    def test_valid_jwt_no_pumper_id_raises(self):
        """JWT with valid base64 but no pumperId raises TandemAuthError."""
        import base64
        import json
        client = self._make_client()
        payload = base64.urlsafe_b64encode(
            json.dumps({"accountId": "acc-1"}).encode()
        ).decode().rstrip("=")
        client.id_token = f"header.{payload}.signature"
        with pytest.raises(TandemAuthError, match="No pumperId"):
            client._extract_jwt_claims()

    def test_valid_jwt_sets_pumper_id(self):
        """Valid JWT payload with pumperId populates client.pumper_id."""
        import base64
        import json
        client = self._make_client()
        payload = base64.urlsafe_b64encode(
            json.dumps({"pumperId": "pump-abc", "accountId": "acc-1"}).encode()
        ).decode().rstrip("=")
        client.id_token = f"header.{payload}.signature"
        client._extract_jwt_claims()
        assert client.pumper_id == "pump-abc"
        assert client.account_id == "acc-1"
