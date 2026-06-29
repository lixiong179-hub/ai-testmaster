"""AutoProjectBuilder 单元测试。

使用真实测试库（tests/conftest.py 的 db fixture，事务隔离 + 自动回滚），
不 Mock 数据库，验证建项成功、重名去重、非法 URL、source 字段、三套环境填充、
跨用户隔离、SQL 注入不生效、域名推导边界与 DB 异常回滚。

清理策略：依赖 db fixture 的事务级回滚，用例执行后全部数据自动清理，
无需逐用例显式删除（other_user fixture 亦同）。
"""
import json
from datetime import datetime

import pytest

from app.models.project import Project
from app.services.url_driven.auto_project_builder import (
    AutoProjectBuilder,
    SOURCE_URL_QUICK_TEST,
)


def _today_str() -> str:
    """与 builder 内部一致地取当日 YYYYMMDD，避免硬编码日期导致跨日失败。"""
    return datetime.now().strftime("%Y%m%d")


def _parse_env_configs(project: Project) -> dict:
    """兼容 dict/str/双重编码读取 web_env_configs，断言稳健。

    web_env_configs 在不同 DB 后端可能以 dict 或 json 字符串读回，
    且现有 create_project/update_project_config 端点写入时经 json.dumps
    可能产生双重编码，此处循环解码直到拿到 dict。
    """
    raw = project.web_env_configs
    if raw is None:
        return {}
    while isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


@pytest.fixture
def builder() -> AutoProjectBuilder:
    return AutoProjectBuilder()


@pytest.fixture
def other_user(db):
    """第二个独立用户，用于跨用户隔离测试。依赖 db 事务回滚自动清理。"""
    from app.models.user import User
    from app.utils.jwt_utils import get_password_hash

    existing = db.query(User).filter(User.username == "other_user_builder").first()
    if existing:
        db.delete(existing)
        db.flush()
    user = User(
        username="other_user_builder",
        email="other_builder@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


class TestBuildSuccess:
    """建项成功路径与字段正确性。"""

    def test_returns_project_with_id_and_source(self, builder, db, testUser):
        project = builder.build("https://shop.example.com", "desc", testUser.id, db)
        assert project.id is not None
        assert project.source == SOURCE_URL_QUICK_TEST
        assert project.user_id == testUser.id
        assert project.description == "desc"
        assert project.project_type == "web"

    def test_name_contains_domain_and_date(self, builder, db, testUser):
        project = builder.build("https://shop.example.com", None, testUser.id, db)
        assert project.name == f"shop.example.com_{_today_str()}"

    def test_strips_www_prefix(self, builder, db, testUser):
        project = builder.build("https://www.example.com/path", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}"

    def test_http_scheme_accepted(self, builder, db, testUser):
        project = builder.build("http://example.com", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}"

    def test_domain_with_port_stripped(self, builder, db, testUser):
        project = builder.build("https://example.com:8080/x", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}"

    def test_domain_with_userinfo_stripped(self, builder, db, testUser):
        project = builder.build("https://user:pass@example.com/x", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}"

    def test_fills_three_env_urls(self, builder, db, testUser):
        url = "https://demo.playwright.dev/todomvc"
        project = builder.build(url, None, testUser.id, db)
        configs = _parse_env_configs(project)
        for env in ("test", "staging", "prod"):
            assert env in configs
            assert configs[env]["url"] == url
            assert configs[env]["username"] is None
            assert configs[env]["password"] is None


class TestDedup:
    """重名去重序号递增。"""

    def test_first_duplicate_gets_suffix_1(self, builder, db, testUser):
        url = "https://example.com"
        p1 = builder.build(url, None, testUser.id, db)
        p2 = builder.build(url, None, testUser.id, db)
        assert p1.name == f"example.com_{_today_str()}"
        assert p2.name == f"example.com_{_today_str()}_1"

    def test_second_duplicate_gets_suffix_2(self, builder, db, testUser):
        url = "https://example.com"
        builder.build(url, None, testUser.id, db)
        builder.build(url, None, testUser.id, db)
        p3 = builder.build(url, None, testUser.id, db)
        assert p3.name == f"example.com_{_today_str()}_2"

    def test_different_domains_no_dedup(self, builder, db, testUser):
        builder.build("https://example.com", None, testUser.id, db)
        p2 = builder.build("https://other.com", None, testUser.id, db)
        assert p2.name == f"other.com_{_today_str()}"

    def test_existing_exact_match_via_orm_triggers_suffix(self, builder, db, testUser):
        """预置与 base_name 完全同名的项目（非 builder 创建），验证查重命中。"""
        db.add(Project(name=f"example.com_{_today_str()}", user_id=testUser.id))
        db.flush()
        project = builder.build("https://example.com", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}_1"

    def test_dedup_uses_max_existing_suffix(self, builder, db, testUser):
        """已有 base_name 与多个序号时，取最大序号 +1。"""
        today = _today_str()
        db.add(Project(name=f"example.com_{today}", user_id=testUser.id))
        db.add(Project(name=f"example.com_{today}_3", user_id=testUser.id))
        db.add(Project(name=f"example.com_{today}_1", user_id=testUser.id))
        db.flush()
        project = builder.build("https://example.com", None, testUser.id, db)
        assert project.name == f"example.com_{today}_4"


class TestInvalidUrl:
    """非法 URL 校验与不创建项目。"""

    @pytest.mark.parametrize("bad_url", [
        "",
        "   ",
        "not-a-url",
        "example.com",
        "file:///etc/passwd",
        "ftp://example.com",
        "javascript:alert(1)",
        "http://",
        "https://",
    ])
    def test_invalid_url_raises_value_error(self, builder, db, testUser, bad_url):
        with pytest.raises(ValueError):
            builder.build(bad_url, None, testUser.id, db)

    def test_invalid_url_does_not_create_project(self, builder, db, testUser):
        before = db.query(Project).filter(Project.user_id == testUser.id).count()
        with pytest.raises(ValueError):
            builder.build("not-a-url", None, testUser.id, db)
        after = db.query(Project).filter(Project.user_id == testUser.id).count()
        assert after == before


class TestSourceField:
    """source 字段：builder 置 url_quick_test，默认建项为 manual。"""

    def test_builder_sets_source_url_quick_test(self, builder, db, testUser):
        project = builder.build("https://example.com", None, testUser.id, db)
        assert project.source == SOURCE_URL_QUICK_TEST
        assert project.source == "url_quick_test"

    def test_manual_project_default_source(self, db, testUser):
        manual = Project(name="manual_proj", user_id=testUser.id)
        db.add(manual)
        db.flush()
        db.refresh(manual)
        assert manual.source == "manual"


class TestCrossUserIsolation:
    """跨用户隔离：同 URL 不同用户不触发查重追加。"""

    def test_same_url_different_users_no_suffix(self, builder, db, testUser, other_user):
        url = "https://example.com"
        p1 = builder.build(url, None, testUser.id, db)
        p2 = builder.build(url, None, other_user.id, db)
        today = _today_str()
        assert p1.name == f"example.com_{today}"
        assert p2.name == f"example.com_{today}"
        assert p1.user_id != p2.user_id


class TestSqlInjectionSafety:
    """参数化查询防注入验证。"""

    def test_quote_in_domain_stored_literally(self, builder, db, testUser):
        """单引号作为域名一部分被字面存储，不破坏 SQL 语义。"""
        project = builder.build("https://ex'ample.com", None, testUser.id, db)
        assert "'" in project.name
        cnt = db.query(Project).filter(
            Project.user_id == testUser.id,
            Project.name == project.name,
        ).count()
        assert cnt == 1

    def test_underscore_wildcard_not_false_match(self, builder, db, testUser):
        """LIKE 的 _ 通配符可能误匹配形如 example.comXDATE 的名字，
        验证 Python 侧精确过滤后不误判重名。"""
        trap = f"example.comX{_today_str()}"
        db.add(Project(name=trap, user_id=testUser.id))
        db.flush()
        project = builder.build("https://example.com", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}"

    def test_unrelated_projects_do_not_interfere(self, builder, db, testUser):
        """预置多个无关项目，验证查重仅返回真正匹配行不污染计数。"""
        db.add(Project(name="zzz_unrelated", user_id=testUser.id))
        db.add(Project(name="example.com_20200101", user_id=testUser.id))
        db.flush()
        project = builder.build("https://example.com", None, testUser.id, db)
        assert project.name == f"example.com_{_today_str()}"


class TestDbExceptionRollback:
    """DB 异常回滚与向上抛出。"""

    def test_commit_failure_rolls_back_and_reraises(self, builder, db, testUser, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("commit failed")
        monkeypatch.setattr(db, "commit", boom)
        with pytest.raises(RuntimeError, match="commit failed"):
            builder.build("https://example.com", None, testUser.id, db)
        assert db.query(Project).filter(Project.user_id == testUser.id).count() == 0
