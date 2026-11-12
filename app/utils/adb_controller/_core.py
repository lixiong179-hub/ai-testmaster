import asyncio
import re
import subprocess
import sys
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
    model: str | None = None
    android_version: str | None = None
    screen_size: tuple[int, int] | None = None


_PACKAGE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9]*(\.[a-zA-Z][a-zA-Z0-9]*)+$')


class _AdbControllerBase:

    def __init__(
        self,
        udid: str | None = None,
        adb_path: str = "adb",
        default_timeout: int = 30
    ):
        self.udid = udid
        self.adb_path = adb_path
        self.default_timeout = default_timeout
        self._screen_size: tuple[int, int] | None = None

    def _build_command(self, *args) -> list[str]:
        cmd = [self.adb_path]
        if self.udid:
            cmd.extend(["-s", self.udid])
        cmd.extend(args)
        return cmd

    async def _execute_command(
        self,
        *args,
        timeout: int | None = None,
        check: bool = True
    ) -> tuple[int, str, str]:
        cmd = self._build_command(*args)
        effective_timeout = timeout or self.default_timeout
        try:
            loop = asyncio.get_event_loop()
            if sys.platform == 'win32':
                proc = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        cmd,
                        capture_output=True,
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
        except (TimeoutError, subprocess.TimeoutExpired):
            raise AdbCommandTimeoutError(
                f"ADB command timed out after {effective_timeout}s: {' '.join(cmd)}"
            )

    @staticmethod
    def _validate_package_name(package: str) -> None:
        if not _PACKAGE_NAME_PATTERN.match(package):
            raise AdbError(f"Invalid package name format: {package}")
