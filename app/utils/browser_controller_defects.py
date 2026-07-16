import time
from typing import Dict, Any
from loguru import logger


class DefectCaptureMixin:
    # 内存泄漏检测阈值：连续增长步数
    _MEMORY_LEAK_STEP_THRESHOLD: int = 5
    # 内存泄漏检测阈值：连续增长总量（MB）
    _MEMORY_LEAK_GROWTH_THRESHOLD_MB: float = 10.0

    # ------------------------------------------------------------------
    # 缺陷捕获：监听器注册、证据收集/清除、内存监控
    # ------------------------------------------------------------------

    def _setup_defect_listeners(self) -> None:
        """在页面创建后注册浏览器缺陷监听器。

        注册四类监听：
        1. console - 仅收集 error 级别日志
        2. pageerror - 收集未捕获异常
        3. response - 收集 5xx 响应（排除预期 4xx）
        4. requestfailed - 收集请求失败
        """
        if self._defect_listeners_registered or not self._page:
            return

        try:
            self._page.on("console", self._on_console_message)
            self._page.on("pageerror", self._on_page_error)
            self._page.on("response", self._on_response)
            self._page.on("requestfailed", self._on_request_failed)
            self._page.on("request", self._on_request_started)
            self._defect_listeners_registered = True
            logger.info("浏览器缺陷监听器已注册")
        except Exception as e:
            logger.warning(f"注册浏览器缺陷监听器失败: {e}")

    def _on_console_message(self, msg: Any) -> None:
        """处理控制台消息，仅收集 error 级别日志。"""
        try:
            if msg.type == "error":
                self._console_errors.append({
                    "type": "console_error",
                    "message": msg.text,
                    "source": f"{msg.location.get('url', '')}:{msg.location.get('lineNumber', '')}" if hasattr(msg, 'location') and msg.location else "",
                })
        except Exception as e:
            logger.debug(f"处理控制台消息异常: {e}")

    def _on_page_error(self, error: Any) -> None:
        """处理页面未捕获异常。"""
        try:
            self._uncaught_exceptions.append({
                "type": "uncaught_exception",
                "message": str(error),
                "stack": getattr(error, 'stack', '') or '',
            })
        except Exception as e:
            logger.debug(f"处理页面异常事件异常: {e}")

    def _on_request_started(self, request: Any) -> None:
        """记录请求开始时间，用于计算响应耗时。"""
        try:
            self._request_start_times[request.url] = time.monotonic()
        except Exception:
            pass

    def _on_response(self, response: Any) -> None:
        """处理响应事件，收集 5xx 响应，排除预期 4xx 请求。

        预期 4xx（如登录失败 401）是测试用例的正常验证行为，不记录为缺陷。
        """
        try:
            status = response.status
            if status >= 500:
                request = response.request
                start_time = self._request_start_times.pop(request.url, None)
                duration_ms = (time.monotonic() - start_time) * 1000 if start_time else 0.0
                self._network_failures.append({
                    "url": request.url,
                    "method": request.method,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                })
        except Exception as e:
            logger.debug(f"处理响应事件异常: {e}")

    def _on_request_failed(self, request: Any) -> None:
        """处理请求失败事件。"""
        try:
            start_time = self._request_start_times.pop(request.url, None)
            duration_ms = (time.monotonic() - start_time) * 1000 if start_time else 0.0
            self._network_failures.append({
                "url": request.url,
                "method": request.method,
                "status": 0,
                "duration_ms": round(duration_ms, 2),
            })
        except Exception as e:
            logger.debug(f"处理请求失败事件异常: {e}")

    async def collect_memory_sample(self) -> None:
        """采集当前 JS 堆内存快照（Chromium only）。

        通过 page.evaluate 调用 performance.memory 获取内存信息。
        如果 API 不可用（非 Chromium 浏览器），则跳过。
        """
        if not self._page:
            return
        try:
            memory_info = await self._page.evaluate("() => performance.memory")
            if memory_info and isinstance(memory_info, dict):
                used_js_heap_size = memory_info.get("usedJSHeapSize", 0)
                used_mb = used_js_heap_size / (1024 * 1024)
                self._memory_samples.append(round(used_mb, 2))
                self._detect_memory_leak()
        except Exception:
            # performance.memory 不可用（非 Chromium），跳过内存监控
            pass

    def _detect_memory_leak(self) -> None:
        """检测内存泄漏嫌疑：连续 N 个步骤内存持续增长超过阈值。"""
        sample_count = len(self._memory_samples)
        if sample_count < self._MEMORY_LEAK_STEP_THRESHOLD:
            return

        # 取最近 N 个样本
        recent = self._memory_samples[-self._MEMORY_LEAK_STEP_THRESHOLD:]
        # 检查是否连续增长
        is_monotonic_growth = all(recent[i + 1] > recent[i] for i in range(len(recent) - 1))
        if not is_monotonic_growth:
            return

        growth_mb = recent[-1] - recent[0]
        if growth_mb > self._MEMORY_LEAK_GROWTH_THRESHOLD_MB:
            self._memory_leak_suspect = {
                "peak_mb": round(recent[-1], 2),
                "growth_mb": round(growth_mb, 2),
                "step_count": self._MEMORY_LEAK_STEP_THRESHOLD,
            }
            logger.warning(
                f"内存泄漏嫌疑: 连续 {self._MEMORY_LEAK_STEP_THRESHOLD} 步增长 "
                f"{growth_mb:.2f}MB, 峰值 {recent[-1]:.2f}MB"
            )

    def get_defect_evidence(self) -> Dict[str, Any]:
        """返回当前收集的缺陷证据字典。

        Returns:
            包含 console_errors / network_failures / memory_leak_suspect /
            uncaught_exceptions 四个键的字典。
        """
        return {
            "console_errors": list(self._console_errors),
            "network_failures": list(self._network_failures),
            "memory_leak_suspect": dict(self._memory_leak_suspect) if self._memory_leak_suspect else None,
            "uncaught_exceptions": list(self._uncaught_exceptions),
        }

    def clear_defect_evidence(self) -> None:
        """在每个步骤开始前清空缺陷收集器，保留内存样本用于泄漏趋势分析。"""
        self._console_errors.clear()
        self._network_failures.clear()
        self._uncaught_exceptions.clear()
        self._request_start_times.clear()
        # 注意：不清空 _memory_samples 和 _memory_leak_suspect，
        # 因为内存泄漏检测需要跨步骤的历史样本
