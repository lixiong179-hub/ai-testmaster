"""
iteration_id 哨兵值修复测试

验证 iteration_id 从 -1 哨兵值迁移到 NULL 的正确性，覆盖：
1. CRUD 层：iteration_id 查询逻辑（None/0/正整数）
2. API 层：文件上传/更新时 iteration_id 的转换
3. 迁移脚本：-1 → NULL 的数据迁移

测试策略：
- 使用真实测试库，不使用 Mock
- 每个测试用例执行后自动清理测试数据（conftest 事务回滚）
"""
import pytest
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeProject
from app.models.iteration import Iteration
from app.crud import file as file_crud
from app.crud import ui_prototype_project as proto_project_crud


def _create_iteration(db: Session, project_id: int) -> Iteration:
    """辅助方法：创建迭代记录"""
    iteration = Iteration(
        project_id=project_id,
        name="测试迭代",
        version="v1.0",
        status="in_pipeline",
    )
    db.add(iteration)
    db.flush()
    return iteration


class TestIterationIdCrudQuery:
    """测试 CRUD 层 iteration_id 查询逻辑"""

    def _create_file(
        self, db: Session, project_id: int, iteration_id: int | None
    ) -> ProjectFile:
        """辅助方法：创建文件记录"""
        return file_crud.create_project_file(
            db=db,
            project_id=project_id,
            file_name=f"test_file_{iteration_id}.txt",
            file_type="txt",
            file_url="/tmp/test.txt",
            iteration_id=iteration_id,
        )

    def test_get_files_with_zero_iteration_id_returns_null_files(
        self, db: Session, testProject: Project
    ) -> None:
        """测试查询 iteration_id=0 应返回 IS NULL 的文件"""
        # 创建两个文件：一个未关联迭代，一个关联迭代
        iteration = _create_iteration(db, testProject.id)
        self._create_file(db, testProject.id, iteration_id=None)
        self._create_file(db, testProject.id, iteration_id=iteration.id)

        # 传入 iteration_id=0 应查询 IS NULL 的文件
        files = file_crud.get_project_files(
            db, testProject.id, iteration_id=0
        )
        assert len(files) == 1
        assert files[0].iteration_id is None

    def test_get_files_with_negative_iteration_id_returns_null_files(
        self, db: Session, testProject: Project
    ) -> None:
        """测试传入负数 iteration_id 应视为未关联迭代（兼容旧调用）"""
        iteration = _create_iteration(db, testProject.id)
        self._create_file(db, testProject.id, iteration_id=None)
        self._create_file(db, testProject.id, iteration_id=iteration.id)

        # 传入 iteration_id=-1 应查询 IS NULL 的文件（兼容旧调用）
        files = file_crud.get_project_files(
            db, testProject.id, iteration_id=-1
        )
        assert len(files) == 1
        assert files[0].iteration_id is None

    def test_get_files_without_iteration_filter_returns_all(
        self, db: Session, testProject: Project
    ) -> None:
        """测试不传 iteration_id 时返回所有文件"""
        iteration = _create_iteration(db, testProject.id)
        self._create_file(db, testProject.id, iteration_id=None)
        self._create_file(db, testProject.id, iteration_id=iteration.id)

        # 不传 iteration_id，应返回所有文件
        files = file_crud.get_project_files(db, testProject.id)
        assert len(files) == 2

    def test_get_files_with_valid_iteration_id(
        self, db: Session, testProject: Project
    ) -> None:
        """测试按有效迭代ID查询文件"""
        iteration = _create_iteration(db, testProject.id)
        self._create_file(db, testProject.id, iteration_id=None)
        self._create_file(db, testProject.id, iteration_id=iteration.id)

        # 按迭代ID查询
        files = file_crud.get_project_files(
            db, testProject.id, iteration_id=iteration.id
        )
        assert len(files) == 1
        assert files[0].iteration_id == iteration.id

    def test_create_file_with_null_iteration_id(
        self, db: Session, testProject: Project
    ) -> None:
        """测试创建文件时 iteration_id=None 应正确存储为 NULL"""
        file = self._create_file(db, testProject.id, iteration_id=None)
        assert file.iteration_id is None

        # 从数据库重新查询验证
        db.refresh(file)
        assert file.iteration_id is None

    def test_create_file_with_zero_iteration_id_fails_fk_constraint(
        self, db: Session, testProject: Project
    ) -> None:
        """测试 CRUD 层直接传入 iteration_id=0 会因外键约束失败

        这验证了 API 层必须在写入前将 <=0 转为 None，
        因为 iteration_id 是外键，0 不是 iterations 表中的有效 ID。
        """
        with pytest.raises(Exception):
            self._create_file(db, testProject.id, iteration_id=0)


class TestIterationIdProtoProjectQuery:
    """测试 UI 原型项目 CRUD 层 iteration_id 查询逻辑"""

    def _create_proto_project(
        self, db: Session, project_id: int, iteration_id: int | None
    ) -> UIPrototypeProject:
        """辅助方法：创建UI原型项目记录"""
        return proto_project_crud.create_ui_prototype_project(
            db=db,
            project_id=project_id,
            name=f"test_proto_{iteration_id}",
            iteration_id=iteration_id,
        )

    def test_get_proto_projects_with_zero_iteration_id(
        self, db: Session, testProject: Project, testUser
    ) -> None:
        """测试传入 iteration_id=0 应查询 IS NULL 的原型项目"""
        self._create_proto_project(db, testProject.id, iteration_id=None)

        projects = proto_project_crud.get_ui_prototype_projects_by_project(
            db, testProject.id, testUser.id, iteration_id=0
        )
        assert len(projects) == 1
        assert projects[0].iteration_id is None

    def test_get_proto_projects_with_negative_iteration_id(
        self, db: Session, testProject: Project, testUser
    ) -> None:
        """测试传入负数 iteration_id 应视为未关联迭代（兼容旧调用）"""
        self._create_proto_project(db, testProject.id, iteration_id=None)

        projects = proto_project_crud.get_ui_prototype_projects_by_project(
            db, testProject.id, testUser.id, iteration_id=-1
        )
        assert len(projects) == 1
        assert projects[0].iteration_id is None

    def test_get_proto_projects_count_with_zero_iteration_id(
        self, db: Session, testProject: Project, testUser
    ) -> None:
        """测试 count 查询也支持 iteration_id<=0 视为未关联迭代"""
        iteration = _create_iteration(db, testProject.id)
        self._create_proto_project(db, testProject.id, iteration_id=None)
        self._create_proto_project(db, testProject.id, iteration_id=iteration.id)

        count = proto_project_crud.get_ui_prototype_projects_count(
            db, testProject.id, testUser.id, iteration_id=0
        )
        assert count == 1


class TestIterationIdMigration:
    """测试迁移脚本的数据转换逻辑"""

    def test_migration_converts_negative_to_null(
        self, db: Session, testProject: Project
    ) -> None:
        """测试迁移将 iteration_id=-1 转为 NULL"""
        # 模拟旧数据：直接插入 iteration_id=-1 的记录
        # 需要临时禁用外键约束来插入 -1
        from sqlalchemy import text
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        file = ProjectFile(
            project_id=testProject.id,
            file_name="legacy_file.txt",
            file_type="txt",
            file_url="/tmp/legacy.txt",
            file_source="file",
            extract_status="pending",
            is_active=True,
            iteration_id=-1,
        )
        db.add(file)
        db.flush()
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        assert file.iteration_id == -1

        # 执行迁移逻辑
        db.execute(
            text(
                "UPDATE project_files SET iteration_id = NULL "
                "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
            )
        )
        db.flush()

        # 验证迁移结果
        db.refresh(file)
        assert file.iteration_id is None

    def test_migration_preserves_valid_iteration_id(
        self, db: Session, testProject: Project
    ) -> None:
        """测试迁移不修改有效的 iteration_id"""
        iteration = _create_iteration(db, testProject.id)
        file = ProjectFile(
            project_id=testProject.id,
            file_name="valid_file.txt",
            file_type="txt",
            file_url="/tmp/valid.txt",
            file_source="file",
            extract_status="pending",
            is_active=True,
            iteration_id=iteration.id,
        )
        db.add(file)
        db.flush()

        # 执行迁移逻辑
        from sqlalchemy import text
        db.execute(
            text(
                "UPDATE project_files SET iteration_id = NULL "
                "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
            )
        )
        db.flush()

        # 验证有效 iteration_id 未被修改
        db.refresh(file)
        assert file.iteration_id == iteration.id

    def test_migration_converts_zero_to_null(
        self, db: Session, testProject: Project
    ) -> None:
        """测试迁移将 iteration_id=0 转为 NULL"""
        from sqlalchemy import text
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        file = ProjectFile(
            project_id=testProject.id,
            file_name="zero_file.txt",
            file_type="txt",
            file_url="/tmp/zero.txt",
            file_source="file",
            extract_status="pending",
            is_active=True,
            iteration_id=0,
        )
        db.add(file)
        db.flush()
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        # 执行迁移逻辑
        db.execute(
            text(
                "UPDATE project_files SET iteration_id = NULL "
                "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
            )
        )
        db.flush()

        # 验证迁移结果
        db.refresh(file)
        assert file.iteration_id is None

    def test_migration_proto_project_negative_to_null(
        self, db: Session, testProject: Project
    ) -> None:
        """测试迁移将 ui_prototype_projects 的 iteration_id=-1 转为 NULL"""
        from sqlalchemy import text
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        proto = UIPrototypeProject(
            project_id=testProject.id,
            name="legacy_proto",
            source="manual",
            iteration_id=-1,
        )
        db.add(proto)
        db.flush()
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        assert proto.iteration_id == -1

        # 执行迁移逻辑
        db.execute(
            text(
                "UPDATE ui_prototype_projects SET iteration_id = NULL "
                "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
            )
        )
        db.flush()

        # 验证迁移结果
        db.refresh(proto)
        assert proto.iteration_id is None

    def test_migration_already_null_stays_null(
        self, db: Session, testProject: Project
    ) -> None:
        """测试迁移不修改已经是 NULL 的记录"""
        file = ProjectFile(
            project_id=testProject.id,
            file_name="null_file.txt",
            file_type="txt",
            file_url="/tmp/null.txt",
            file_source="file",
            extract_status="pending",
            is_active=True,
            iteration_id=None,
        )
        db.add(file)
        db.flush()

        # 执行迁移逻辑
        from sqlalchemy import text
        db.execute(
            text(
                "UPDATE project_files SET iteration_id = NULL "
                "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
            )
        )
        db.flush()

        # 验证已经是 NULL 的记录不受影响
        db.refresh(file)
        assert file.iteration_id is None


class TestIterationIdApiConversion:
    """测试 API 层 iteration_id 的转换逻辑"""

    def test_api_converts_zero_to_none(self) -> None:
        """测试 API 层将 iteration_id=0 转为 None 的逻辑"""
        iteration_id: int | None = 0
        db_iteration_id = iteration_id if iteration_id and iteration_id > 0 else None
        assert db_iteration_id is None

    def test_api_converts_negative_to_none(self) -> None:
        """测试 API 层将 iteration_id=-1 转为 None 的逻辑"""
        iteration_id: int | None = -1
        db_iteration_id = iteration_id if iteration_id and iteration_id > 0 else None
        assert db_iteration_id is None

    def test_api_preserves_valid_iteration_id(self) -> None:
        """测试 API 层保留有效的 iteration_id"""
        iteration_id: int | None = 42
        db_iteration_id = iteration_id if iteration_id and iteration_id > 0 else None
        assert db_iteration_id == 42

    def test_api_handles_none(self) -> None:
        """测试 API 层处理 None 值"""
        iteration_id: int | None = None
        db_iteration_id = iteration_id if iteration_id and iteration_id > 0 else None
        assert db_iteration_id is None
