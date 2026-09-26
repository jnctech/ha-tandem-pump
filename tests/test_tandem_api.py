"""Tests for the Tandem Source API client."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from custom_components.tandem.tandem_api import (
    EVT_AA_DAILY_STATUS,
    EVT_AA_PCM_CHANGE,
    EVT_ALARM_ACTIVATED,
    EVT_ALARM_CLEARED,
    EVT_ALERT_ACTIVATED,
    EVT_ALERT_CLEARED,
    EVT_CGM_DATA_G7,
    EVT_CGM_DATA_GXB,
    EVT_CGM_SESSION_JOIN,
    EVT_CGM_SESSION_START,
    EVT_CGM_SESSION_STOP,
    EVT_MALFUNCTION_ACTIVATED,
    EVT_BOLUS_REQUESTED_MSG1,
    EVT_BOLUS_REQUESTED_MSG2,
    EVT_BOLUS_REQUESTED_MSG3,
    EVT_BATTERY_1,
    EVT_DAILY_BASAL,
    EVT_STATUS,
    TandemSourceClient,
    TandemAuthError,
    TandemApiError,
    map_pump_log_event,
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
# TandemSourceClient injected (Home Assistant managed) session
# ═══════════════════════════════════════════════════════════════════════════


class TestTandemSourceClientInjectedSession:
    """An injected session is reused verbatim and never closed by us."""

    async def test_get_client_returns_injected_session(self):
        """_get_client returns the injected client without building its own."""
        injected = AsyncMock(spec=httpx.AsyncClient)
        injected.is_closed = False
        client = TandemSourceClient("user@test.com", "pass", session=injected)

        assert client._owns_client is False
        assert await client._get_client() is injected

    async def test_close_does_not_close_injected_session(self):
        """close() must not aclose a Home-Assistant-owned shared client."""
        injected = AsyncMock(spec=httpx.AsyncClient)
        injected.is_closed = False
        client = TandemSourceClient("user@test.com", "pass", session=injected)

        await client.close()

        injected.aclose.assert_not_called()
        # The injected reference is retained (not nulled) so the client stays usable.
        assert client._client is injected


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

        with (
            patch.object(
                client,
                "get_pump_event_metadata",
                new_callable=AsyncMock,
                return_value=[{"serialNumber": "SN123", "modelNumber": "t:slim X2"}],
            ),
            patch.object(
                client,
                "get_pumper_info",
                new_callable=AsyncMock,
                return_value={"firstName": "Test", "lastName": "User"},
            ),
            patch.object(
                client,
                "get_therapy_timeline",
                new_callable=AsyncMock,
                return_value={"cgm": [], "bolus": [], "basal": []},
            ),
            patch.object(
                client,
                "get_dashboard_summary",
                new_callable=AsyncMock,
                return_value={"averageReading": 120},
            ),
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

        with (
            patch.object(
                client,
                "get_pump_event_metadata",
                new_callable=AsyncMock,
                side_effect=Exception("API error"),
            ),
            patch.object(
                client,
                "get_pumper_info",
                new_callable=AsyncMock,
                return_value={"firstName": "Test"},
            ),
            patch.object(
                client,
                "get_therapy_timeline",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                client,
                "get_dashboard_summary",
                new_callable=AsyncMock,
                return_value=None,
            ),
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

        with (
            patch.object(
                client,
                "get_pump_event_metadata",
                new_callable=AsyncMock,
                side_effect=Exception("No pumper_id"),
            ),
            patch.object(
                client,
                "get_pumper_info",
                new_callable=AsyncMock,
                side_effect=Exception("No pumper_id"),
            ),
            patch.object(
                client,
                "get_therapy_timeline",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                client,
                "get_dashboard_summary",
                new_callable=AsyncMock,
                return_value=None,
            ),
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
        payload = base64.urlsafe_b64encode(json.dumps({"accountId": "acc-1"}).encode()).decode().rstrip("=")
        client.id_token = f"header.{payload}.signature"
        with pytest.raises(TandemAuthError, match="No pumperId"):
            client._extract_jwt_claims()

    def test_valid_jwt_sets_pumper_id(self):
        """Valid JWT payload with pumperId populates client.pumper_id."""
        import base64
        import json

        client = self._make_client()
        payload = (
            base64.urlsafe_b64encode(json.dumps({"pumperId": "pump-abc", "accountId": "acc-1"}).encode())
            .decode()
            .rstrip("=")
        )
        client.id_token = f"header.{payload}.signature"
        client._extract_jwt_claims()
        assert client.pumper_id == "pump-abc"
        assert client.account_id == "acc-1"


# ═══════════════════════════════════════════════════════════════════════════
# _needs_login and login skip
# ═══════════════════════════════════════════════════════════════════════════


class TestNeedsLogin:
    """Tests for _needs_login and login early-return (lines 373-383)."""

    def test_needs_login_no_token(self):
        """No access_token → needs login."""
        client = TandemSourceClient("user@test.com", "pass")
        assert client._needs_login() is True

    def test_needs_login_expired_token(self):
        """Token expiring within 5 minutes → needs login."""
        import time

        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid"
        client.token_expires_at = time.time() + 60  # expires in 60s (< 300s buffer)
        assert client._needs_login() is True

    def test_needs_login_valid_token(self):
        """Token with plenty of time left → does NOT need login."""
        import time

        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid"
        client.token_expires_at = time.time() + 3600  # expires in 1 hour
        assert client._needs_login() is False

    async def test_login_skips_when_not_needed(self):
        """Login returns immediately when token is still valid (line 383)."""
        import time

        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid_token"
        client.token_expires_at = time.time() + 3600

        # If login tried to do anything it would fail because _get_client isn't mocked
        await client.login()  # should return immediately, no exception


# ═══════════════════════════════════════════════════════════════════════════
# Login error paths (lines 405-406, 410, 441, 464-465)
# ═══════════════════════════════════════════════════════════════════════════


class TestLoginErrors:
    """Tests for login authentication error paths."""

    async def test_login_non_200_status(self):
        """Login with non-200 HTTP status raises TandemAuthError (line 405-406)."""
        client = TandemSourceClient("user@test.com", "pass")

        mock_login_page = MagicMock()
        mock_login_page.status_code = 200

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 401
        mock_login_resp.text = "Unauthorized"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_login_page)
        mock_http.post = AsyncMock(return_value=mock_login_resp)
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemAuthError, match="Login failed with HTTP 401"):
            await client.login()

    async def test_login_rejected_status(self):
        """Login with status != SUCCESS raises TandemAuthError (line 410)."""
        client = TandemSourceClient("user@test.com", "pass")

        mock_login_page = MagicMock()
        mock_login_page.status_code = 200

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"status": "LOCKED_OUT", "message": "Too many attempts"}

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_login_page)
        mock_http.post = AsyncMock(return_value=mock_login_resp)
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemAuthError, match="Login rejected"):
            await client.login()

    async def test_login_no_auth_code(self):
        """Missing authorization code in redirect raises TandemAuthError (line 441)."""
        client = TandemSourceClient("user@test.com", "pass")

        mock_login_page = MagicMock()
        mock_login_page.status_code = 200

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"status": "SUCCESS"}

        mock_auth_resp = MagicMock()
        mock_auth_resp.url = "https://example.com/callback?error=access_denied"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=[mock_login_page, mock_auth_resp])
        mock_http.post = AsyncMock(return_value=mock_login_resp)
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemAuthError, match="No authorization code"):
            await client.login()

    async def test_login_token_exchange_bad_status(self):
        """Token exchange with non-2xx status raises TandemAuthError (lines 464-465)."""
        client = TandemSourceClient("user@test.com", "pass")

        mock_login_page = MagicMock()
        mock_login_page.status_code = 200

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"status": "SUCCESS"}

        mock_auth_resp = MagicMock()
        mock_auth_resp.url = "https://example.com/callback?code=test_auth_code"

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 400
        mock_token_resp.text = "Bad Request"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=[mock_login_page, mock_auth_resp])
        mock_http.post = AsyncMock(side_effect=[mock_login_resp, mock_token_resp])
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemAuthError, match="Token exchange HTTP 400"):
            await client.login()

    async def test_login_authorize_follows_redirects(self):
        """Regression: the OAuth authorize GET must set follow_redirects=True.

        The authorization code is delivered via a 302 to …/callback?code=….
        When Home Assistant injects its shared client (get_async_client), that
        client defaults to follow_redirects=False, so without an explicit
        per-request override the code is never read and login fails with
        `invalid_auth` in HA while passing here (the mock pre-sets .url). Guard
        the override so the live regression cannot silently return.
        """
        client = TandemSourceClient("user@test.com", "pass")

        mock_login_page = MagicMock()
        mock_login_page.status_code = 200

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"status": "SUCCESS"}

        mock_auth_resp = MagicMock()
        mock_auth_resp.url = "https://example.com/callback?code=test_auth_code"

        # Stop the flow at token exchange — we only assert the authorize call.
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 400
        mock_token_resp.text = "stop here"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=[mock_login_page, mock_auth_resp])
        mock_http.post = AsyncMock(side_effect=[mock_login_resp, mock_token_resp])
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemAuthError):
            await client.login()

        # The authorize request is the 2nd GET (after the login page).
        authorize_call = mock_http.get.call_args_list[1]
        assert authorize_call.kwargs.get("follow_redirects") is True


# ═══════════════════════════════════════════════════════════════════════════
# _api_get retry on transient errors (lines 539, 560)
# ═══════════════════════════════════════════════════════════════════════════


class TestApiGetRetry:
    """Tests for _api_get transient error retry logic."""

    async def test_api_get_retries_on_connect_error(self):
        """ConnectError retries and eventually raises TandemApiError (line 539, 560)."""
        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid_token"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemApiError, match="failed after"):
            await client._api_get("https://api.test.com/data", _retries=1)

        # Should have retried: 1 initial + 1 retry = 2 calls
        assert mock_http.get.call_count == 2

    async def test_api_get_retries_on_read_timeout(self):
        """ReadTimeout retries then raises TandemApiError."""
        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid_token"

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.ReadTimeout("read timed out"))
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(TandemApiError, match="failed after"):
            await client._api_get("https://api.test.com/data", _retries=0)

        assert mock_http.get.call_count == 1

    async def test_api_get_succeeds_after_transient_failure(self):
        """First call fails with ConnectError, second succeeds."""
        client = TandemSourceClient("user@test.com", "pass")
        client.access_token = "valid_token"

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"ok": True}

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=[httpx.ConnectError("transient"), mock_success])
        mock_http.is_closed = False
        client._client = mock_http

        result = await client._api_get("https://api.test.com/data", _retries=1)
        assert result == {"ok": True}
        assert mock_http.get.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# get_pumper_info (line 579)
# ═══════════════════════════════════════════════════════════════════════════


class TestGetPumperInfo:
    """Tests for get_pumper_info endpoint."""

    async def test_get_pumper_info_calls_api_get(self):
        """get_pumper_info delegates to _api_get with correct URL (line 579)."""
        client = TandemSourceClient("user@test.com", "pass")
        client.pumper_id = "pump-abc"

        with patch.object(
            client,
            "_api_get",
            new_callable=AsyncMock,
            return_value={"firstName": "Test", "lastName": "User"},
        ) as mock_get:
            result = await client.get_pumper_info()

        assert result["firstName"] == "Test"
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert "pump-abc" in call_url


# ═══════════════════════════════════════════════════════════════════════════
# map_pump_log_event — BFF JSON → legacy decoded-event dict
# ═══════════════════════════════════════════════════════════════════════════
class TestMapPumpLogEventBolusCalculator:
    """Bolus-calculator events 64/65/66 map to the coordinator's join contract."""

    def _event(self, code, props):
        return {
            "eventCode": code,
            "pumpDateTime": "2026-09-06T13:04:00",
            "sequenceNumber": 7,
            "eventProperties": props,
        }

    def test_msg1_bg_carbs_iob(self):
        evt = map_pump_log_event(
            self._event(
                EVT_BOLUS_REQUESTED_MSG1,
                {
                    "bolusId": 42,
                    "bg": 145,
                    "iob": 1.5,
                    "carbAmount": 30,
                    "carbRatio": 8000,
                    "bolusType": [4],
                    "correctionBolusIncluded": 1,
                },
            )
        )
        assert evt is not None
        assert evt["event_id"] == EVT_BOLUS_REQUESTED_MSG1
        assert evt["event_name"] == "BolusRequestedMsg1"
        assert evt["bolus_id"] == 42
        assert evt["bg_mgdl"] == 145
        assert evt["iob"] == 1.5
        assert evt["carb_amount"] == 30
        assert evt["carb_ratio"] == 8.0  # 8000 fixed-point / 1000
        assert evt["bolus_type"] == 16  # bitmask [4] → 1<<4
        assert evt["correction_included"] is True
        assert evt["timestamp"].tzinfo is None  # naive pump-local

    def test_msg1_missing_fields_are_none(self):
        evt = map_pump_log_event(self._event(EVT_BOLUS_REQUESTED_MSG1, {"bolusId": 1}))
        assert evt is not None
        assert evt["bg_mgdl"] is None
        assert evt["carb_amount"] is None
        assert evt["carb_ratio"] is None  # non-numeric carbRatio → None, not a crash

    def test_msg2_targets(self):
        evt = map_pump_log_event(
            self._event(
                EVT_BOLUS_REQUESTED_MSG2,
                {
                    "bolusId": 42,
                    "standardPercent": 100,
                    "targetBg": 110,
                    "isf": 45,
                    "duration": 0,
                    "declinedCorrection": 0,
                    "userOverride": 1,
                },
            )
        )
        assert evt["event_name"] == "BolusRequestedMsg2"
        assert evt["bolus_id"] == 42
        assert evt["target_bg"] == 110
        assert evt["isf"] == 45
        assert evt["duration_minutes"] == 0
        assert evt["declined_correction"] is False
        assert evt["user_override"] is True

    def test_msg3_split_sizes(self):
        evt = map_pump_log_event(
            self._event(
                EVT_BOLUS_REQUESTED_MSG3,
                {
                    "bolusId": 42,
                    "foodBolusSize": 7.63,
                    "correctionBolusSize": 0.0,
                    "totalBolusSize": 7.63,
                },
            )
        )
        assert evt["event_name"] == "BolusRequestedMsg3"
        assert evt["bolus_id"] == 42
        assert evt["food_bolus_size"] == 7.63
        assert evt["correction_bolus_size"] == 0.0
        assert evt["total_bolus_size"] == 7.63


class TestMapPumpLogEventDailyStatus:
    """AA daily status (313) supplies the CGM sensor type."""

    def _event(self, props):
        return {
            "eventCode": EVT_AA_DAILY_STATUS,
            "pumpDateTime": "2026-09-06T00:00:00",
            "sequenceNumber": 1,
            "eventProperties": props,
        }

    def test_sensor_type_g7(self):
        evt = map_pump_log_event(self._event({"sensorType": 3, "usermode": 0, "pumpControlState": 2}))
        assert evt["event_name"] == "AADailyStatus"
        assert evt["sensor_type_id"] == 3
        assert evt["sensor_type"] == "G7"
        assert evt["user_mode"] == 0
        assert evt["pump_control_state"] == 2

    def test_sensor_type_unknown_code(self):
        evt = map_pump_log_event(self._event({"sensorType": 9}))
        assert evt["sensor_type"] == "Unknown (9)"


class TestMapPumpLogEventBattery:
    """Pump-status / battery events (9/34/35) supply the battery level from `abc`."""

    def _event(self, code, props):
        return {
            "eventCode": code,
            "pumpDateTime": "2026-09-06T13:04:00",
            "sequenceNumber": 3,
            "eventProperties": props,
        }

    def test_status_event_battery_from_abc(self):
        # `abc` (actual battery charge) is the display %, not `ibc` (reads ceilinged).
        evt = map_pump_log_event(self._event(EVT_STATUS, {"abc": 96, "ibc": 100}))
        assert evt is not None
        assert evt["event_id"] == EVT_STATUS
        assert evt["event_name"] == "PumpStatus"
        assert evt["battery_percent"] == 96

    def test_battery_detail_event_named_battery(self):
        evt = map_pump_log_event(self._event(EVT_BATTERY_1, {"abc": 88}))
        assert evt["event_name"] == "Battery"
        assert evt["battery_percent"] == 88

    def test_missing_abc_is_none(self):
        evt = map_pump_log_event(self._event(EVT_STATUS, {"ibc": 100}))
        assert evt["battery_percent"] is None

    def test_status_event_iob_duration(self):
        # Insulin-on-board remaining duration is read from the status event (9).
        evt = map_pump_log_event(self._event(EVT_STATUS, {"abc": 96, "iobHours": 2, "iobMinutes": 45}))
        assert evt["iob_hours"] == 2
        assert evt["iob_minutes"] == 45

    def test_missing_iob_duration_is_none(self):
        evt = map_pump_log_event(self._event(EVT_STATUS, {"abc": 96}))
        assert evt["iob_hours"] is None
        assert evt["iob_minutes"] is None

    def test_battery_detail_event_has_no_iob(self):
        # Battery-detail events (34/35) carry no IOB fields.
        evt = map_pump_log_event(self._event(EVT_BATTERY_1, {"abc": 88}))
        assert evt["iob_hours"] is None
        assert evt["iob_minutes"] is None


class TestMapPumpLogEventCgm:
    """CGM data events (256/399) supply glucose plus transmitter signal strength."""

    def _event(self, code, props):
        return {
            "eventCode": code,
            "pumpDateTime": "2026-09-06T13:04:00",
            "sequenceNumber": 7,
            "eventProperties": props,
        }

    def test_cgm_gxb_event_reads_rssi(self):
        evt = map_pump_log_event(self._event(EVT_CGM_DATA_GXB, {"currentGlucoseDisplayValue": 120, "rssi": -62}))
        assert evt["event_name"] == "CGM"
        assert evt["glucose_mgdl"] == 120
        assert evt["rssi"] == -62

    def test_cgm_g7_event_reads_rssi(self):
        evt = map_pump_log_event(self._event(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 110, "rssi": -70}))
        assert evt["rssi"] == -70

    def test_cgm_missing_rssi_is_none(self):
        evt = map_pump_log_event(self._event(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 110}))
        assert evt["rssi"] is None


class TestMapPumpLogEventPcm:
    """PCM change events (230) carry the Control-IQ closed-loop-preferred setting."""

    def _event(self, props):
        return {
            "eventCode": EVT_AA_PCM_CHANGE,
            "pumpDateTime": "2026-09-06T13:04:00",
            "sequenceNumber": 11,
            "eventProperties": props,
        }

    def test_pcm_event_reads_closed_loop_preferred_true(self):
        evt = map_pump_log_event(self._event({"currentPcm": 1, "closedLoopPreferred": True}))
        assert evt["event_name"] == "PCMChange"
        assert evt["closed_loop_preferred"] is True

    def test_pcm_event_reads_closed_loop_preferred_false(self):
        evt = map_pump_log_event(self._event({"currentPcm": 0, "closedLoopPreferred": False}))
        assert evt["closed_loop_preferred"] is False

    def test_pcm_missing_closed_loop_preferred_is_none(self):
        evt = map_pump_log_event(self._event({"currentPcm": 1}))
        assert evt["closed_loop_preferred"] is None


class TestMapPumpLogEventAlertsAlarms:
    """Alert/alarm lifecycle events (4/5/6/26/28) map to the parser contract.

    The coordinator's ``_parse_alert_alarm_events`` reads ``event_name`` plus a
    single ``alert_id`` key for both alerts and alarms, so the mapper stores the
    id there regardless of the BFF field name (alertId / alarmId / malfId).
    """

    def _event(self, code, props):
        return {
            "eventCode": code,
            "pumpDateTime": "2026-09-06T13:04:00",
            "sequenceNumber": 9,
            "eventProperties": props,
        }

    def test_alert_activated(self):
        evt = map_pump_log_event(self._event(EVT_ALERT_ACTIVATED, {"alertId": 22}))
        assert evt is not None
        assert evt["event_name"] == "AlertActivated"
        assert evt["alert_id"] == 22

    def test_alert_cleared(self):
        evt = map_pump_log_event(self._event(EVT_ALERT_CLEARED, {"alertId": 22}))
        assert evt["event_name"] == "AlertCleared"
        assert evt["alert_id"] == 22

    def test_alarm_activated_uses_alarmid(self):
        evt = map_pump_log_event(self._event(EVT_ALARM_ACTIVATED, {"alarmId": 5}))
        assert evt["event_name"] == "AlarmActivated"
        assert evt["alert_id"] == 5

    def test_malfunction_uses_malfid(self):
        # Event 6 carries malfId (not alarmId) per tconnectsync events.json.
        evt = map_pump_log_event(self._event(EVT_MALFUNCTION_ACTIVATED, {"malfId": 7}))
        assert evt["event_name"] == "MalfunctionActivated"
        assert evt["alert_id"] == 7

    def test_alarm_cleared_uses_alarmid(self):
        evt = map_pump_log_event(self._event(EVT_ALARM_CLEARED, {"alarmId": 5}))
        assert evt["event_name"] == "AlarmCleared"
        assert evt["alert_id"] == 5


class TestMapPumpLogEventCgmSession:
    """CGM session events (212/213/214) expose the raw transmitter-clock fields.

    The coordinator derives wall-clock start/expiry from these; the mapper only
    forwards the values (sessionStartTime/currentTransmitterTime seconds,
    sessionDuration days) plus the session reason.
    """

    def _event(self, code, props):
        return {
            "eventCode": code,
            "pumpDateTime": "2026-09-05T16:13:46",
            "sequenceNumber": 4,
            "eventProperties": props,
        }

    def test_session_join_fields(self):
        evt = map_pump_log_event(
            self._event(
                EVT_CGM_SESSION_JOIN,
                {
                    "currentTransmitterTime": 1673785,
                    "sessionStartTime": 905139,
                    "sessionDuration": 10,
                    "sessionJoinReason": 0,
                },
            )
        )
        assert evt is not None
        assert evt["event_name"] == "CGMSessionJoin"
        assert evt["current_transmitter_time"] == 1673785
        assert evt["session_start_time"] == 905139
        assert evt["session_duration_days"] == 10
        assert evt["session_reason"] == 0

    def test_session_start_fields(self):
        evt = map_pump_log_event(
            self._event(
                EVT_CGM_SESSION_START,
                {
                    "currentTransmitterTime": 382,
                    "sessionStartTime": 300,
                    "sessionDuration": 10,
                    "sessionStartReason": 0,
                },
            )
        )
        assert evt["event_name"] == "CGMSessionStart"
        assert evt["session_duration_days"] == 10

    def test_session_stop_carries_sentinel_start(self):
        # Stop events carry the 0xFFFFFFFF sentinel for sessionStartTime.
        evt = map_pump_log_event(
            self._event(
                EVT_CGM_SESSION_STOP,
                {
                    "currentTransmitterTime": 1769181,
                    "sessionStartTime": 4294967295,
                    "sessionStopTime": 0,
                    "sessionDuration": 10,
                    "sessionStopReason": 6,
                },
            )
        )
        assert evt["event_name"] == "CGMSessionStop"
        assert evt["session_start_time"] == 4294967295
        assert evt["session_stop_time"] == 0
        assert evt["session_reason"] == 6


class TestMapPumpLogEventBoundaries:
    """Events still unmapped return None; malformed input returns None."""

    def test_unmapped_event_returns_none(self):
        # Daily basal (81) is deliberately not yet mapped (battery follow-up).
        evt = map_pump_log_event(
            {"eventCode": EVT_DAILY_BASAL, "pumpDateTime": "2026-09-06T00:00:00", "eventProperties": {}}
        )
        assert evt is None

    def test_missing_datetime_returns_none(self):
        assert map_pump_log_event({"eventCode": EVT_BOLUS_REQUESTED_MSG1, "eventProperties": {}}) is None

    def test_missing_event_code_returns_none(self):
        assert map_pump_log_event({"pumpDateTime": "2026-09-06T00:00:00"}) is None
