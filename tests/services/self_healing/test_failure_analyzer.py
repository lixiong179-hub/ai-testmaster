"""FailureAnalyzer 单元测试。

覆盖：
    - 关键词匹配分类（load_delay / element_gone / env_noise / dom_changed 默认）
    - DOM 快照校正（元素存在/不存在/部分匹配）
    - suggested_strategy 映射
    - 边界：error=None / 空字符串 / dom_snapshot="" / old_selector=None
    - 置信度范围 0.0-1.0

被测：app/services/self_healing/failure_analyzer.py + models.py
"""
import pytest

from app.services.self_healing.failure_analyzer import FailureAnalyzer
from app.services.self_healing.models import FailureAnalysis, FailureType


class TestFailureAnalyzerClassifyByError:
    """按错误关键词初判的失败类型分类。"""

    def setup_method(self) -> None:
        self.analyzer = FailureAnalyzer()

    def test_load_delay_classification(self):
        """error 含 timeout 关键词 + DOM 含元素 → load_delay。"""
        error = Exception("timeout waiting for selector")
        dom = '<button id="login-btn" class="btn">登录</button>'
        result = self.analyzer.analyze(error, dom, "#login-btn")
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.suggested_strategy == "retry"
        assert 0.0 <= result.confidence <= 1.0
        # DOM 校正后置信度应为 0.75
        assert result.confidence == 0.75

    def test_element_gone_classification(self):
        """error 含 not found + DOM 不含元素 → element_gone。"""
        error = Exception("element not found in DOM")
        dom = "<div><span>无关元素</span></div>"
        result = self.analyzer.analyze(error, dom, "#missing-btn")
        assert result.failure_type == FailureType.ELEMENT_GONE
        assert result.suggested_strategy == "ai_heal"
        assert result.confidence == 0.8

    def test_env_noise_classification(self):
        """error 含 net::ERR_CONNECTION_RESET → env_noise。

        不传 old_selector，避免 DOM 校正覆盖 env_noise 分类。
        """
        error = Exception("net::ERR_CONNECTION_RESET")
        result = self.analyzer.analyze(error, "<html></html>", None)
        assert result.failure_type == FailureType.ENV_NOISE
        assert result.suggested_strategy == "skip"
        assert result.confidence == 0.8

    def test_env_noise_dominates_other_keywords(self):
        """env_noise 优先级高于 element_gone/load_delay。"""
        # 同时含 network 与 not found，应优先 env_noise
        error = Exception("network error caused element not found")
        result = self.analyzer.analyze(error, "", None)
        assert result.failure_type == FailureType.ENV_NOISE
        assert result.suggested_strategy == "skip"

    def test_dom_changed_default_classification(self):
        """无关键词匹配 → dom_changed（默认）。"""
        error = Exception("some unknown failure reason")
        result = self.analyzer.analyze(error, "", None)
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.suggested_strategy == "ai_heal"
        assert result.confidence == 0.4

    def test_chinese_keyword_load_delay(self):
        """中文关键词：超时/等待 → load_delay。"""
        error = Exception("元素超时未出现")
        result = self.analyzer.analyze(error, "", None)
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.suggested_strategy == "retry"

    def test_chinese_keyword_element_gone(self):
        """中文关键词：未找到/不存在 → element_gone。"""
        error = Exception("元素未找到")
        result = self.analyzer.analyze(error, "", None)
        assert result.failure_type == FailureType.ELEMENT_GONE
        assert result.suggested_strategy == "ai_heal"

    def test_chinese_keyword_env_noise(self):
        """中文关键词：弹窗 → env_noise。"""
        error = Exception("弹窗遮挡了元素")
        result = self.analyzer.analyze(error, "", None)
        assert result.failure_type == FailureType.ENV_NOISE
        assert result.suggested_strategy == "skip"


class TestFailureAnalyzerDomCorrection:
    """DOM 快照校正逻辑。"""

    def setup_method(self) -> None:
        self.analyzer = FailureAnalyzer()

    def test_dom_present_element_load_delay(self):
        """DOM 含完整关键词 → load_delay（即使 error 是 not found）。"""
        error = Exception("element not found")
        dom = '<input id="username" class="form-control" />'
        result = self.analyzer.analyze(error, dom, "#username")
        # DOM 校正覆盖 error 分类
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.confidence == 0.75
        assert result.evidence["dom_check_result"]["selector_matched"] == ["username"]

    def test_dom_partial_match_dom_changed(self):
        """DOM 部分匹配关键词 → dom_changed。"""
        error = Exception("element not found")
        # DOM 只含 username 不含 password
        dom = '<input id="username" />'
        # 选择器同时引用两个关键词
        old_selector = "#username#password"
        result = self.analyzer.analyze(error, dom, old_selector)
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.confidence == 0.7
        assert result.evidence["dom_check_result"]["partial_match"] is True

    def test_dom_no_match_element_gone(self):
        """DOM 完全不匹配 → element_gone。"""
        error = Exception("timeout waiting")
        dom = "<div>无关内容</div>"
        result = self.analyzer.analyze(error, dom, "#missing-id")
        assert result.failure_type == FailureType.ELEMENT_GONE
        assert result.confidence == 0.8

    def test_dom_skipped_when_no_selector(self):
        """old_selector=None → 跳过 DOM 校正，保留 error 分类。"""
        error = Exception("timeout waiting for selector")
        dom = "<div>some dom</div>"
        result = self.analyzer.analyze(error, dom, None)
        # old_selector=None 时 DOM 校正返回 confidence=0.0，保留 error 分类
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.confidence == 0.6
        assert result.evidence["dom_check_result"] == {"skipped": "no_selector"}

    def test_dom_skipped_when_no_keywords_extracted(self):
        """old_selector 无法提取关键词 → 跳过 DOM 校正。"""
        error = Exception("timeout")
        # 选择器只含标签，无 id/class/name
        result = self.analyzer.analyze(error, "<div></div>", "div > span")
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.evidence["dom_check_result"] == {
            "skipped": "no_keywords_extracted"
        }

    def test_xpath_selector_keyword_extraction(self):
        """xpath= 前缀选择器关键词提取。"""
        error = Exception("element not found")
        dom = '<button id="submit" class="primary">提交</button>'
        selector = "xpath=//button[@id='submit' and @class='primary']"
        result = self.analyzer.analyze(error, dom, selector)
        # DOM 校正应识别为 load_delay（元素存在）
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.confidence == 0.75

    def test_empty_dom_snapshot_keeps_error_classification(self):
        """dom_snapshot='' → 仅用 error 分类。"""
        error = Exception("timeout waiting for selector")
        result = self.analyzer.analyze(error, "", "#login")
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.confidence == 0.6
        # dom_check_result 应为 None
        assert result.evidence["dom_check_result"] is None

    def test_whitespace_dom_snapshot_keeps_error_classification(self):
        """dom_snapshot 仅含空白 → 仅用 error 分类。"""
        error = Exception("timeout")
        result = self.analyzer.analyze(error, "   \n\t  ", "#login")
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.evidence["dom_check_result"] is None


class TestFailureAnalyzerBoundaries:
    """边界场景：空值/None 输入。"""

    def setup_method(self) -> None:
        self.analyzer = FailureAnalyzer()

    def test_error_none_returns_dom_changed(self):
        """error=None → 默认 dom_changed，confidence=0.3。"""
        result = self.analyzer.analyze(None, "<div></div>", "#x")
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.confidence == 0.3
        assert result.suggested_strategy == "ai_heal"
        assert result.evidence == {"reason": "empty_error"}

    def test_empty_string_error_returns_dom_changed(self):
        """error 为空字符串 → dom_changed。"""
        result = self.analyzer.analyze(Exception(""), "<div></div>", "#x")
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.confidence == 0.3
        assert result.evidence == {"reason": "empty_error"}

    def test_whitespace_only_error_returns_dom_changed(self):
        """error 仅含空白 → dom_changed。"""
        result = self.analyzer.analyze(Exception("   \n\t  "), "<div></div>", "#x")
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.confidence == 0.3

    def test_old_selector_none_with_dom_present(self):
        """old_selector=None 时 DOM 校正跳过。"""
        error = Exception("timeout")
        result = self.analyzer.analyze(error, "<div id='x'></div>", None)
        assert result.failure_type == FailureType.LOAD_DELAY
        # 校正被跳过，使用 error 置信度
        assert result.confidence == 0.6

    def test_non_exception_error_object(self):
        """error 为非 Exception 对象时通过 str() 转换。"""
        # str(123) = "123" 不匹配任何关键词
        result = self.analyzer.analyze(123, "", None)  # type: ignore[arg-type]
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.confidence == 0.4


class TestFailureAnalyzerStrategyMap:
    """suggested_strategy 映射正确性。"""

    def setup_method(self) -> None:
        self.analyzer = FailureAnalyzer()

    def test_load_delay_strategy_retry(self):
        result = self.analyzer.analyze(Exception("timeout"), "", None)
        assert result.failure_type == FailureType.LOAD_DELAY
        assert result.suggested_strategy == "retry"

    def test_env_noise_strategy_skip(self):
        result = self.analyzer.analyze(Exception("net::ERR"), "", None)
        assert result.failure_type == FailureType.ENV_NOISE
        assert result.suggested_strategy == "skip"

    def test_element_gone_strategy_ai_heal(self):
        result = self.analyzer.analyze(Exception("element not found"), "", None)
        assert result.failure_type == FailureType.ELEMENT_GONE
        assert result.suggested_strategy == "ai_heal"

    def test_dom_changed_strategy_ai_heal(self):
        result = self.analyzer.analyze(Exception("unknown error"), "", None)
        assert result.failure_type == FailureType.DOM_CHANGED
        assert result.suggested_strategy == "ai_heal"


class TestFailureAnalyzerConfidenceRange:
    """置信度始终在 0.0-1.0 范围内。"""

    def setup_method(self) -> None:
        self.analyzer = FailureAnalyzer()

    @pytest.mark.parametrize(
        "error_msg,dom,selector",
        [
            ("timeout waiting for selector", "<div id='x'></div>", "#x"),
            ("element not found", "<div></div>", "#missing"),
            ("net::ERR_CONNECTION_RESET", "", None),
            ("unknown error", "", None),
            ("", "", None),
        ],
    )
    def test_confidence_always_in_valid_range(self, error_msg, dom, selector):
        error = Exception(error_msg) if error_msg else None
        result = self.analyzer.analyze(error, dom, selector)
        assert 0.0 <= result.confidence <= 1.0


class TestFailureAnalysisDataclass:
    """FailureAnalysis 数据结构验证。"""

    def test_default_evidence_is_empty_dict(self):
        analysis = FailureAnalysis(
            failure_type=FailureType.LOAD_DELAY,
            confidence=0.5,
            suggested_strategy="retry",
        )
        assert analysis.evidence == {}

    def test_evidence_custom_values(self):
        analysis = FailureAnalysis(
            failure_type=FailureType.ELEMENT_GONE,
            confidence=0.8,
            suggested_strategy="ai_heal",
            evidence={"matched_keywords": ["not found"]},
        )
        assert analysis.evidence["matched_keywords"] == ["not found"]


class TestExtractSelectorKeywords:
    """选择器关键词提取静态方法。"""

    def test_css_id_selector(self):
        kws = FailureAnalyzer._extract_selector_keywords("#login-btn")
        assert "login-btn" in kws

    def test_css_class_selector(self):
        kws = FailureAnalyzer._extract_selector_keywords(".btn-primary")
        assert "btn-primary" in kws

    def test_xpath_with_id_attribute(self):
        kws = FailureAnalyzer._extract_selector_keywords(
            "xpath=//button[@id='submit']"
        )
        assert "submit" in kws

    def test_xpath_with_class_attribute(self):
        kws = FailureAnalyzer._extract_selector_keywords(
            "xpath=//div[@class='container']"
        )
        assert "container" in kws

    def test_xpath_with_name_attribute(self):
        kws = FailureAnalyzer._extract_selector_keywords(
            "xpath=//input[@name='username']"
        )
        assert "username" in kws

    def test_dedup_keywords(self):
        # 重复出现的关键词应去重
        kws = FailureAnalyzer._extract_selector_keywords("#btn.btn")
        assert kws.count("btn") == 1

    def test_empty_selector(self):
        kws = FailureAnalyzer._extract_selector_keywords("")
        assert kws == []

    def test_no_matching_keywords(self):
        kws = FailureAnalyzer._extract_selector_keywords("div > span > p")
        assert kws == []
