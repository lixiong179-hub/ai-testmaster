"""
AI流式响应处理模块

本模块实现AI服务的SSE（Server-Sent Events）流式响应处理，是AI客户端分层架构中的"流式层"。
流式响应的核心价值是实时向客户端推送处理进度，避免长时间等待无反馈。

核心类：
    - AIStreamMixin: 流式处理Mixin，提供两个异步生成器方法

核心方法：
    - analyze_requirements_stream: 流式分析需求，实时推送分析进度
    - generate_test_case_stream: 流式生成测试用例，实时推送生成进度

流式响应处理流程：
    1. 构建请求Payload（stream=True）
    2. 通过requests.post发送流式请求
    3. 逐chunk解析SSE数据（data: {...}格式）
    4. 累积完整内容并计算进度百分比
    5. 流式接收完成后，解析完整内容为结构化数据
    6. 解析失败时降级到fallback提取策略

错误处理策略：
    - 网络错误：自动重试（max_retries次），每次间隔retry_delay秒
    - AI服务错误：通过_detect_ai_error映射为业务异常
    - 解析错误：降级到fix_common_json_issues和extract_json_objects_fallback

依赖：
    - requests: HTTP请求库（同步流式）
    - app.utils.ai_client_core: 异常体系和错误检测
    - app.utils.ai_client_parser: JSON修复和兜底提取
"""
import requests
import json
import re
import time
from typing import Dict, Any, Optional, AsyncGenerator, List
from loguru import logger

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    _detect_ai_error,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    extract_json_objects_fallback,
)


class AIStreamMixin:
    """AI流式响应处理Mixin

    为AIClient提供SSE流式响应处理能力。通过Mixin模式组合到AIClient中，
    避免流式处理逻辑与核心业务逻辑耦合。

    该Mixin依赖AIClientBase提供的以下属性：
    - self.api_url: AI API端点地址
    - self.api_key: API密钥
    - self.model: 模型名称
    - self.max_retries: 最大重试次数
    - self.retry_delay: 重试间隔秒数
    """

    async def analyze_requirements_stream(self, content: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式分析需求文档，提取结构化测试点

        向AI发送需求分析请求，通过SSE流式接收响应，实时推送进度。
        每次yield一个字典，包含progress（0-100）、message和可选的data字段。

        Args:
            content: 需求文档内容文本

        Yields:
            Dict[str, Any]: 进度消息字典
                - progress: 进度百分比（0-100）
                - message: 进度描述文本
                - data: 最终结果数据（仅progress=100时存在）
                - error: 错误标记（仅出错时存在）
                - status: 状态标记（"error"表示出错）
        """
        logger.info(f"开始AI分析需求（流式），输入内容长度: {len(content)} 字符")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt_template = (
            "你是一名专业的测试工程师，请根据以下需求内容分析并提取结构化测试点：\n\n"
            "需求内容：\n{REQ_CONTENT_PLACEHOLDER}\n\n"
            "请按照以下格式提取测试点：\n"
            "1. 按模块分组，每个模块下的测试点要逻辑清晰\n"
            "2. 每个测试点必须包含：\n"
            "   - module: 模块名称\n   - function: 功能名称\n"
            "   - point: 测试点描述\n   - priority: 优先级（1高/2中/3低）\n"
            "3. 测试点要求：具体明确、覆盖全面、逻辑独立、可执行\n\n"
            "请严格以JSON格式输出：\n[\n  {\n"
            '    "module": "用户管理",\n    "function": "用户注册",\n'
            '    "point": "验证用户使用有效邮箱和密码注册成功",\n'
            '    "priority": 1\n  }\n]\n\n'
            "重要要求：只输出JSON，确保格式正确，测试点详细具体，优先级合理，覆盖所有重要功能点\n"
        )
        prompt = prompt_template.replace("{REQ_CONTENT_PLACEHOLDER}", content)
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": True
        }
        full_content = ""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI分析需求（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=120)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        chunk_str = chunk.decode('utf-8')
                        lines = chunk_str.split('\n')
                        for line in lines:
                            if line.startswith('data: '):
                                data_part = line[6:]
                                if data_part == '[DONE]':
                                    break
                                try:
                                    chunk_data = json.loads(data_part)
                                    if 'choices' in chunk_data:
                                        delta = chunk_data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            full_content += delta['content']
                                            progress = min(int(len(full_content) / 20), 95)
                                            yield {"progress": progress, "message": "分析中..."}
                                except json.JSONDecodeError:
                                    pass
                logger.info(f"AI流式响应接收完成，内容长度: {len(full_content)} 字符")
                test_points = self._parse_stream_test_points(full_content)
                if test_points is not None:
                    yield {"progress": 100, "message": "分析完成", "data": test_points}
                    return
                raise AIResponseParseError()
            except requests.RequestException as e:
                logger.error(f"AI分析需求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    logger.error(error.message)
                    yield {"progress": 100, "message": error.message, "status": "error", "error": True}
                    return
            except AIServiceError as e:
                yield {"progress": 100, "message": e.message, "status": "error", "error": True}
                return
            except Exception as e:
                error_message = f"分析失败: {str(e)}"
                logger.error(error_message)
                yield {"progress": 100, "message": error_message, "status": "error", "error": True}
                return

    def _parse_stream_test_points(self, full_content: str) -> Optional[List[Dict[str, Any]]]:
        """解析流式响应的完整内容为测试点列表

        采用多级降级解析策略：
        1. 直接JSON解析
        2. 从Markdown代码块（```json...```）中提取后解析
        3. 正则匹配JSON数组后解析
        4. 上述均失败时，使用fix_common_json_issues修复后重试
        5. 最终降级到extract_json_objects_fallback兜底提取

        Args:
            full_content: 流式响应累积的完整文本内容

        Returns:
            Optional[List[Dict[str, Any]]]: 解析成功的测试点列表，全部失败返回None
        """
        try:
            test_points = json.loads(full_content)
            if isinstance(test_points, list):
                logger.info("AI分析需求（流式响应）成功")
                return test_points
        except json.JSONDecodeError:
            pass
        json_match = re.search(r'```(?:json)?\s*\n?(\[[\s\S]*?\])\s*\n?```', full_content)
        if json_match:
            json_str = json_match.group(1)
            try:
                test_points = json.loads(json_str)
                logger.info("AI分析需求（流式响应）成功 - 从markdown代码块提取")
                return test_points
            except json.JSONDecodeError:
                fixed_json = fix_common_json_issues(json_str)
                if fixed_json:
                    try:
                        test_points = json.loads(fixed_json)
                        logger.info("AI分析需求（流式响应）成功 - JSON已修复")
                        return test_points
                    except json.JSONDecodeError:
                        pass
        json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', full_content)
        if json_match:
            json_str = json_match.group(0)
            try:
                test_points = json.loads(json_str)
                logger.info("AI分析需求（流式响应）成功")
                return test_points
            except json.JSONDecodeError:
                fixed_json = fix_common_json_issues(json_str)
                if fixed_json:
                    try:
                        test_points = json.loads(fixed_json)
                        logger.info("AI分析需求（流式响应）成功 - JSON已修复")
                        return test_points
                    except json.JSONDecodeError:
                        pass
        logger.warning(f"AI返回的内容无法解析为JSON。内容长度: {len(full_content)}")
        logger.warning(f"内容前500字符: {full_content[:500]}")
        debug_file = "ai_response_debug.txt"
        try:
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(full_content)
            logger.info(f"完整AI响应已保存到: {debug_file}")
        except Exception as e:
            logger.warning(f"无法保存调试文件: {e}")
        test_points = extract_json_objects_fallback(full_content)
        if test_points:
            logger.info(f"使用fallback方法成功提取 {len(test_points)} 个测试点")
            return test_points
        return None

    async def generate_test_case_stream(self, test_point: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成单个测试用例

        根据给定的测试点，通过SSE流式请求AI生成完整的测试用例。
        生成完成后验证必要字段（title、precondition、steps、expected_result、case_type），
        缺少任何字段都会返回错误。

        Args:
            test_point: 测试点字典，包含module、function、point、priority字段

        Yields:
            Dict[str, Any]: 进度消息字典
                - progress: 进度百分比（0-100）
                - message: 进度描述文本
                - data: 生成的测试用例数据（仅成功时存在）
                - error: 错误标记（仅出错时存在）
                - status: 状态标记（"error"表示出错）
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt = f"""你是一名专业的测试工程师，请根据以下测试点生成可执行的测试用例：

模块：{test_point['module']}
功能：{test_point['function']}
测试点：{test_point['point']}
优先级：{test_point['priority']}（1高/2中/3低）

请按照以下格式生成测试用例：
1. 用例标题 2. 前置条件 3. 可执行步骤 4. 预期结果 5. 用例类型

请以JSON格式输出，结构如下：
{{
  "title": "用例标题",
  "precondition": "前置条件",
  "steps": [
    {{
      "step": 1,
      "action": "业务操作描述",
      "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
      "input_value": "输入值",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_results": ["步骤1的预期验证条件"],
  "case_type": "UI/API/功能",
  "test_category": "ui_automation/manual/api_automation"
}}

重要要求：只输出JSON，格式正确，步骤详细可执行，action_type使用枚举值
"""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500,
            "stream": True
        }
        full_content = ""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI生成测试用例（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=60)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        chunk_str = chunk.decode('utf-8')
                        lines = chunk_str.split('\n')
                        for line in lines:
                            if line.startswith('data: '):
                                data_part = line[6:]
                                if data_part == '[DONE]':
                                    break
                                try:
                                    chunk_data = json.loads(data_part)
                                    if 'choices' in chunk_data:
                                        delta = chunk_data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            full_content += delta['content']
                                            progress = min(int(len(full_content) / 15), 95)
                                            yield {"progress": progress, "message": "生成中..."}
                                except json.JSONDecodeError:
                                    pass
                try:
                    generated_case = json.loads(full_content)
                    if isinstance(generated_case, dict):
                        required_fields = ['title', 'precondition', 'steps', 'expected_result', 'case_type']
                        missing_fields = [f for f in required_fields if f not in generated_case]
                        if missing_fields:
                            yield {"progress": 100, "message": f"AI响应缺少必要字段: {', '.join(missing_fields)}", "status": "error", "error": True}
                            return
                        yield {"progress": 100, "message": "生成完成", "data": generated_case}
                        return
                except json.JSONDecodeError:
                    json_match = re.search(r'\{\s*"title"[\s\S]*\}', full_content)
                    if json_match:
                        try:
                            generated_case = json.loads(json_match.group(0))
                            required_fields = ['title', 'precondition', 'steps', 'expected_result', 'case_type']
                            missing_fields = [f for f in required_fields if f not in generated_case]
                            if missing_fields:
                                yield {"progress": 100, "message": f"AI响应缺少必要字段: {', '.join(missing_fields)}", "status": "error", "error": True}
                                return
                            yield {"progress": 100, "message": "生成完成", "data": generated_case}
                            return
                        except json.JSONDecodeError:
                            pass
                yield {"progress": 100, "message": "AI响应格式错误，无法解析", "status": "error", "error": True}
                return
            except requests.RequestException as e:
                logger.error(f"AI生成测试用例失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    yield {"progress": 100, "message": error.message, "status": "error", "error": True}
                    return
            except AIServiceError as e:
                yield {"progress": 100, "message": e.message, "status": "error", "error": True}
                return
            except Exception as e:
                error_message = f"生成失败: {str(e)}"
                logger.error(error_message)
                yield {"progress": 100, "message": error_message, "status": "error", "error": True}
                return
