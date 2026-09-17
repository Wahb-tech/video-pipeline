import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(
        description="Open ZOOP locally and save a fresh Playwright session."
    )
    parser.add_argument("--output", default="zoop_state.json")
    args = parser.parse_args()
    output = Path(args.output).resolve()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(
            "https://app.zoop.club/profile",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        print("Connect to ZOOP in the opened browser window.")
        input("Once your ZOOP profile is visible, return here and press Enter... ")
        page.goto(
            "https://app.zoop.club/profile",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(3000)
        if any(value in page.url.lower() for value in ("login", "signin", "sign-in", "signup", "sign-up")):
            browser.close()
            raise RuntimeError(f"ZOOP login was not completed: {page.url}")
        context.storage_state(path=str(output))
        os.chmod(output, 0o600)
        browser.close()

    print(f"Fresh ZOOP session saved to {output}")
    print("Keep this file private and delete it after updating the GitHub secret.")


if __name__ == "__main__":
    main()
