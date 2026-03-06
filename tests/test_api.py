"""Tests for the Carelink API client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestCarelinkClient:
    """Tests for CarelinkClient."""

    def test_init(self, mock_carelink_client):
        """Test CarelinkClient initialization."""
        assert mock_carelink_client is not None
        assert mock_carelink_client._async_client is None

    def test_async_client_property(self, mock_carelink_client):
        """Test async_client property creates client on first access."""
        client = mock_carelink_client.async_client
        assert client is not None
        # Second access should return same client
        assert mock_carelink_client.async_client is client

    async def test_close(self, mock_carelink_client):
        """Test closing the HTTP client."""
        # Create client first
        _ = mock_carelink_client.async_client
        assert mock_carelink_client._async_client is not None

        # Close it
        await mock_carelink_client.close()
        assert mock_carelink_client._async_client is None

    async def test_close_when_not_initialized(self, mock_carelink_client):
        """Test closing when client was never created."""
        # Should not raise
        await mock_carelink_client.close()
        assert mock_carelink_client._async_client is None

    async def test_fetch_async(self, mock_carelink_client):
        """Test fetch_async method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"test": "data"}'

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_carelink_client._async_client = mock_client

        response = await mock_carelink_client.fetch_async("https://test.com", headers={"Authorization": "Bearer test"})

        assert response.status_code == 200
        mock_client.get.assert_called_once()

    async def test_post_async(self, mock_carelink_client):
        """Test post_async method."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_carelink_client._async_client = mock_client

        response = await mock_carelink_client.post_async(
            "https://test.com",
            headers={"Content-Type": "application/json"},
            data={"key": "value"},
        )

        assert response.status_code == 200
        mock_client.post.assert_called_once()

    async def test_fetch_async_timeout(self, mock_carelink_client):
        """Test fetch_async handles timeout exception."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
        mock_carelink_client._async_client = mock_client

        with pytest.raises(httpx.TimeoutException):
            await mock_carelink_client.fetch_async("https://test.com", headers={"Authorization": "Bearer test"})

    async def test_fetch_async_request_error(self, mock_carelink_client):
        """Test fetch_async handles request error."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
        mock_carelink_client._async_client = mock_client

        with pytest.raises(httpx.RequestError):
            await mock_carelink_client.fetch_async("https://test.com", headers={"Authorization": "Bearer test"})

    async def test_post_async_timeout(self, mock_carelink_client):
        """Test post_async handles timeout exception."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
        mock_carelink_client._async_client = mock_client

        with pytest.raises(httpx.TimeoutException):
            await mock_carelink_client.post_async(
                "https://test.com",
                headers={"Content-Type": "application/json"},
                data={"key": "value"},
            )

    async def test_post_async_request_error(self, mock_carelink_client):
        """Test post_async handles request error."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
        mock_carelink_client._async_client = mock_client

        with pytest.raises(httpx.RequestError):
            await mock_carelink_client.post_async(
                "https://test.com",
                headers={"Content-Type": "application/json"},
                data={"key": "value"},
            )


class TestTokenProcessing:
    """Tests for token processing methods."""

    def test_get_access_token_payload_valid(self, mock_carelink_client, mock_token_data):
        """Test extracting payload from valid JWT token."""
        result = mock_carelink_client._get_access_token_payload(mock_token_data)

        assert result is not None
        assert "token_details" in result
        assert result["token_details"]["country"] == "NL"

    def test_get_access_token_payload_missing_token(self, mock_carelink_client):
        """Test handling missing access token."""
        result = mock_carelink_client._get_access_token_payload({})
        assert result is None

    def test_get_access_token_payload_invalid_token(self, mock_carelink_client):
        """Test handling invalid/malformed token."""
        result = mock_carelink_client._get_access_token_payload({"access_token": "invalid_token_without_dots"})
        assert result is None

    def test_get_access_token_payload_none_input(self, mock_carelink_client):
        """Test handling None input."""
        result = mock_carelink_client._get_access_token_payload(None)
        assert result is None


class TestWriteTokenFile:
    """Tests for token file writing."""

    async def test_write_token_file(self, mock_carelink_client, tmp_path):
        """Test writing token file."""
        token_file = tmp_path / "token.json"
        token_data = {"access_token": "test", "refresh_token": "test"}

        await mock_carelink_client._write_token_file(token_data, str(token_file))

        assert token_file.exists()
        with open(token_file) as f:
            saved_data = json.load(f)
        assert saved_data == token_data

    async def test_write_token_file_creates_directory(self, mock_carelink_client, tmp_path):
        """Test that writing token file creates parent directories."""
        token_file = tmp_path / "subdir" / "token.json"
        token_data = {"access_token": "test"}

        await mock_carelink_client._write_token_file(token_data, str(token_file))

        assert token_file.exists()


class TestProcessTokenFile:
    """Tests for token file processing."""

    async def test_process_token_file_valid(self, mock_carelink_client, tmp_path, mock_token_data):
        """Test processing a valid token file."""
        token_file = tmp_path / "token.json"
        with open(token_file, "w") as f:
            json.dump(mock_token_data, f)

        result = await mock_carelink_client._process_token_file(str(token_file))

        assert result is not None
        assert result["access_token"] == mock_token_data["access_token"]

    async def test_process_token_file_not_exists(self, mock_carelink_client, tmp_path):
        """Test processing non-existent token file with no static config."""
        token_file = tmp_path / "nonexistent.json"

        # Client has no static config set
        mock_carelink_client._CarelinkClient__carelink_access_token = None
        mock_carelink_client._CarelinkClient__carelink_refresh_token = None
        mock_carelink_client._CarelinkClient__client_id = None

        result = await mock_carelink_client._process_token_file(str(token_file))

        assert result is None

    async def test_process_token_file_missing_required_fields(self, mock_carelink_client, tmp_path):
        """Test processing token file with missing required fields."""
        token_file = tmp_path / "token.json"
        incomplete_data = {"access_token": "test"}  # Missing refresh_token and client_id

        with open(token_file, "w") as f:
            json.dump(incomplete_data, f)

        result = await mock_carelink_client._process_token_file(str(token_file))

        assert result is None

    async def test_process_token_file_invalid_json(self, mock_carelink_client, tmp_path):
        """Test processing token file with invalid JSON."""
        token_file = tmp_path / "token.json"
        with open(token_file, "w") as f:
            f.write("not valid json {{{")

        result = await mock_carelink_client._process_token_file(str(token_file))

        assert result is None

    async def test_process_token_file_permission_error(self, mock_carelink_client, tmp_path):
        """Test processing token file with permission error (OSError)."""
        token_file = tmp_path / "token.json"

        # Client has no static config set
        mock_carelink_client._CarelinkClient__carelink_access_token = None
        mock_carelink_client._CarelinkClient__carelink_refresh_token = None
        mock_carelink_client._CarelinkClient__client_id = None

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = await mock_carelink_client._process_token_file(str(token_file))

        assert result is None


class TestHeaderMutation:
    """Verify __common_headers is not mutated between requests (H8)."""

    def test_common_headers_initial_keys(self, mock_carelink_client):
        """__common_headers should not contain request-specific keys at init."""
        headers = mock_carelink_client._CarelinkClient__common_headers
        assert "Authorization" not in headers
        assert "mag-identifier" not in headers
        assert "Accept" in headers
        assert "Content-Type" in headers

    async def test_common_headers_not_mutated_by_get_data(self, mock_carelink_client):
        """__get_data must not write Authorization into __common_headers (H8)."""
        common = mock_carelink_client._CarelinkClient__common_headers
        initial_keys = set(common.keys())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_carelink_client._CarelinkClient__token_data = {
            "access_token": "tok",
            "mag-identifier": "mag123",
        }
        mock_carelink_client._CarelinkClient__session_config = {"baseUrlCumulus": "https://example.com"}

        with (
            patch.object(
                mock_carelink_client,
                "_CarelinkClient__handle_authorization_token",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch.object(
                mock_carelink_client,
                "fetch_async",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            try:
                await mock_carelink_client._CarelinkClient__get_data()
            except Exception:
                pass  # not testing full flow, just header safety

        assert set(common.keys()) == initial_keys, (
            "__common_headers was mutated — Authorization leaked into shared dict"
        )
        assert "Authorization" not in common


class TestHasRequiredTokenFields:
    """Pure-function tests for _has_required_token_fields."""

    def test_none_returns_false(self, mock_carelink_client):
        """None input returns False."""
        assert mock_carelink_client._has_required_token_fields(None) is False

    def test_all_fields_present_returns_true(self, mock_carelink_client):
        """Dict with all three required fields returns True."""
        token = {"access_token": "a", "refresh_token": "r", "client_id": "c"}
        assert mock_carelink_client._has_required_token_fields(token) is True

    def test_missing_access_token_returns_false(self, mock_carelink_client):
        """Dict missing access_token returns False."""
        token = {"refresh_token": "r", "client_id": "c"}
        assert mock_carelink_client._has_required_token_fields(token) is False

    def test_missing_refresh_token_returns_false(self, mock_carelink_client):
        """Dict missing refresh_token returns False."""
        token = {"access_token": "a", "client_id": "c"}
        assert mock_carelink_client._has_required_token_fields(token) is False

    def test_missing_client_id_returns_false(self, mock_carelink_client):
        """Dict missing client_id returns False."""
        token = {"access_token": "a", "refresh_token": "r"}
        assert mock_carelink_client._has_required_token_fields(token) is False

    def test_empty_dict_returns_false(self, mock_carelink_client):
        """Empty dict returns False."""
        assert mock_carelink_client._has_required_token_fields({}) is False


class TestSelectPatient:
    """Tests for the private __select_patient method."""

    def test_active_patient_returned(self, mock_carelink_client):
        """ACTIVE patient is returned when present."""
        patients = [
            {"username": "inactive_user", "status": "INACTIVE"},
            {"username": "active_user", "status": "ACTIVE"},
        ]
        result = mock_carelink_client._CarelinkClient__select_patient(patients)
        assert result["username"] == "active_user"

    def test_only_inactive_patients_returns_none(self, mock_carelink_client):
        """Returns None when no ACTIVE patient exists."""
        patients = [{"username": "user1", "status": "INACTIVE"}]
        result = mock_carelink_client._CarelinkClient__select_patient(patients)
        assert result is None

    def test_none_input_returns_none(self, mock_carelink_client):
        """None input returns None."""
        result = mock_carelink_client._CarelinkClient__select_patient(None)
        assert result is None

    def test_empty_list_returns_none(self, mock_carelink_client):
        """Empty list returns None."""
        result = mock_carelink_client._CarelinkClient__select_patient([])
        assert result is None


class TestLoadSharedSeedIfNewer:
    """Async tests for _load_shared_seed_if_newer using tmp_path."""

    async def test_entry_file_newer_returns_none(self, mock_carelink_client, tmp_path):
        """Returns None when entry file is newer than shared file."""
        import os

        shared_file = tmp_path / "carelink_logindata.json"
        entry_file = tmp_path / "carelink_logindata_entry.json"

        shared_data = {"access_token": "shared", "refresh_token": "r", "client_id": "c"}
        shared_file.write_text(json.dumps(shared_data))
        entry_file.write_text(json.dumps({"access_token": "entry", "refresh_token": "r", "client_id": "c"}))
        # Make entry strictly newer than shared by setting explicit mtimes
        os.utime(shared_file, (1000000, 1000000))
        os.utime(entry_file, (1000001, 1000001))

        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        result = await mock_carelink_client._load_shared_seed_if_newer(str(entry_file))
        assert result is None

    async def test_shared_file_newer_returns_token(self, mock_carelink_client, tmp_path):
        """Returns shared token data when shared file is newer than entry file."""
        import os

        entry_file = tmp_path / "carelink_logindata_entry.json"
        shared_file = tmp_path / "carelink_logindata.json"

        entry_file.write_text(json.dumps({"access_token": "old", "refresh_token": "r", "client_id": "c"}))
        shared_data = {"access_token": "newer", "refresh_token": "r", "client_id": "c"}
        shared_file.write_text(json.dumps(shared_data))
        # Make shared strictly newer than entry by setting explicit mtimes
        os.utime(entry_file, (1000000, 1000000))
        os.utime(shared_file, (1000001, 1000001))

        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        result = await mock_carelink_client._load_shared_seed_if_newer(str(entry_file))
        assert result is not None
        assert result["access_token"] == "newer"

    async def test_files_dont_exist_returns_none(self, mock_carelink_client, tmp_path):
        """Returns None when both files don't exist (FileNotFoundError)."""
        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(tmp_path / "nonexistent_shared.json")
        result = await mock_carelink_client._load_shared_seed_if_newer(str(tmp_path / "nonexistent_entry.json"))
        assert result is None

    async def test_shared_file_invalid_json_returns_none(self, mock_carelink_client, tmp_path):
        """Returns None when shared file contains invalid JSON."""
        import os

        entry_file = tmp_path / "carelink_logindata_entry.json"
        shared_file = tmp_path / "carelink_logindata.json"

        entry_file.write_text("{}")
        shared_file.write_text("not valid json {{{")
        os.utime(entry_file, (1000000, 1000000))
        os.utime(shared_file, (1000001, 1000001))

        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        result = await mock_carelink_client._load_shared_seed_if_newer(str(entry_file))
        assert result is None

    async def test_shared_file_missing_required_fields_returns_none(self, mock_carelink_client, tmp_path):
        """Returns None when shared file is missing required token fields."""
        import os

        entry_file = tmp_path / "carelink_logindata_entry.json"
        shared_file = tmp_path / "carelink_logindata.json"

        entry_file.write_text("{}")
        shared_file.write_text(json.dumps({"access_token": "only_one_field"}))
        os.utime(entry_file, (1000000, 1000000))
        os.utime(shared_file, (1000001, 1000001))

        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        result = await mock_carelink_client._load_shared_seed_if_newer(str(entry_file))
        assert result is None


class TestProcessTokenFileAdditional:
    """Additional async tests for _process_token_file edge cases."""

    async def test_static_config_when_no_file_exists(self, mock_carelink_client, tmp_path):
        """Uses static config (access/refresh/client_id on client) when no file exists."""
        # Ensure none of the fallback files exist
        entry_file = tmp_path / "nonexistent_entry.json"
        shared_file = tmp_path / "nonexistent_shared.json"
        legacy_file = tmp_path / "nonexistent_legacy.json"

        mock_carelink_client._CarelinkClient__auth_file_path = str(entry_file)
        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        mock_carelink_client._CarelinkClient__legacy_auth_file_path = str(legacy_file)
        mock_carelink_client._CarelinkClient__carelink_access_token = "static_access"
        mock_carelink_client._CarelinkClient__carelink_refresh_token = "static_refresh"
        mock_carelink_client._CarelinkClient__client_id = "static_client_id"

        result = await mock_carelink_client._process_token_file(str(entry_file))
        assert result is not None
        assert result["access_token"] == "static_access"
        assert result["refresh_token"] == "static_refresh"
        assert result["client_id"] == "static_client_id"

    async def test_legacy_file_fallback(self, mock_carelink_client, tmp_path):
        """Falls back to legacy file when entry and shared files don't exist."""
        entry_file = tmp_path / "nonexistent_entry.json"
        shared_file = tmp_path / "nonexistent_shared.json"
        legacy_file = tmp_path / "legacy_token.json"

        legacy_data = {"access_token": "legacy_tok", "refresh_token": "legacy_r", "client_id": "legacy_c"}
        legacy_file.write_text(json.dumps(legacy_data))

        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        mock_carelink_client._CarelinkClient__legacy_auth_file_path = str(legacy_file)
        # No static config so it must fall back to legacy
        mock_carelink_client._CarelinkClient__carelink_access_token = None
        mock_carelink_client._CarelinkClient__carelink_refresh_token = None
        mock_carelink_client._CarelinkClient__client_id = None

        result = await mock_carelink_client._process_token_file(str(entry_file))
        assert result is not None
        assert result["access_token"] == "legacy_tok"

    async def test_json_decode_error_in_entry_file_returns_none(self, mock_carelink_client, tmp_path):
        """Returns None when entry file exists but contains invalid JSON."""
        entry_file = tmp_path / "bad_token.json"
        entry_file.write_text("THIS IS NOT JSON }{")

        mock_carelink_client._CarelinkClient__carelink_access_token = None
        mock_carelink_client._CarelinkClient__carelink_refresh_token = None
        mock_carelink_client._CarelinkClient__client_id = None

        result = await mock_carelink_client._process_token_file(str(entry_file))
        assert result is None


class TestLoginAdditional:
    """Additional async tests for the login() method."""

    async def test_already_initialized_no_newer_shared_seed_returns_true(self, mock_carelink_client, tmp_path):
        """login() returns True immediately when already initialized and no newer shared seed."""
        # Mark as initialized
        mock_carelink_client._CarelinkClient__initialized = True
        # Ensure no shared seed file exists so _load_shared_seed_if_newer returns None
        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(tmp_path / "nonexistent_shared.json")
        mock_carelink_client._CarelinkClient__auth_file_path = str(tmp_path / "nonexistent_entry.json")

        result = await mock_carelink_client.login()
        assert result is True

    async def test_not_initialized_no_token_no_static_config_returns_false(self, mock_carelink_client, tmp_path):
        """login() returns False when not initialized, no files, and no static credentials."""
        entry_file = tmp_path / "nonexistent_entry.json"
        shared_file = tmp_path / "nonexistent_shared.json"
        legacy_file = tmp_path / "nonexistent_legacy.json"

        mock_carelink_client._CarelinkClient__initialized = False
        mock_carelink_client._CarelinkClient__auth_file_path = str(entry_file)
        mock_carelink_client._CarelinkClient__shared_auth_file_path = str(shared_file)
        mock_carelink_client._CarelinkClient__legacy_auth_file_path = str(legacy_file)
        mock_carelink_client._CarelinkClient__carelink_access_token = None
        mock_carelink_client._CarelinkClient__carelink_refresh_token = None
        mock_carelink_client._CarelinkClient__client_id = None

        result = await mock_carelink_client.login()
        assert result is False
