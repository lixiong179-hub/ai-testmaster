import pytest
import json
from app.models.test_data import TestData, DataType, GenerationRule
from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.models.user import User


class TestDataTypeEnum:
    def test_all_values(self):
        expected = {
            "text", "number", "date", "datetime", "email",
            "phone", "enum", "boolean", "url", "id_card", "bank_card"
        }
        actual = {e.value for e in DataType}
        assert actual == expected

    def test_str_enum_behavior(self):
        assert isinstance(DataType.TEXT, str)
        assert DataType.TEXT == "text"

    def test_from_value(self):
        assert DataType("email") is DataType.EMAIL
        assert DataType("phone") is DataType.PHONE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DataType("invalid_type")

    def test_member_count(self):
        assert len(DataType) == 11


class TestGenerationRuleEnum:
    def test_all_values(self):
        expected = {
            "random", "boundary_min", "boundary_max",
            "boundary_over", "special_chars", "empty", "custom"
        }
        actual = {e.value for e in GenerationRule}
        assert actual == expected

    def test_str_enum_behavior(self):
        assert isinstance(GenerationRule.RANDOM, str)
        assert GenerationRule.RANDOM == "random"

    def test_from_value(self):
        assert GenerationRule("custom") is GenerationRule.CUSTOM

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            GenerationRule("invalid_rule")

    def test_member_count(self):
        assert len(GenerationRule) == 7


@pytest.fixture
def test_user(db):
    user = User(
        username="td_test_user",
        email="td_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestData).filter(TestData.step_id.in_(
        db.query(TestStep.id).filter(TestStep.test_case_id.in_(
            db.query(TestCase.id).filter(TestCase.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            ))
        ))
    )).delete(synchronize_session=False)
    db.query(TestStep).filter(TestStep.test_case_id.in_(
        db.query(TestCase.id).filter(TestCase.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="数据测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_step(db, test_project):
    tc = TestCase(
        case_no="TC-TD-001",
        project_id=test_project.id,
        module="模块",
        title="数据测试用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI"
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    step = TestStep(
        test_case_id=tc.id,
        step_number=1,
        action="输入",
        expected_result="显示"
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    yield step


class TestTestDataModel:
    def test_create_test_data(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="username",
            field_type=DataType.TEXT,
            data_value="testuser"
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        assert td.id is not None
        assert td.step_id == test_step.id
        assert td.field_name == "username"
        assert td.field_type == DataType.TEXT
        assert td.data_value == "testuser"
        assert td.generation_rule == GenerationRule.RANDOM
        assert td.created_at is not None
        db.delete(td)
        db.commit()

    def test_test_data_default_values(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="field1"
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        assert td.field_type == DataType.TEXT
        assert td.generation_rule == GenerationRule.RANDOM
        assert td.data_value is None
        assert td.rule_config is None
        assert td.min_length is None
        assert td.max_length is None
        assert td.min_value is None
        assert td.max_value is None
        assert td.enum_values is None
        assert td.description is None
        assert td.is_required is True
        assert td.sort_order == 0
        db.delete(td)
        db.commit()

    def test_test_data_with_constraints(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="age",
            field_type=DataType.NUMBER,
            generation_rule=GenerationRule.BOUNDARY_MIN,
            min_value=0,
            max_value=150,
            data_value="25"
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        assert td.field_type == DataType.NUMBER
        assert td.generation_rule == GenerationRule.BOUNDARY_MIN
        assert td.min_value == 0
        assert td.max_value == 150
        db.delete(td)
        db.commit()

    def test_test_data_with_enum_values(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="gender",
            field_type=DataType.ENUM,
            enum_values='["male","female"]'
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        assert td.enum_values == '["male","female"]'
        db.delete(td)
        db.commit()

    def test_test_data_field_types(self, db, test_step):
        for ftype in [DataType.TEXT, DataType.NUMBER, DataType.DATE, DataType.EMAIL, DataType.PHONE]:
            td = TestData(
                step_id=test_step.id,
                field_name=f"field_{ftype.value}",
                field_type=ftype
            )
            db.add(td)
            db.commit()
            db.refresh(td)
            assert td.field_type == ftype
            db.delete(td)
            db.commit()

    def test_test_data_generation_rules(self, db, test_step):
        for rule in [GenerationRule.RANDOM, GenerationRule.BOUNDARY_MIN, GenerationRule.BOUNDARY_MAX,
                     GenerationRule.SPECIAL_CHARS, GenerationRule.EMPTY, GenerationRule.CUSTOM]:
            td = TestData(
                step_id=test_step.id,
                field_name=f"field_{rule.value}",
                generation_rule=rule
            )
            db.add(td)
            db.commit()
            db.refresh(td)
            assert td.generation_rule == rule
            db.delete(td)
            db.commit()

    def test_test_data_to_dict(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="email",
            field_type=DataType.EMAIL,
            data_value="test@example.com",
            generation_rule=GenerationRule.RANDOM,
            min_length=5,
            max_length=100,
            description="邮箱字段"
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        d = td.to_dict()
        assert d["step_id"] == test_step.id
        assert d["field_name"] == "email"
        assert d["field_type"] == "email"
        assert d["data_value"] == "test@example.com"
        assert d["generation_rule"] == "random"
        assert d["min_length"] == 5
        assert d["max_length"] == 100
        assert d["description"] == "邮箱字段"
        assert d["is_required"] is True
        db.delete(td)
        db.commit()

    def test_test_data_to_dict_with_json_fields(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="options",
            field_type=DataType.ENUM,
            enum_values='["a","b","c"]',
            rule_config='{"pattern":"seq"}'
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        d = td.to_dict()
        assert d["enum_values"] == ["a", "b", "c"]
        assert d["rule_config"] == {"pattern": "seq"}
        db.delete(td)
        db.commit()

    def test_test_data_repr(self, db, test_step):
        td = TestData(
            step_id=test_step.id,
            field_name="repr_field"
        )
        db.add(td)
        db.commit()
        db.refresh(td)
        repr_str = repr(td)
        assert "TestData" in repr_str
        assert "repr_field" in repr_str
        db.delete(td)
        db.commit()
