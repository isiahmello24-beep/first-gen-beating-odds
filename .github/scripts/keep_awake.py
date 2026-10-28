"""Open the live Streamlit app in a real browser so Community Cloud does not put it to sleep.

A plain HTTP request does not wake a sleeping app: the sleep page needs a click on "Yes, get this app back up!".
Exit code 0 when the app's own page title and hero text render, 1 otherwise, so the Action log shows success or failure.
"""
import re
import sys
import time
from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

URL = "https://first-gen-beating-odds.streamlit.app"
WAKE_BUTTON = re.compile(r"get this app back up", re.I)
HERO_TEXT = "Share of the gap explained by money"


def main() -> int:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        print(f"opened {URL} in {time.time() - t0:.0f}s, title: {page.title()!r}")
        button = page.get_by_role("button", name=WAKE_BUTTON)
        try:
            button.wait_for(state="visible", timeout=20_000)
            button.click()
            print("app was asleep: clicked the wake button")
        except PWTimeout:
            print("no wake button: app was already up")
        try:
            page.wait_for_function("() => document.title && !/^streamlit$/i.test(document.title.trim())", timeout=240_000)
            page.get_by_text(HERO_TEXT, exact=False).first.wait_for(state="visible", timeout=240_000)
        except PWTimeout:
            print(f"FAILURE: app did not render within {time.time() - t0:.0f}s, title: {page.title()!r}")
            browser.close()
            return 1
        print(f"SUCCESS: title {page.title()!r}, hero text visible after {time.time() - t0:.0f}s")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
