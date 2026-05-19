import asyncio
import re
import subprocess
import sys
from typing import Optional, List, Tuple
from dataclasses import dataclass


class AdbError(Exception):
    pass


class DeviceNotConnectedError(AdbError):
    pass


class AdbCommandTimeoutError(AdbError):
    pass


@dataclass
class DeviceInfo:
    udid: str
    state: str
    model: Optional[str] = None
    android_version: Optional[str] = None
    screen_size: Optional[Tuple[int, int]] = None


_PACKAGE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9]*(\.[a-zA-Z][a-zA-Z0-9]*)+$')


class _AdbControllerBase:

    def __init__(
        self,
        udid: Optional[str] = None,
        adb_path: str = "adb",
        default_timeout: int = 30
    ):
        self.udid = udid
        self.adb_path = adb_path
        self.default_timeout = default_timeout
        self._screen_size: Optional[Tuple[int, int]] = None

    def _build_command(self, *args) -> List[str]:
        cmd = [self.adb_path]
        if self.udid:
            cmd.extend(["-s", self.udid])
        cmd.extend(args)
        return cmd

    async def _execute_command(
        self,
        *args,
        timeout: Optional[int] = None,
        check: bool = True
    ) -> Tuple[int, str, str]:
        cmd = self._build_command(*args)
        effective_timeout = timeout or self.default_timeout
        try:
            loop = asyncio.get_event_loop()
            if sys.platform == 'win32':
                proc = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=effective_timeout,
                        check=False
                    )
                )
                stdout_str = proc.stdout.decode("utf-8", errors="replace").strip()
                stderr_str = proc.stderr.decode("utf-8", errors="replace").strip()
                return_code = proc.returncode
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout
                )
                return_code = process.returncode
                stdout_str = stdout.decode("utf-8", errors="replace").strip()
                stderr_str = stderr.decode("utf-8", errors="replace").strip()
            if check and return_code != 0:
                raise AdbError(f"ADB command failed: {stderr_str or stdout_str}")
            return return_code, stdout_str, stderr_str
        except (asyncio.TimeoutError, subprocess.TimeoutExpired):
            raise AdbCommandTimeoutError(
                f"ADB command timed out after {effective_timeout}s: {' '.join(cmd)}"
            )

    @staticmethod
    def _validate_package_name(package: str) -> None:
        if not _PACKAGE_NAME_PATTERN.match(package):
            raise AdbError(f"Invalid package name format: {package}")
