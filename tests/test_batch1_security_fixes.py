"""第一批修复验证测试 — P0-1 路径遍历 + P1-7 跨项目迭代归属校验

测试范围:
    - _sanitize_filename_component: 验证各种路径遍历 payload 均被清理
    - before_flush 守卫: 验证同项目迭代赋值通过、跨项目赋值被拦截

技术要求:
    - 使用真实数据库（禁止 Mock）
    - 覆盖正常值、边界值、异常值
"""
import os
from datetime import datetime
import pytest

from app.api.v1.endpoints.ui_prototype.helpers import _sanitize_filename_component
from app.models.project import Project
from app.models.user import User
from app.utils.jwt_utils import get_password_hash


class TestSanitizeFilenameComponent:
    """P0-1: 验证文件名组成部分清理函数的安全性。"""

    def test_normal_name_unchanged(self):
        """正常名称应保持不变。"""
        assert _sanitize_filename_component("login_page") == "login_page"
        assert _sanitize_filename_component("homepage-v2") == "homepage-v2"
        assert _sanitize_filename_component("原型A") == "原型A"

    def test_empty_returns_default(self):
        """空字符串返回默认值。"""
        assert _sanitize_filename_component("") == "unnamed"
        assert _sanitize_filename_component(None) == "unnamed"

    def test_path_traversal_dotdot(self):
        """../ 路径遍历 payload 应被清理。"""
        result = _sanitize_filename_component("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_path_traversal_backslash(self):
        """Windows 反斜杠路径遍历应被清理。"""
        result = _sanitize_filename_component("..\\..\\windows\\system32")
        assert ".." not in result
        assert "\\" not in result
        assert "/" not in result

    def test_path_traversal_mixed_separators(self):
        """混合分隔符应被清理。"""
        result = _sanitize_filename_component("..//..\\..//etc")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_null_byte_injection(self):
        """Null 字节注入应被清理。"""
        result = _sanitize_filename_component("evil\x00.txt")
        assert "\x00" not in result

    def test_absolute_path_injection(self):
        """绝对路径注入应被清理。"""
        result = _sanitize_filename_component("/etc/shadow")
        assert "/" not in result
        assert not os.path.isabs(result)

    def test_windows_drive_injection(self):
        """Windows 盘符注入应被清理。"""
        result = _sanitize_filename_component("C:\\Windows\\system32")
        assert ":" not in result
        assert "\\" not in result

    def test_only_special_chars(self):
        """全特殊字符应返回默认值。"""
        result = _sanitize_filename_component("../../")
        assert result == "unnamed" or ".." not in result


class TestProjectFileIterationGuard:
    """P1-7: 验证 before_flush 守卫拦截跨项目迭代赋值。"""

    def test_same_project_iteration_allowed(self, db, test_project, test_iteration):
        """同项目迭代赋值应成功。"""
        from app.crud import file as file_crud
        file_obj = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="guard_test.pdf",
            file_type="pdf",
            file_url="/uploads/test/guard.pdf",
        )
        file_obj.iteration_id = test_iteration.id
        db.commit()  # 不应抛出异常

        db.refresh(file_obj)
        assert file_obj.iteration_id == test_iteration.id

    def test_cross_project_iteration_blocked(self, db, test_project, test_iteration):
        """跨项目迭代赋值应被 before_flush 守卫拦截。"""
        from app.crud import file as file_crud
        from app.models.iteration import Iteration

        file_obj = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="cross_proj_test.pdf",
            file_type="pdf",
            file_url="/uploads/test/cross.pdf",
        )

        # 创建另一个用户和项目
        other_user = User(
            username=f"other_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            email=f"other_{datetime.now().strftime('%Y%m%d%H%M%S')}@test.com",
            password_hash=get_password_hash("OtherPassword123!"),
        )
        db.add(other_user)
        db.flush()
        db.refresh(other_user)

        other_project = Project(
            name=f"other_project_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            description="跨项目测试",
            user_id=other_user.id,
            project_type="web",
        )
        db.add(other_project)
        db.flush()
        db.refresh(other_project)

        other_iteration = Iteration(
            project_id=other_project.id,
            name="Other Sprint",
            version="v1.0",
        )
        db.add(other_iteration)
        db.flush()
        db.refresh(other_iteration)

        # 使用嵌套 savepoint 确保 ValueError 不会破坏外层事务
        # 先创建 savepoint（此时 iteration_id 尚未修改，flush 不会触发守卫）
        sp = db.begin_nested()
        # 修改 iteration_id 标记对象为 dirty
        file_obj.iteration_id = other_iteration.id
        # flush 触发 before_flush 守卫，应抛出 ValueError
        with pytest.raises(ValueError, match="不属于文件所在项目"):
            db.flush()
        sp.rollback()

    def test_clear_iteration_id_allowed(self, db, test_project, test_iteration):
        """清除 iteration_id（设为 None）应成功。"""
        from app.crud import file as file_crud
        file_obj = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="clear_iter_test.pdf",
            file_type="pdf",
            file_url="/uploads/test/clear.pdf",
        )
        file_obj.iteration_id = test_iteration.id
        db.commit()

        file_obj.iteration_id = None
        db.commit()  # 不应抛出异常
        db.refresh(file_obj)
        assert file_obj.iteration_id is None
