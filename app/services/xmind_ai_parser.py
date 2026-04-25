"""XMind AI 增强解析器。

使用 LLM 将 XMind 路径批量转换为结构化测试用例。
对每批路径调用一次 AI，返回与 XmindCaseParser 兼容的 dict 列表。

依赖:
    - openai: OpenAI 兼容 SDK（DeepSeek）
    - app.core.config.settings: API 密钥与模型配置
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import OpenAI

from app.core.config import settings
from app.utils.ai_client_core import AITimeoutError, _detect_ai_error

BATCH_SIZE = 10
DEFAULT_AI_TIMEOUT = 60

SYSTEM_PROMPT = """\
你是一名资深测试工程师，擅长将思维导图路径转换为结构化测试用例。

输入格式：每行一条路径，节点之间用 " → " 分隔。
第一个节点是模块名，后续节点组成测试场景。

你的任务：
1. 识别 **前置条件** —— 描述系统状态、数据准备等（如"有教材内容""已选汉字""有记录""无网络时"）
2. 识别 **操作步骤** —— 用户执行的动作（如"点击XX""选择XX""输入XX"）
3. 识别 **中间预期** —— 系统对某步骤的响应（如"弹出提示框""界面显示XX"）
4. 识别 **最终预期结果** —— 通常是路径最后一个节点描述的结果
5. 生成简洁的 **用例标题**（≤50字）

输出 JSON 数组，每个元素对应一条输入路径，字段：
{
  "module": "模块名",
  "precondition": "前置条件1\\n前置条件2",
  "title": "简洁的用例标题",
  "steps": [
    {"action": "操作描述", "expected_result": "该步预期（可为空）"}
  ],
  "expected_result": "最终预期结果",
  "priority": 2
}

规则：
- steps 中每个 action 必须是用户主动操作；系统响应放在上一步的 expected_result 中
- priority 默认为 2（中），如路径中出现"核心""必须""关键"等设为 1（高），出现"可选""低优"设为 3（低）
- precondition 不能包含操作步骤或预期结果
- 如果路径只有状态描述没有操作步骤，action 设为 "验证场景"
- 输出格式必须是 JSON 对象：{"cases": [...]}
- 只输出 JSON，不要任何解释文字
"""


def _build_user_prompt(paths: List[List[str]]) -> str:
    """将多条路径拼成用户提示。"""
    lines = []
    for i, path in enumerate(paths, 1):
        lines.append(f"{i}. {' → '.join(path)}")
    return "\n".join(lines)


def _parse_ai_response(text: str, expected_count: int) -> Optional[List[Dict[str, Any]]]:
    """从 AI 响应中提取 JSON 数组。"""
    text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"[{\[].*[}\]]", text, re.DOTALL)
        if not json_match:
            logger.warning("AI 响应中未找到 JSON")
            return None
        try:
            parsed = json.loads(json_match.group())
        except json.JSONDecodeError as exc:
            logger.warning(f"AI 响应 JSON 解析失败: {exc}")
            return None

    if isinstance(parsed, dict):
        for key in ("cases", "items", "data", "results"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break

    if not isinstance(parsed, list):
        logger.warning("AI 响应无法提取为数组")
        return None

    if len(parsed) != expected_count:
        logger.warning(
            f"AI 返回 {len(parsed)} 条，期望 {expected_count} 条"
        )

    return parsed


def _normalize_case(raw: Dict[str, Any], fallback_module: str) -> Dict[str, Any]:
    """将 AI 返回的单条数据规范化为 XmindCaseParser 兼容格式。"""
    module = raw.get("module", fallback_module) or fallback_module
    precondition = raw.get("precondition", "")
    title = raw.get("title", "")[:255]
    expected_result = raw.get("expected_result", "")
    priority = raw.get("priority", 2)
    if priority not in (1, 2, 3):
        priority = 2

    raw_steps = raw.get("steps", [])
    steps: List[Dict[str, Any]] = []
    for idx, step in enumerate(raw_steps, 1):
        if isinstance(step, dict):
            steps.append({
                "step": idx,
                "action": step.get("action", ""),
                "expected_result": step.get("expected_result", ""),
                "param": "",
            })

    if not steps and expected_result:
        steps = [{
            "step": 1,
            "action": f"验证场景：{expected_result}",
            "expected_result": expected_result,
            "param": "",
        }]

    actions = [s["action"] for s in steps if s["action"]]

    function_name = ""
    if precondition:
        first_line = precondition.split("\n")[0].strip()
        function_name = first_line[:200]

    point = actions[0][:500] if actions else title[:500]

    return {
        "module": module[:100],
        "function": function_name,
        "title": title,
        "point": point,
        "precondition": precondition,
        "steps": steps,
        "expected_result": expected_result,
        "priority": priority,
        "case_type": "manual",
        "source_depth": 0,
        "action_count": len(actions),
        "expected_count": 1 if expected_result else 0,
        "condition_count": len(precondition.split("\n")) if precondition else 0,
        "ignored_count": 0,
    }


class XmindAIParser:
    """使用 LLM 将 XMind 路径批量转换为测试用例。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = BATCH_SIZE,
        timeout: int = DEFAULT_AI_TIMEOUT,
    ) -> None:
        self._api_key = api_key or settings.DEEPSEEK_API_KEY
        self._base_url = base_url or "https://api.deepseek.com"
        self._model = model or settings.DEEPSEEK_MODEL
        self._batch_size = batch_size
        self._timeout = timeout
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def parse_paths(
        self,
        paths: List[List[str]],
    ) -> List[Dict[str, Any]]:
        """将多条路径通过 AI 转换为测试用例。

        Args:
            paths: 每条路径是字符串列表，如 ["字词听写", "有教材内容", "点击听写记录", ...]

        Returns:
            与 XmindCaseParser 兼容的 dict 列表。
        """
        if not paths:
            return []

        all_results: List[Dict[str, Any]] = []

        for batch_start in range(0, len(paths), self._batch_size):
            batch = paths[batch_start : batch_start + self._batch_size]
            batch_results = self._call_ai(batch)

            if batch_results is not None and len(batch_results) == len(batch):
                for raw, path in zip(batch_results, batch):
                    fallback_module = path[0] if path else ""
                    all_results.append(_normalize_case(raw, fallback_module))
            else:
                logger.warning(
                    f"AI 批次 {batch_start}-{batch_start + len(batch)} 失败，跳过"
                )

        logger.info(f"AI 增强解析完成，成功 {len(all_results)}/{len(paths)} 条")
        return all_results

    def _call_ai(self, batch: List[List[str]]) -> Optional[List[Dict[str, Any]]]:
        """调用 LLM 处理一个批次。"""
        user_prompt = _build_user_prompt(batch)
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            logger.debug(f"AI 响应长度: {len(content)} 字符")
            return _parse_ai_response(content, len(batch))
        except Exception as exc:
            ai_error = _detect_ai_error(exc)
            if isinstance(ai_error, AITimeoutError):
                logger.warning(f"AI 调用超时（{self._timeout}秒）: {exc}")
            else:
                logger.error(f"AI 调用失败: {exc}")
            return None
