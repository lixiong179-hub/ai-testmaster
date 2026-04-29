import requests
import json
import re
import time
from typing import Dict, Any, Optional, List
from loguru import logger

from app.utils.ai_client_core import (
    AIClientBase,
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
    _detect_ai_error,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)


class AITestCaseMixin:
    def analyze_requirements(self, content: str) -> List[Dict[str, Any]]:
        cache_key = self._get_cache_key("analyze_requirements", content)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
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
            "max_tokens": 2000
        }
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI分析需求 - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, timeout=60)
                response.raise_for_status()
                result = response.json()
                resp_content = result["choices"][0]["message"]["content"]
                test_points = None
                try:
                    parsed = json.loads(resp_content)
                    if isinstance(parsed, list):
                        test_points = parsed
                except json.JSONDecodeError:
                    json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', resp_content)
                    if json_match:
                        try:
                            test_points = json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            pass
                if test_points is not None:
                    logger.info("AI分析需求成功")
                    self._set_to_cache(cache_key, test_points)
                    return test_points
                logger.warning("AI返回的内容不是有效的JSON格式")
                return []
            except requests.RequestException as e:
                logger.error(f"AI分析需求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    logger.error(error.message)
                    raise error
            except AIServiceError:
                raise
            except Exception as e:
                logger.error(f"AI分析需求失败: {str(e)}")
                raise AIServiceError(f"AI分析需求失败: {str(e)}")

    def generate_test_case(self, test_point: Dict[str, Any]) -> Dict[str, Any]:
        cache_key = self._get_cache_key("generate_test_case", test_point)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        module = test_point['module']
        function = test_point['function']
        point = test_point['point']
        priority = test_point['priority']
        prompt = f"""你是一名专业的测试工程师，请根据以下测试点生成可执行的测试用例：

模块：{module}
功能：{function}
测试点：{point}
优先级：{priority}（1高/2中/3低）

请按照以下格式生成测试用例：
1. 用例标题
2. 前置条件
3. 可执行步骤
4. 预期结果
5. 用例类型（ui_automation/manual/api_automation/performance/security）

请以JSON格式输出，结构如下：
{{
  "title": "用例标题",
  "precondition": "前置条件",
  "steps": [
    {{
      "step": 1,
      "action": "业务操作描述",
      "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
      "input_value": "输入值（仅input类型有值，其他为空字符串）",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_results": ["步骤1的预期验证条件", "步骤2的预期验证条件"],
  "case_type": "ui_automation/manual/api_automation/performance/security",
  "test_category": "与case_type保持一致"
}}

重要要求：
1. 只输出JSON格式内容，不要添加任何其他文字
2. 确保JSON格式正确，可直接被解析
3. 步骤要详细、可执行，参数要明确
4. action_type必须是以下枚举之一：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress
5. expected_results中每条必须是验证条件，不包含输入值
"""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI生成测试用例 - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                resp_content = result["choices"][0]["message"]["content"]
                generated_case = self._parse_generate_response(resp_content)
                if generated_case:
                    logger.info("AI生成测试用例成功")
                    self._set_to_cache(cache_key, generated_case)
                    return generated_case
                raise AIResponseParseError()
            except requests.RequestException as e:
                logger.error(f"AI生成测试用例失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    logger.error(error.message)
                    raise error
            except AIServiceError:
                raise
            except json.JSONDecodeError as e:
                logger.error(f"AI返回内容解析失败: {str(e)}")
                raise AIResponseParseError()
            except Exception as e:
                logger.error(f"AI生成测试用例失败: {str(e)}")
                raise AIServiceError(f"AI生成测试用例失败: {str(e)}")

    def _parse_generate_response(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            generated_case = json.loads(content)
            if isinstance(generated_case, dict):
                return self._validate_and_normalize_case(generated_case)
        except json.JSONDecodeError:
            pass
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                generated_case = json.loads(json_match.group(0))
                return self._validate_and_normalize_case(generated_case)
            except (json.JSONDecodeError, Exception):
                logger.warning("提取的JSON格式错误")
                raise AIResponseParseError()
        logger.warning("AI返回的内容不是有效的JSON格式")
        raise AIResponseParseError()

    def _validate_and_normalize_case(self, generated_case: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = ['title', 'precondition', 'steps']
        missing_fields = [f for f in required_fields if f not in generated_case]
        if missing_fields:
            logger.warning(f"AI返回的JSON缺少必要字段: {missing_fields}")
            raise AIResponseFormatError(f"AI响应缺少必要字段: {', '.join(missing_fields)}")
        if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
            generated_case = normalize_new_format(generated_case)
            logger.info("检测到新格式(expected_results分离)，已标准化")
        elif 'steps' in generated_case:
            generated_case = normalize_old_format(generated_case)
            logger.info("检测到旧格式，已标准化为P0/P2/P3优先级")
        return generated_case
