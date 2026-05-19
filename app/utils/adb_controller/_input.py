import asyncio
from typing import Optional

from app.utils.adb_controller._core import AdbError


class _InputMixin:

    async def click(self, x: int, y: int) -> None:
        await self._execute_command(
            "shell", "input", "tap", str(x), str(y), check=True
        )

    async def input_text(self, text: str) -> None:
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        shell_escaped = input_escaped.replace("'", "'\\''")
        cmd = self._build_command("shell", f"input text '{shell_escaped}'")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=self.default_timeout
        )
        if process.returncode != 0:
            raise AdbError(f"Input text failed: {stderr.decode('utf-8', errors='replace')}")

    async def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int = 500
    ) -> None:
        await self._execute_command(
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration),
            check=True
        )

    async def press_key(self, keycode: int) -> None:
        await self._execute_command(
            "shell", "input", "keyevent", str(keycode), check=True
        )

    async def press_back(self) -> None:
        await self.press_key(4)

    async def press_home(self) -> None:
        await self.press_key(3)

    async def press_enter(self) -> None:
        await self.press_key(66)

    async def start_app(self, package: str, activity: str) -> None:
        import re
        self._validate_package_name(package)
        if not re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', activity):
            raise AdbError(f"Invalid activity name: {activity}")
        component = f"{package}/{activity}"
        await self._execute_command(
            "shell", "am", "start", "-n", component, check=True
        )

    async def clear_app_data(self, package: str) -> None:
        self._validate_package_name(package)
        await self._execute_command(
            "shell", "pm", "clear", package, check=True
        )

    async def wake_up(self) -> None:
        await self._execute_command("shell", "input", "keyevent", "26", check=True)
