"""失败分析器 - 基于错误信息与 DOM 快照分析元素定位失败类型。

分类流程:
    1. _classify_by_error: 按错误信息关键词初判失败类型
    2. _classify_by_dom: 用 DOM 快照校正（DOM 证据置信度更高，覆盖初判）
    3. suggested_strategy 映射: load_delay→retry, env_noise→skip, 其余→ai_heal
"""
import re
from typing import Any, Optional

from app.services.self_healing.models import FailureAnalysis, FailureType


# 失败类型到建议策略的映射
_STRATEGY_MAP: dict[FailureType, str] = {
    FailureType.LOAD_DELAY: "retry",
    FailureType.ENV_NOISE: "skip",
    FailureType.ELEMENT_GONE: "ai_heal",
    FailureType.DOM_CHANGED: "ai_heal",
}

# DOM 校正置信度阈值：低于该值视为无法判断，保留 error 分类
_DOM_CONFIDENT_THRESHOLD = 0.0


class FailureAnalyzer:
    """基于错误信息与 DOM 快照分析元素定位失败类型。"""

    _LOAD_DELAY_KEYWORDS = ("timeout", "waiting", "等待", "超时", "not visible", "not attached")
    _ELEMENT_GONE_KEYWORDS = ("not found", "no element", "未找到", "不存在", "stale", "detached")
    _ENV_NOISE_KEYWORDS = ("network", "navigation", "net::err", "target closed", "crashed", "弹窗")

    def analyze(
        self,
        error: Optional[Exception],
        dom_snapshot: str,
        old_selector: Optional[str] = None,
    ) -> FailureAnalysis:
        """分析失败类型，先按错误关键词初判，再用 DOM 快照校正。

        Args:
            error: 捕获的异常对象，None 或空消息视为无法判断。
            dom_snapshot: 失败时的 DOM 快照 HTML 文本，空字符串则仅用错误分类。
            old_selector: 失败前使用的定位器，None 时跳过 DOM 校正。

        Returns:
            FailureAnalysis: 包含失败类型、置信度、建议策略与分类证据。
        """
        error_str = "" if error is None else str(error)
        if not error_str.strip():
            return FailureAnalysis(
                failure_type=FailureType.DOM_CHANGED,
                confidence=0.3,
                suggested_strategy=_STRATEGY_MAP[FailureType.DOM_CHANGED],
                evidence={"reason": "empty_error"},
            )

        err_type, err_conf, matched_keywords = self._classify_by_error(error_str)
        final_type, final_conf = err_type, err_conf
        dom_evidence: Optional[dict[str, Any]] = None

        if dom_snapshot and dom_snapshot.strip():
            dom_type, dom_conf, dom_evidence = self._classify_by_dom(dom_snapshot, old_selector)
            # DOM 证据置信度更高，可判断时覆盖 error 分类
            if dom_conf > _DOM_CONFIDENT_THRESHOLD:
                final_type, final_conf = dom_type, dom_conf

        return FailureAnalysis(
            failure_type=final_type,
            confidence=final_conf,
            suggested_strategy=_STRATEGY_MAP[final_type],
            evidence={"matched_keywords": matched_keywords, "dom_check_result": dom_evidence},
        )

    def _classify_by_error(self, error_str: str) -> tuple[FailureType, float, list[str]]:
        """启发式分类：返回 (类型, 置信度, 匹配关键词)。

        优先级: env_noise(0.8) > element_gone(0.7) > load_delay(0.6) > 默认 dom_changed(0.4)。
        """
        lower = error_str.lower()
        for kws, fail_type, conf in (
            (self._ENV_NOISE_KEYWORDS, FailureType.ENV_NOISE, 0.8),
            (self._ELEMENT_GONE_KEYWORDS, FailureType.ELEMENT_GONE, 0.7),
            (self._LOAD_DELAY_KEYWORDS, FailureType.LOAD_DELAY, 0.6),
        ):
            matched = [kw for kw in kws if kw.lower() in lower]
            if matched:
                return fail_type, conf, matched
        return FailureType.DOM_CHANGED, 0.4, []

    def _classify_by_dom(
        self,
        dom_snapshot: str,
        old_selector: Optional[str],
    ) -> tuple[FailureType, float, dict[str, Any]]:
        """DOM 检查校正:
        - 元素存在于 DOM 但可能不可见 → load_delay
        - 元素不存在 → element_gone
        - selector 部分匹配(属性可能变更) → dom_changed
        无法判断(无 selector 或未提取到关键词)时置信度返回 0.0 以保留 error 分类。
        """
        if not old_selector:
            return FailureType.DOM_CHANGED, 0.0, {"skipped": "no_selector"}

        keywords = self._extract_selector_keywords(old_selector)
        if not keywords:
            return FailureType.DOM_CHANGED, 0.0, {"skipped": "no_keywords_extracted"}

        dom_lower = dom_snapshot.lower()
        found = [kw for kw in keywords if kw.lower() in dom_lower]
        base_evidence: dict[str, Any] = {
            "extracted_keywords": keywords,
            "selector_matched": found,
        }

        if len(found) == len(keywords):
            return FailureType.LOAD_DELAY, 0.75, base_evidence
        if not found:
            return FailureType.ELEMENT_GONE, 0.8, base_evidence
        return FailureType.DOM_CHANGED, 0.7, {**base_evidence, "partial_match": True}

    @staticmethod
    def _extract_selector_keywords(selector: str) -> list[str]:
        """从 css/xpath 选择器中提取 id/class/name 关键词用于 DOM 搜索。

        支持格式:
            - css: #id / .class
            - xpath: @id='x' / @class='x' / @name='x'（含 xpath= 前缀）
        """
        clean = selector.strip()
        if clean.lower().startswith("xpath="):
            clean = clean[len("xpath="):]

        tokens: list[str] = []
        tokens.extend(re.findall(r"id\s*=\s*['\"]([^'\"]+)['\"]", clean))
        tokens.extend(re.findall(r"class\s*=\s*['\"]([^'\"]+)['\"]", clean))
        tokens.extend(re.findall(r"name\s*=\s*['\"]([^'\"]+)['\"]", clean))
        tokens.extend(re.findall(r"#([\w-]+)", clean))
        tokens.extend(re.findall(r"\.([\w-]+)", clean))

        seen: set[str] = set()
        unique: list[str] = []
        for tk in tokens:
            if tk and tk not in seen:
                seen.add(tk)
                unique.append(tk)
        return unique


__all__ = ["FailureAnalyzer"]
