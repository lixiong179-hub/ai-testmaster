import pytest
from app.utils.adb_controller._core import (
    AdbError,
    DeviceNotConnectedError,
    AdbCommandTimeoutError,
    DeviceInfo,
    _AdbControllerBase,
)


class TestAdbErrorHierarchy:
    def test_adb_error_is_exception(self):
        assert issubclass(AdbError, Exception)

    def test_device_not_connected_is_adb_error(self):
        assert issubclass(DeviceNotConnectedError, AdbError)

    def test_command_timeout_is_adb_error(self):
        assert issubclass(AdbCommandTimeoutError, AdbError)

    def test_raise_adb_error(self):
        with pytest.raises(AdbError):
            raise AdbError("test error")

    def test_raise_device_not_connected(self):
        with pytest.raises(DeviceNotConnectedError):
            raise DeviceNotConnectedError("device offline")

    def test_raise_command_timeout(self):
        with pytest.raises(AdbCommandTimeoutError):
            raise AdbCommandTimeoutError("timeout 30s")


class TestDeviceInfo:
    def test_normal(self):
        info = DeviceInfo(udid="emulator-5554", state="device")
        assert info.udid == "emulator-5554"
        assert info.state == "device"
        assert info.model is None
        assert info.android_version is None
        assert info.screen_size is None

    def test_with_all_fields(self):
        info = DeviceInfo(
            udid="device1",
            state="device",
            model="Pixel 6",
            android_version="14",
            screen_size=(1080, 2400),
        )
        assert info.model == "Pixel 6"
        assert info.android_version == "14"
        assert info.screen_size == (1080, 2400)


class TestAdbControllerBase:
    def test_init_defaults(self):
        ctrl = _AdbControllerBase()
        assert ctrl.udid is None
        assert ctrl.adb_path == "adb"
        assert ctrl.default_timeout == 30
        assert ctrl._screen_size is None

    def test_init_with_udid(self):
        ctrl = _AdbControllerBase(udid="emulator-5554")
        assert ctrl.udid == "emulator-5554"

    def test_init_custom_params(self):
        ctrl = _AdbControllerBase(
            udid="dev1", adb_path="/usr/bin/adb", default_timeout=60,
        )
        assert ctrl.adb_path == "/usr/bin/adb"
        assert ctrl.default_timeout == 60

    def test_build_command_without_udid(self):
        ctrl = _AdbControllerBase()
        cmd = ctrl._build_command("devices")
        assert cmd == ["adb", "devices"]

    def test_build_command_with_udid(self):
        ctrl = _AdbControllerBase(udid="emulator-5554")
        cmd = ctrl._build_command("shell", "ls")
        assert cmd == ["adb", "-s", "emulator-5554", "shell", "ls"]

    def test_validate_package_name_valid(self):
        _AdbControllerBase._validate_package_name("com.example.app")
        _AdbControllerBase._validate_package_name("org.project.module")

    def test_validate_package_name_invalid(self):
        with pytest.raises(AdbError):
            _AdbControllerBase._validate_package_name("invalid")
        with pytest.raises(AdbError):
            _AdbControllerBase._validate_package_name("123.bad")
        with pytest.raises(AdbError):
            _AdbControllerBase._validate_package_name("")
