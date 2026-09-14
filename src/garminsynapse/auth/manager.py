"""Dual Auth Manager combining curl_cffi primary and Playwright fallback."""
import logging
import threading
from typing import Optional, Dict, Any
from garminsynapse.auth.tokens import TokenManager
from garminsynapse.auth.cffi_strategy import CffiStrategy
from garminsynapse.auth.playwright_strategy import PlaywrightAuthStrategy

logger = logging.getLogger(__name__)

# Module-level lock to prevent concurrent redundant logins / rate limits
_login_lock = threading.Lock()


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
                self.token_manager.save_credentials(email, password)
                return tokens
        except Exception as e:
            logger.warning(f"Primary curl_cffi login failed: {e}. Falling back to Playwright...")

        # Fallback
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                tokens = pool.submit(asyncio.run, self.playwright_auth.login_with_browser(email, password)).result()
        else:
            tokens = asyncio.run(self.playwright_auth.login_with_browser(email, password))
        if tokens:
            self.token_manager.save_tokens(tokens)
            self.token_manager.save_credentials(email, password)
            return tokens

        raise RuntimeError("Authentication failed with all strategies (curl_cffi & Playwright).")

    def get_active_tokens(self, auto_refresh: bool = True) -> Optional[Dict[str, Any]]:
        """Load active tokens from disk, auto-refreshing if expired and credentials are saved."""
        tokens = self.token_manager.load_tokens()
        if tokens and not self.token_manager.is_token_expired(tokens):
            return tokens

        # If expired or missing, auto-login if credentials exist
        if auto_refresh and self.token_manager.has_credentials():
            logger.info("Tokens missing or expired, attempting auto-login...")
            new_tokens = self.auto_login()
            if new_tokens:
                return new_tokens

        return tokens

    def auto_login(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """Attempt to automatically log in using saved credentials with thread deduplication."""
        with _login_lock:
            # Re-check inside lock in case another thread already refreshed
            if not force:
                tokens = self.token_manager.load_tokens()
                if tokens and not self.token_manager.is_token_expired(tokens):
                    logger.info("Tokens already refreshed by concurrent thread.")
                    return tokens

            creds = self.token_manager.load_credentials()
            if not creds:
                logger.warning("No saved credentials for auto-login.")
                return None
            logger.info(f"Auto-login triggered for {creds['email']}...")
            try:
                return self.login(creds['email'], creds['password'])
            except Exception as e:
                logger.error(f"Auto-login failed: {e}")
                return None

    def logout(self) -> None:
        """Clear tokens and saved credentials from disk."""
        self.token_manager.delete_tokens()
        self.token_manager.delete_credentials()
