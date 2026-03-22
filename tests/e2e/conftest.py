import multiprocessing
import time

import httpx
import pytest
import pytest_asyncio
import uvicorn
from playwright.async_api import Page


def _run_server():
    """Run the app in a subprocess for E2E testing."""
    uvicorn.run("dirt.app:app", host="127.0.0.1", port=8765, log_level="warning")


@pytest.fixture(scope="session")
def app_server():
    """Start the app server in a background process for the test session."""
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()
    for _ in range(30):
        try:
            r = httpx.get("http://127.0.0.1:8765/login", timeout=1)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("App server did not start in time")
    yield "http://127.0.0.1:8765"
    proc.kill()
    proc.join(timeout=5)


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_page(app_server: str, page: Page) -> Page:
    """A Playwright page that is already logged in."""
    await page.goto(f"{app_server}/login")
    await page.fill('input[name="username"]', "admin")
    await page.fill('input[name="password"]', "changeme")
    await page.click('button[type="submit"]')
    await page.wait_for_url(f"{app_server}/")
    return page
