import asyncio
import re
from typing import Optional, List, Tuple

from app.utils.adb_controller._core import (
    AdbError,
    DeviceInfo,
)


class _DeviceMixin:

    async def list_devices(self) -> List[DeviceInfo]:
        _, stdout, _ = await self._execute_command("devices", "-l", check=True)
        devices = []
        for line in stdout.split("\n")[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            udid = parts[0]
            state = parts[1]
            model = None
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1]
                elif part.startswith("device:"):
                    pass
            devices.append(DeviceInfo(udid=udid, state=state, model=model))
        return devices

    async def is_device_connected(self) -> bool:
        try:
            devices = await self.list_devices()
            if self.udid:
                return any(d.udid == self.udid and d.state == "device" for d in devices)
            return any(d.state == "device" for d in devices)
        except AdbError:
            return False

    async def get_device_info(self) -> Optional[DeviceInfo]:
        devices = await self.list_devices()
        if self.udid:
            for d in devices:
                if d.udid == self.udid:
                    return d
        elif devices:
            return devices[0]
        return None

    async def get_screen_size(self) -> Tuple[int, int]:
        if self._screen_size:
            return self._screen_size
        _, stdout, _ = await self._execute_command(
            "shell", "wm", "size", check=True
        )
        match = re.search(r"(\d+)x(\d+)", stdout)
        if match:
            width, height = int(match.group(1)), int(match.group(2))
            self._screen_size = (width, height)
            return self._screen_size
        raise AdbError(f"Failed to parse screen size: {stdout}")

    async def take_screenshot(self) -> bytes:
        cmd = self._build_command("exec-out", "screencap", "-p")
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
            raise AdbError(f"Screenshot failed: {stderr.decode('utf-8', errors='replace')}")
        if not stdout:
            raise AdbError("Screenshot returned empty data")
        return stdout

    async def get_current_activity(self) -> Optional[str]:
        _, stdout, _ = await self._execute_command(
            "shell", "dumpsys", "activity", "activities", check=False
        )
        match = re.search(r"mResumedActivity.*?(\S+/\S+)", stdout)
        if match:
            return match.group(1)
        return None

    async def is_screen_on(self) -> bool:
        _, stdout, _ = await self._execute_command(
            "shell", "dumpsys", "power", check=False
        )
        return "mWakefulness=Awake" in stdout or "Display Power: state=ON" in stdout
