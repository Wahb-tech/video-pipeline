import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

VIDEO = Path(os.environ.get("ZOOP_VIDEO", "/tmp/zoop_test.mp4"))
CAPTION = os.environ.get("ZOOP_CAPTION", "ONE DAY.")
STATE = os.environ.get("ZOOP_STATE", "zoop_state.json")
SCHEDULE_DATE = os.environ.get("ZOOP_SCHEDULE_DATE", "")
SCHEDULE_TIME = os.environ.get("ZOOP_SCHEDULE_TIME", "")
SCHEDULE_COMMIT = os.environ.get("ZOOP_SCHEDULE_COMMIT", "0") == "1"

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


def schedule_post(page):
    if not SCHEDULE_DATE or not SCHEDULE_TIME:
        raise RuntimeError("Schedule date/time missing")

    button = page.get_by_role(
        "button",
        name=re.compile(r"schedule post", re.I),
    )

    button.first.wait_for(state="visible", timeout=15000)
    button.first.click()

    page.wait_for_timeout(1200)

    def fill_field(kind, value):
        labels = page.get_by_label(re.compile(kind, re.I))

        for i in range(labels.count()):
            field = labels.nth(i)
            try:
                if field.is_visible():
                    field.fill(value)
                    return True
            except Exception:
                pass

        selectors = [
            f'input[type="{kind}"]',
            f'input[placeholder*="{kind}" i]',
            f'input[aria-label*="{kind}" i]',
            f'[role="textbox"][aria-label*="{kind}" i]',
        ]

        for selector in selectors:
            fields = page.locator(selector)

            for i in range(fields.count()):
                field = fields.nth(i)

                try:
                    if not field.is_visible():
                        continue

                    field.fill(value)
                    return True
                except Exception:
                    try:
                        field.click()
                        page.keyboard.press("Control+A")
                        page.keyboard.type(value)
                        return True
                    except Exception:
                        pass

        return False

    if not fill_field("date", SCHEDULE_DATE):
        page.screenshot(
            path="zoop_schedule_field_error.png",
            full_page=True,
        )
        raise RuntimeError("Schedule date field not found")

    if not fill_field("time", SCHEDULE_TIME):
        page.screenshot(
            path="zoop_schedule_field_error.png",
            full_page=True,
        )
        raise RuntimeError("Schedule time field not found")

    page.screenshot(
        path="zoop_schedule_ready.png",
        full_page=True,
    )

    final_button = page.get_by_role(
        "button",
        name=re.compile(r"^schedule$", re.I),
    )

    final_button.first.wait_for(
        state="visible",
        timeout=10000,
    )

    if not SCHEDULE_COMMIT:
        print("ZOOP_SCHEDULE_DRY_RUN_OK", flush=True)
        print(f"DATE={SCHEDULE_DATE}", flush=True)
        print(f"TIME={SCHEDULE_TIME}", flush=True)
        return

    final_button.first.click()
    page.wait_for_timeout(3000)

    if "/connection-error" in page.url:
        raise RuntimeError("ZOOP connection error while scheduling")

    print("ZOOP_SCHEDULE_SUBMITTED", flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    context = browser.new_context(
        storage_state=STATE,
        viewport={"width": 1440, "height": 1000},
        timezone_id="Europe/Zurich",
    )

    def zoop_api_bridge(route):
        request = route.request

        try:
            if request.method == "OPTIONS":
                requested_headers = request.headers.get(
                    "access-control-request-headers",
                    "authorization,content-type",
                )

                requested_method = request.headers.get(
                    "access-control-request-method",
                    "GET",
                )

                route.fulfill(
                    status=204,
                    headers={
                        "Access-Control-Allow-Origin": "https://app.zoop.club",
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Headers": requested_headers,
                        "Access-Control-Allow-Methods": (
                            f"{requested_method}, GET, POST, PUT, PATCH, DELETE, OPTIONS"
                        ),
                        "Access-Control-Max-Age": "600",
                    },
                    body="",
                )

                print(
                    "CORS_BRIDGE_PREFLIGHT",
                    requested_method,
                    requested_headers,
                    flush=True,
                )
                return

            response = route.fetch(timeout=60000)

            headers = dict(response.headers)
            headers["access-control-allow-origin"] = "https://app.zoop.club"
            headers["access-control-allow-credentials"] = "true"

            print(
                "CORS_BRIDGE_RESPONSE",
                response.status,
                request.method,
                request.url,
                flush=True,
            )

            route.fulfill(
                response=response,
                headers=headers,
            )

        except Exception as exc:
            print(
                "CORS_BRIDGE_ERROR",
                request.method,
                request.url,
                repr(exc),
                flush=True,
            )
            route.abort()

    context.route(
        "https://api-v2.influencerindex.com/**",
        zoop_api_bridge,
    )

    page = context.new_page()

    def log_response(response):
        try:
            if response.status >= 400:
                print(
                    "HTTP_ERROR",
                    response.status,
                    response.request.method,
                    response.url,
                    flush=True,
                )
        except Exception:
            pass

    def log_request_failed(request):
        try:
            print(
                "REQUEST_FAILED",
                request.method,
                request.url,
                request.failure,
                flush=True,
            )
        except Exception:
            pass

    def log_console(msg):
        try:
            if msg.type in ("error", "warning"):
                print(
                    "BROWSER_CONSOLE",
                    msg.type,
                    msg.text,
                    flush=True,
                )
        except Exception:
            pass

    page.on("response", log_response)
    page.on("requestfailed", log_request_failed)
    page.on("console", log_console)

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

    print("=== ZOOP DEBUG ===")
    print("URL:", page.url)
    print("TITLE:", page.title())

    try:
        print("BODY TEXT:")
        print(page.locator("body").inner_text()[:12000])
    except Exception as e:
        print("BODY TEXT ERROR:", e)

    print("FRAMES:", len(page.frames))
    for i, frame in enumerate(page.frames):
        print("FRAME", i, frame.url)

    html = page.content()
    Path("zoop_debug.html").write_text(html)

    page.screenshot(
        path="zoop_before_caption.png",
        full_page=True,
    )

    if "/connection-error" in page.url:
        page.screenshot(
            path="zoop_connection_error.png",
            full_page=True,
        )
        raise RuntimeError(
            "ZOOP redirected to connection-error after the upload/Next step"
        )

    fill_caption(page)

    schedule_post(page)

    page.screenshot(
        path="zoop_dry_run.png",
        full_page=True,
    )

    print("ZOOP_DRY_RUN_OK")
    print(f"URL={page.url}")
    print(f"CAPTION={CAPTION}")

    browser.close()
