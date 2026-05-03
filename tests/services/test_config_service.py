"""
M1-T15 Config Service 测试模块

覆盖：
    - get_config 从 DB 读取
    - get_config 缓存命中
    - get_config 默认值
    - set_config 新建/更新
    - set_config 写入 audit_log
    - set_config 未知 key 抛 ValueError
    - init_default_configs 幂等
    - _cast_value 类型转换
    - _cast_value 非法值
    - clear_cache
"""
import pytest

from app.models.pipeline_config import PipelineConfig
from app.services.config_service import (
    get_config,
    set_config,
    init_default_configs,
    clear_cache,
    _cast_value,
    DEFAULT_CONFIGS,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


class TestGetConfig:
    def test_get_config_from_db(self, db):
        row = PipelineConfig(key="TEST_KEY", value="42", value_type="int")
        db.add(row)
        db.flush()
        result = get_config(db, "TEST_KEY")
        assert result == 42

    def test_get_config_cache_hit(self, db):
        row = PipelineConfig(key="CACHED_KEY", value="hello", value_type="str")
        db.add(row)
        db.flush()
        result1 = get_config(db, "CACHED_KEY")
        db.query(PipelineConfig).filter(PipelineConfig.key == "CACHED_KEY").delete()
        db.flush()
        result2 = get_config(db, "CACHED_KEY")
        assert result1 == result2 == "hello"

    def test_get_config_default(self, db):
        result = get_config(db, "NONEXISTENT_KEY", default="fallback")
        assert result == "fallback"

    def test_get_config_default_none(self, db):
        result = get_config(db, "NONEXISTENT_KEY")
        assert result is None


class TestSetConfig:
    def test_set_config_new_key(self, db, testUser):
        row = set_config(db, "LIFECYCLE_DEPRECATE_COOLDOWN_HOURS", 48, actor_id=testUser.id)
        assert row.value == "48"
        assert row.id is not None

    def test_set_config_update_existing(self, db, testUser):
        set_config(db, "AI_TOKEN_BUDGET_PER_RUN", 500000)
        row = set_config(db, "AI_TOKEN_BUDGET_PER_RUN", 600000, actor_id=testUser.id)
        assert row.value == "600000"

    def test_set_config_unknown_key_raises(self, db):
        with pytest.raises(ValueError, match="Unknown config key"):
            set_config(db, "NONEXISTENT_KEY", "value")

    def test_set_config_refreshes_cache(self, db):
        set_config(db, "CONFIDENCE_THRESHOLD", 0.7)
        result = get_config(db, "CONFIDENCE_THRESHOLD")
        assert result == 0.7
        set_config(db, "CONFIDENCE_THRESHOLD", 0.8)
        result = get_config(db, "CONFIDENCE_THRESHOLD")
        assert result == 0.8

    def test_set_config_writes_audit_log(self, db, testUser):
        from app.services.audit_service import query_logs
        set_config(db, "REVIEW_LOCK_TTL_HOURS", 48, actor_id=testUser.id)
        logs = query_logs(db, action="config_change")
        assert any(
            l.detail and l.detail.get("key") == "REVIEW_LOCK_TTL_HOURS"
            for l in logs
        )

    def test_set_config_audit_contains_old_value(self, db, testUser):
        from app.services.audit_service import query_logs
        set_config(db, "PIPELINE_PAUSE_TIMEOUT_DAYS", 7, actor_id=testUser.id)
        set_config(db, "PIPELINE_PAUSE_TIMEOUT_DAYS", 14, actor_id=testUser.id)
        logs = query_logs(db, action="config_change")
        change_logs = [
            l for l in logs
            if l.detail and l.detail.get("key") == "PIPELINE_PAUSE_TIMEOUT_DAYS"
            and l.detail.get("old_value") is not None
        ]
        assert len(change_logs) >= 1
        assert change_logs[0].detail["old_value"] == "7"
        assert change_logs[0].detail["new_value"] == "14"


class TestInitDefaultConfigs:
    def test_init_creates_all_defaults(self, db):
        init_default_configs(db)
        count = db.query(PipelineConfig).count()
        assert count == len(DEFAULT_CONFIGS)

    def test_init_idempotent(self, db):
        init_default_configs(db)
        count1 = db.query(PipelineConfig).count()
        init_default_configs(db)
        count2 = db.query(PipelineConfig).count()
        assert count1 == count2

    def test_init_all_keys_accessible(self, db):
        init_default_configs(db)
        for key in DEFAULT_CONFIGS:
            result = get_config(db, key)
            assert result is not None


class TestCastValue:
    def test_cast_int(self):
        assert _cast_value("42", "int") == 42

    def test_cast_float(self):
        assert _cast_value("3.14", "float") == 3.14

    def test_cast_str(self):
        assert _cast_value("hello", "str") == "hello"

    def test_cast_bool_true(self):
        assert _cast_value("true", "bool") is True

    def test_cast_bool_false(self):
        assert _cast_value("false", "bool") is False

    def test_cast_bool_1(self):
        assert _cast_value("1", "bool") is True

    def test_cast_json(self):
        assert _cast_value('{"a": 1}', "json") == {"a": 1}

    def test_cast_invalid_int_raises(self):
        with pytest.raises(ValueError, match="Cannot cast"):
            _cast_value("abc", "int")

    def test_cast_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Cannot cast"):
            _cast_value("{invalid", "json")


class TestClearCache:
    def test_clear_cache_forces_db_read(self, db):
        row = PipelineConfig(key="CACHE_TEST", value="original", value_type="str")
        db.add(row)
        db.flush()
        result1 = get_config(db, "CACHE_TEST")
        assert result1 == "original"
        row.value = "modified"
        db.flush()
        result2 = get_config(db, "CACHE_TEST")
        assert result2 == "original"
        clear_cache()
        result3 = get_config(db, "CACHE_TEST")
        assert result3 == "modified"
