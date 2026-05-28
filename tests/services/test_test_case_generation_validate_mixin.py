import pytest

from app.core.config import settings
from app.models.test_case import TestCase as AppTestCase, TestStep as AppTestStep
from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin


class _DummyValidateService(TestCaseGenerationValidateMixin):
    def __init__(self, db):
        self.db = db


@pytest.mark.asyncio
async def test_save_test_case_binds_source_test_point(db, testProject, monkeypatch):
    from app.models.test_point import TestPoint

    monkeypatch.setattr(settings, "AUTO_PARSE_PRECONDITION", False)

    test_point = TestPoint(
        project_id=testProject.id,
        module="bind_module",
        point="bind point",
        priority=1,
        created_by="tester",
    )
    db.add(test_point)
    db.flush()

    service = _DummyValidateService(db)
    generated_case = {
        "module": "bind_module",
        "title": "已登录用户打开绑定页面并完成保存校验",
        "precondition": "账号已登录，浏览器网络正常，具备绑定页面访问权限",
        "steps": [
            {
                "step": "1",
                "description": "导航到绑定页面",
                "action": "导航到绑定页面",
                "action_type": "navigate",
                "expected_result": "绑定页面标题和主表单区域可见",
            },
            {
                "step": "2",
                "description": "点击保存按钮",
                "action": "点击保存按钮",
                "action_type": "click",
                "expected_result": "保存按钮保持可点击且页面显示保存完成提示",
            },
        ],
        "expected_result": "页面显示保存完成提示，绑定数据保存状态更新为已保存",
        "priority": 1,
        "case_type": "manual",
        "case_category": "positive",
    }

    saved_case = await service._save_test_case(
        project_id=testProject.id,
        generated_case=generated_case,
        test_point={"id": test_point.id, "module": test_point.module, "priority": test_point.priority},
    )

    assert saved_case.test_point_id == test_point.id
    persisted_case = db.query(AppTestCase).filter(AppTestCase.id == saved_case.id).one()
    persisted_steps = db.query(AppTestStep).filter(AppTestStep.test_case_id == saved_case.id).all()
    assert persisted_case.module == "bind_module"
    assert len(persisted_steps) == 2
