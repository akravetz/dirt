from playwright.async_api import Page, expect


async def test_login_page_renders(app_server: str, page: Page):
    """Login page should display a form with username, password, and submit."""
    await page.goto(f"{app_server}/login")
    await expect(page.locator('input[name="username"]')).to_be_visible()
    await expect(page.locator('input[name="password"]')).to_be_visible()
    await expect(page.locator('button[type="submit"]')).to_be_visible()
    await expect(page.locator("h1")).to_have_text("Dirt")


async def test_login_with_valid_credentials(app_server: str, page: Page):
    """Valid credentials should redirect to the index page."""
    await page.goto(f"{app_server}/login")
    await page.fill('input[name="username"]', "admin")
    await page.fill('input[name="password"]', "changeme")
    await page.click('button[type="submit"]')
    await page.wait_for_url(f"{app_server}/")
    await expect(page.locator("h1")).to_have_text("Dirt")


async def test_login_with_invalid_credentials(app_server: str, page: Page):
    """Invalid credentials should show an error on the login page."""
    await page.goto(f"{app_server}/login")
    await page.fill('input[name="username"]', "admin")
    await page.fill('input[name="password"]', "wrongpassword")
    await page.click('button[type="submit"]')
    await expect(page.locator(".error")).to_have_text("Invalid username or password")


async def test_logout(app_server: str, authenticated_page: Page):
    """Logout should clear session and redirect to login."""
    await authenticated_page.click('a[href="/logout"]')
    await authenticated_page.wait_for_url(f"{app_server}/login")
    await expect(authenticated_page.locator('input[name="username"]')).to_be_visible()


async def test_protected_route_redirects_to_login(app_server: str, page: Page):
    """Accessing the index without auth should redirect to login."""
    await page.goto(f"{app_server}/")
    await page.wait_for_url(f"{app_server}/login")
