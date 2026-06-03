import functools
import time
import traceback
from typing import Optional, Dict, Any, Tuple, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import asyncio
import gc


class BrowserType(str, Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class BrowserError(Exception):
    pass


class BrowserNotInitializedError(BrowserError):
    pass


class NavigationError(BrowserError):
    pass


class ElementNotFoundError(BrowserError):
    pass


@dataclass
class BrowserConfig:
    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = False
    viewport_width: int = 1920
    viewport_height: int = 1080
    device_scale_factor: float = 1.0
    user_agent: Optional[str] = None
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"
    proxy_server: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    navigation_timeout: int = 30000
    action_timeout: int = 10000
    window_maximized: bool = True
    disable_animations: bool = True
    record_video: bool = False
    video_dir: Optional[str] = None
    video_size: Tuple[int, int] = (1920, 1080)


@dataclass
class ElementInfo:
    x: float
    y: float
    width: float
    height: float
    tag: str = ""
    id: str = ""
    class_name: str = ""
    name: str = ""
    text: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


def require_initialized(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if not self._is_initialized:
            error_msg = f"浏览器未初始化，无法执行: {func.__name__}"
            logger.error(error_msg)
            raise BrowserNotInitializedError(error_msg)
        return await func(self, *args, **kwargs)
    return wrapper


def handle_browser_errors(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except BrowserError:
            raise
        except TimeoutError as e:
            error_msg = f"{func.__name__} 超时: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            raise BrowserError(error_msg) from e
        except ConnectionError as e:
            error_msg = f"{func.__name__} 连接错误: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            raise BrowserError(error_msg) from e
        except Exception as e:
            error_msg = f"{func.__name__} 失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            raise BrowserError(error_msg) from e
    return wrapper


class BrowserControllerV2:
    # 内存泄漏检测阈值：连续增长步数
    _MEMORY_LEAK_STEP_THRESHOLD: int = 5
    # 内存泄漏检测阈值：连续增长总量（MB）
    _MEMORY_LEAK_GROWTH_THRESHOLD_MB: float = 10.0

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright: Optional[Any] = None
        self._browser: Optional[Any] = None
        self._context: Optional[Any] = None
        self._page: Optional[Any] = None
        self._current_frame: Optional[Any] = None
        self._is_initialized: bool = False
        self._window_size_fixed: bool = False
        self._last_screenshot_time: float = 0
        self._screenshot_cache: Optional[bytes] = None

        # 缺陷捕获相关状态
        self._console_errors: List[Dict[str, str]] = []
        self._network_failures: List[Dict[str, Any]] = []
        self._uncaught_exceptions: List[Dict[str, str]] = []
        self._memory_samples: List[float] = []
        self._memory_leak_suspect: Optional[Dict[str, Any]] = None
        self._request_start_times: Dict[str, float] = {}
        self._defect_listeners_registered: bool = False

    async def initialize(self) -> 'BrowserControllerV2':
        if self._is_initialized:
            logger.warning("浏览器已经初始化")
            return self
        try:
            from playwright.async_api import async_playwright
            logger.info(f"正在启动 {self.config.browser_type.value} 浏览器...")
            self._playwright = await async_playwright().start()
            browser_type_map = {
                BrowserType.CHROMIUM: self._playwright.chromium,
                BrowserType.FIREFOX: self._playwright.firefox,
                BrowserType.WEBKIT: self._playwright.webkit
            }
            browser_launcher = browser_type_map[self.config.browser_type]
            launch_options: Dict[str, Any] = {
                "headless": self.config.headless,
                "args": [
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                    "--start-maximized",
                    "--force-device-scale-factor=1",
                    "--disable-blink-features=AutomationControlled",
                    "--exclude-switches=enable-automation",
                    "--disable-infobars",
                ]
            }
            if self.config.proxy_server:
                launch_options["proxy"] = {"server": self.config.proxy_server}
                if self.config.proxy_username:
                    proxy_config = launch_options["proxy"]
                    if isinstance(proxy_config, dict):
                        proxy_config["username"] = self.config.proxy_username
                        proxy_config["password"] = self.config.proxy_password
            self._browser = await browser_launcher.launch(**launch_options)
            context_options: Dict[str, Any] = {
                "viewport": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height
                },
                "device_scale_factor": self.config.device_scale_factor,
                "locale": self.config.locale,
                "timezone_id": self.config.timezone_id,
                "screen": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height
                }
            }
            if self.config.user_agent:
                context_options["user_agent"] = self.config.user_agent
            if self.config.record_video:
                import os
                video_dir = self.config.video_dir or "./videos"
                os.makedirs(video_dir, exist_ok=True)
                context_options["record_video_dir"] = video_dir
                context_options["record_video_size"] = {
                    "width": self.config.video_size[0],
                    "height": self.config.video_size[1]
                }
                logger.info(f"已启用视频录制，保存目录: {video_dir}")
            self._context = await self._browser.new_context(**context_options)
            self._context.set_default_navigation_timeout(self.config.navigation_timeout)
            self._context.set_default_timeout(self.config.action_timeout)
            self._page = await self._context.new_page()
            try:
                from playwright_stealth import Stealth
                stealth = Stealth()
                await stealth.apply_stealth_async(self._page)
                logger.info("已应用stealth模式隐藏自动化特征")
            except ImportError:
                logger.warning("playwright-stealth未安装，跳过stealth模式")
            except Exception as e:
                logger.warning(f"应用stealth模式失败: {e}")
            if self.config.disable_animations:
                await self._page.add_init_script("""
                    const style = document.createElement('style');
                    style.textContent = `
                        *, *::before, *::after {
                            animation-duration: 0.01ms !important;
                            animation-iteration-count: 1 !important;
                            transition-duration: 0.01ms !important;
                        }
                    `;
                    document.head.appendChild(style);
                """)
            if not self.config.headless and self.config.window_maximized:
                await self._maximize_window()
            self._setup_defect_listeners()
            self._is_initialized = True
            logger.info("浏览器启动成功")
            return self
        except ImportError as e:
            error_msg = "Playwright未安装，请运行: pip install playwright"
            logger.error(error_msg)
            raise BrowserError(error_msg) from e
        except Exception as e:
            logger.error(f"浏览器启动失败: {str(e)}")
            logger.debug(traceback.format_exc())
            await self._cleanup_resources()
            raise BrowserError(f"浏览器启动失败: {str(e)}") from e

    async def _maximize_window(self):
        if self._window_size_fixed:
            return
        try:
            await self._page.evaluate("""
                () => {
                    window.moveTo(0, 0);
                    window.resizeTo(screen.width, screen.height);
                }
            """)
            await asyncio.sleep(0.5)
            self._window_size_fixed = True
            logger.info(f"窗口已最大化: {self.config.viewport_width}x{self.config.viewport_height}")
        except Exception as e:
            logger.warning(f"窗口最大化失败: {e}")

    async def _cleanup_resources(self):
        resources = (
            ("_page", "close"),
            ("_context", "close"),
            ("_browser", "close"),
        )
        for attr, method in resources:
            resource = getattr(self, attr)
            if resource:
                try:
                    await getattr(resource, method)()
                except Exception as e:
                    logger.warning(f"清理资源时出错: {method}, {e}")
                finally:
                    setattr(self, attr, None)
        self._current_frame = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"清理资源时出错: stop, {e}")
            finally:
                self._playwright = None
            gc.collect()
            await asyncio.sleep(0.15)
            gc.collect()

    async def close(self) -> Optional[str]:
        if (
            not self._is_initialized
            and self._page is None
            and self._context is None
            and self._browser is None
            and self._playwright is None
        ):
            return None
        logger.info("正在关闭浏览器...")
        video_path = None
        if self.config.record_video and self._page:
            try:
                video = self._page.video
                if video:
                    video_path = await video.path()
                    logger.info(f"视频已保存: {video_path}")
            except Exception as e:
                logger.warning(f"获取视频路径失败: {e}")
        await self._cleanup_resources()
        self._is_initialized = False
        self._window_size_fixed = False
        self._defect_listeners_registered = False
        gc.collect()
        await asyncio.sleep(0.1)
        logger.info("浏览器已关闭")
        return video_path

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""

    @property
    def active_page(self) -> Optional[Any]:
        return self._current_frame or self._page

    def switch_to_frame(self, frame: Any) -> None:
        self._current_frame = frame

    def switch_to_main(self) -> None:
        self._current_frame = None

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
