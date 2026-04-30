import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def capture_screenshots():
    """Capture mobile-viewport screenshots of the dashboard."""

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Mobile viewport (iPhone 12)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
        )
        page = await context.new_page()

        # Screenshots directory
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)

        base_url = "http://localhost:8800"

        try:
            # 1. Home page (available slots)
            print("Capturing home page...")
            await page.goto(f"{base_url}/")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=screenshots_dir / "01_home.png")
            print("  ✓ Saved to 01_home.png")

            # 2. Change log page
            print("Capturing change log page...")
            await page.goto(f"{base_url}/changelog")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=screenshots_dir / "02_changelog.png")
            print("  ✓ Saved to 02_changelog.png")

            # 3. Settings page
            print("Capturing settings page...")
            await page.goto(f"{base_url}/settings")
            await page.wait_for_load_state("networkidle")
            # Scroll to show settings form
            await page.evaluate("window.scrollTo(0, 500)")
            await page.screenshot(path=screenshots_dir / "03_settings.png")
            print("  ✓ Saved to 03_settings.png")

            print(f"\n✓ All screenshots saved to {screenshots_dir}/")

        except Exception as e:
            print(f"✗ Screenshot capture failed: {e}")
            return False
        finally:
            await context.close()
            await browser.close()

        return True

if __name__ == "__main__":
    success = asyncio.run(capture_screenshots())
    exit(0 if success else 1)
