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
import hashlib
import json
import logging
import os
import re
import ssl
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, parse_qs

import certifi
import httpx

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


class TandemAuthError(Exception):
    """Raised when authentication fails."""


class TandemApiError(Exception):
    """Raised when an API call fails."""


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

    def __init__(self, email: str, password: str, region: str = "EU"):
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

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client.

        Creates the SSL context in an executor to avoid blocking the event loop
        with load_verify_locations().
        """
        if self._client is None or self._client.is_closed:
            loop = asyncio.get_running_loop()
            ssl_ctx = await loop.run_in_executor(
                None,
                lambda: ssl.create_default_context(cafile=certifi.where()),
            )
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
        """Check if we need to (re)authenticate."""
        if not self.access_token:
            return True
        # Re-login 5 minutes before expiry
        return time.time() >= (self.token_expires_at - 300)

    async def login(self) -> bool:
        """Perform OIDC/PKCE authentication.

        Returns True on success, raises TandemAuthError on failure.
        """
        if not self._needs_login():
            return True

        client = await self._get_client()

        _LOGGER.debug("Tandem: Starting OIDC login for %s region", self.region)

        # Step 1: Initialize session (establish cookies)
        try:
            await client.get(self.LOGIN_PAGE_URL)
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Cannot reach login page: {e}") from e

        # Step 2: POST credentials to login API
        try:
            login_resp = await client.post(
                self.urls["LOGIN_API"],
                json={"username": self.email, "password": self.password},
                headers={"Referer": self.LOGIN_PAGE_URL},
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Login request failed: {e}") from e

        if login_resp.status_code != 200:
            raise TandemAuthError(
                f"Login failed with HTTP {login_resp.status_code}: {login_resp.text[:200]}"
            )

        login_json = login_resp.json()
        if login_json.get("status") != "SUCCESS":
            raise TandemAuthError(
                f"Login rejected: {login_json.get('message', 'Unknown error')}"
            )

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
            auth_resp = await client.get(
                self.urls["AUTHORIZE"] + "?" + urlencode(auth_params),
                headers={"Referer": self.LOGIN_PAGE_URL},
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Authorization request failed: {e}") from e

        # Extract authorization code from redirect URL
        final_url = str(auth_resp.url)
        parsed = urlparse(final_url)
        query_params = parse_qs(parsed.query)

        if "code" not in query_params:
            raise TandemAuthError(
                f"No authorization code in redirect URL: {final_url[:200]}"
            )

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
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as e:
            raise TandemAuthError(f"Token exchange failed: {e}") from e

        if token_resp.status_code // 100 != 2:
            raise TandemAuthError(
                f"Token exchange HTTP {token_resp.status_code}: {token_resp.text[:200]}"
            )

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
        return True

    def _extract_jwt_claims(self):
        """Extract claims from the id_token JWT payload.

        We skip cryptographic verification since we received the token over
        HTTPS directly from the token endpoint.
        """
        parts = self.id_token.split(".")
        if len(parts) != 3:
            raise TandemAuthError("Invalid JWT format")

        # Base64url decode the payload (middle part)
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)

        try:
            claims = json.loads(base64.urlsafe_b64decode(payload))
        except (json.JSONDecodeError, Exception) as e:
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

    def _api_headers(self) -> dict:
        """Get headers for authenticated API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT,
        }

    async def _api_get(self, url: str) -> dict:
        """Make an authenticated GET request with automatic re-login on 401."""
        client = await self._get_client()

        resp = await client.get(url, headers=self._api_headers())

        if resp.status_code == 401:
            _LOGGER.info("Tandem: Got 401, attempting re-login")
            self.access_token = None
            await self.login()
            resp = await client.get(url, headers=self._api_headers())

        if resp.status_code != 200:
            raise TandemApiError(
                f"API GET {url} failed ({resp.status_code}): {resp.text[:300]}"
            )

        return resp.json()

    # ── Tandem Source API endpoints ──────────────────────────────────────

    async def get_pumper_info(self) -> dict:
        """Get user and pump information."""
        return await self._api_get(
            f"{self.urls['SOURCE_URL']}api/pumpers/pumpers/{self.pumper_id}"
        )

    async def get_pump_event_metadata(self) -> list:
        """Get pump event metadata (serial, model, last upload, etc.).

        Returns a list of dicts, one per pump on the account. Each dict has:
        tconnectDeviceId, serialNumber, modelNumber, minDateWithEvents,
        maxDateWithEvents, lastUpload, patientName, patientDateOfBirth,
        patientCareGiver, softwareVersion, partNumber
        """
        return await self._api_get(
            f"{self.urls['SOURCE_URL']}api/reports/reportsfacade/"
            f"{self.pumper_id}/pumpeventmetadata"
        )

    # ── ControlIQ API endpoints ──────────────────────────────────────────
    # These use the TDC services base URL and may or may not accept the
    # Tandem Source OIDC access token. Failures are handled gracefully.

    async def get_therapy_timeline(
        self, start_date: str, end_date: str
    ) -> dict | None:
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
            return await self._api_get(url)
        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.debug("Therapy timeline not available: %s", e)
            return None

    async def get_dashboard_summary(
        self, start_date: str, end_date: str
    ) -> dict | None:
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
            return await self._api_get(url)
        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.debug("Dashboard summary not available: %s", e)
            return None

    async def get_therapy_events(
        self, start_date: str, end_date: str
    ) -> dict | None:
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
            return await self._api_get(url)
        except (TandemApiError, httpx.HTTPError) as e:
            _LOGGER.debug("Therapy events not available: %s", e)
            return None

    # ── Unified data fetch ───────────────────────────────────────────────

    async def get_recent_data(self) -> dict:
        """Fetch all available recent data from both Tandem Source and ControlIQ APIs.

        Returns a unified dict with keys:
            pump_metadata: dict or None
            pumper_info: dict or None
            therapy_timeline: dict or None
            dashboard_summary: dict or None
        """
        data = {
            "pump_metadata": None,
            "pumper_info": None,
            "therapy_timeline": None,
            "dashboard_summary": None,
        }

        # Pump event metadata (Tandem Source API - should always work)
        try:
            metadata_list = await self.get_pump_event_metadata()
            if metadata_list and isinstance(metadata_list, list) and len(metadata_list) > 0:
                data["pump_metadata"] = metadata_list[0]
            elif isinstance(metadata_list, dict):
                data["pump_metadata"] = metadata_list
        except Exception as e:
            _LOGGER.warning("Failed to fetch pump metadata: %s", e)

        # Pumper info (Tandem Source API - should always work)
        try:
            data["pumper_info"] = await self.get_pumper_info()
        except Exception as e:
            _LOGGER.warning("Failed to fetch pumper info: %s", e)

        # Therapy timeline for last 1 day (ControlIQ API - may not work
        # with Source OIDC tokens; sensors degrade gracefully if unavailable)
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        start = yesterday.strftime("%m-%d-%Y")
        end = today.strftime("%m-%d-%Y")

        _LOGGER.debug(
            "Tandem: Fetching ControlIQ data for %s to %s", start, end
        )

        data["therapy_timeline"] = await self.get_therapy_timeline(start, end)
        data["dashboard_summary"] = await self.get_dashboard_summary(start, end)

        if not data["therapy_timeline"]:
            _LOGGER.info(
                "Tandem: ControlIQ therapy timeline not available "
                "(Source OIDC token may not be accepted by ControlIQ API)"
            )
        if not data["dashboard_summary"]:
            _LOGGER.info(
                "Tandem: ControlIQ dashboard summary not available "
                "(Source OIDC token may not be accepted by ControlIQ API)"
            )

        return data

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


def parse_dotnet_date(date_str) -> datetime | None:
    """Parse .NET /Date(epoch_ms)/ or /Date(epoch_ms+offset)/ format.

    Also handles plain ISO 8601 date strings and epoch integers.
    """
    if date_str is None:
        return None

    if isinstance(date_str, (int, float)):
        return datetime.fromtimestamp(date_str / 1000 if date_str > 1e12 else date_str)

    if isinstance(date_str, str):
        # .NET date format: /Date(1234567890000)/ or /Date(1234567890000+0000)/
        match = re.match(r"/Date\((\d+)([+-]\d+)?\)/", date_str)
        if match:
            epoch_ms = int(match.group(1))
            return datetime.fromtimestamp(epoch_ms / 1000)

        # ISO 8601 format
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except (ValueError, AttributeError):
            pass

    return None
