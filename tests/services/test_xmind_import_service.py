import io
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile, HTTPException

from app.services.xmind_import_service import (
    validate_file,
    save_upload_file,
    filter_valid_points,
    collect_skip_reasons,
    should_treat_as_case_tree,
    handle_case_style_import,
    handle_ai_enhanced_import,
)


class TestValidateFile:
    def test_valid_xmind_file(self):
        f = MagicMock(spec=UploadFile)
        f.filename = "test.xmind"
        validate_file(f)

    def test_non_xmind_extension(self):
        f = MagicMock(spec=UploadFile)
        f.filename = "test.xlsx"
        with pytest.raises(HTTPException) as exc_info:
            validate_file(f)
        assert exc_info.value.status_code == 400

    def test_no_filename(self):
        f = MagicMock(spec=UploadFile)
        f.filename = None
        with pytest.raises(HTTPException) as exc_info:
            validate_file(f)
        assert exc_info.value.status_code == 400

    def test_empty_filename(self):
        f = MagicMock(spec=UploadFile)
        f.filename = ""
        with pytest.raises(HTTPException) as exc_info:
            validate_file(f)
        assert exc_info.value.status_code == 400


class TestSaveUploadFile:
    @pytest.mark.asyncio
    async def test_save_small_file(self):
        content = b"xmind content data"
        f = MagicMock(spec=UploadFile)
        f.read = AsyncMock(side_effect=[content, b""])
        path = await save_upload_file(f)
        try:
            assert os.path.exists(path)
            assert path.endswith(".xmind")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    @pytest.mark.asyncio
    async def test_save_empty_file(self):
        f = MagicMock(spec=UploadFile)
        f.read = AsyncMock(return_value=b"")
        path = await save_upload_file(f)
        try:
            assert os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestFilterValidPoints:
    def test_valid_points(self):
        points = [
            {"module": "登录模块", "point": "用户名验证"},
            {"module": "注册模块", "point": "邮箱格式校验"},
        ]
        result = filter_valid_points(points)
        assert len(result) == 2

    def test_filter_missing_module(self):
        points = [{"point": "用户名验证"}]
        result = filter_valid_points(points)
        assert len(result) == 0

    def test_filter_missing_point(self):
        points = [{"module": "登录模块"}]
        result = filter_valid_points(points)
        assert len(result) == 0

    def test_filter_empty_module(self):
        points = [{"module": "", "point": "用户名验证"}]
        result = filter_valid_points(points)
        assert len(result) == 0

    def test_filter_empty_point(self):
        points = [{"module": "登录模块", "point": ""}]
        result = filter_valid_points(points)
        assert len(result) == 0

    def test_mixed_valid_and_invalid(self):
        points = [
            {"module": "登录模块", "point": "用户名验证"},
            {"module": "", "point": "无模块"},
            {"module": "注册模块", "point": ""},
        ]
        result = filter_valid_points(points)
        assert len(result) == 1

    def test_empty_list(self):
        assert filter_valid_points([]) == []


class TestCollectSkipReasons:
    def test_skip_missing_module(self):
        points = [{"point": "用户名验证"}]
        reasons = collect_skip_reasons(points)
        assert "模块名称为空" in reasons

    def test_skip_missing_point(self):
        points = [{"module": "登录模块"}]
        reasons = collect_skip_reasons(points)
        assert "测试点名称为空" in reasons

    def test_no_skip_reasons(self):
        points = [{"module": "登录模块", "point": "用户名验证"}]
        reasons = collect_skip_reasons(points)
        assert len(reasons) == 0

    def test_max_20_reasons(self):
        points = [{"point": f"测试点{i}"} for i in range(30)]
        reasons = collect_skip_reasons(points)
        assert len(reasons) == 20

    def test_empty_list(self):
        assert collect_skip_reasons([]) == []


class TestShouldTreatAsCaseTree:
    def test_empty_list(self):
        assert should_treat_as_case_tree([]) is False

    def test_single_case_like_item(self):
        parsed = [{
            "source_depth": 4,
            "action_count": 2,
            "expected_count": 1,
            "condition_count": 1,
            "ignored_count": 0,
        }]
        assert should_treat_as_case_tree(parsed) is True

    def test_single_non_case_like_item(self):
        parsed = [{
            "source_depth": 2,
            "action_count": 0,
            "expected_count": 0,
            "condition_count": 0,
            "ignored_count": 0,
        }]
        assert should_treat_as_case_tree(parsed) is False

    def test_multiple_items_majority_case_like(self):
        parsed = [
            {"source_depth": 4, "action_count": 2, "expected_count": 1, "condition_count": 1, "ignored_count": 0},
            {"source_depth": 4, "action_count": 2, "expected_count": 1, "condition_count": 0, "ignored_count": 1},
            {"source_depth": 2, "action_count": 0, "expected_count": 0, "condition_count": 0, "ignored_count": 0},
        ]
        assert should_treat_as_case_tree(parsed) is True

    def test_multiple_items_minority_case_like(self):
        parsed = [
            {"source_depth": 2, "action_count": 0, "expected_count": 0, "condition_count": 0, "ignored_count": 0},
            {"source_depth": 2, "action_count": 0, "expected_count": 0, "condition_count": 0, "ignored_count": 0},
            {"source_depth": 4, "action_count": 2, "expected_count": 1, "condition_count": 1, "ignored_count": 0},
        ]
        assert should_treat_as_case_tree(parsed) is False

    def test_insufficient_depth(self):
        parsed = [{"source_depth": 3, "action_count": 2, "expected_count": 1, "condition_count": 1, "ignored_count": 0}]
        assert should_treat_as_case_tree(parsed) is False

    def test_no_actions(self):
        parsed = [{"source_depth": 4, "action_count": 0, "expected_count": 1, "condition_count": 1, "ignored_count": 0}]
        assert should_treat_as_case_tree(parsed) is False

    def test_no_expected(self):
        parsed = [{"source_depth": 4, "action_count": 2, "expected_count": 0, "condition_count": 1, "ignored_count": 0}]
        assert should_treat_as_case_tree(parsed) is False

    def test_two_actions_without_condition(self):
        parsed = [{"source_depth": 4, "action_count": 2, "expected_count": 1, "condition_count": 0, "ignored_count": 0}]
        assert should_treat_as_case_tree(parsed) is True


class TestHandleCaseStyleImportPreview:
    def test_preview_mode(self, db, testProject):
        parsed_cases = [
            {
                "module": "登录模块",
                "point": "用户名验证",
                "priority": 2,
                "title": "验证用户名格式",
                "precondition": "已打开登录页",
                "expected_result": "提示格式错误",
                "steps": [
                    {"action": "输入用户名", "expected_result": "显示输入内容"},
                ],
            }
        ]
        result = handle_case_style_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            parsed_cases=parsed_cases,
            preview=True,
        )
        assert result.preview_mode == "test_cases"
        assert result.total == 1
        assert result.case_total == 1
        assert len(result.case_items) == 1
        assert result.case_items[0].title == "验证用户名格式"
        assert len(result.case_items[0].steps) == 1

    def test_preview_with_multiple_cases(self, db, testProject):
        parsed_cases = [
            {"module": "模块A", "point": "测试点1", "priority": 1, "title": "用例1", "precondition": "", "expected_result": "", "steps": []},
            {"module": "模块B", "point": "测试点2", "priority": 3, "title": "用例2", "precondition": "", "expected_result": "", "steps": []},
        ]
        result = handle_case_style_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            parsed_cases=parsed_cases,
            preview=True,
        )
        assert result.total == 2
        assert result.case_total == 2

    def test_preview_empty_cases(self, db, testProject):
        result = handle_case_style_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            parsed_cases=[],
            preview=True,
        )
        assert result.total == 0
        assert result.case_total == 0

    def test_preview_with_ai_timeout(self, db, testProject):
        parsed_cases = [
            {"module": "模块A", "point": "测试点1", "priority": 2, "title": "用例1", "precondition": "", "expected_result": "", "steps": []},
        ]
        result = handle_case_style_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            parsed_cases=parsed_cases,
            preview=True,
            ai_timeout=True,
        )
        assert result.ai_timeout is True


class TestHandleCaseStyleImportSave:
    def test_save_mode(self, db, testProject):
        parsed_cases = [
            {
                "module": "登录模块",
                "point": "密码验证",
                "priority": 2,
                "title": "验证密码强度",
                "precondition": "已打开注册页",
                "expected_result": "密码强度提示",
                "steps": [
                    {"action": "输入弱密码", "expected_result": "提示密码过弱"},
                ],
            }
        ]
        result = handle_case_style_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            parsed_cases=parsed_cases,
            preview=False,
        )
        assert result.saved_count == 1
        assert result.saved_case_count == 1
        assert result.total_parsed == 1
        assert result.skipped_count == 0

    def test_save_multiple_cases(self, db, testProject):
        parsed_cases = [
            {"module": "模块A", "point": "测试点1", "priority": 1, "title": "用例1", "precondition": "", "expected_result": "", "steps": []},
            {"module": "模块B", "point": "测试点2", "priority": 2, "title": "用例2", "precondition": "", "expected_result": "", "steps": []},
        ]
        result = handle_case_style_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            parsed_cases=parsed_cases,
            preview=False,
        )
        assert result.saved_count == 2
        assert result.saved_case_count == 2


class TestHandleAiEnhancedImport:
    def test_delegates_to_case_style_import(self, db, testProject):
        ai_cases = [
            {"module": "AI模块", "point": "AI测试点", "priority": 2, "title": "AI用例", "precondition": "", "expected_result": "", "steps": []},
        ]
        result = handle_ai_enhanced_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            ai_cases=ai_cases,
            preview=True,
        )
        assert result.preview_mode == "test_cases"
        assert result.total == 1

    def test_save_mode(self, db, testProject):
        ai_cases = [
            {"module": "AI模块", "point": "AI测试点", "priority": 2, "title": "AI用例", "precondition": "", "expected_result": "", "steps": []},
        ]
        result = handle_ai_enhanced_import(
            db=db,
            project_id=testProject.id,
            current_username="test_user",
            ai_cases=ai_cases,
            preview=False,
        )
        assert result.saved_count == 1
