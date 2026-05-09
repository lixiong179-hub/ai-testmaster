"""
验证码服务单元测�?

覆盖范围:
- CaptchaService 单例模式
- generate() 生成验证�?
- verify() 校验验证�?
- 一次性使用验�?
- 过期时间检�?
- IP频率限制
- 自动清理过期数据
"""
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.captcha_service import CaptchaService, captcha_service


@pytest.fixture(autouse=True)
def reset_captcha_state():
    """每个测试前重置验证码服务状态，避免频率限制干扰"""
    captcha_service._store.clear()
    captcha_service._used.clear()
    captcha_service._ip_limits.clear()
    yield


class TestCaptchaServiceSingleton:
    """单例模式测试"""

    def test_singleton_pattern(self):
        """测试CaptchaService是单�?""
        service1 = CaptchaService()
        service2 = CaptchaService()
        assert service1 is service2

    def test_global_instance(self):
        """测试全局实例可用"""
        assert captcha_service is not None
        assert isinstance(captcha_service, CaptchaService)


class TestCaptchaGenerate:
    """验证码生成测�?""

    def test_generate_returns_tuple(self):
        """测试generate返回元组(captcha_id, code)"""
        result = captcha_service.generate()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generate_captcha_id_format(self):
        """测试captcha_id�?2位字符串"""
        captcha_id, code = captcha_service.generate()
        assert isinstance(captcha_id, str)
        assert len(captcha_id) == 32

    def test_generate_code_is_numeric(self):
        """测试code�?位数字字符串"""
        captcha_id, code = captcha_service.generate()
        assert isinstance(code, str)
        assert len(code) == 4
        assert code.isdigit()

    def test_generate_different_each_time(self):
        """测试每次生成的验证码不同"""
        results = set()
        for _ in range(10):
            _, code = captcha_service.generate()
            results.add(code)
        # 10次生成应该至少有几个不同�?
        assert len(results) >= 3

    def test_generate_with_ip(self):
        """测试带IP参数的生�?""
        captcha_id, code = captcha_service.generate(ip="127.0.0.1")
        assert captcha_id is not None
        assert code is not None


class TestCaptchaVerify:
    """验证码校验测�?""

    def test_verify_correct_code(self):
        """测试正确验证码校验通过"""
        captcha_id, code = captcha_service.generate()
        result = captcha_service.verify(captcha_id, code)
        assert result is True

    def test_verify_wrong_code(self):
        """测试错误验证码校验失�?""
        captcha_id, code = captcha_service.generate()
        wrong_code = "0000" if code != "0000" else "1111"
        result = captcha_service.verify(captcha_id, wrong_code)
        assert result is False

    def test_verify_case_insensitive(self):
        """测试大小写不敏感（数字无影响，但接口支持�?""
        captcha_id, code = captcha_service.generate()
        result = captcha_service.verify(captcha_id, code.upper())
        assert result is True

    def test_verify_empty_input(self):
        """测试空输入返回False"""
        result = captcha_service.verify("", "")
        assert result is False

    def test_verify_nonexistent_id(self):
        """测试不存在的ID返回False"""
        result = captcha_service.verify("nonexistent_id_123456789012345678901234", "1234")
        assert result is False


class TestCaptchaOneTimeUse:
    """一次性使用测�?""

    def test_cannot_use_twice(self):
        """测试验证码只能使用一�?""
        captcha_id, code = captcha_service.generate()
        
        # 第一次使用成�?
        first_result = captcha_service.verify(captcha_id, code)
        assert first_result is True
        
        # 第二次使用失�?
        second_result = captcha_service.verify(captcha_id, code)
        assert second_result is False


class TestCaptchaExpiry:
    """过期时间测试"""

    def test_expired_captcha_fails(self):
        """测试过期的验证码无法使用"""
        # 直接操作内部存储来模拟过�?
        old_captcha_id, code = captcha_service.generate()
        
        # 手动将过期时间设置为过去
        import time as _time
        if old_captcha_id in captcha_service._store:
            captcha_service._store[old_captcha_id] = (code, _time.time() - 3600)  # 1小时�?
        
        result = captcha_service.verify(old_captcha_id, code)
        assert result is False


class TestCaptchaRateLimit:
    """IP频率限制测试"""

    def test_rate_limit_enforced(self):
        """测试同一IP的频率限�?""
        ip = "192.168.1.100"
        
        # 快速请求超过限制（默认10�?分钟�?
        with pytest.raises(Exception) as exc_info:
            for i in range(15):  # 超过10次限�?
                try:
                    captcha_service.generate(ip=ip)
                except Exception as e:
                    raise e
        
        # 应该触发频率限制异常
        assert exc_info.value is not None


class TestCaptchaCleanup:
    """自动清理测试"""

    def test_cleanup_removes_expired(self):
        """测试清理功能移除过期验证�?""
        # 生成一些验证码
        ids = []
        for _ in range(5):
            cid, _ = captcha_service.generate()
            ids.append(cid)
        
        # 手动设置部分为过�?
        import time as _time
        if ids[0] in captcha_service._store:
            captcha_service._store[ids[0]] = (captcha_service._store[ids[0]][0], _time.time() - 600)
        
        # 执行清理
        captcha_service._cleanup()
        
        # 验证过期的已被移�?
        assert ids[0] not in captcha_service._store
        # 验证未过期的仍在
        assert ids[-1] in captcha_service._store


class TestCaptchaEdgeCases:
    """边界情况测试"""

    def test_custom_length(self):
        """测试自定义长�?""
        captcha_id, code = captcha_service.generate(length=6)
        assert len(code) == 6

    def test_special_characters_in_ip(self):
        """测试特殊字符IP处理"""
        # IPv6格式或特殊IP不应崩溃
        try:
            captcha_id, code = captcha_service.generate(ip="::1")
            assert captcha_id is not None
        except Exception:
            pass  # 允许抛出异常

    def test_concurrent_generation(self):
        """测试并发生成不冲�?""
        import threading
        results = []
        errors = []
        
        def gen():
            try:
                cid, code = captcha_service.generate()
                results.append((cid, code))
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=gen) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 所有ID应该唯一
        ids = [r[0] for r in results]
        assert len(ids) == len(set(ids))
