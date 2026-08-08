"""Playwright browser fallback login for Cloudflare CAPTCHA / MFA."""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PlaywrightAuthStrategy:
    """Fallback strategy using Playwright headless browser to bypass Turnstile CAPTCHA."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def login_with_browser(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Launch browser, perform login, and extract session cookies & tokens."""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()
                logger.info("Navigating to Garmin Connect login via Playwright...")
                await page.goto("https://connect.garmin.com/signin")
                
                # Fill credentials if elements present
                if await page.query_selector("input[type='email']"):
                    await page.fill("input[type='email']", email)
                    await page.fill("input[type='password']", password)
                    await page.click("button[type='submit']")
                    await page.wait_for_timeout(5000)

                cookies = await context.cookies()
                await browser.close()

                cookie_dict = {c["name"]: c["value"] for c in cookies}
                if "SESSIONID" in cookie_dict or "GARMIN-SSO-GUID" in cookie_dict:
                    return {"cookies": cookie_dict, "source": "playwright"}
                return None
        except Exception as e:
            logger.error(f"Playwright auth failed: {e}")
            return None
