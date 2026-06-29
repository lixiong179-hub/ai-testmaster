"""网址驱动快速测试 - 页面结构驱动用例生成。

基于站点探索产出的真实 DOM 元素，自动推导测试点并调用 DeepSeek 生成可执行
用例，禁止编造不存在的元素；AI 失败时降级为仅生成登录用例，保证流程不阻断。

设计要点：
- 复用 app/ai/ 的 AIClient（OpenAIClient + FallbackAIClient），不新造调用入口；
- 复用已落地 TestCase.element_verified_ratio 字段做元素锚定校验，新增
  grounding_source="dom_snapshot" 标识锚定来源；
- 单文件 ≤350 行：Prompt 构建/锚定校验/测试点推导分别拆 _prompt_mixin /
  _validation_mixin / _test_point_mixin，主类聚焦编排与持久化；
- AI 调用/JSON 解析/单测试点失败均异常捕获降级，不阻断整体生成；
- 复用 CaseNumberService 生成 case_no，参数化查询防注入。
"""
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.client import AIClient, AIResponse
from app.core.config import settings
from app.core.constants import normalize_priority
from app.models.test_case import TestCase
from app.services.case_number_service import CaseNumberService
from app.services.url_driven._prompt_mixin import PromptMixin
from app.services.url_driven._test_point_mixin import TestPointMixin
from app.services.url_driven._validation_mixin import ValidationMixin
from app.services.url_driven.site_explorer import PageSnapshot, SiteMap
from app.utils.ai_client_parser import parse_ai_json_response

# 元素锚定来源标识：本生成器产出的用例均基于真实 DOM 快照
GROUNDING_SOURCE_DOM_SNAPSHOT = "dom_snapshot"
# AI 生成用例的默认类型（Web UI 自动化）
_DEFAULT_CASE_TYPE = "ui_automation"
# 合法 action_type 白名单，AI 给出的非白名单值降级为 navigate
_VALID_ACTION_TYPES = frozenset({"click", "input", "navigate", "verify"})


class AutoCaseGenerator(TestPointMixin, PromptMixin, ValidationMixin):
    """页面结构驱动用例生成器。

    输入 SiteMap，推导测试点 → 调用 DeepSeek 生成用例 → 元素锚定校验 →
    持久化 TestCase。AI 失败时降级为仅生成登录用例，保证流程不阻断。

    依赖注入：
    - ai_client: AIClient 实例（推荐 FallbackAIClient 包装主备模型），None 时
      由 create_ai_client 构造默认主备切换客户端，支持测试注入替身。
    """

    def __init__(self, ai_client: Optional[AIClient] = None) -> None:
        self._ai_client: Optional[AIClient] = ai_client

    def generate(
        self,
        site_map: SiteMap,
        project_id: int,
        description: Optional[str],
        user_id: int,
        session: Session,
    ) -> List[TestCase]:
        """基于 SiteMap 生成并持久化用例，返回已入库的 TestCase 列表。

        编排链路：推导测试点 → 逐点 AI 生成 → 元素锚定校验 → 全失败则降级
        登录用例 → 持久化。任一测试点 AI 失败仅跳过该点，不阻断其他点；
        全部失败时降级为仅生成登录用例（spec Scenario：AI 失败降级）。

        Args:
            site_map: 站点探索产物，提供真实页面元素清单。
            project_id: 关联项目 ID，用例归属与 case_no 生成依据。
            description: 用户自然语言描述，聚焦测试范围，None 表示无聚焦。
            user_id: 触发生成的用户 ID（项目所有者），用于审计日志上下文。
            session: SQLAlchemy 会话，由调用方管理事务生命周期。

        Returns:
            List[TestCase]: 已持久化的用例列表；无可用页面时返回空列表。
        """
        if not site_map or not site_map.pages:
            logger.warning(f"SiteMap 无页面快照，跳过用例生成: project_id={project_id}")
            return []

        test_points = self._derive_test_points(site_map)
        if not test_points:
            logger.info(f"未识别到核心入口测试点，降级为仅生成登录用例: project_id={project_id}")
            test_points = self._fallback_login_test_points(site_map)

        case_dicts: List[Dict[str, Any]] = []
        for test_point in test_points:
            page_snapshot = test_point.get("page_snapshot")
            if not isinstance(page_snapshot, PageSnapshot):
                continue
            cases = self._generate_for_test_point(test_point, page_snapshot, description)
            for case in cases:
                case["element_verified_ratio"] = self._validate_elements(case, page_snapshot)
                case["module"] = test_point.get("test_point_type", "url_quick_test")
            case_dicts.extend(cases)

        if not case_dicts:
            logger.warning(
                f"AI 生成全部失败，降级为仅生成登录用例: project_id={project_id} user_id={user_id}"
            )
            case_dicts = self._fallback_login_cases(site_map)

        if not case_dicts:
            logger.warning(f"降级后仍无用例可生成: project_id={project_id}")
            return []

        return self._persist_cases(case_dicts, project_id, session)

    def _generate_for_test_point(
        self,
        test_point: Dict[str, Any],
        page_snapshot: PageSnapshot,
        description: Optional[str],
    ) -> List[Dict[str, Any]]:
        """构建 Prompt → 调用 AI → 解析用例字典列表，失败返回空列表。"""
        prompt = self._build_prompt(test_point, page_snapshot, description)
        raw_content = self._call_ai(prompt)
        if not raw_content:
            return []
        return self._parse_cases(raw_content)

    def _call_ai(self, prompt: str) -> Optional[str]:
        """调用 AIClient 生成用例文本，异常或空响应返回 None 触发上层降级。

        复用 FallbackAIClient 的主备切换能力（主模型失败达阈值自动切备用），
        complete 抛出的任何异常（超时/额度/格式/不可用）均吞掉返回 None，
        由 generate 主流程决定是否降级登录用例。

        max_tokens 使用 settings.AI_MAX_TOKENS（默认 4096）而非硬编码 2048：
        DeepSeek v4-flash 等推理模型会先消耗 reasoning_tokens 再产出 content，
        2048 不足以同时容纳推理与用例 JSON 输出，导致 content 为空。
        """
        client = self._get_ai_client()
        try:
            response: AIResponse = client.complete(
                prompt,
                system="你是 Web 自动化测试用例生成助手，严格基于真实元素生成可执行用例。",
                temperature=0.3,
                max_tokens=settings.AI_MAX_TOKENS,
                metadata={"step_name": "url_driven_case_generation"},
            )
            content = (response.content or "").strip()
            if not content:
                logger.warning("AI 返回空内容，降级处理")
                return None
            return content
        except Exception as e:
            logger.warning(f"AI 调用失败（含 Fallback 后仍失败），降级处理: {e}")
            return None

    def _get_ai_client(self) -> AIClient:
        """懒加载默认 AIClient（主备切换），支持测试注入替换。"""
        if self._ai_client is None:
            from app.api.v1.endpoints.pipeline_resume import create_ai_client
            self._ai_client = create_ai_client()
        return self._ai_client

    def _parse_cases(self, raw_content: str) -> List[Dict[str, Any]]:
        """解析 AI 返回 JSON 为用例字典列表，解析失败返回空列表。

        复用 parse_ai_json_response 的 4 级容错解析（直接/修复/清洗/代码块提取），
        容忍 AI 偶尔包裹 markdown 代码块或带尾逗号的输出。
        """
        parsed = parse_ai_json_response(raw_content)
        if parsed is None:
            logger.warning("AI 用例 JSON 解析失败，降级处理")
            return []
        if isinstance(parsed, dict):
            cases = parsed.get("cases")
        elif isinstance(parsed, list):
            cases = parsed
        else:
            cases = None
        if not isinstance(cases, list):
            logger.warning("AI 用例 JSON 缺少 cases 数组，降级处理")
            return []
        return [case for case in cases if isinstance(case, dict) and case.get("title")]

    def _fallback_login_cases(self, site_map: SiteMap) -> List[Dict[str, Any]]:
        """AI 全失败降级：基于检测到的登录元素硬编码登录用例。

        从登录页 elements 提取 textbox（用户名/密码）与 button（登录按钮），
        生成一条正向登录用例，target_element 全部来自真实元素保证锚定 ratio 高。
        无登录页或无可用元素时返回空列表（无可降级路径）。
        """
        login_page = next((p for p in site_map.pages if p.is_login_page), None)
        if login_page is None:
            return []
        textboxes = [e for e in login_page.elements if e.get("role") == "textbox"]
        buttons = [e for e in login_page.elements if e.get("role") == "button"]
        if not textboxes or not buttons:
            return []
        steps: List[Dict[str, Any]] = []
        if len(textboxes) >= 1:
            steps.append({
                "action": f"在 {textboxes[0].get('name', '用户名')} 输入有效用户名",
                "action_type": "input", "target_element": textboxes[0].get("name", ""),
            })
        if len(textboxes) >= 2:
            steps.append({
                "action": f"在 {textboxes[1].get('name', '密码')} 输入有效密码",
                "action_type": "input", "target_element": textboxes[1].get("name", ""),
            })
        steps.append({
            "action": "点击登录按钮提交登录",
            "action_type": "click", "target_element": buttons[0].get("name", ""),
        })
        return [{
            "title": "用户使用有效凭据登录成功",
            "case_category": "positive",
            "precondition": "已注册有效账号且处于未登录状态",
            "priority": 1,
            "steps": steps,
            "expected_result": "登录成功并跳转到登录后页面",
            "element_verified_ratio": 1.0,
            "module": "login",
        }]

    def _persist_cases(
        self, case_dicts: List[Dict[str, Any]], project_id: int, session: Session
    ) -> List[TestCase]:
        """批量生成 case_no 并持久化用例，写入 grounding_source 与锚定 ratio。"""
        case_nos = CaseNumberService.generate_batch(project_id, len(case_dicts), session)
        persisted: List[TestCase] = []
        for case_data, case_no in zip(case_dicts, case_nos):
            test_case = self._build_test_case(case_data, project_id, case_no)
            session.add(test_case)
            persisted.append(test_case)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"用例持久化失败，已回滚: project_id={project_id} err={e}")
            raise
        for test_case in persisted:
            session.refresh(test_case)
        logger.info(
            f"页面驱动用例生成完成: project_id={project_id} count={len(persisted)}"
        )
        return persisted

    def _build_test_case(
        self, case_data: Dict[str, Any], project_id: int, case_no: str
    ) -> TestCase:
        """从用例字典构造 TestCase，统一字段规范化与锚定来源标记。"""
        steps_json = self._normalize_steps(case_data.get("steps"))
        return TestCase(
            project_id=project_id,
            case_no=case_no,
            module=str(case_data.get("module", "url_quick_test")),
            title=str(case_data.get("title", "(untitled)")).strip() or "(untitled)",
            precondition=str(case_data.get("precondition", "无") or "无"),
            steps_json=steps_json,
            expected_result=str(case_data.get("expected_result", "")),
            priority=normalize_priority(case_data.get("priority", 2)),
            case_type=_DEFAULT_CASE_TYPE,
            test_category=_DEFAULT_CASE_TYPE,
            case_category=str(case_data.get("case_category", "") or "").strip() or None,
            generate_status=1,
            element_verified_ratio=self._sanitize_ratio(case_data.get("element_verified_ratio")),
            grounding_source=GROUNDING_SOURCE_DOM_SNAPSHOT,
            lifecycle_status="draft",
        )

    @staticmethod
    def _normalize_steps(steps: Any) -> List[Dict[str, Any]]:
        """规范化 AI 步骤为 steps_json 格式，action_type 非白名单降级为 navigate。"""
        if not isinstance(steps, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            action_type = str(step.get("action_type", "") or "").strip().lower()
            if action_type not in _VALID_ACTION_TYPES:
                action_type = "navigate"
            normalized.append({
                "step": str(idx),
                "description": str(step.get("description", "") or ""),
                "action": str(step.get("action", "执行") or "执行"),
                "expected_result": str(step.get("expected_result", "") or ""),
                "param": str(step.get("param", "") or ""),
                "action_type": action_type,
                "input_value": str(step.get("input_value", "") or ""),
                "target_element": str(step.get("target_element", "") or ""),
                "test_data": step.get("test_data", []) if isinstance(step.get("test_data"), list) else [],
            })
        return normalized

    @staticmethod
    def _sanitize_ratio(value: Any) -> Optional[float]:
        """校验 ratio 在 [0.0, 1.0]，非法值返回 None。"""
        if value is None:
            return None
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            return None
        if ratio < 0.0 or ratio > 1.0:
            return None
        return ratio
