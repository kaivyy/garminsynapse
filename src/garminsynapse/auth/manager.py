"""Dual Auth Manager combining curl_cffi primary and Playwright fallback."""
import logging
from typing import Optional, Dict, Any
from garminsynapse.auth.tokens import TokenManager
from garminsynapse.auth.cffi_strategy import CffiStrategy
from garminsynapse.auth.playwright_strategy import PlaywrightAuthStrategy

logger = logging.getLogger(__name__)


class DualAuthManager:
    """Orchestrates fast curl_cffi login with automatic Playwright fallback."""

    def __init__(self, token_manager: Optional[TokenManager] = None):
        self.token_manager = token_manager or TokenManager()
        self.cffi_auth = CffiStrategy()
        self.playwright_auth = PlaywrightAuthStrategy()

    def login(self, email: str, password: str, prompt_mfa=None) -> Dict[str, Any]:
        """Attempt primary curl_cffi 5-stage login, falling back to Playwright if 429'd."""
        logger.info("Attempting primary 5-stage curl_cffi login...")
        try:
            tokens = self.cffi_auth.login(email, password, prompt_mfa=prompt_mfa)
            if tokens:
                self.token_manager.save_tokens(tokens)
                return tokens
        except Exception as e:
            logger.warning(f"Primary curl_cffi login failed: {e}. Falling back to Playwright...")

        # Fallback
        import asyncio
        tokens = asyncio.run(self.playwright_auth.login_with_browser(email, password))
        if tokens:
            self.token_manager.save_tokens(tokens)
            return tokens

        raise RuntimeError("Authentication failed with all strategies (curl_cffi & Playwright).")

    def get_active_tokens(self) -> Optional[Dict[str, Any]]:
        """Load active tokens from disk."""
        return self.token_manager.load_tokens()

    def logout(self) -> None:
        """Clear tokens from disk."""
        self.token_manager.delete_tokens()
