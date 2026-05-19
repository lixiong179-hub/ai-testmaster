import json
import re
from typing import Dict, Any, Optional, List
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


class _AnalyzeStreamMixin:

    async def analyze_requirements_stream(self, content: str):
        logger.info(f"开始AI分析需求（流式），输入内容长度: {len(content)} 字符")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt_template = (
            "你是一名资深测试工程师，请根据以下需求内容分析并提取结构化测试点：\n\n"
            "需求内容：\n{REQ_CONTENT_PLACEHOLDER}\n\n"
            "## 测试点提取规则\n"
            "1. 按模块分组，每个模块下的测试点要逻辑清晰、不重复\n"
            "2. 每个测试点必须包含：module（模块名称）、function（功能名称）、point（测试点描述）、priority（1高/2中/3低）\n"
            "3. **禁止重复**：同一模块下不允许出现测试价值重复的测试点\n"
            "4. **必须有验证目标**：测试点必须说明要验证什么结果\n"
            "5. **覆盖异常和边界**：必须覆盖无网络、无数据、权限异常、重复提交、边界值等场景\n"
            "6. **优先级合理**：核心流程设为1（高）；一般验证设为2（中）；边缘场景设为3（低）\n\n"
            "请严格以JSON格式输出：\n[\n  {\n"
            '    "module": "模块名称",\n'
            '    "function": "功能名称",\n'
            '    "point": "测试点描述",\n'
            '    "priority": 1\n  }\n]\n'
        )
        prompt = prompt_template.replace("{REQ_CONTENT_PLACEHOLDER}", content)
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": True
        }
        full_content = ""
        import requests
        import time
        from app.core.constants import TimeoutConfig
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI分析需求（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=TimeoutConfig.AI_API)
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
