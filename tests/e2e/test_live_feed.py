from playwright.async_api import Page, expect


async def test_live_feed_page_loads(app_server: str, authenticated_page: Page):
    """The live feed page should load with the feed container."""
    await expect(authenticated_page.locator(".feed-container")).to_be_visible()


async def test_live_feed_has_status(app_server: str, authenticated_page: Page):
    """The feed status area should be present."""
    await expect(authenticated_page.locator(".feed-status")).to_be_visible()


async def test_live_feed_has_htmx_polling(app_server: str, authenticated_page: Page):
    """The live feed image should self-refresh via HTMX."""
    feed_img = authenticated_page.get_by_role("img", name="Live feed")
    await expect(feed_img).to_be_visible()
    await expect(feed_img).to_have_attribute("hx-trigger", "load delay:15s")
