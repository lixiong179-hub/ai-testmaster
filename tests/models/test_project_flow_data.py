"""
ProjectFlowData 模型单元测试

覆盖范围:
    - 表名校验
    - 列定义校验（id/project_id/flow_data/create_time/update_time）
    - project_id 唯一约束校验
    - 最小字段实例化
    - 数据库持久化操作（写/读/唯一约束 IntegrityError）

使用 conftest.py 提供的 db（事务回滚隔离）、testUser 夹具。
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.project_flow_data import ProjectFlowData
from app.models.project import Project


@pytest.fixture
def flow_project(db, testUser):
    """为 FK 创建测试项目"""
    project = Project(
        name="flow_model_proj",
        user_id=testUser.id,
        description="project for flow data model tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


class TestProjectFlowDataModel:
    """ProjectFlowData 模型定义校验"""

    def test_table_name(self):
        assert ProjectFlowData.__tablename__ == "project_flow_data"

    def test_column_definitions(self):
        columns = {c.name: c for c in ProjectFlowData.__table__.columns}

        assert "id" in columns
        assert columns["id"].primary_key is True
        assert columns["id"].autoincrement is True

        assert "project_id" in columns
        assert columns["project_id"].nullable is False
        assert columns["project_id"].unique is True
        # 验证 FK 目标
        fk_target = list(columns["project_id"].foreign_keys)[0]
        assert fk_target.column.table.name == "projects"
        assert fk_target.column.name == "id"

        assert "flow_data" in columns
        assert columns["flow_data"].nullable is False

        assert "create_time" in columns
        assert columns["create_time"].nullable is False

        assert "update_time" in columns
        assert columns["update_time"].nullable is False

    def test_project_id_unique_constraint(self):
        column = ProjectFlowData.__table__.columns["project_id"]
        assert column.unique is True

    def test_instantiate_with_minimum_fields(self, flow_project):
        record = ProjectFlowData(
            project_id=flow_project.id,
            flow_data={"nodes": [], "edges": []},
        )
        assert record.project_id == flow_project.id
        assert record.flow_data == {"nodes": [], "edges": []}

    def test_create_and_persist(self, db, flow_project):
        record = ProjectFlowData(
            project_id=flow_project.id,
            flow_data={"nodes": [{"id": "1"}], "edges": [{"from": "1", "to": "2"}]},
        )
        db.add(record)
        db.flush()

        assert record.id is not None
        assert record.project_id == flow_project.id
        assert record.flow_data == {"nodes": [{"id": "1"}], "edges": [{"from": "1", "to": "2"}]}
        assert record.create_time is not None
        assert record.update_time is not None

        # 验证可重新查询
        fetched = db.query(ProjectFlowData).filter(
            ProjectFlowData.id == record.id
        ).first()
        assert fetched is not None
        assert fetched.project_id == flow_project.id

    def test_unique_constraint_raises_integrity_error(self, db, flow_project):
        first = ProjectFlowData(
            project_id=flow_project.id,
            flow_data={"nodes": [{"id": "a"}]},
        )
        db.add(first)
        db.flush()

        second = ProjectFlowData(
            project_id=flow_project.id,
            flow_data={"nodes": [{"id": "b"}]},
        )
        db.add(second)
        with pytest.raises(IntegrityError):
            db.flush()
