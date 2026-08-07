"""Token management and disk storage for garminsynapse."""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_DIR = Path.home() / ".garminsynapse"
DEFAULT_TOKEN_FILE = DEFAULT_TOKEN_DIR / "tokens.json"


class TokenManager:
    """Manages reading and writing Garmin OAuth tokens to disk."""

    def __init__(self, token_file: Optional[Path] = None):
        self.token_file = Path(token_file) if token_file else DEFAULT_TOKEN_FILE

    def save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Save token dictionary to JSON file atomically."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.token_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
        temp_file.replace(self.token_file)
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
