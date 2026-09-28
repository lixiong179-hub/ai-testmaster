"""SelfHealingConfigService 单元测试。

覆盖：
    - get_project_config：项目无配置 → 默认值
    - get_project_config：项目有配置 → 合并值
    - get_project_config：全局开关关 → enabled=False
    - get_project_config：项目不存在 → enabled=False
    - set_project_config：成功更新 Project.config
    - set_project_config：项目不存在 → 404
    - set_project_config：strategies 含非法值 → 400
    - set_project_config：token_limit 超范围 → 400
    - is_self_healing_enabled：全局关 → False
    - is_self_healing_enabled：项目关 → False
    - is_self_healing_enabled：都开 → True

被测：app/services/self_healing/config_service.py（SelfHealingConfigService）
使用真实测试库（db fixture 事务隔离）。
"""
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.self_healing.config_service import (
    ALLOWED_STRATEGIES,
    CONFIG_KEY,
    DEFAULT_SELF_HEALING_CONFIG,
    TOKEN_LIMIT_MAX,
    TOKEN_LIMIT_MIN,
    SelfHealingConfigService,
)


@pytest.fixture
def seed_project(db: Session, testUser):
    """创建测试项目（无自愈配置）。"""
    project = Project(
        name="config_test_project",
        user_id=testUser.id,
        description="config service test",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture
def seed_project_with_config(db: Session, testUser):
    """创建带自愈配置的测试项目。"""
    project = Project(
        name="config_test_project_with_config",
        user_id=testUser.id,
        description="project with config",
        status=1,
        project_type="web",
        config={
            CONFIG_KEY: {
                "enabled": True,
                "strategies": ["mcp", "vision", "stagehand"],
                "token_limit": 3000,
            }
        },
    )
    db.add(project)
    db.flush()
    return project


class TestGetProjectConfig:
    """get_project_config 配置读取与合并。"""

    def test_get_config_no_stored_returns_defaults(
        self, db: Session, seed_project
    ):
        """项目无配置 → 返回默认值（全局开关开启时 enabled=True）。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            config = service.get_project_config(seed_project.id)
        assert config["enabled"] == DEFAULT_SELF_HEALING_CONFIG["enabled"]
        assert config["strategies"] == DEFAULT_SELF_HEALING_CONFIG["strategies"]
        assert config["token_limit"] == DEFAULT_SELF_HEALING_CONFIG["token_limit"]

    def test_get_config_no_stored_global_disabled_returns_enabled_false(
        self, db: Session, seed_project
    ):
        """项目无配置 + 全局关 → enabled=False。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                False,
            )
            config = service.get_project_config(seed_project.id)
        assert config["enabled"] is False

    def test_get_config_with_stored_returns_merged(
        self, db: Session, seed_project_with_config
    ):
        """项目有配置 → 返回合并值（存储值覆盖默认值）。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            config = service.get_project_config(seed_project_with_config.id)
        assert config["enabled"] is True
        assert config["strategies"] == ["mcp", "vision", "stagehand"]
        assert config["token_limit"] == 3000

    def test_get_config_global_disabled_overrides_project(
        self, db: Session, seed_project_with_config
    ):
        """全局开关关 → enabled=False（即使项目开启）。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                False,
            )
            config = service.get_project_config(seed_project_with_config.id)
            assert config["enabled"] is False

    def test_get_config_project_not_exists_returns_disabled(self, db: Session):
        """项目不存在 → 返回 enabled=False 的默认配置。"""
        service = SelfHealingConfigService(db)
        config = service.get_project_config(999999)
        assert config["enabled"] is False
        assert config["strategies"] == DEFAULT_SELF_HEALING_CONFIG["strategies"]
        assert config["token_limit"] == DEFAULT_SELF_HEALING_CONFIG["token_limit"]

    def test_get_config_partial_stored_merges_with_defaults(
        self, db: Session, testUser
    ):
        """项目配置仅含部分字段 → 与默认值合并。"""
        project = Project(
            name="partial_config_project",
            user_id=testUser.id,
            description="partial",
            status=1,
            project_type="web",
            config={CONFIG_KEY: {"token_limit": 5000}},
        )
        db.add(project)
        db.flush()

        service = SelfHealingConfigService(db)
        config = service.get_project_config(project.id)
        # token_limit 来自存储，其余来自默认
        assert config["token_limit"] == 5000
        assert config["strategies"] == DEFAULT_SELF_HEALING_CONFIG["strategies"]

    def test_get_config_invalid_stored_type_returns_defaults(
        self, db: Session, testUser
    ):
        """项目 config 字段非 dict → 返回默认值。"""
        project = Project(
            name="invalid_config_project",
            user_id=testUser.id,
            description="invalid",
            status=1,
            project_type="web",
            config="not a dict",  # type: ignore[arg-type]
        )
        db.add(project)
        db.flush()

        service = SelfHealingConfigService(db)
        config = service.get_project_config(project.id)
        assert config["strategies"] == DEFAULT_SELF_HEALING_CONFIG["strategies"]

    def test_get_config_invalid_self_healing_config_value(
        self, db: Session, testUser
    ):
        """self_healing_config 值非 dict → 返回默认值。"""
        project = Project(
            name="invalid_sh_config_project",
            user_id=testUser.id,
            description="invalid sh",
            status=1,
            project_type="web",
            config={CONFIG_KEY: "invalid"},  # 应为 dict
        )
        db.add(project)
        db.flush()

        service = SelfHealingConfigService(db)
        config = service.get_project_config(project.id)
        assert config["strategies"] == DEFAULT_SELF_HEALING_CONFIG["strategies"]


class TestSetProjectConfig:
    """set_project_config 配置写入与校验。"""

    def test_set_config_success(self, db: Session, seed_project):
        """成功更新 Project.config['self_healing_config']。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            result = service.set_project_config(
                seed_project.id,
                {
                    "enabled": True,
                    "strategies": ["mcp", "vision"],
                    "token_limit": 2000,
                },
            )
        assert result["enabled"] is True
        assert result["strategies"] == ["mcp", "vision"]
        assert result["token_limit"] == 2000

        # 验证 DB 持久化
        db.expire_all()
        project = db.query(Project).filter(Project.id == seed_project.id).first()
        assert project.config[CONFIG_KEY]["strategies"] == ["mcp", "vision"]

    def test_set_config_partial_input_filled_with_defaults(
        self, db: Session, seed_project
    ):
        """输入仅含部分字段 → 用默认值填充。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            result = service.set_project_config(
                seed_project.id,
                {"token_limit": 5000},
            )
        assert result["enabled"] == DEFAULT_SELF_HEALING_CONFIG["enabled"]
        assert result["strategies"] == DEFAULT_SELF_HEALING_CONFIG["strategies"]
        assert result["token_limit"] == 5000

    def test_set_config_project_not_exists_raises_404(self, db: Session):
        """项目不存在 → 404。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(999999, {"enabled": True})
        assert exc_info.value.status_code == 404
        assert "项目不存在" in exc_info.value.detail

    def test_set_config_invalid_strategy_raises_400(self, db: Session, seed_project):
        """strategies 含非法值 → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id,
                {"strategies": ["mcp", "invalid_strategy"]},
            )
        assert exc_info.value.status_code == 400
        assert "strategies 含非法值" in exc_info.value.detail

    def test_set_config_token_limit_below_min_raises_400(
        self, db: Session, seed_project
    ):
        """token_limit < TOKEN_LIMIT_MIN → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id,
                {"token_limit": TOKEN_LIMIT_MIN - 1},
            )
        assert exc_info.value.status_code == 400
        assert "token_limit 取值范围" in exc_info.value.detail

    def test_set_config_token_limit_above_max_raises_400(
        self, db: Session, seed_project
    ):
        """token_limit > TOKEN_LIMIT_MAX → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id,
                {"token_limit": TOKEN_LIMIT_MAX + 1},
            )
        assert exc_info.value.status_code == 400
        assert "token_limit 取值范围" in exc_info.value.detail

    def test_set_config_token_limit_boundary_min(self, db: Session, seed_project):
        """token_limit = TOKEN_LIMIT_MIN → 成功。"""
        service = SelfHealingConfigService(db)
        result = service.set_project_config(
            seed_project.id, {"token_limit": TOKEN_LIMIT_MIN}
        )
        assert result["token_limit"] == TOKEN_LIMIT_MIN

    def test_set_config_token_limit_boundary_max(self, db: Session, seed_project):
        """token_limit = TOKEN_LIMIT_MAX → 成功。"""
        service = SelfHealingConfigService(db)
        result = service.set_project_config(
            seed_project.id, {"token_limit": TOKEN_LIMIT_MAX}
        )
        assert result["token_limit"] == TOKEN_LIMIT_MAX

    def test_set_config_invalid_enabled_type_raises_400(
        self, db: Session, seed_project
    ):
        """enabled 非 bool → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id, {"enabled": "yes"}  # type: ignore[dict-item]
            )
        assert exc_info.value.status_code == 400
        assert "enabled 必须为布尔值" in exc_info.value.detail

    def test_set_config_strategies_non_list_raises_400(
        self, db: Session, seed_project
    ):
        """strategies 非 list → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id, {"strategies": "mcp"}  # type: ignore[dict-item]
            )
        assert exc_info.value.status_code == 400
        assert "strategies 必须为字符串列表" in exc_info.value.detail

    def test_set_config_strategies_non_string_element_raises_400(
        self, db: Session, seed_project
    ):
        """strategies 元素非字符串 → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id, {"strategies": ["mcp", 123]}  # type: ignore[list-item]
            )
        assert exc_info.value.status_code == 400

    def test_set_config_token_limit_non_int_raises_400(
        self, db: Session, seed_project
    ):
        """token_limit 非 int → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id, {"token_limit": "2000"}  # type: ignore[dict-item]
            )
        assert exc_info.value.status_code == 400
        assert "token_limit 必须为整数" in exc_info.value.detail

    def test_set_config_token_limit_bool_rejected(self, db: Session, seed_project):
        """token_limit 为 bool（int 子类）→ 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id, {"token_limit": True}
            )
        assert exc_info.value.status_code == 400

    def test_set_config_non_dict_raises_400(self, db: Session, seed_project):
        """config 非 dict → 400。"""
        service = SelfHealingConfigService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.set_project_config(
                seed_project.id, "not a dict"  # type: ignore[arg-type]
            )
        assert exc_info.value.status_code == 400
        assert "配置必须为字典对象" in exc_info.value.detail

    def test_set_config_global_disabled_returns_enabled_false(
        self, db: Session, seed_project
    ):
        """全局开关关时，set_project_config 返回 enabled=False。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                False,
            )
            result = service.set_project_config(
                seed_project.id, {"enabled": True}
            )
            # 全局关，即使项目开，返回 enabled=False
            assert result["enabled"] is False

    def test_set_config_preserves_other_project_config_keys(
        self, db: Session, testUser
    ):
        """set_project_config 应保留 Project.config 中的其他 key。"""
        project = Project(
            name="multi_config_project",
            user_id=testUser.id,
            description="multi",
            status=1,
            project_type="web",
            config={"other_key": {"foo": "bar"}, "another": 123},
        )
        db.add(project)
        db.flush()

        service = SelfHealingConfigService(db)
        service.set_project_config(project.id, {"enabled": True})

        db.expire_all()
        proj = db.query(Project).filter(Project.id == project.id).first()
        # 其他 key 应保留
        assert proj.config["other_key"] == {"foo": "bar"}
        assert proj.config["another"] == 123
        # self_healing_config 应写入
        assert CONFIG_KEY in proj.config


class TestIsSelfHealingEnabled:
    """is_self_healing_enabled 快捷判断。"""

    def test_enabled_when_global_and_project_both_on(
        self, db: Session, seed_project_with_config
    ):
        """全局开 + 项目开 → True。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            assert service.is_self_healing_enabled(seed_project_with_config.id) is True

    def test_disabled_when_global_off(self, db: Session, seed_project_with_config):
        """全局关 → False（即使项目开）。"""
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                False,
            )
            assert service.is_self_healing_enabled(seed_project_with_config.id) is False

    def test_disabled_when_project_off(self, db: Session, seed_project):
        """项目无配置（默认 enabled=True）+ 全局开 → True。

        注意：DEFAULT_SELF_HEALING_CONFIG['enabled'] = True，
        所以项目无配置时，默认是开的。
        """
        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            # 项目无配置，使用默认 enabled=True
            assert service.is_self_healing_enabled(seed_project.id) is True

    def test_disabled_when_project_explicitly_disabled(
        self, db: Session, testUser
    ):
        """项目显式 enabled=False → False。"""
        project = Project(
            name="disabled_project",
            user_id=testUser.id,
            description="disabled",
            status=1,
            project_type="web",
            config={CONFIG_KEY: {"enabled": False}},
        )
        db.add(project)
        db.flush()

        service = SelfHealingConfigService(db)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.services.self_healing.config_service.settings"
                ".AI_SELF_HEALING_ENABLED",
                True,
            )
            assert service.is_self_healing_enabled(project.id) is False

    def test_disabled_when_project_not_exists(self, db: Session):
        """项目不存在 → False。"""
        service = SelfHealingConfigService(db)
        assert service.is_self_healing_enabled(999999) is False


class TestConstants:
    """常量与允许值集合验证。"""

    def test_allowed_strategies_contains_all_expected(self):
        assert ALLOWED_STRATEGIES == frozenset({"mcp", "vision", "stagehand"})

    def test_token_limit_range(self):
        assert TOKEN_LIMIT_MIN == 1
        assert TOKEN_LIMIT_MAX == 10000

    def test_default_config_keys(self):
        assert set(DEFAULT_SELF_HEALING_CONFIG.keys()) == {
            "enabled",
            "strategies",
            "token_limit",
        }
