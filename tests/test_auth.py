"""Unit tests for TokenManager and Auth strategies."""
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
