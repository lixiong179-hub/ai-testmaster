"""
项目流程数据 CRUD 单元测试

覆盖范围:
    - save_project_flow_data: 首次保存创建、再次保存更新（create_time 不变/update_time 变化）、返回对象校验
    - get_project_flow_data: 查询已有数据、查询不存在数据返回 None

使用 conftest.py 提供的 db（事务回滚隔离）、testUser 夹具。
"""
import time
import pytest

from app.crud.project_flow_data import save_project_flow_data, get_project_flow_data
from app.models.project_flow_data import ProjectFlowData
from app.models.project import Project


@pytest.fixture
def test_project(db, testUser):
    """创建测试项目（name="proj"）"""
    project = Project(
        name="proj",
        user_id=testUser.id,
        description="project for flow data crud tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


class TestSaveProjectFlowData:
    """save_project_flow_data 保存逻辑测试"""

    def test_first_save_creates_new_record(self, db, test_project):
        flow = {"nodes": [{"id": "1"}], "edges": []}
        result = save_project_flow_data(db, test_project.id, flow)

        assert result.id is not None
        assert result.project_id == test_project.id
        assert result.flow_data == flow
        assert result.create_time is not None
        assert result.update_time is not None
        assert result.create_time == result.update_time

    def test_second_save_updates_existing_record(self, db, test_project):
        flow1 = {"nodes": [{"id": "a"}], "edges": []}
        first = save_project_flow_data(db, test_project.id, flow1)
        first_create = first.create_time

        # 短暂等待后再次保存
        time.sleep(0.5)

        flow2 = {"nodes": [{"id": "b"}], "edges": [{"from": "b", "to": "c"}]}
        second = save_project_flow_data(db, test_project.id, flow2)

        # 同一 project_id 应更新同一条记录（id 相同，flow_data 已变）
        assert second.id == first.id
        assert second.project_id == test_project.id
        assert second.flow_data == flow2
        # create_time 不变
        assert second.create_time == first_create
        # update_time 存在且不早于首次更新时间
        assert second.update_time is not None
        assert second.update_time >= first.update_time

        # 确认表中仅有一条记录
        count = db.query(ProjectFlowData).filter(
            ProjectFlowData.project_id == test_project.id
        ).count()
        assert count == 1

    def test_returned_object_has_correct_fields(self, db, test_project):
        flow = {"nodes": [{"id": "x", "name": "首页"}], "edges": [], "module_info": {}}
        result = save_project_flow_data(db, test_project.id, flow)

        assert result.project_id == test_project.id
        assert result.flow_data == flow


class TestGetProjectFlowData:
    """get_project_flow_data 查询逻辑测试"""

    def test_returns_existing_data(self, db, test_project):
        flow = {"nodes": [{"id": "1"}], "edges": [{"from": "1", "to": "2"}]}
        save_project_flow_data(db, test_project.id, flow)

        result = get_project_flow_data(db, test_project.id)
        assert result is not None
        assert result.project_id == test_project.id
        assert result.flow_data == flow

    def test_returns_none_for_nonexistent_project_id(self, db):
        result = get_project_flow_data(db, 99999)
        assert result is None
