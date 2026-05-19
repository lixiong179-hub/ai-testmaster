import ipaddress
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from loguru import logger


class _ApiSetupHelpersMixin:

    def _extract_api_vars(
        self,
        response: httpx.Response,
        extract_config: Dict[str, str],
    ) -> None:
        try:
            response_data = response.json()
        except Exception:
            return

        for var_name, json_path in extract_config.items():
            value = self._resolve_json_path(response_data, json_path)
            if value is not None:
                self._api_extracted_vars[var_name] = value
                logger.debug(f"提取变量: {var_name} = {value}")

    def _resolve_json_path(self, data: Any, path: str) -> Any:
        if not path.startswith("$"):
            return data.get(path) if isinstance(data, dict) else None

        parts = path.split(".")
        current = data
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def _substitute_api_vars(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and "{{" in value and "}}" in value:
                var_name = value.replace("{{", "").replace("}}", "").strip()
                if var_name in self._api_extracted_vars:
                    result[key] = self._api_extracted_vars[var_name]
                else:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self._substitute_api_vars(value)
            else:
                result[key] = value
        return result

    def _get_base_url(self) -> Optional[str]:
        if hasattr(self, '_project_base_url') and self._project_base_url:
            return self._project_base_url

        if self.browser and getattr(self.browser, '_page', None):
            current_url = self.browser._page.url
            if current_url and current_url.startswith(("http://", "https://")):
                parts = current_url.split("/")
                base = "/".join(parts[:3])
                self._project_base_url = base
                return base

        return None

    async def _get_auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}

        if not self.browser or not getattr(self.browser, '_context', None):
            return headers

        try:
            context = self.browser._context
            cookies = await context.cookies()
            auth_token = None
            for cookie in cookies:
                name = cookie.get("name", "")
                if name in ("token", "access_token", "auth_token", "jwt", "session_id"):
                    auth_token = cookie.get("value", "")
                    break

            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
        except Exception:
            pass

        return headers

    def _build_setup_api_calls_from_main_steps(
        self,
        main_steps: List[Dict[str, Any]],
        anchor_step: int,
    ) -> List[Dict[str, Any]]:
        api_calls = []
        for step in main_steps:
            step_num = step.get("step") or step.get("step_number")
            if step_num is None:
                continue
            try:
                num = int(step_num)
            except (ValueError, TypeError):
                continue
            if num > anchor_step:
                break

            action = step.get("action", "") or step.get("description", "")
            action_type = (step.get("action_type") or "").lower()

            if action_type == "navigate":
                url = step.get("input_value", "") or action
                if url and url.startswith("/"):
                    api_calls.append({
                        "method": "GET",
                        "url": url,
                        "assert": {"status_code": 200},
                    })

        return api_calls

    async def _is_safe_url(self, url: str) -> bool:
        if not url:
            return False

        if url.startswith("/"):
            return True

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                return False

            if hostname in ("localhost", "localhost.localdomain"):
                return False

            import socket
            import asyncio
            loop = asyncio.get_event_loop()
            resolved_ip = await loop.run_in_executor(
                None, socket.gethostbyname, hostname
            )
            ip = ipaddress.ip_address(resolved_ip)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False

        except (socket.gaierror, ValueError, TypeError):
            return False

        return True
