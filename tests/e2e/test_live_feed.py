from playwright.async_api import Page, expect


async def test_live_feed_page_loads(app_server: str, authenticated_page: Page):
    """The live feed page should load with the feed container."""
    await expect(authenticated_page.locator(".feed-container")).to_be_visible()


async def test_live_feed_has_status(app_server: str, authenticated_page: Page):
    """The feed status area should be present."""
    await expect(authenticated_page.locator(".feed-status")).to_be_visible()


async def test_live_feed_has_htmx_polling(app_server: str, authenticated_page: Page):
    """The feed container should have HTMX polling configured."""
    feed_div = authenticated_page.locator('[hx-get="/feed/image"]')
    await expect(feed_div).to_be_visible()
    await expect(feed_div).to_have_attribute("hx-trigger", "load, every 5s")
