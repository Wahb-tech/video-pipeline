import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

VIDEO = Path(os.environ.get("ZOOP_VIDEO", "/tmp/zoop_test.mp4"))
CAPTION = os.environ.get("ZOOP_CAPTION", "ONE DAY.")
STATE = os.environ.get("ZOOP_STATE", "zoop_state.json")

def click_if_visible(locator):
    try:
        if locator.count() > 0 and locator.first.is_visible():
            locator.first.click()
            return True
    except Exception:
        pass
    return False

def fill_caption(page):
    page.wait_for_timeout(3000)

    selectors = [
        'textarea[placeholder*="caption" i]',
        'input[placeholder*="caption" i]',
        '[aria-label*="caption" i]',
        '[data-placeholder*="caption" i]',
        'textarea',
        '[contenteditable="true"]',
        '[role="textbox"]',
    ]

    for selector in selectors:
        locator = page.locator(selector)

        for i in range(locator.count()):
            field = locator.nth(i)

            try:
                if not field.is_visible():
                    continue

                field.click()
                field.fill(CAPTION)
                print(f"Caption filled with selector: {selector}")
                return
            except Exception:
                try:
                    field.click()
                    page.keyboard.press("ControlOrMeta+A")
                    page.keyboard.type(CAPTION)
                    print(f"Caption typed with selector: {selector}")
                    return
                except Exception:
                    pass

    print("Visible inputs:")
    for selector in ["input", "textarea", '[contenteditable="true"]', '[role="textbox"]']:
        locator = page.locator(selector)

        for i in range(locator.count()):
            field = locator.nth(i)
            try:
                if field.is_visible():
                    print(
                        selector,
                        i,
                        "placeholder=",
                        field.get_attribute("placeholder"),
                        "aria-label=",
                        field.get_attribute("aria-label"),
                        "class=",
                        field.get_attribute("class"),
                    )
            except Exception:
                pass

    page.screenshot(path="zoop_caption_not_found.png", full_page=True)
    raise RuntimeError("Caption field not found")

def upload_video(page):
    file_input = page.locator('input[type="file"]')

    if file_input.count() > 0:
        file_input.first.set_input_files(str(VIDEO))
        return

    candidates = [
        page.get_by_role("button", name=re.compile("create", re.I)),
        page.get_by_role("button", name=re.compile("new post", re.I)),
        page.get_by_role("button", name=re.compile("upload", re.I)),
        page.locator('button[aria-label*="post" i]'),
        page.locator('button[aria-label*="create" i]'),
    ]

    for candidate in candidates:
        try:
            if candidate.count() > 0 and candidate.first.is_visible():
                with page.expect_file_chooser(timeout=5000) as chooser:
                    candidate.first.click()
                chooser.value.set_files(str(VIDEO))
                return
        except Exception:
            pass

    raise RuntimeError("Upload control not found")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    context = browser.new_context(
        storage_state=STATE,
        viewport={"width": 1440, "height": 1000},
        timezone_id="Europe/Zurich",
    )

    page = context.new_page()

    page.goto(
        "https://app.zoop.club/profile",
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(4000)

    if "login" in page.url.lower() or "sign" in page.url.lower():
        raise RuntimeError("ZOOP session expired")

    click_if_visible(
        page.get_by_role("button", name=re.compile("^accept$", re.I))
    )

    upload_video(page)

    page.get_by_text("9:16", exact=True).wait_for(
        state="visible",
        timeout=60000,
    )
    page.get_by_text("9:16", exact=True).click()

    page.get_by_role(
        "button",
        name=re.compile("^Next$", re.I),
    ).click()

    page.wait_for_timeout(3000)

    fill_caption(page)

    page.screenshot(
        path="zoop_dry_run.png",
        full_page=True,
    )

    print("ZOOP_DRY_RUN_OK")
    print(f"URL={page.url}")
    print(f"CAPTION={CAPTION}")

    browser.close()
