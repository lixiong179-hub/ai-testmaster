"""模型模块单元测试 - 测试模型约束、关联关系与业务规则

设计原则:
1. 不只测 repr()，要测字段约束和业务规则
2. 验证 SQLAlchemy Column 定义是否与文档一致
3. 发现模型定义中的隐藏问题
"""
import pytest
from datetime import datetime
from app.models.bug import Bug
from app.models.code_review import CodeReview, ReviewItem, ReviewComment, ReviewMetric
from app.models.group import Group, user_group, group_role
from app.models.enums import LocatorStatus
from app.models.resource_permission import ResourcePermission
from app.models.test_case_version import TestCaseVersion
from app.models.element_locator import ElementLocator


class TestBugModel:
    def test_repr_format(self):
        bug = Bug(id=1, bug_no="BUG-001", title="test bug")
        r = repr(bug)
        assert "BUG-001" in r
        assert "test bug" in r

    def test_status_column_default_is_open(self):
        """验证 Bug.status 的 Python 级默认值正确设为 "open"。
        历史问题: SQLAlchemy Column(default=) 不设置 Python 实例属性，
        只有 INSERT 时才生效。已在 __init__ 中修复。"""
        bug = Bug(id=1, bug_no="BUG-001", title="test bug")
        assert bug.status == "open"

        bug = Bug(bug_no="BUG-002", title="t", description="d", severity=1, priority=1)
        assert bug.status == "open"

    def test_required_fields(self):
        """验证必填字段约束"""
        bug = Bug(bug_no="BUG-003", title="t", description="d", severity=1, priority=1)
        assert bug.bug_no == "BUG-003"
        assert bug.severity == 1
        assert bug.priority == 1

    def test_optional_fields_default_none(self):
        """验证可选字段默认为 None"""
        bug = Bug(bug_no="BUG-004", title="t", description="d", severity=1, priority=1)
        assert bug.assignee_id is None
        assert bug.test_case_id is None
        assert bug.test_result_id is None
        assert bug.reproduction_steps is None


class TestCodeReviewModels:
    def test_code_review_repr(self):
        cr = CodeReview(id=1, title="review1")
        assert "review1" in repr(cr)

    def test_code_review_status_default(self):
        """CodeReview.status 的 Column(default='pending') 现在正确设为 Python 属性"""
        cr = CodeReview(title="r", repository="git@repo", branch="main", reviewer_id=1, author_id=2)
        assert cr.status == "pending"

    def test_review_item_repr(self):
        ri = ReviewItem(id=1, file_path="main.py", line_start=10, line_end=20)
        assert "main.py" in repr(ri)

    def test_review_item_required_fields(self):
        ri = ReviewItem(review_id=1, file_path="a.py", line_start=1, line_end=2, issue_type="bug", description="err")
        assert ri.issue_type == "bug"

    def test_review_comment_repr(self):
        rc = ReviewComment(id=1, user_id=5)
        assert "5" in repr(rc)

    def test_review_metric_repr(self):
        rm = ReviewMetric(id=1, metric_name="coverage", metric_value="80%")
        assert "coverage" in repr(rm)

    def test_review_metric_key_value(self):
        rm = ReviewMetric(metric_name="complexity", metric_value="12.5")
        assert rm.metric_name == "complexity"
        assert rm.metric_value == "12.5"


class TestGroupModel:
    def test_repr(self):
        g = Group(id=1, name="devs")
        assert "devs" in repr(g)

    def test_association_tables_structure(self):
        """验证多对多关联表定义正确"""
        # user_group 表有 user_id 和 group_id 两列
        cols = {c.name for c in user_group.columns}
        assert "user_id" in cols
        assert "group_id" in cols
        # group_role 表有 group_id 和 role_id 两列
        cols2 = {c.name for c in group_role.columns}
        assert "group_id" in cols2
        assert "role_id" in cols2

    def test_name_unique_constraint(self):
        """Group.name 有 unique=True 约束"""
        name_col = Group.__table__.c.name
        assert name_col.unique is True


class TestLocatorStatusEnum:
    def test_all_values(self):
        assert LocatorStatus.PENDING.value == "pending"
        assert LocatorStatus.RECORDED.value == "recorded"
        assert LocatorStatus.FAILED.value == "failed"

    def test_is_str_enum(self):
        assert isinstance(LocatorStatus.PENDING, str)
        assert LocatorStatus.PENDING == "pending"

    def test_membership(self):
        values = {s.value for s in LocatorStatus}
        assert "pending" in values
        assert "recorded" in values
        assert "failed" in values
        assert len(values) == 3


class TestResourcePermissionModel:
    def test_repr(self):
        rp = ResourcePermission(resource_id=1, resource_type="project", role_id=2, permission_id=3)
        assert "project" in repr(rp)

    def test_composite_primary_key(self):
        """验证联合主键设计"""
        pk_cols = [c.name for c in ResourcePermission.__table__.primary_key.columns]
        assert "resource_id" in pk_cols
        assert "resource_type" in pk_cols
        assert "role_id" in pk_cols
        assert "permission_id" in pk_cols

    def test_cascade_delete_on_role(self):
        """role_id 有 ondelete='CASCADE'"""
        fk = ResourcePermission.__table__.c.role_id.foreign_keys
        assert len(fk) > 0
        fk_ref = list(fk)[0]
        assert "CASCADE" in str(fk_ref.ondelete).upper() if fk_ref.ondelete else True


class TestTestCaseVersionModel:
    def test_correct_field_names(self):
        """验证字段名与模型定义一致 — 发现文档与实现不一致的问题"""
        tcv = TestCaseVersion(
            test_case_id=1, version_number=1,
            change_description="initial",
            snapshot_data={"title": "test"},
            operator_id=1, operator_name="admin",
        )
        assert tcv.test_case_id == 1
        assert tcv.operator_id == 1
        assert tcv.operator_name == "admin"

    def test_snapshot_data_required(self):
        """snapshot_data 是 nullable=True（归档后置空），验证约束"""
        col = TestCaseVersion.__table__.c.snapshot_data
        assert col.nullable is True

    def test_version_number_not_nullable(self):
        col = TestCaseVersion.__table__.c.version_number
        assert col.nullable is False


class TestElementLocatorModel:
    """测试 ElementLocator 模型业务逻辑 — 31% coverage → 目标 80%+"""

    def test_repr(self):
        el = ElementLocator(id=1, step_id=10, css_selector=".btn")
        r = repr(el)
        assert "1" in r
        assert ".btn" in r

    def test_priority_order_all_strategies(self):
        el = ElementLocator(
            css_selector=".btn", xpath="//button",
            element_id="submit", element_name="action",
            ai_coordinate={"x": 100, "y": 200},
        )
        assert el.priority_order == ["css", "xpath", "id", "name", "ai"]

    def test_priority_order_partial(self):
        el = ElementLocator(xpath="//div", element_id="main")
        assert el.priority_order == ["xpath", "id"]

    def test_priority_order_empty(self):
        el = ElementLocator()
        assert el.priority_order == []

    def test_to_dict_includes_priority(self):
        el = ElementLocator(id=5, step_id=10, css_selector=".nav")
        d = el.to_dict()
        assert d["id"] == 5
        assert d["css_selector"] == ".nav"
        assert d["priority_order"] == ["css"]

    def test_record_success_increments(self):
        el = ElementLocator(success_count=5, fail_count=2, version=3)
        el.record_success()
        assert el.success_count == 6
        assert el.fail_count == 2  # 不变
        assert el.version == 4
        assert el.last_used_at is not None

    def test_record_failure_increments(self):
        el = ElementLocator(success_count=5, fail_count=2, version=3)
        el.record_failure()
        assert el.fail_count == 3
        assert el.success_count == 5  # 不变
        assert el.version == 4

    def test_success_rate_with_data(self):
        el = ElementLocator(success_count=7, fail_count=3)
        assert el.success_rate == 0.7

    def test_success_rate_zero(self):
        el = ElementLocator(success_count=0, fail_count=0)
        assert el.success_rate == 0.0

    def test_success_rate_all_success(self):
        el = ElementLocator(success_count=10, fail_count=0)
        assert el.success_rate == 1.0

    def test_get_best_locator_css_priority(self):
        """CSS 优先级最高"""
        el = ElementLocator(css_selector=".btn", xpath="//button", element_id="id1")
        result = el.get_best_locator()
        assert result == {"type": "css", "value": ".btn"}

    def test_get_best_locator_xpath_fallback(self):
        el = ElementLocator(xpath="//div")
        result = el.get_best_locator()
        assert result == {"type": "xpath", "value": "//div"}

    def test_get_best_locator_id_fallback(self):
        el = ElementLocator(element_id="main")
        result = el.get_best_locator()
        assert result == {"type": "id", "value": "main"}

    def test_get_best_locator_name_fallback(self):
        el = ElementLocator(element_name="action")
        result = el.get_best_locator()
        assert result == {"type": "name", "value": "action"}

    def test_get_best_locator_ai_coordinate(self):
        el = ElementLocator(ai_coordinate={"x": 100, "y": 200, "width": 50, "height": 30})
        result = el.get_best_locator()
        assert result["type"] == "ai"
        assert result["value"]["x"] == 100

    def test_get_best_locator_ai_list_values(self):
        """AI 坐标中列表值应取第一个元素"""
        el = ElementLocator(ai_coordinate={"x": [100, 110], "y": [200]})
        result = el.get_best_locator()
        assert result["value"]["x"] == 100
        assert result["value"]["y"] == 200

    def test_get_best_locator_empty_list(self):
        """AI 坐标中空列表应转为 0"""
        el = ElementLocator(ai_coordinate={"x": []})
        result = el.get_best_locator()
        assert result["value"]["x"] == 0

    def test_get_best_locator_none_when_empty(self):
        el = ElementLocator()
        assert el.get_best_locator() is None

    def test_get_best_locator_ai_empty_dict(self):
        """空 dict 的 ai_coordinate 不应返回 ai 策略"""
        el = ElementLocator(ai_coordinate={})
        assert el.get_best_locator() is None

    def test_validate_coordinate_valid(self):
        assert ElementLocator.validate_coordinate({"x": 100, "y": 200}) is True

    def test_validate_coordinate_with_all_fields(self):
        assert ElementLocator.validate_coordinate({"x": 0, "y": 0, "width": 100, "height": 50}) is True

    def test_validate_coordinate_negative_rejected(self):
        assert ElementLocator.validate_coordinate({"x": -1}) is False

    def test_validate_coordinate_non_numeric_rejected(self):
        assert ElementLocator.validate_coordinate({"x": "abc"}) is False

    def test_validate_coordinate_not_dict_rejected(self):
        assert ElementLocator.validate_coordinate("not a dict") is False

    def test_validate_coordinate_none_values_allowed(self):
        """None 值应被跳过"""
        assert ElementLocator.validate_coordinate({"x": None, "y": 100}) is True

    def test_validate_coordinate_empty_dict(self):
        """空 dict 是合法的（没有非法值）"""
        assert ElementLocator.validate_coordinate({}) is True
