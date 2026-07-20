import pytest
import time
from app.services.captcha_service import CaptchaService


class TestCaptchaGenerate:
    def setup_method(self):
        # 保存原 _instance 以便 teardown 还原，避免污染后续测试的 singleton 查询
        self._orig_instance = CaptchaService._instance
        CaptchaService._instance = None
        self.svc = CaptchaService()

    def teardown_method(self):
        # 还原 _instance 到原始 captcha_service 单例
        CaptchaService._instance = self._orig_instance

    def test_generate_returns_tuple(self):
        captcha_id, code = self.svc.generate()
        assert isinstance(captcha_id, str)
        assert isinstance(code, str)
        assert len(captcha_id) == 32
        assert len(code) == 4

    def test_generate_custom_length(self):
        _, code = self.svc.generate(length=6)
        assert len(code) == 6

    def test_generate_code_is_digits(self):
        _, code = self.svc.generate()
        assert code.isdigit()

    def test_generate_unique_ids(self):
        id1, _ = self.svc.generate()
        id2, _ = self.svc.generate()
        assert id1 != id2

    def test_ip_rate_limit(self):
        # conftest.py 设置 CAPTCHA_RATE_LIMIT=10000 以放宽批量测试限制,
        # 本测试需低阈值验证触发逻辑, 故显式设置实例属性为 10
        self.svc._rate_limit = 10
        for _ in range(10):
            self.svc.generate(ip="1.2.3.4")
        with pytest.raises(Exception, match="请求过于频繁"):
            self.svc.generate(ip="1.2.3.4")

    def test_different_ip_no_limit(self):
        for _ in range(10):
            self.svc.generate(ip="1.1.1.1")
        self.svc.generate(ip="2.2.2.2")


class TestCaptchaVerify:
    def setup_method(self):
        self._orig_instance = CaptchaService._instance
        CaptchaService._instance = None
        self.svc = CaptchaService()

    def teardown_method(self):
        CaptchaService._instance = self._orig_instance

    def test_verify_correct_code(self):
        captcha_id, code = self.svc.generate()
        assert self.svc.verify(captcha_id, code) is True

    def test_verify_wrong_code(self):
        captcha_id, _ = self.svc.generate()
        assert self.svc.verify(captcha_id, "0000") is False

    def test_verify_case_insensitive(self):
        captcha_id, code = self.svc.generate()
        assert self.svc.verify(captcha_id, code.lower()) is True

    def test_verify_empty_captcha_id(self):
        assert self.svc.verify("", "1234") is False

    def test_verify_empty_input(self):
        assert self.svc.verify("some_id", "") is False

    def test_verify_nonexistent_id(self):
        assert self.svc.verify("nonexistent", "1234") is False

    def test_verify_one_time_use(self):
        captcha_id, code = self.svc.generate()
        assert self.svc.verify(captcha_id, code) is True
        assert self.svc.verify(captcha_id, code) is False

    def test_verify_expired_code(self):
        captcha_id, code = self.svc.generate()
        stored = self.svc._store[captcha_id]
        self.svc._store[captcha_id] = (stored[0], time.time() - 1)
        assert self.svc.verify(captcha_id, code) is False


class TestCaptchaCleanup:
    def setup_method(self):
        self._orig_instance = CaptchaService._instance
        CaptchaService._instance = None
        self.svc = CaptchaService()

    def teardown_method(self):
        CaptchaService._instance = self._orig_instance

    def test_cleanup_removes_expired(self):
        self.svc._store["expired_id"] = ("1234", time.time() - 1)
        self.svc._store["valid_id"] = ("5678", time.time() + 300)
        self.svc._cleanup()
        assert "expired_id" not in self.svc._store
        assert "valid_id" in self.svc._store

    def test_cleanup_truncates_used_set(self):
        for i in range(1100):
            self.svc._used.add(f"used_{i}")
        self.svc._cleanup()
        assert len(self.svc._used) <= 1000
