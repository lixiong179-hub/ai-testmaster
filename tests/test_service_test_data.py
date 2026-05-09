import json
import uuid
import pytest
from app.services.test_data_service import TestDataService
from app.models.test_data import TestData, DataType, GenerationRule
from app.models.test_case import TestCase, TestStep
from app.crud.test_case_mutate import create_test_case
from tests.helpers import createTestUser, createTestProject


class TestTestDataCrudCreate:
    def test_create_test_data_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="testdata",
            title="test data crud",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input text",
            expected_result="text entered",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="username",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            description="test username field",
        )
        assert td is not None
        assert td.id is not None
        assert td.step_id == step.id
        assert td.field_name == "username"
        assert td.field_type == DataType.TEXT
        assert td.generation_rule == GenerationRule.RANDOM

    def test_create_test_data_with_constraints(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="constraints",
            title="test data constraints",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input number",
            expected_result="number entered",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="age",
            field_type=DataType.NUMBER,
            generation_rule=GenerationRule.RANDOM,
            min_value=1,
            max_value=100,
            description="age field",
        )
        assert td.min_value == 1
        assert td.max_value == 100

    def test_create_test_data_with_enum(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="enum",
            title="test data enum",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="select option",
            expected_result="option selected",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="gender",
            field_type=DataType.ENUM,
            generation_rule=GenerationRule.RANDOM,
            enum_values=["male", "female"],
            description="gender field",
        )
        assert td.enum_values is not None
        parsed = json.loads(td.enum_values)
        assert parsed == ["male", "female"]

    def test_create_test_data_with_rule_config(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDR-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="ruleconfig",
            title="test data rule config",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="email_field",
            field_type=DataType.EMAIL,
            generation_rule=GenerationRule.RANDOM,
            rule_config={"domain": "test.com"},
        )
        assert td.rule_config is not None

    def test_create_test_data_with_custom_value(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDV-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="custom",
            title="test data custom value",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="custom_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.CUSTOM,
            data_value="fixed_value",
        )
        assert td.data_value == "fixed_value"

    def test_create_test_data_with_length_constraints(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="length",
            title="test data length",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="name",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            min_length=1,
            max_length=50,
        )
        assert td.min_length == 1
        assert td.max_length == 50

    def test_create_test_data_with_sort_order(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDS-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="sortorder",
            title="test data sort order",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="sorted_field",
            field_type=DataType.TEXT,
            sort_order=5,
        )
        assert td.sort_order == 5

    def test_create_test_data_required_flag(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TDREQ-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="required",
            title="test data required",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="optional_field",
            field_type=DataType.TEXT,
            is_required=False,
        )
        assert td.is_required is False


class TestTestDataCrudGet:
    def test_get_test_data_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GETTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="gettd",
            title="get test data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="get_field",
            field_type=DataType.TEXT,
        )
        found = service.get_test_data(td.id)
        assert found is not None
        assert found.id == td.id

    def test_get_test_data_nonexistent(self, db):
        service = TestDataService(db)
        found = service.get_test_data(99999)
        assert found is None

    def test_get_test_data_by_step(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-STEPTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="steptd",
            title="step test data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        service.create_test_data(
            step_id=step.id,
            field_name="field_a",
            field_type=DataType.TEXT,
            sort_order=0,
        )
        service.create_test_data(
            step_id=step.id,
            field_name="field_b",
            field_type=DataType.NUMBER,
            sort_order=1,
        )
        results = service.get_test_data_by_step(step.id)
        assert len(results) == 2
        assert results[0].sort_order <= results[1].sort_order

    def test_get_test_data_by_step_empty(self, db):
        service = TestDataService(db)
        results = service.get_test_data_by_step(99999)
        assert results == []


class TestTestDataCrudUpdate:
    def test_update_test_data_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-UPDTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="updtd",
            title="update test data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="original",
            field_type=DataType.TEXT,
        )
        updated = service.update_test_data(td.id, field_name="updated_name")
        assert updated is not None
        assert updated.field_name == "updated_name"

    def test_update_test_data_nonexistent(self, db):
        service = TestDataService(db)
        result = service.update_test_data(99999, field_name="nope")
        assert result is None

    def test_update_test_data_rule_config(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-UPDRC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="updrc",
            title="update rule config",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="config_field",
            field_type=DataType.TEXT,
        )
        updated = service.update_test_data(td.id, rule_config={"pattern": "email"})
        assert updated is not None
        parsed = json.loads(updated.rule_config)
        assert parsed == {"pattern": "email"}

    def test_update_test_data_enum_values(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-UPDEV-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="updev",
            title="update enum values",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="select",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="select_field",
            field_type=DataType.ENUM,
        )
        updated = service.update_test_data(td.id, enum_values=["a", "b", "c"])
        assert updated is not None
        parsed = json.loads(updated.enum_values)
        assert parsed == ["a", "b", "c"]

    def test_update_test_data_multiple_fields(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-UPDMF-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="updmf",
            title="update multiple fields",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="multi_field",
            field_type=DataType.TEXT,
            description="original",
        )
        updated = service.update_test_data(
            td.id,
            field_name="new_name",
            description="new_desc",
            min_length=5,
            max_length=100,
        )
        assert updated.field_name == "new_name"
        assert updated.description == "new_desc"
        assert updated.min_length == 5
        assert updated.max_length == 100


class TestTestDataCrudDelete:
    def test_delete_test_data_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-DELTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="deltd",
            title="delete test data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="to_delete",
            field_type=DataType.TEXT,
        )
        result = service.delete_test_data(td.id)
        assert result is True
        found = service.get_test_data(td.id)
        assert found is None

    def test_delete_test_data_nonexistent(self, db):
        service = TestDataService(db)
        result = service.delete_test_data(99999)
        assert result is False


class TestTestDataGenGenerateValue:
    def test_generate_value_text(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENV-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genv",
            title="generate value text",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="text_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
        )
        value = service.generate_value(td)
        assert isinstance(value, str)
        assert len(value) > 0

    def test_generate_value_number(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENN-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genn",
            title="generate value number",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="num_field",
            field_type=DataType.NUMBER,
            generation_rule=GenerationRule.RANDOM,
            min_value=1,
            max_value=100,
        )
        value = service.generate_value(td)
        assert isinstance(value, str)
        int_val = int(value)
        assert 1 <= int_val <= 100

    def test_generate_value_custom(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genc",
            title="generate value custom",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="custom_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.CUSTOM,
            rule_config={"custom_value": "fixed_custom_value"},
        )
        value = service.generate_value(td)
        assert value == "fixed_custom_value"

    def test_generate_value_empty_rule(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="gene",
            title="generate value empty",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="empty_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.EMPTY,
        )
        value = service.generate_value(td)
        assert value == ""

    def test_generate_value_boundary_min(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENMIN-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genmin",
            title="generate value boundary min",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="min_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.BOUNDARY_MIN,
            min_length=3,
        )
        value = service.generate_value(td)
        assert len(value) == 3

    def test_generate_value_boundary_max(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENMAX-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genmax",
            title="generate value boundary max",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="max_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.BOUNDARY_MAX,
            max_length=10,
        )
        value = service.generate_value(td)
        assert len(value) == 10

    def test_generate_value_special_chars(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENSP-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="gensp",
            title="generate value special chars",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="special_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.SPECIAL_CHARS,
        )
        value = service.generate_value(td)
        assert len(value) > 0

    def test_generate_value_email(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENEM-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genem",
            title="generate value email",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="email_field",
            field_type=DataType.EMAIL,
            generation_rule=GenerationRule.RANDOM,
        )
        value = service.generate_value(td)
        assert "@" in value

    def test_generate_value_phone(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENPH-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genph",
            title="generate value phone",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="phone_field",
            field_type=DataType.PHONE,
            generation_rule=GenerationRule.RANDOM,
        )
        value = service.generate_value(td)
        assert len(value) == 11

    def test_generate_value_date(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENDT-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="gendt",
            title="generate value date",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="date_field",
            field_type=DataType.DATE,
            generation_rule=GenerationRule.RANDOM,
        )
        value = service.generate_value(td)
        assert "-" in value

    def test_generate_value_boolean(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENBL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genbl",
            title="generate value boolean",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="bool_field",
            field_type=DataType.BOOLEAN,
            generation_rule=GenerationRule.RANDOM,
        )
        value = service.generate_value(td)
        assert value in ["true", "false"]

    def test_generate_value_url(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENURL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genurl",
            title="generate value url",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="url_field",
            field_type=DataType.URL,
            generation_rule=GenerationRule.RANDOM,
        )
        value = service.generate_value(td)
        assert "://" in value

    def test_generate_value_enum(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENENUM-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="genenum",
            title="generate value enum",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="select",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="enum_field",
            field_type=DataType.ENUM,
            generation_rule=GenerationRule.RANDOM,
            enum_values=["option_a", "option_b", "option_c"],
        )
        value = service.generate_value(td)
        assert value in ["option_a", "option_b", "option_c"]


class TestTestDataGenGenerateStepData:
    def test_generate_step_data(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENSD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="gensd",
            title="generate step data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        service.create_test_data(
            step_id=step.id,
            field_name="field_a",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
        )
        service.create_test_data(
            step_id=step.id,
            field_name="field_b",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
        )
        result = service.generate_step_data(step.id)
        assert "field_a" in result
        assert "field_b" in result
        assert len(result["field_a"]) > 0
        assert len(result["field_b"]) > 0

    def test_generate_step_data_empty(self, db):
        service = TestDataService(db)
        result = service.generate_step_data(99999)
        assert result == {}


class TestTestDataGenBatchCreate:
    def test_batch_create_test_data(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-BATCHTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="batchtd",
            title="batch create test data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        data_list = [
            {
                "field_name": "field_1",
                "field_type": DataType.TEXT,
                "generation_rule": GenerationRule.RANDOM,
            },
            {
                "field_name": "field_2",
                "field_type": DataType.NUMBER,
                "generation_rule": GenerationRule.RANDOM,
                "min_value": 0,
                "max_value": 100,
            },
        ]
        created = service.batch_create_test_data(step.id, data_list)
        assert len(created) == 2
        assert created[0].field_name == "field_1"
        assert created[1].field_name == "field_2"

    def test_batch_create_test_data_empty(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-BATCHEMPTY-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="batchempty",
            title="batch empty",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.batch_create_test_data(step.id, [])
        assert created == []


class TestTestDataGenCopy:
    def test_copy_test_data(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-COPYTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="copytd",
            title="copy test data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        source_step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        target_step = TestStep(
            test_case_id=case.id,
            step_number=2,
            action="verify",
            expected_result="ok",
        )
        db.add(source_step)
        db.add(target_step)
        db.flush()
        service = TestDataService(db)
        service.create_test_data(
            step_id=source_step.id,
            field_name="copy_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            description="source data",
        )
        copied = service.copy_test_data(source_step.id, target_step.id)
        assert copied == 1
        target_data = service.get_test_data_by_step(target_step.id)
        assert len(target_data) == 1
        assert target_data[0].field_name == "copy_field"

    def test_copy_test_data_empty_source(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-COPYEMPTY-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="copyempty",
            title="copy empty source",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        source_step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        target_step = TestStep(
            test_case_id=case.id,
            step_number=2,
            action="verify",
            expected_result="ok",
        )
        db.add(source_step)
        db.add(target_step)
        db.flush()
        service = TestDataService(db)
        copied = service.copy_test_data(source_step.id, target_step.id)
        assert copied == 0


class TestTestDataGenAutoGenerate:
    def test_auto_generate_for_product(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AUTOPROD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="autoprod",
            title="auto generate product",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.auto_generate_for_step(step.id, "选择产品�?)
        assert len(created) >= 1
        field_names = [td.field_name for td in created]
        assert "product_name" in field_names

    def test_auto_generate_for_input(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AUTOINP-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="autoinp",
            title="auto generate input",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.auto_generate_for_step(step.id, "输入用户�?)
        field_names = [td.field_name for td in created]
        assert "input_value" in field_names

    def test_auto_generate_for_select(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AUTOSEL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="autosel",
            title="auto generate select",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="select",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.auto_generate_for_step(step.id, "选择城市")
        field_names = [td.field_name for td in created]
        assert "select_value" in field_names

    def test_auto_generate_for_date(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AUTODATE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="autodate",
            title="auto generate date",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.auto_generate_for_step(step.id, "选择日期")
        field_names = [td.field_name for td in created]
        assert "date_value" in field_names

    def test_auto_generate_no_match(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AUTONONE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="autonone",
            title="auto generate no match",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="navigate",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.auto_generate_for_step(step.id, "navigate to page")
        assert created == []

    def test_auto_generate_combined_keywords(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AUTOCOMB-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="autocomb",
            title="auto generate combined",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        created = service.auto_generate_for_step(step.id, "选择产品线并输入日期")
        field_names = [td.field_name for td in created]
        assert "product_name" in field_names
        assert "select_value" in field_names
        assert "input_value" in field_names
        assert "date_value" in field_names


class TestTestDataGenGenerateCaseData:
    def test_generate_case_data(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-GENCD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="gencd",
            title="generate case data",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        service.create_test_data(
            step_id=step.id,
            field_name="case_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
        )
        result = service.generate_case_data(case.id)
        assert step.id in result
        assert "case_field" in result[step.id]

    def test_generate_case_data_nonexistent(self, db):
        service = TestDataService(db)
        result = service.generate_case_data(99999)
        assert result == {}


class TestTestDataModel:
    def test_test_data_to_dict(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TODICTTD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="todicttd",
            title="test data to dict",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        service = TestDataService(db)
        td = service.create_test_data(
            step_id=step.id,
            field_name="dict_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            description="to dict test",
        )
        d = td.to_dict()
        assert d["field_name"] == "dict_field"
        assert d["field_type"] == "text"
        assert d["generation_rule"] == "random"
        assert d["description"] == "to dict test"
        assert "id" in d
        assert "step_id" in d

    def test_data_type_enum_values(self):
        assert DataType.TEXT == "text"
        assert DataType.NUMBER == "number"
        assert DataType.DATE == "date"
        assert DataType.EMAIL == "email"
        assert DataType.ENUM == "enum"
        assert DataType.BOOLEAN == "boolean"
        assert DataType.URL == "url"

    def test_generation_rule_enum_values(self):
        assert GenerationRule.RANDOM == "random"
        assert GenerationRule.BOUNDARY_MIN == "boundary_min"
        assert GenerationRule.BOUNDARY_MAX == "boundary_max"
        assert GenerationRule.SPECIAL_CHARS == "special_chars"
        assert GenerationRule.EMPTY == "empty"
        assert GenerationRule.CUSTOM == "custom"
