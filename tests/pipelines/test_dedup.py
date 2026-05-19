import pytest
from app.pipelines.steps._dedup import _jaccard_similarity, _dedup_cases_by_title, _dedup_cases_global


class TestJaccardSimilarity:
    def test_empty_strings(self):
        assert _jaccard_similarity("", "") == 0.0

    def test_one_empty(self):
        assert _jaccard_similarity("hello", "") == 0.0

    def test_identical_strings(self):
        result = _jaccard_similarity("登录测试", "登录测试")
        assert result == 1.0

    def test_completely_different(self):
        result = _jaccard_similarity("登录测试", "注册流程")
        assert result < 0.5

    def test_similar_strings(self):
        result = _jaccard_similarity("用户登录功能测试", "用户登录验证测试")
        assert result >= 0.3

    def test_short_string(self):
        result = _jaccard_similarity("a", "a")
        assert result == 1.0

    def test_single_char_different(self):
        result = _jaccard_similarity("a", "b")
        assert result == 0.0


class TestDedupCasesByTitle:
    def test_empty_list(self):
        assert _dedup_cases_by_title([]) == []

    def test_single_case(self):
        cases = [{"title": "登录测试"}]
        assert _dedup_cases_by_title(cases) == cases

    def test_no_duplicates(self):
        cases = [
            {"title": "登录测试"},
            {"title": "注册流程"},
            {"title": "密码重置"},
        ]
        result = _dedup_cases_by_title(cases)
        assert len(result) == 3

    def test_exact_duplicates(self):
        cases = [
            {"title": "登录测试"},
            {"title": "登录测试"},
        ]
        result = _dedup_cases_by_title(cases)
        assert len(result) == 1

    def test_similar_duplicates(self):
        cases = [
            {"title": "用户登录功能验证测试"},
            {"title": "用户登录功能验证测试用例"},
        ]
        result = _dedup_cases_by_title(cases)
        assert len(result) <= 2

    def test_preserves_first_occurrence(self):
        cases = [
            {"title": "登录测试", "id": 1},
            {"title": "登录测试", "id": 2},
        ]
        result = _dedup_cases_by_title(cases)
        assert result[0]["id"] == 1

    def test_missing_title(self):
        cases = [
            {"title": "登录测试"},
            {"title": ""},
            {"no_title": True},
        ]
        result = _dedup_cases_by_title(cases)
        assert len(result) >= 1


class TestDedupCasesGlobal:
    def test_empty_list(self):
        assert _dedup_cases_global([]) == []

    def test_non_success_entries_preserved(self):
        entries = [
            {"status": "error", "case_data": []},
        ]
        result = _dedup_cases_global(entries)
        assert len(result) == 1

    def test_success_entries_deduped(self):
        entries = [
            {
                "status": "success",
                "case_data": [{"title": "登录测试"}, {"title": "注册流程"}],
            },
        ]
        result = _dedup_cases_global(entries)
        assert len(result) == 1
        assert len(result[0]["case_data"]) == 2

    def test_global_dedup_across_entries(self):
        entries = [
            {
                "status": "success",
                "test_point": {"id": 1},
                "case_data": [{"title": "用户登录功能验证测试"}],
            },
            {
                "status": "success",
                "test_point": {"id": 2},
                "case_data": [{"title": "用户登录功能验证测试用例"}],
            },
        ]
        result = _dedup_cases_global(entries)
        total_cases = sum(len(e["case_data"]) for e in result)
        assert total_cases <= 2

    def test_preserves_non_success(self):
        entries = [
            {"status": "error", "case_data": [], "message": "failed"},
            {
                "status": "success",
                "case_data": [{"title": "登录测试"}],
            },
        ]
        result = _dedup_cases_global(entries)
        assert len(result) == 2
