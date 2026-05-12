"""
ADB控制器模块

提供基于Android Debug Bridge (ADB)的设备控制能力，用于移动端自动化测试。
封装了设备管理、屏幕操作、输入控制、应用管理等常用ADB命令。

设计要点：
    - 异步架构：所有ADB命令通过asyncio异步执行，不阻塞事件循环
    - 跨平台兼容：Windows使用subprocess.run，Linux/Mac使用asyncio.subprocess
    - 输入校验：包名和Activity名通过正则校验，防止命令注入
    - 超时控制：所有命令支持自定义超时，默认30秒

异常体系：
    - AdbError: ADB操作基础异常
    - DeviceNotConnectedError: 设备未连接
    - AdbCommandTimeoutError: 命令执行超时

核心类：
    - AdbController: ADB控制器
    - DeviceInfo: 设备信息数据类

依赖：
    - asyncio: 异步执行框架
    - subprocess: 进程管理（Windows平台）
"""
import asyncio
import re
import subprocess
import sys
from typing import Optional, List, Tuple
from dataclasses import dataclass


class AdbError(Exception):
    """ADB操作基础异常"""
    pass


class DeviceNotConnectedError(AdbError):
    """设备未连接异常"""
    pass


class AdbCommandTimeoutError(AdbError):
    """ADB命令执行超时异常"""
    pass


@dataclass
class DeviceInfo:
    """Android设备信息数据类

    Attributes:
        udid: 设备唯一标识符
        state: 设备状态（device/offline/unauthorized等）
        model: 设备型号（如Pixel 6）
        android_version: Android版本号
        screen_size: 屏幕尺寸（宽, 高）元组
    """
    udid: str
    state: str
    model: Optional[str] = None
    android_version: Optional[str] = None
    screen_size: Optional[Tuple[int, int]] = None


# Android包名合法正则 — 必须符合Java包名规范（如com.example.app）
_PACKAGE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9]*(\.[a-zA-Z][a-zA-Z0-9]*)+$')


class AdbController:
    """ADB控制器

    封装ADB命令行工具，提供异步的设备控制接口。
    支持设备管理、屏幕截图、点击/滑动/输入、应用启停等操作。

    跨平台实现：
        Windows: 使用subprocess.run同步执行（因asyncio.subprocess在Windows上有限制）
        Linux/Mac: 使用asyncio.create_subprocess_exec异步执行

    Attributes:
        udid: 目标设备UDID，为None时操作首个可用设备
        adb_path: ADB可执行文件路径，默认"adb"（依赖PATH）
        default_timeout: 默认命令超时时间（秒）
    """

    def __init__(
        self,
        udid: Optional[str] = None,
        adb_path: str = "adb",
        default_timeout: int = 30
    ):
        self.udid = udid
        self.adb_path = adb_path
        self.default_timeout = default_timeout
        self._screen_size: Optional[Tuple[int, int]] = None  # 缓存屏幕尺寸

    def _build_command(self, *args) -> List[str]:
        """构建ADB命令行参数列表

        如果指定了udid，自动添加-s参数选择目标设备。

        Args:
            *args: ADB子命令和参数

        Returns:
            List[str]: 完整的命令行参数列表
        """
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
        """执行ADB命令的内部方法

        根据操作系统选择不同的执行方式：
        - Windows: subprocess.run（同步，通过run_in_executor转为异步）
        - Linux/Mac: asyncio.create_subprocess_exec（原生异步）

        Args:
            *args: ADB子命令和参数
            timeout: 超时时间（秒），None使用default_timeout
            check: 是否检查返回码，非0时抛出AdbError

        Returns:
            Tuple[int, str, str]: (返回码, 标准输出, 标准错误)

        Raises:
            AdbCommandTimeoutError: 命令执行超时
            AdbError: 命令执行失败（check=True时）
        """
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

    async def list_devices(self) -> List[DeviceInfo]:
        """列出所有已连接的ADB设备

        Returns:
            List[DeviceInfo]: 设备信息列表
        """
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
        """检查目标设备是否已连接且状态为device

        Returns:
            bool: 设备已连接返回True，否则返回False
        """
        try:
            devices = await self.list_devices()
            if self.udid:
                return any(d.udid == self.udid and d.state == "device" for d in devices)
            return any(d.state == "device" for d in devices)
        except AdbError:
            return False

    async def get_device_info(self) -> Optional[DeviceInfo]:
        """获取目标设备的详细信息

        Returns:
            Optional[DeviceInfo]: 设备信息，设备不存在返回None
        """
        devices = await self.list_devices()
        if self.udid:
            for d in devices:
                if d.udid == self.udid:
                    return d
        elif devices:
            return devices[0]
        return None

    async def get_screen_size(self) -> Tuple[int, int]:
        """获取设备屏幕尺寸（缓存结果）

        首次调用时通过ADB命令获取，后续调用返回缓存值。

        Returns:
            Tuple[int, int]: (宽度, 高度) 像素值

        Raises:
            AdbError: 无法解析屏幕尺寸时抛出
        """
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
        """截取设备屏幕截图

        使用adb exec-out screencap命令获取PNG格式的屏幕截图。
        注意：此方法直接使用asyncio.subprocess，不经过_execute_command，
        因为需要直接读取二进制stdout数据。

        Returns:
            bytes: PNG格式的截图字节数据

        Raises:
            AdbError: 截图失败或返回空数据时抛出
        """
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

    async def click(self, x: int, y: int) -> None:
        """点击屏幕指定坐标

        Args:
            x: 横坐标（像素）
            y: 纵坐标（像素）
        """
        await self._execute_command(
            "shell", "input", "tap", str(x), str(y), check=True
        )

    async def input_text(self, text: str) -> None:
        """在当前焦点输入框中输入文本

        对特殊字符进行ADB shell转义：
        - % 转义为 %%（ADB input text的转义规则）
        - 空格转义为 %s
        - 单引号使用 '\'' 转义（shell层转义）

        Args:
            text: 要输入的文本内容

        Raises:
            AdbError: 输入失败时抛出
        """
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
        """从坐标(x1,y1)滑动到坐标(x2,y2)

        Args:
            x1: 起始横坐标
            y1: 起始纵坐标
            x2: 终止横坐标
            y2: 终止纵坐标
            duration: 滑动持续时间（毫秒），默认500ms
        """
        await self._execute_command(
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration),
            check=True
        )

    async def press_key(self, keycode: int) -> None:
        """按下指定按键

        Args:
            keycode: Android按键码（如3=HOME, 4=BACK, 66=ENTER）
        """
        await self._execute_command(
            "shell", "input", "keyevent", str(keycode), check=True
        )

    async def press_back(self) -> None:
        """按下返回键（keycode=4）"""
        await self.press_key(4)

    async def press_home(self) -> None:
        """按下Home键（keycode=3）"""
        await self.press_key(3)

    async def press_enter(self) -> None:
        """按下Enter键（keycode=66）"""
        await self.press_key(66)

    async def start_app(self, package: str, activity: str) -> None:
        """启动指定应用

        通过am start命令启动应用的指定Activity。
        包名和Activity名会经过正则校验，防止命令注入。

        Args:
            package: 应用包名（如com.example.app）
            activity: Activity名（如.MainActivity）

        Raises:
            AdbError: 包名或Activity名格式无效，或启动失败
        """
        self._validate_package_name(package)
        if not re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', activity):
            raise AdbError(f"Invalid activity name: {activity}")
        component = f"{package}/{activity}"
        await self._execute_command(
            "shell", "am", "start", "-n", component, check=True
        )

    async def clear_app_data(self, package: str) -> None:
        """清除应用数据

        通过pm clear命令清除指定应用的所有用户数据（相当于卸载重装）。

        Args:
            package: 应用包名

        Raises:
            AdbError: 包名格式无效，或清除失败
        """
        self._validate_package_name(package)
        await self._execute_command(
            "shell", "pm", "clear", package, check=True
        )

    @staticmethod
    def _validate_package_name(package: str) -> None:
        """校验Android包名格式

        包名必须符合Java包名规范：以字母开头，由字母、数字和点组成。
        此校验防止恶意包名导致的命令注入攻击。

        Args:
            package: 待校验的包名

        Raises:
            AdbError: 包名格式不合法
        """
        if not _PACKAGE_NAME_PATTERN.match(package):
            raise AdbError(f"Invalid package name format: {package}")

    async def get_current_activity(self) -> Optional[str]:
        """获取当前前台Activity

        通过dumpsys activity命令获取当前正在显示的Activity。

        Returns:
            Optional[str]: 当前Activity的组件名（如com.app/.MainActivity），获取失败返回None
        """
        _, stdout, _ = await self._execute_command(
            "shell", "dumpsys", "activity", "activities", check=False
        )
        match = re.search(r"mResumedActivity.*?(\S+/\S+)", stdout)
        if match:
            return match.group(1)
        return None

    async def is_screen_on(self) -> bool:
        """检查屏幕是否亮起

        通过dumpsys power命令检查屏幕唤醒状态。

        Returns:
            bool: 屏幕亮起返回True，熄灭返回False
        """
        _, stdout, _ = await self._execute_command(
            "shell", "dumpsys", "power", check=False
        )
        return "mWakefulness=Awake" in stdout or "Display Power: state=ON" in stdout

    async def wake_up(self) -> None:
        """唤醒屏幕（按下电源键，keycode=26）"""
        await self._execute_command("shell", "input", "keyevent", "26", check=True)
