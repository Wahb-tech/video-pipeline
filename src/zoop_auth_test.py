from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state="zoop_state.json")
    page = context.new_page()

    page.goto(
        "https://app.zoop.club/profile",
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(5000)

    url = page.url.lower()

    if any(x in url for x in ["login", "signin", "sign-in", "signup", "sign-up"]):
        raise RuntimeError(f"ZOOP session not authenticated: {page.url}")

    print("ZOOP_SESSION_OK")
    print(f"Final URL: {page.url}")

    browser.close()
