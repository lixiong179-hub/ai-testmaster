import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.utils.adb_controller._core import (
    AdbError,
    DeviceNotConnectedError,
    AdbCommandTimeoutError,
    DeviceInfo,
    _AdbControllerBase,
)
from app.utils.adb_controller._device import _DeviceMixin
from app.utils.adb_controller._input import _InputMixin


class _ConcreteController(_DeviceMixin, _InputMixin, _AdbControllerBase):
    pass


class TestAdbErrors:
    def test_adb_error(self):
        with pytest.raises(AdbError):
            raise AdbError("test")

    def test_device_not_connected(self):
        assert issubclass(DeviceNotConnectedError, AdbError)

    def test_command_timeout(self):
        assert issubclass(AdbCommandTimeoutError, AdbError)


class TestDeviceInfo:
    def test_defaults(self):
        info = DeviceInfo(udid="abc123", state="device")
        assert info.udid == "abc123"
        assert info.model is None
        assert info.android_version is None
        assert info.screen_size is None

    def test_full_info(self):
        info = DeviceInfo(
            udid="abc123",
            state="device",
            model="Pixel 6",
            android_version="13",
            screen_size=(1080, 2400),
        )
        assert info.model == "Pixel 6"
        assert info.screen_size == (1080, 2400)


class TestAdbControllerBase:
    def test_init_defaults(self):
        ctrl = _AdbControllerBase()
        assert ctrl.udid is None
        assert ctrl.adb_path == "adb"
        assert ctrl.default_timeout == 30

    def test_init_with_udid(self):
        ctrl = _AdbControllerBase(udid="device123")
        assert ctrl.udid == "device123"

    def test_build_command_no_udid(self):
        ctrl = _AdbControllerBase()
        cmd = ctrl._build_command("devices")
        assert cmd == ["adb", "devices"]

    def test_build_command_with_udid(self):
        ctrl = _AdbControllerBase(udid="device123")
        cmd = ctrl._build_command("shell", "ls")
        assert cmd == ["adb", "-s", "device123", "shell", "ls"]

    def test_validate_package_name_valid(self):
        _AdbControllerBase._validate_package_name("com.example.app")
        _AdbControllerBase._validate_package_name("org.test.myapp")

    def test_validate_package_name_invalid(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            _AdbControllerBase._validate_package_name("invalid")
        with pytest.raises(AdbError, match="Invalid package name"):
            _AdbControllerBase._validate_package_name("123.bad")

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self):
        ctrl = _AdbControllerBase(default_timeout=1)
        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired(cmd="adb", timeout=1)):
            with pytest.raises(AdbCommandTimeoutError):
                await ctrl._execute_command("devices")

    @pytest.mark.asyncio
    async def test_execute_command_failure(self):
        ctrl = _AdbControllerBase()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"error")
            with pytest.raises(AdbError, match="ADB command failed"):
                await ctrl._execute_command("devices", check=True)

    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        ctrl = _AdbControllerBase()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"output", stderr=b"")
            code, stdout, stderr = await ctrl._execute_command("devices")
            assert code == 0
            assert stdout == "output"


class TestDeviceMixin:
    @pytest.mark.asyncio
    async def test_list_devices(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "List of devices attached\ndevice123\tdevice\tmodel:Pixel6\n", "")):
            devices = await ctrl.list_devices()
            assert len(devices) == 1
            assert devices[0].udid == "device123"
            assert devices[0].model == "Pixel6"

    @pytest.mark.asyncio
    async def test_list_devices_empty(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "List of devices attached\n", "")):
            devices = await ctrl.list_devices()
            assert devices == []

    @pytest.mark.asyncio
    async def test_is_device_connected_true(self):
        ctrl = _ConcreteController(udid="device123")
        with patch.object(ctrl, "list_devices", return_value=[DeviceInfo(udid="device123", state="device")]):
            assert await ctrl.is_device_connected() is True

    @pytest.mark.asyncio
    async def test_is_device_connected_false(self):
        ctrl = _ConcreteController(udid="device123")
        with patch.object(ctrl, "list_devices", return_value=[DeviceInfo(udid="device123", state="offline")]):
            assert await ctrl.is_device_connected() is False

    @pytest.mark.asyncio
    async def test_is_device_connected_error(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "list_devices", side_effect=AdbError("error")):
            assert await ctrl.is_device_connected() is False

    @pytest.mark.asyncio
    async def test_get_device_info_found(self):
        ctrl = _ConcreteController(udid="device123")
        with patch.object(ctrl, "list_devices", return_value=[DeviceInfo(udid="device123", state="device")]):
            info = await ctrl.get_device_info()
            assert info is not None
            assert info.udid == "device123"

    @pytest.mark.asyncio
    async def test_get_device_info_not_found(self):
        ctrl = _ConcreteController(udid="nonexistent")
        with patch.object(ctrl, "list_devices", return_value=[DeviceInfo(udid="device123", state="device")]):
            info = await ctrl.get_device_info()
            assert info is None

    @pytest.mark.asyncio
    async def test_get_device_info_no_udid(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "list_devices", return_value=[DeviceInfo(udid="device123", state="device")]):
            info = await ctrl.get_device_info()
            assert info is not None

    @pytest.mark.asyncio
    async def test_get_screen_size_cached(self):
        ctrl = _ConcreteController()
        ctrl._screen_size = (1080, 2400)
        result = await ctrl.get_screen_size()
        assert result == (1080, 2400)

    @pytest.mark.asyncio
    async def test_get_screen_size_from_device(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "Physical size: 1080x2400", "")):
            result = await ctrl.get_screen_size()
            assert result == (1080, 2400)

    @pytest.mark.asyncio
    async def test_get_screen_size_parse_error(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "invalid output", "")):
            with pytest.raises(AdbError, match="Failed to parse screen size"):
                await ctrl.get_screen_size()

    @pytest.mark.asyncio
    async def test_get_current_activity(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "mResumedActivity=com.app/.MainActivity", "")):
            result = await ctrl.get_current_activity()
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_current_activity_none(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "no activity info", "")):
            result = await ctrl.get_current_activity()
            assert result is None

    @pytest.mark.asyncio
    async def test_is_screen_on(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "mWakefulness=Awake", "")):
            assert await ctrl.is_screen_on() is True

    @pytest.mark.asyncio
    async def test_is_screen_off(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "mWakefulness=Asleep", "")):
            assert await ctrl.is_screen_on() is False


class TestInputMixin:
    @pytest.mark.asyncio
    async def test_click(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.click(100, 200)

    @pytest.mark.asyncio
    async def test_input_text(self):
        ctrl = _ConcreteController()
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await ctrl.input_text("hello world")

    @pytest.mark.asyncio
    async def test_input_text_with_percent(self):
        ctrl = _ConcreteController()
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await ctrl.input_text("100%")

    @pytest.mark.asyncio
    async def test_swipe(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.swipe(100, 200, 100, 500)

    @pytest.mark.asyncio
    async def test_press_key(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.press_key(4)

    @pytest.mark.asyncio
    async def test_press_back(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")) as mock_exec:
            await ctrl.press_back()
            mock_exec.assert_called_once()
            assert "4" in mock_exec.call_args[0]

    @pytest.mark.asyncio
    async def test_press_home(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.press_home()

    @pytest.mark.asyncio
    async def test_press_enter(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.press_enter()

    @pytest.mark.asyncio
    async def test_start_app(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.start_app("com.example.app", ".MainActivity")

    @pytest.mark.asyncio
    async def test_start_app_invalid_package(self):
        ctrl = _ConcreteController()
        with pytest.raises(AdbError, match="Invalid package name"):
            await ctrl.start_app("invalid", ".MainActivity")

    @pytest.mark.asyncio
    async def test_start_app_invalid_activity(self):
        ctrl = _ConcreteController()
        with pytest.raises(AdbError, match="Invalid activity name"):
            await ctrl.start_app("com.example.app", "123invalid")

    @pytest.mark.asyncio
    async def test_clear_app_data(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.clear_app_data("com.example.app")

    @pytest.mark.asyncio
    async def test_clear_app_data_invalid_package(self):
        ctrl = _ConcreteController()
        with pytest.raises(AdbError, match="Invalid package name"):
            await ctrl.clear_app_data("invalid")

    @pytest.mark.asyncio
    async def test_wake_up(self):
        ctrl = _ConcreteController()
        with patch.object(ctrl, "_execute_command", return_value=(0, "", "")):
            await ctrl.wake_up()
