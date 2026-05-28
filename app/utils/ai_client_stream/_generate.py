import json
import re
import time
from typing import Dict, Any
from loguru import logger

import requests

from app.utils.ai_client_core import (
    AIServiceError,
    _detect_ai_error,
)
from app.utils.ai_client_parser import parse_ai_json_response


class _GenerateStreamMixin:

    async def generate_test_case_stream(self, test_point: Dict[str, Any]):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt = f"""你是一名专业的测试工程师，请根据以下测试点生成可执行的测试用例：

模块：{test_point.get('module', '未知模块')}
功能：{test_point.get('function', '')}
测试点：{test_point.get('point', '')}
优先级：{test_point.get('priority', 2)}（1高/2中/3低）

请按照以下格式生成测试用例：
1. 用例标题（必须具体明确，格式：场景/条件+操作+验证重点）
2. 前置条件
3. 可执行步骤
4. 预期结果
5. 用例类型

请以JSON格式输出，结构如下：
{{
  "title": "场景+操作+验证重点",
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
            "temperature": 0.3,
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
                    generated_case = parse_ai_json_response(full_content)
                    if generated_case is not None:
                        required_fields = ['title', 'precondition', 'steps', 'expected_result', 'case_type']
                        missing_fields = [f for f in required_fields if f not in generated_case]
                        if missing_fields:
                            yield {"progress": 100, "message": f"AI响应缺少必要字段: {', '.join(missing_fields)}", "status": "error", "error": True}
                            return
                        yield {"progress": 100, "message": "生成完成", "data": generated_case}
                        return
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
