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
        "title": "生成的测试用例",
        "precondition": "",
        "steps": [
            {
                "step": "1",
                "description": "打开页面",
                "action": "打开页面",
                "expected_result": "页面打开成功",
            }
        ],
        "expected_result": "流程正常",
        "priority": 1,
        "case_type": "manual",
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
    assert len(persisted_steps) == 1
