"""
Real browser login smoke test for Hongen admin.

This test is intentionally excluded from the default regression run by pytest.ini
because it opens an external site and needs a visual model API key for captcha.
Run explicitly with:
    python -m pytest tests/test_hongen_login_real.py -m "real_browser or real_api" -s
"""

import asyncio
from datetime import datetime
import json
import os
import re
import sys
import unittest

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.utils.browser_controller_v2 import BrowserConfig, BrowserControllerV2
from app.utils.unified_vision_model import create_vision_model

pytestmark = [pytest.mark.real_browser, pytest.mark.real_api]


class TestHongenLoginReal(unittest.TestCase):
    def setUp(self):
        self.base_url = os.getenv("HONGEN_BASE_URL", "https://admin-jxw-panda-test.ihumand.com")
        self.username = os.getenv("HONGEN_USERNAME", "admin123")
        self.password = os.getenv("HONGEN_PASSWORD", "admin123")
        self.headless = os.getenv("HONGEN_HEADLESS", "0") == "1"
        self.vision_model = create_vision_model(os.getenv("HONGEN_VISION_MODEL"))
        self.record_process = os.getenv("HONGEN_RECORD_PROCESS", "0") == "1"
        self.artifact_dir = os.getenv("HONGEN_ARTIFACT_DIR", "")
        if self.record_process and not self.artifact_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.artifact_dir = os.path.join("test_screenshots", f"hongen_login_process_{timestamp}")
        if self.artifact_dir:
            os.makedirs(self.artifact_dir, exist_ok=True)

    def test_01_navigate_to_login_page(self):
        async def run_test():
            controller = await self._new_controller()
            try:
                await controller.navigate(self.base_url)
                page = self._page(controller)
                await page.wait_for_load_state("domcontentloaded")
                await self._capture_step(page, "01_login_page_loaded")
                page_info = await controller.get_page_info()

                self.assertIn(self.base_url, page_info["url"])
                self.assertGreaterEqual(await page.locator("input:visible").count(), 2)
            finally:
                await self._close_controller(controller)

        asyncio.run(run_test())

    def test_02_login_with_captcha(self):
        async def run_test():
            if not self.vision_model.api_key:
                api_key_env = self.vision_model.provider_config.api_key_env
                pytest.skip(f"{api_key_env} is required for Hongen captcha recognition")

            controller = await self._new_controller()
            try:
                await controller.navigate(self.base_url)
                page = self._page(controller)
                await page.wait_for_load_state("domcontentloaded")
                await self._capture_step(page, "01_login_page_loaded")

                await self._fill_login_form(page, controller)
                await self._submit_login(page)
                await self._capture_step(page, "06_login_submitted")
                await self._assert_login_success(page, controller)
                await self._capture_step(page, "07_home_page_loaded")
            finally:
                await self._close_controller(controller)

        asyncio.run(run_test())

    async def _new_controller(self) -> BrowserControllerV2:
        config = BrowserConfig(
            headless=self.headless,
            viewport_width=1920,
            viewport_height=1080,
            record_video=self.record_process,
            video_dir=self.artifact_dir or None,
        )
        controller = BrowserControllerV2(config)
        await controller.initialize()
        return controller

    def _page(self, controller: BrowserControllerV2):
        page = getattr(controller, "_page", None)
        if page is None:
            raise RuntimeError("browser page is not initialized")
        return page

    async def _fill_login_form(self, page, controller: BrowserControllerV2) -> None:
        inputs = page.locator("input:visible")
        input_count = await inputs.count()
        self.assertGreaterEqual(input_count, 3, "login page should contain username, password and captcha inputs")

        await inputs.nth(0).fill(self.username)
        await self._capture_step(page, "02_username_filled")
        await inputs.nth(1).fill(self.password)
        await self._capture_step(page, "03_password_filled")

        captcha = await self._recognize_captcha(page, controller)
        self.assertTrue(captcha, "captcha recognition returned empty result")
        await inputs.nth(2).fill(captcha)
        await self._capture_step(page, "05_captcha_filled")

    async def _submit_login(self, page) -> None:
        login_button = page.get_by_role("button", name=re.compile(r"登录|login", re.I))
        if await login_button.count():
            await login_button.first.click()
            return

        visible_buttons = page.locator("button:visible")
        if await visible_buttons.count():
            await visible_buttons.last.click()
            return

        raise AssertionError("login button was not found")

    async def _assert_login_success(self, page, controller: BrowserControllerV2) -> None:
        try:
            await page.wait_for_function(
                """
                ([baseUrl]) => {
                    const url = window.location.href;
                    return !url.startsWith(baseUrl) ||
                        /productLineManage|index|home|dashboard/i.test(url);
                }
                """,
                arg=[self.base_url],
                timeout=10000,
            )
        except Exception:
            await self._save_diagnostics(page, controller, "hongen_login_failed")
            page_text = (await page.locator("body").inner_text()).strip()
            current_url = page.url
            self.fail(
                "Hongen login did not enter the home page. "
                f"url={current_url}, page_text={page_text[:500]!r}"
            )

        current_url = page.url
        self.assertNotEqual(current_url.rstrip("/"), self.base_url.rstrip("/"))

    async def _recognize_captcha(self, page, controller: BrowserControllerV2) -> str:
        captcha_image = await self._find_captcha_image(page)
        if captcha_image is not None:
            screenshot = await captcha_image.screenshot()
        else:
            screenshot = await controller.take_screenshot()

        self._write_artifact("04_captcha_image.png", screenshot, binary=True)

        prompt = """
Read the captcha image on this login page.
It is usually a simple arithmetic expression, for example 5-2=?.
Return only JSON:
{"captcha_original":"5-2=?","captcha_result":"3"}
If it is text instead of arithmetic, put the exact text in captcha_result.
"""
        response = self.vision_model.analyze_image(screenshot, prompt)
        self._write_artifact("04_captcha_response.txt", response)
        return self._parse_captcha_response(response)

    async def _find_captcha_image(self, page):
        images = page.locator("img:visible")
        for index in range(await images.count()):
            image = images.nth(index)
            box = await image.bounding_box()
            if not box:
                continue
            if box["width"] >= 40 and box["height"] >= 20:
                return image
        return None

    def _parse_captcha_response(self, response: str) -> str:
        if not response:
            return ""

        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                data = json.loads(match.group(0))
                result = data.get("captcha_result")
                if result is not None:
                    return str(result).strip()
            except json.JSONDecodeError:
                pass

        arithmetic = re.search(r"(\d+)\s*([+\-xX*/÷])\s*(\d+)", response)
        if arithmetic:
            left = int(arithmetic.group(1))
            operator = arithmetic.group(2)
            right = int(arithmetic.group(3))
            if operator == "+":
                return str(left + right)
            if operator == "-":
                return str(left - right)
            if operator in ("x", "X", "*"):
                return str(left * right)
            if operator in ("/", "÷") and right != 0:
                return str(left // right)

        number = re.search(r"\d+", response)
        return number.group(0) if number else ""

    async def _save_diagnostics(self, page, controller: BrowserControllerV2, name: str) -> None:
        screenshot = await controller.take_screenshot()
        with open(f"{name}.png", "wb") as file:
            file.write(screenshot)
        with open(f"{name}.txt", "w", encoding="utf-8") as file:
            file.write(f"url={page.url}\n\n")
            file.write(await page.locator("body").inner_text())

    async def _capture_step(self, page, name: str) -> None:
        if not self.record_process:
            return
        screenshot_path = os.path.join(self.artifact_dir, f"{name}.png")
        text_path = os.path.join(self.artifact_dir, f"{name}.txt")
        await page.screenshot(path=screenshot_path, full_page=True)
        with open(text_path, "w", encoding="utf-8") as file:
            file.write(f"url={page.url}\n\n")
            try:
                file.write(await page.locator("body").inner_text())
            except Exception as exc:
                file.write(f"<failed to read body text: {exc}>")
        print(f"[Hongen process] saved {screenshot_path}")

    def _write_artifact(self, filename: str, content, binary: bool = False) -> None:
        if not self.record_process:
            return
        path = os.path.join(self.artifact_dir, filename)
        mode = "wb" if binary else "w"
        kwargs = {} if binary else {"encoding": "utf-8"}
        with open(path, mode, **kwargs) as file:
            file.write(content)
        print(f"[Hongen process] saved {path}")

    async def _close_controller(self, controller: BrowserControllerV2) -> None:
        video_path = await controller.close()
        if video_path:
            print(f"[Hongen process] video saved {video_path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
