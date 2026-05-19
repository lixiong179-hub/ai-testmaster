import json
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from app.models.test_case import TestCase
from app.services.test_execution_engine.api_setup_mixin._helpers import _ApiSetupHelpersMixin


class _ExecutorMixin(_ApiSetupHelpersMixin):

    _api_extracted_vars: Dict[str, Any]

    def _init_api_setup_state(self) -> None:
        self._api_extracted_vars: Dict[str, Any] = {}

    async def _execute_setup_api_calls(
        self, case: TestCase
    ) -> Tuple[bool, str]:
        setup_api_raw = getattr(case, 'setup_api_calls', None)
        if not setup_api_raw:
            return False, "无API前置准备"

        try:
            if isinstance(setup_api_raw, str):
                api_calls = json.loads(setup_api_raw)
            elif isinstance(setup_api_raw, list):
                api_calls = setup_api_raw
            else:
                logger.warning(f"setup_api_calls 类型异常: {type(setup_api_raw)}")
                return False, "格式异常"
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"setup_api_calls 解析失败: {e}")
            return False, "JSON解析失败"

        if not api_calls:
            return False, "API列表为空"

        base_url = self._get_base_url()
        if not base_url:
            logger.warning("无法获取API基础URL，跳过API前置准备")
            return False, "无基础URL"

        auth_headers = await self._get_auth_headers()

        async with httpx.AsyncClient(
            base_url=base_url,
            headers=auth_headers,
            timeout=30.0,
            verify=False,
        ) as client:
            for i, api_call in enumerate(api_calls):
                success = await self._execute_single_api_call(
                    client, api_call, i + 1
                )
                if not success:
                    return False, f"API调用{i + 1}失败"

        logger.info(
            f"API前置准备完成: 用例 {case.case_no}, "
            f"执行 {len(api_calls)} 个API调用, "
            f"提取变量: {list(self._api_extracted_vars.keys())}"
        )
        return True, "Level0-API前置准备"

    async def _execute_single_api_call(
        self,
        client: httpx.AsyncClient,
        api_call: Dict[str, Any],
        call_index: int,
    ) -> bool:
        method = (api_call.get("method") or "GET").upper()
        url = api_call.get("url", "")
        body = api_call.get("body") or api_call.get("data") or api_call.get("json")
        headers = api_call.get("headers", {})
        extract = api_call.get("extract", {})
        assert_config = api_call.get("assert") or api_call.get("expected", {})

        if not await self._is_safe_url(url):
            logger.warning(f"API调用{call_index}URL不安全(内网/保留地址): {url}")
            return False

        if body and isinstance(body, dict):
            body = self._substitute_api_vars(body)

        try:
            request_kwargs: Dict[str, Any] = {}
            if body and method in ("POST", "PUT", "PATCH"):
                request_kwargs["json"] = body
            if headers:
                request_kwargs["headers"] = headers

            response = await client.request(method, url, **request_kwargs)

            if assert_config:
                expected_status = assert_config.get("status_code")
                if expected_status and response.status_code != expected_status:
                    logger.warning(
                        f"API调用{call_index}断言失败: "
                        f"期望状态码 {expected_status}, "
                        f"实际 {response.status_code}, "
                        f"响应: {response.text[:200]}"
                    )
                    return False

            if extract:
                self._extract_api_vars(response, extract)

            logger.info(
                f"API调用{call_index}成功: {method} {url} -> {response.status_code}"
            )
            return True

        except httpx.TimeoutException:
            logger.warning(f"API调用{call_index}超时: {method} {url}")
            return False
        except httpx.ConnectError as e:
            logger.warning(f"API调用{call_index}连接失败: {e}")
            return False
        except Exception as e:
            logger.warning(f"API调用{call_index}异常: {e}")
            return False
