"""Unit tests for TokenManager and Auth strategies."""
import json
from pathlib import Path
from garminsynapse.auth.tokens import TokenManager
from garminsynapse.core.fit_encoder import FitEncoder


def test_token_manager_file_ops(tmp_path: Path):
    token_file = tmp_path / "tokens.json"
    manager = TokenManager(token_file=token_file)

    assert manager.load_tokens() is None

    test_tokens = {"access_token": "abc123token", "expires_in": 3600}
    manager.save_tokens(test_tokens)

    loaded = manager.load_tokens()
    assert loaded == test_tokens

    manager.delete_tokens()
    assert manager.load_tokens() is None


def test_fit_encoder_crc():
    test_data = b"FIT_HEADER_TEST"
    crc = FitEncoder.calc_crc(test_data)
    assert isinstance(crc, int)
    assert 0 <= crc <= 65535


def test_credentials_lifecycle(tmp_path: Path):
    token_file = tmp_path / "tokens.json"
    manager = TokenManager(token_file=token_file)

    assert not manager.has_credentials()
    assert manager.load_credentials() is None

    manager.save_credentials("test@example.com", "secret123")
    assert manager.has_credentials()
    creds = manager.load_credentials()
    assert creds["email"] == "test@example.com"
    assert creds["password"] == "secret123"

    manager.delete_credentials()
    assert not manager.has_credentials()
    assert manager.load_credentials() is None


def test_token_expiration_logic(tmp_path: Path):
    import time, json, base64
    token_file = tmp_path / "tokens.json"
    manager = TokenManager(token_file=token_file)

    # Missing tokens -> expired
    assert manager.is_token_expired(None) is True

    # Valid unexpired token (exp = now + 3600)
    future_exp = int(time.time()) + 3600
    payload = json.dumps({"exp": future_exp})
    b64_payload = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    fake_jwt = f"header.{b64_payload}.sig"
    valid_tokens = {"client_state": json.dumps({"di_token": fake_jwt})}
    assert manager.is_token_expired(valid_tokens) is False

    # Expired token (exp = now - 600)
    past_exp = int(time.time()) - 600
    payload_exp = json.dumps({"exp": past_exp})
    b64_exp = base64.urlsafe_b64encode(payload_exp.encode()).decode().rstrip("=")
    fake_jwt_exp = f"header.{b64_exp}.sig"
    expired_tokens = {"client_state": json.dumps({"di_token": fake_jwt_exp})}
    assert manager.is_token_expired(expired_tokens) is True


def test_fast_refresh_integration(tmp_path: Path):
    from unittest.mock import patch, MagicMock
    from garminsynapse.auth.manager import DualAuthManager

    token_file = tmp_path / "tokens.json"
    manager = TokenManager(token_file=token_file)
    initial_tokens = {
        "email": "test@example.com",
        "client_state": json.dumps({
            "di_token": "old_token",
            "di_refresh_token": "valid_refresh",
            "di_client_id": "test_client"
        }),
        "headers": {}
    }
    manager.save_tokens(initial_tokens)

    auth_mgr = DualAuthManager(token_manager=manager)

    with patch("garminconnect.Garmin") as mock_garmin_cls:
        mock_instance = MagicMock()
        mock_instance.client.di_refresh_token = "valid_refresh"
        mock_instance.client.dumps.return_value = json.dumps({
            "di_token": "new_refreshed_jwt",
            "di_refresh_token": "new_rotated_refresh",
            "di_client_id": "test_client"
        })
        mock_instance.client.get_api_headers.return_value = {"Authorization": "Bearer new_refreshed_jwt"}
        mock_garmin_cls.return_value = mock_instance

        refreshed = auth_mgr.fast_refresh()
        assert refreshed is not None
        assert "new_refreshed_jwt" in refreshed["client_state"]
        assert refreshed["headers"]["Authorization"] == "Bearer new_refreshed_jwt"
        mock_instance.client._refresh_di_token.assert_called_once()
