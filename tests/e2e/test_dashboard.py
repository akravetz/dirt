from playwright.async_api import Page, expect


async def test_dashboard_displays_after_login(
    app_server: str, authenticated_page: Page
):
    """Dashboard should show both the live feed and sensor chart after login."""
    # Live feed section
    await expect(authenticated_page.locator(".feed-container")).to_be_visible()

    # Sensor section
    await expect(authenticated_page.locator("#temp-chart")).to_be_visible()
    await expect(authenticated_page.locator("#hum-chart")).to_be_visible()

    # Range buttons
    buttons = authenticated_page.locator(".range-btn")
    await expect(buttons).to_have_count(4)

    # Current stats load via HTMX
    await expect(authenticated_page.locator(".current-stats")).to_be_visible(
        timeout=10000
    )
