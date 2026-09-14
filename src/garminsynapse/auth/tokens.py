"""Token management and disk storage for garminsynapse."""
import os
import json
import logging
import base64
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_DIR = Path.home() / ".garminsynapse"
DEFAULT_TOKEN_FILE = DEFAULT_TOKEN_DIR / "tokens.json"
DEFAULT_CRED_FILE = DEFAULT_TOKEN_DIR / "credentials.json"


class TokenManager:
    """Manages reading and writing Garmin OAuth tokens to disk."""

    def __init__(self, token_file: Optional[Path] = None):
        self.token_file = Path(token_file) if token_file else DEFAULT_TOKEN_FILE
        self.cred_file = self.token_file.parent / "credentials.json"

    def save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Save token dictionary to JSON file atomically."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.token_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
        temp_file.replace(self.token_file)
        os.chmod(self.token_file, 0o600)
        logger.info(f"Saved tokens to {self.token_file}")

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load tokens from JSON file if present."""
        if not self.token_file.exists():
            return None
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tokens from {self.token_file}: {e}")
            return None

    def delete_tokens(self) -> None:
        """Remove saved tokens file."""
        if self.token_file.exists():
            self.token_file.unlink()
            logger.info(f"Deleted tokens file {self.token_file}")

    def save_credentials(self, email: str, password: str) -> None:
        """Save credentials for auto-refresh securely."""
        self.cred_file.parent.mkdir(parents=True, exist_ok=True)
        # Obfuscate password to prevent casual shoulder-surfing (not true encryption)
        obfuscated = base64.b64encode(password.encode()).decode()
        data = {"email": email, "password": obfuscated}
        temp_file = self.cred_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        temp_file.replace(self.cred_file)
        os.chmod(self.cred_file, 0o600)
        logger.info("Saved auto-login credentials.")

    def load_credentials(self) -> Optional[Dict[str, str]]:
        """Load and decode credentials if present."""
        if not self.cred_file.exists():
            return None
        try:
            with open(self.cred_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "email": data["email"],
                "password": base64.b64decode(data["password"]).decode()
            }
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None

    def has_credentials(self) -> bool:
        """Check if auto-login credentials exist and are non-empty."""
        return self.cred_file.exists() and self.cred_file.stat().st_size > 0

    def delete_credentials(self) -> None:
        """Remove saved credentials file (e.g. on explicit logout)."""
        if self.cred_file.exists():
            self.cred_file.unlink()
            logger.info(f"Deleted credentials file {self.cred_file}")

    def is_token_expired(self, tokens: Optional[Dict[str, Any]] = None) -> bool:
        """Inspect the JWT expiration inside client_state to determine validity."""
        import time
        tok = tokens if tokens is not None else self.load_tokens()
        if not tok:
            return True
        client_state_raw = tok.get("client_state")
        if not client_state_raw:
            return True
        try:
            cs = json.loads(client_state_raw)
            token = cs.get("di_token")
            if not token:
                return True
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
                exp = payload.get("exp")
                if exp and time.time() > (int(exp) - 300):
                    return True
            return False
        except Exception as e:
            logger.debug(f"Error checking token expiration: {e}")
            return True
