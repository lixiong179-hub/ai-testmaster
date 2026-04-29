"""
测试执行引擎 V2 - 优化版本

用于AI视觉测试的测试用例执行
- 执行测试步骤
- 集成前置条件检查
- 集成元素定位
- 集成AI视觉识别
- 集成测试数据参数化
- 集成AI自愈（元素定位失败时AI兜底+定位器回写）
- 记录执行结果

优化内容：
1. 使用BrowserControllerV2减少闪屏
2. 优化验证码识别和输入逻辑
3. 改进元素定位策略
4. 添加执行过程可视化
5. 集成AI视觉元素识别
6. 集成测试数据参数化
7. 集成AI自愈机制（Stagehand + 本地AI兜底）
"""
import json
import asyncio
import functools
import traceback
import re
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from app.utils.db_time import utcnow
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.models.test_case import TestCase, TestStep, TestCaseExecution, TestCasePreconditionStep
from app.models.element_locator import ElementLocator
from app.core.constants import LocatorStatus
from app.services.precondition_service import PreconditionService
from app.services.element_locator_service import ElementLocatorService
from app.services.selector_registry import SelectorRegistry
from app.services.test_data_service import TestDataService
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext
from app.utils.browser_controller_v2 import BrowserControllerV2
from app.utils.unified_vision_model import UnifiedVisionModel
from app.core.config import settings
from app.services.recognizers.mcp_recognizer import MCPRecognizer
from app.interfaces.element_recognizer import RecognitionResult


class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    PASSED = "passed"        # 通过
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过
    ERROR = "error"          # 执行错误


class ActionType(str, Enum):
    """操作类型"""
    CLICK = "click"          # 点击
    INPUT = "input"          # 输入
    NAVIGATE = "navigate"    # 导航
    VERIFY = "verify"        # 验证
    WAIT = "wait"            # 等待
    SCROLL = "scroll"        # 滚动
    HOVER = "hover"          # 悬停
    SELECT = "select"        # 选择
    CAPTCHA = "captcha"      # 验证码识别
    REFRESH = "refresh"      # 刷新页面
    KEYPRESS = "keypress"    # 按键操作


class ExecutionError(Exception):
    """执行错误"""
    pass


class StepExecutionError(ExecutionError):
    """步骤执行错误"""
    pass


class VerificationError(ExecutionError):
    """验证错误"""
    pass


@dataclass
class StepExecutionResult:
    """步骤执行结果"""
    step_number: int
    action: str
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: int = 0
    screenshot: Optional[bytes] = None
    error_message: Optional[str] = None
    element_locator: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[str] = None
    execution_detail: Optional[str] = None  # 执行详情
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "element_locator": self.element_locator,
            "ai_analysis": self.ai_analysis,
            "execution_detail": self.execution_detail
        }


@dataclass
class TestExecutionResult:
    """测试执行结果"""
    execution_id: int
    test_case_id: int
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: int = 0
    step_results: List[StepExecutionResult] = field(default_factory=list)
    actual_result: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "test_case_id": self.test_case_id,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "step_results": [sr.to_dict() for sr in self.step_results],
            "actual_result": self.actual_result,
            "error_message": self.error_message
        }


def handle_execution_errors(func: Callable) -> Callable:
    """装饰器：处理执行错误"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ExecutionError:
            raise
        except Exception as e:
            error_msg = f"{func.__name__} 执行失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            raise ExecutionError(error_msg) from e
    return wrapper


class ExecutionMode(str, Enum):
    PREPROCESS = "preprocess"
    REALTIME = "realtime"
    SMART = "smart"
    MOBILE_REALTIME = "mobile_realtime"
    MOBILE_SMART = "mobile_smart"


class TestExecutionEngineV2:
    """
    测试执行引擎 V2 - 优化版本
    
    功能：
    - 执行测试用例
    - 管理测试步骤执行流程
    - 集成前置条件服务
    - 集成元素定位服务
    - 记录执行结果
    - 优化验证码处理
    """
    
    # 类常量
    DEFAULT_STEP_TIMEOUT = 30  # 默认步骤超时（秒）
    DEFAULT_VERIFY_TIMEOUT = 10  # 默认验证超时（秒）
    MAX_RETRY_COUNT = 3  # 最大重试次数
    
    def __init__(
        self,
        db: Session,
        precondition_service: Optional[PreconditionService] = None,
        locator_service: Optional[ElementLocatorService] = None,
        browser: Optional[BrowserControllerV2] = None,
        vision_model: Optional[UnifiedVisionModel] = None,
        enable_ai_recognition: bool = True,
        enable_test_data_param: bool = True,
        mobile_device_id: Optional[str] = None
    ):
        """
        初始化测试执行引擎
        
        Args:
            db: 数据库会话
            precondition_service: 前置条件服务
            locator_service: 元素定位服务
            browser: 浏览器控制器（V2版本）
            vision_model: 视觉模型
            enable_ai_recognition: 是否启用AI识别作为元素定位的备选策略
            enable_test_data_param: 是否启用测试数据参数化
        """
        self.db = db
        self.precondition_service = precondition_service
        self.locator_service = locator_service
        self.browser = browser
        self.vision_model = vision_model
        self._current_execution: Optional[TestCaseExecution] = None
        self._step_results: List[StepExecutionResult] = []
        
        # 集成AI识别和测试数据参数化
        self.enable_ai_recognition = enable_ai_recognition
        self.enable_test_data_param = enable_test_data_param
        self.test_data_service: Optional[TestDataService] = None
        self.parameterizer: Optional[TestDataParameterizer] = None
        
        # 如果启用测试数据参数化，初始化服务
        if self.enable_test_data_param:
            self.test_data_service = TestDataService(db)
        
        # AI自愈相关属性
        self._stagehand_client = None
        self._stagehand_session_id = None
        self._self_healing_attempts = 0
        self._self_healing_successes = 0
        self._self_healing_stats = {
            "total_attempts": 0,
            "total_healed": 0,
            "failed_attempts": 0,
            "healed_steps": [],
            "strategy_usage": {},
        }
        self._mobile_device_id = mobile_device_id
        self._mobile_executor = None
    
    @handle_execution_errors
    async def execute_test_case(
        self,
        test_case: TestCase,
        project_id: int,
        skip_precondition: bool = False,
        execution_id: Optional[int] = None,
        execution_mode: str = "smart",
        mobile_device_id: Optional[str] = None
    ) -> TestExecutionResult:
        """
        执行测试用例
        
        Args:
            test_case: 测试用例
            project_id: 项目ID
            skip_precondition: 是否跳过前置条件
            execution_id: 执行ID（用于参数化上下文）
            
        Returns:
            测试执行结果
        """
        logger.info(f"开始执行测试用例: {test_case.case_no} - {test_case.title}")
        
        start_time = utcnow()
        self._step_results = []
        if mobile_device_id:
            self._mobile_device_id = mobile_device_id
        
        # 1. 创建执行记录
        execution = TestCaseExecution(
            test_case_id=test_case.id,
            status=ExecutionStatus.RUNNING.value,
            started_at=start_time
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        self._current_execution = execution
        
        # 2. 初始化参数化解析器（从ai_test_executor.py集成）
        if execution_id is None:
            execution_id = execution.id
        self.parameterizer = self._create_parameterizer(execution_id, test_case.id)
        
        try:
            # 3. 执行前置条件（智能检测登录状态）
            if not skip_precondition and self.precondition_service:
                login_valid = await self._check_precondition_status()
                if login_valid and self.precondition_service.is_browser_ready:
                    logger.info("登录状态有效，跳过前置条件（登录）")
                else:
                    logger.info("登录状态无效或浏览器未启动，执行前置条件（登录）")
                    await self._execute_precondition(project_id)

            # 3.5 执行用例前置条件步骤（将页面导航到目标位置）
            precondition_steps = self.db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == test_case.id
            ).order_by(TestCasePreconditionStep.step_number).all()

            all_passed = True
            if precondition_steps:
                logger.info(f"开始执行 {len(precondition_steps)} 个前置条件步骤")
                for pc_step in precondition_steps:
                    step_result = await self._execute_precondition_step(pc_step)
                    self._step_results.append(step_result)
                    
                    if step_result.status != ExecutionStatus.PASSED:
                        logger.warning(f"前置条件步骤 {pc_step.step_number} 失败，跳过用例执行")
                        all_passed = False
                        break
                else:
                    logger.info("所有前置条件步骤执行成功")
            
            # 4. 执行测试步骤
            steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case.id
            ).order_by(TestStep.step_number).all()
            
            # 仅当前置条件步骤全部通过时才执行测试步骤
            if all_passed:
                for step in steps:
                    step_result = await self._execute_step(step, execution_mode=execution_mode)
                    self._step_results.append(step_result)
                    
                    if step_result.status != ExecutionStatus.PASSED:
                        all_passed = False
                        # 如果步骤失败，后续步骤跳过
                        if step_result.status == ExecutionStatus.FAILED:
                            logger.warning(f"步骤 {step.step_number} 失败，跳过后续步骤")
                            break
            else:
                logger.warning("前置条件步骤失败，跳过测试步骤执行")
            
            # 5. 更新执行结果
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            
            final_status = ExecutionStatus.PASSED if all_passed else ExecutionStatus.FAILED
            
            execution.status = final_status.value
            execution.completed_at = end_time
            execution.actual_result = self._generate_execution_summary()
            
            self.db.commit()
            
            # 输出自愈摘要
            healing_summary = self.get_self_healing_summary()
            if healing_summary["self_healing_attempts"] > 0:
                logger.info(
                    f"自愈摘要 | 尝试: {healing_summary['self_healing_attempts']} | "
                    f"成功: {healing_summary['self_healing_successes']} | "
                    f"成功率: {healing_summary['self_healing_success_rate']:.1%}"
                )
            
            result = TestExecutionResult(
                execution_id=execution.id,
                test_case_id=test_case.id,
                status=final_status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration,
                step_results=self._step_results,
                actual_result=execution.actual_result
            )
            
            logger.info(f"测试用例执行完成: {test_case.case_no}, 状态: {final_status.value}")
            return result
            
        except Exception as e:
            # 执行出错
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            
            execution.status = ExecutionStatus.ERROR.value
            execution.completed_at = end_time
            execution.actual_result = f"执行错误: {str(e)}"
            self.db.commit()
            
            logger.error(f"测试用例执行错误: {test_case.case_no}, 错误: {str(e)}")
            
            return TestExecutionResult(
                execution_id=execution.id,
                test_case_id=test_case.id,
                status=ExecutionStatus.ERROR,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration,
                step_results=self._step_results,
                error_message=str(e)
            )

    async def _check_precondition_status(self) -> bool:
        """
        检测前置条件（登录）状态是否仍然有效

        Returns:
            True=登录状态有效可跳过, False=需要重新执行前置条件
        """
        if not self.precondition_service:
            return True

        if not self.precondition_service.is_browser_ready:
            return False

        try:
            login_valid = await self.precondition_service.check_login_status()
            if login_valid:
                logger.info("登录状态检测: 有效")
            else:
                logger.info("登录状态检测: 无效，需要重新登录")
            return login_valid
        except Exception as e:
            logger.warning(f"登录状态检测异常: {e}")
            return False

    async def _execute_precondition(
        self,
        project_id: int,
        target_env: str = "test",
        skip_init: bool = False
    ) -> None:
        """
        执行前置条件
        
        Args:
            project_id: 项目ID
            target_env: 目标环境名称，从 web_env_configs 中选择配置
            skip_init: 是否跳过初始化（仅启动浏览器+导航，不执行登录）
        """
        if not self.precondition_service:
            logger.warning("前置条件服务未初始化，跳过前置条件执行")
            return
        
        logger.info(f"执行前置条件 (环境={target_env}, 跳过初始化={skip_init})")
        
        # 如果浏览器未启动，执行Web前置操作
        if not self.precondition_service.is_browser_ready:
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                # 从 web_env_configs 中选择目标环境配置（兼容双重编码JSON字符串）
                env_config = {}
                raw_web_cfg = getattr(project, 'web_env_configs', None)
                resolved_web_cfg = None
                if raw_web_cfg:
                    if isinstance(raw_web_cfg, dict):
                        resolved_web_cfg = raw_web_cfg
                    elif isinstance(raw_web_cfg, str):
                        try:
                            parsed = json.loads(raw_web_cfg)
                            if isinstance(parsed, dict):
                                resolved_web_cfg = parsed
                            elif isinstance(parsed, str):
                                inner = json.loads(parsed)
                                if isinstance(inner, dict):
                                    resolved_web_cfg = inner
                        except (json.JSONDecodeError, ValueError, TypeError):
                            pass
                
                if resolved_web_cfg:
                    env_config = resolved_web_cfg.get(target_env, {})
                    if not env_config:
                        available_envs = list(resolved_web_cfg.keys())
                        if available_envs:
                            fallback_env = available_envs[0]
                            env_config = resolved_web_cfg.get(fallback_env, {})
                            logger.warning(f"目标环境 '{target_env}' 不存在，回退到 '{fallback_env}'")
                        else:
                            logger.warning(f"项目无可用环境配置，使用项目默认配置")
                
                await self.precondition_service.read_test_object_info(
                    project,
                    env_config=env_config if env_config else None
                )
                
                # skip_init=True 时仅启动浏览器+导航，不登录；False 时完整初始化含登录
                browser = await self.precondition_service.execute_web_precondition(
                    headless=False,
                    auto_login=(not skip_init)
                )
                # 使用V2版本的浏览器控制器
                if browser and hasattr(browser, '_page'):
                    self.browser = browser
                
                # 更新元素定位服务的浏览器
                if self.locator_service:
                    self.locator_service.browser = browser
        
        logger.info("前置条件执行完成")
    
    VALID_EXECUTION_MODES = {"preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"}

    async def _execute_step(self, step: TestStep, execution_mode: str = "smart") -> StepExecutionResult:
        if execution_mode not in self.VALID_EXECUTION_MODES:
            logger.warning(f"非法执行模式 '{execution_mode}'，回退到 'smart'")
            execution_mode = "smart"
        logger.info(f"执行步骤 {step.step_number}: {step.action[:50]}...")
        
        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            # 生成测试数据并替换参数（从ai_test_executor.py集成）
            step_test_data = {}
            action_with_data = step.action
            
            if self.enable_test_data_param:
                step_test_data = self._generate_step_test_data(step.id, self.parameterizer)
                if step_test_data:
                    logger.info(f"步骤 {step.step_number}: 生成的测试数据: {step_test_data}")
                    # 替换操作描述中的占位符
                    action_with_data = self._substitute_parameters_in_action(
                        step.action, 
                        step_test_data
                    )
                    if action_with_data != step.action:
                        logger.info(f"步骤 {step.step_number}: 替换后操作: {action_with_data}")
            
            # 保存执行详情
            if step_test_data:
                result.execution_detail = json.dumps(step_test_data, ensure_ascii=False)
            
            # 解析步骤动作
            if hasattr(step, 'action_type') and step.action_type:
                action_type_str = step.action_type.lower()
                action_type_map = {
                    "click": ActionType.CLICK,
                    "input": ActionType.INPUT,
                    "navigate": ActionType.NAVIGATE,
                    "verify": ActionType.VERIFY,
                    "wait": ActionType.WAIT,
                    "scroll": ActionType.SCROLL,
                    "hover": ActionType.HOVER,
                    "select": ActionType.SELECT,
                    "captcha": ActionType.CAPTCHA,
                    "refresh": ActionType.REFRESH,
                    "keypress": ActionType.KEYPRESS,
                }
                action_type = action_type_map.get(action_type_str, ActionType.CLICK)
                action_info = {"type": action_type, "text": action_with_data}
            else:
                action_info = self._parse_step_action(action_with_data)
                action_type = action_info.get("type", ActionType.CLICK)

            if action_type == ActionType.INPUT and hasattr(step, 'input_value') and step.input_value:
                action_info["input_value"] = step.input_value
            
            # 获取元素定位信息（集成AI识别）
            locator_record = None
            element_info = None
            if self.locator_service and step.id:
                locator_record = self.locator_service.get_locator(step.id)
                if locator_record:
                    result.element_locator = locator_record.get_best_locator()

            is_mobile_mode = execution_mode in (ExecutionMode.MOBILE_REALTIME.value, ExecutionMode.MOBILE_SMART.value)
            if is_mobile_mode:
                await self._execute_mobile_step(step, action_with_data, execution_mode, result)
                end_time = utcnow()
                duration = int((end_time - start_time).total_seconds() * 1000)
                result.end_time = end_time
                result.duration_ms = duration
                return result

            if execution_mode == ExecutionMode.PREPROCESS.value:
                if action_type in (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT) and not locator_record:
                    raise StepExecutionError(f"步骤 {step.step_number} 缺少元素定位信息，请先批量补充")
            elif execution_mode in (ExecutionMode.REALTIME.value, ExecutionMode.SMART.value):
                if not locator_record and self.locator_service and self.browser:
                    logger.info(f"步骤 {step.step_number}: 无预存定位，尝试AI实时识别 (mode={execution_mode})")
                    try:
                        page_title = await self._get_current_page_title()
                        element_info = await self.locator_service.smart_locate_element(
                            action_description=action_with_data,
                            page_title=page_title,
                            action_type=action_type.value if isinstance(action_type, ActionType) else action_type,
                            input_value=action_info.get("input_value")
                        )
                        if element_info:
                            direct_executed = element_info.pop("_direct_executed", False)
                            if direct_executed:
                                logger.info(f"步骤 {step.step_number}: MCP直执成功，跳过Controller执行")
                            locator_record = await self._save_realtime_locator(step, element_info)
                            if locator_record:
                                result.element_locator = locator_record.get_best_locator()
                                if not direct_executed:
                                    logger.info(f"步骤 {step.step_number}: AI实时识别成功，已缓存定位信息")
                        else:
                            if execution_mode == ExecutionMode.REALTIME.value:
                                logger.warning(f"步骤 {step.step_number}: AI实时识别失败")
                    except Exception as e:
                        logger.warning(f"步骤 {step.step_number}: AI实时识别异常: {e}")

            if action_type == ActionType.NAVIGATE:
                await self._execute_navigate(action_info)
            elif action_type in (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT):
                if element_info and direct_executed:
                    pass
                elif locator_record:
                    await self._execute_with_self_healing(
                        step, locator_record, action_type, action_info, step_test_data
                    )
                else:
                    await self._execute_action_by_type(action_type, action_info, step, step_test_data)
            elif action_type == ActionType.VERIFY:
                await self._execute_verify(action_info, step.id)
            elif action_type == ActionType.WAIT:
                await self._execute_wait(action_info)
            elif action_type == ActionType.SCROLL:
                await self._execute_scroll(action_info)
            elif action_type == ActionType.HOVER:
                await self._execute_hover(action_info, step.id, step_test_data)
            elif action_type == ActionType.SELECT:
                await self._execute_select(action_info, step.id, step_test_data)
            elif action_type == ActionType.CAPTCHA:
                await self._execute_captcha(action_info, step.id)
            elif action_type == ActionType.REFRESH:
                await self._execute_refresh(action_info)
            elif action_type == ActionType.KEYPRESS:
                await self._execute_keypress(action_info)
            else:
                await self._execute_click(action_info, step.id, step_test_data)
            
            # 截取执行后截图（用于AI验证）
            before_screenshot = None
            after_screenshot = None
            if self.browser and self.enable_ai_recognition:
                before_screenshot = await self.browser.take_screenshot()
            
            # 等待页面响应
            await asyncio.sleep(2)
            
            # 执行后截图
            if self.browser:
                after_screenshot = await self.browser.take_screenshot()
                result.screenshot = after_screenshot
            
            # AI验证执行结果（从ai_test_executor.py集成）
            if (before_screenshot and after_screenshot and 
                self.enable_ai_recognition and step.expected_result):
                is_passed = await self.verify_execution_result(
                    before_screenshot,
                    after_screenshot,
                    action_with_data,
                    step.expected_result
                )
                if not is_passed:
                    logger.warning(f"步骤 {step.step_number}: AI验证不通过")
                    # 注意：这里不直接标记失败，因为实际元素可能已正确操作
            
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            
            result.status = ExecutionStatus.PASSED
            result.end_time = end_time
            result.duration_ms = duration
            result.ai_analysis = f"执行动作: {action_with_data}"
            
            logger.info(f"步骤 {step.step_number} 执行成功")
            
        except Exception as e:
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            
            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration_ms = duration
            result.error_message = str(e)
            
            # 失败时截图
            if self.browser:
                try:
                    result.screenshot = await self.browser.take_screenshot()
                except Exception:
                    pass
            
            logger.error(f"步骤 {step.step_number} 执行失败: {str(e)}")
        
        return result

    def _get_mobile_executor(self) -> Optional[Any]:
        if self._mobile_executor is None:
            try:
                from app.services.mobile_ai_executor import MobileAIExecutor
                from app.utils.adb_controller import AdbController
                adb = AdbController(udid=self._mobile_device_id)
                self._mobile_executor = MobileAIExecutor(
                    db=self.db,
                    adb=adb,
                )
            except Exception as e:
                logger.warning(f"初始化MobileAIExecutor失败: {e}")
        return self._mobile_executor

    async def _execute_mobile_step(
        self,
        step: TestStep,
        action_with_data: str,
        execution_mode: str,
        result: StepExecutionResult,
    ) -> None:
        mobile_executor = self._get_mobile_executor()
        if not mobile_executor:
            raise StepExecutionError("移动端执行器未初始化，请检查ADB连接")
        use_cache = execution_mode == ExecutionMode.MOBILE_SMART.value
        action_result = await mobile_executor.execute_action(
            description=action_with_data,
            step_id=step.id,
            use_cache=use_cache,
        )
        if action_result.coordinates:
            result.element_locator = action_result.coordinates
        result.ai_analysis = f"移动端AI执行: {action_with_data}"
        if action_result.used_cache:
            result.ai_analysis += " (缓存命中)"
        if not action_result.success:
            raise StepExecutionError(action_result.error_message or "移动端执行失败")

    async def _get_current_page_title(self) -> Optional[str]:
        try:
            if self.browser:
                title = await self.browser.execute_javascript("document.title")
                return title if isinstance(title, str) else None
        except Exception as e:
            logger.debug(f"获取页面标题失败: {e}")
        return None

    async def _save_realtime_locator(self, step: TestStep, element_info: Dict[str, Any]) -> Optional[ElementLocator]:
        if not self.locator_service or not self.browser:
            return None
        try:
            confidence = element_info.get("confidence", 0)
            if confidence < 0.8:
                logger.info(f"步骤 {step.step_number}: 实时识别置信度 {confidence} < 0.8，跳过缓存")
                return None
            element_attrs = await self.locator_service._get_element_attributes(element_info)
            if not element_attrs:
                return None
            css_selector = self.locator_service._generate_css_selector(element_attrs)
            xpath = self.locator_service._generate_xpath(element_attrs)
            coordinate = self.locator_service._normalize_coordinate(element_info)
            locator = ElementLocator(
                step_id=step.id,
                element_description=step.action,
                element_type=element_attrs.get("tag"),
                css_selector=css_selector,
                xpath=xpath,
                element_id=element_attrs.get("id"),
                element_name=element_attrs.get("name"),
                element_class=element_attrs.get("class"),
                element_text=element_attrs.get("text"),
                ai_coordinate=coordinate,
                ai_confidence=confidence,
                source="ai_realtime"
            )
            self.db.add(locator)
            self.db.commit()
            self.db.refresh(locator)
            step_record = self.db.query(TestStep).filter(TestStep.id == step.id).first()
            if step_record:
                step_record.has_locator = 1
                step_record.locator_status = LocatorStatus.RECORDED.value
                self.db.commit()
            logger.info(f"步骤 {step.step_number}: 实时定位信息已缓存，ID={locator.id}")
            return locator
        except Exception as e:
            logger.warning(f"保存实时定位信息失败: {e}")
            return None

    async def _execute_precondition_step(self, step) -> StepExecutionResult:
        """
        执行前置条件步骤（简化版，不含测试数据参数化和自愈机制）
        
        Args:
            step: TestCasePreconditionStep 对象
            
        Returns:
            步骤执行结果
        """
        logger.info(f"执行前置条件步骤 {step.step_number}: {step.action[:50]}...")
        
        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            # 解析步骤动作
            if hasattr(step, 'action_type') and step.action_type:
                action_type_str = step.action_type.lower()
                action_type_map = {
                    "click": ActionType.CLICK,
                    "input": ActionType.INPUT,
                    "navigate": ActionType.NAVIGATE,
                    "verify": ActionType.VERIFY,
                    "wait": ActionType.WAIT,
                    "scroll": ActionType.SCROLL,
                    "hover": ActionType.HOVER,
                    "select": ActionType.SELECT,
                    "captcha": ActionType.CAPTCHA,
                    "refresh": ActionType.REFRESH,
                    "keypress": ActionType.KEYPRESS,
                }
                action_type = action_type_map.get(action_type_str, ActionType.CLICK)
                action_info = {"type": action_type, "text": step.action}
            else:
                action_info = self._parse_step_action(step.action)
                action_type = action_info.get("type", ActionType.CLICK)

            if action_type == ActionType.INPUT and hasattr(step, 'input_value') and step.input_value:
                action_info["input_value"] = step.input_value
            
            # 获取前置条件步骤的元素定位信息
            locator_record = None
            if self.locator_service and step.id:
                locator_record = self.db.query(ElementLocator).filter(
                    ElementLocator.precondition_step_id == step.id
                ).first()
            
            # 执行动作
            if action_type == ActionType.NAVIGATE:
                await self._execute_navigate(action_info)
            elif action_type in (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT):
                if locator_record:
                    await self._execute_action_directly(action_type, action_info, locator_record)
                else:
                    element_info = await self.smart_locate_with_ai_fallback(step.action)
                    if element_info:
                        temp_locator = ElementLocator(
                            css_selector=element_info.get('css_selector'),
                            ai_coordinate=element_info
                        )
                        await self._execute_action_directly(action_type, action_info, temp_locator)
                    else:
                        raise StepExecutionError(f"前置条件步骤 {step.step_number}: 无法定位元素 - {step.action}")
            elif action_type == ActionType.VERIFY:
                await self._execute_verify(action_info, step.id)
            elif action_type == ActionType.WAIT:
                await self._execute_wait(action_info)
            elif action_type == ActionType.SCROLL:
                await self._execute_scroll(action_info)
            elif action_type == ActionType.CAPTCHA:
                await self._execute_captcha(action_info, step.id)
            elif action_type == ActionType.REFRESH:
                await self._execute_refresh(action_info)
            elif action_type == ActionType.KEYPRESS:
                await self._execute_keypress(action_info)
            else:
                await self._execute_click(action_info, step.id)
            
            # 等待页面响应
            await asyncio.sleep(2)
            
            # 执行后截图
            if self.browser:
                result.screenshot = await self.browser.take_screenshot()
            
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            
            result.status = ExecutionStatus.PASSED
            result.end_time = end_time
            result.duration_ms = duration
            result.ai_analysis = f"前置条件步骤执行动作: {step.action}"
            
            logger.info(f"前置条件步骤 {step.step_number} 执行成功")
            
        except Exception as e:
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            
            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration_ms = duration
            result.error_message = str(e)
            
            # 失败时截图
            if self.browser:
                try:
                    result.screenshot = await self.browser.take_screenshot()
                except Exception:
                    pass
            
            logger.error(f"前置条件步骤 {step.step_number} 执行失败: {str(e)}")
        
        return result
    
    def _parse_step_action(self, action_text: str) -> Dict[str, Any]:
        """解析步骤动作文本"""
        action_lower = action_text.lower()
        
        # 识别动作类型
        if "导航" in action_text or "访问" in action_text or "打开" in action_text or "navigate" in action_lower:
            return {"type": ActionType.NAVIGATE, "text": action_text}
        elif "验证码" in action_text or "captcha" in action_lower:
            return {"type": ActionType.CAPTCHA, "text": action_text}
        elif "刷新" in action_text or "refresh" in action_lower:
            return {"type": ActionType.REFRESH, "text": action_text}
        elif "按下" in action_text or "按键" in action_text or "key" in action_lower:
            return {"type": ActionType.KEYPRESS, "text": action_text}
        elif "输入" in action_text or "填写" in action_text or "input" in action_lower:
            return {"type": ActionType.INPUT, "text": action_text}
        elif "点击" in action_text or "按下" in action_text or "click" in action_lower:
            return {"type": ActionType.CLICK, "text": action_text}
        elif "验证" in action_text or "检查" in action_text or "assert" in action_lower or "verify" in action_lower:
            return {"type": ActionType.VERIFY, "text": action_text}
        elif "等待" in action_text or "wait" in action_lower:
            return {"type": ActionType.WAIT, "text": action_text}
        elif "滚动" in action_text or "scroll" in action_lower:
            return {"type": ActionType.SCROLL, "text": action_text}
        elif "悬停" in action_text or "hover" in action_lower:
            return {"type": ActionType.HOVER, "text": action_text}
        elif "选择" in action_text or "select" in action_lower:
            return {"type": ActionType.SELECT, "text": action_text}
        else:
            return {"type": ActionType.CLICK, "text": action_text}
    
    async def _execute_navigate(self, action_info: Dict[str, Any]) -> None:
        """执行导航操作"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        url = self._extract_url(text)
        
        if url:
            await self.browser.navigate(url)
            logger.info(f"导航到: {url}")
        else:
            raise StepExecutionError(f"无法从动作中提取URL: {text}")
    
    async def _execute_input(self, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        """执行输入操作（使用智能元素定位集成AI识别）"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        input_text = action_info.get("input_value", "") or self._extract_input_text(text)
        
        # 优先使用测试数据中的值（从ai_test_executor.py集成）
        if step_test_data:
            for field_name, value in step_test_data.items():
                if field_name in text.lower() or field_name in action_info.get("text", ""):
                    input_text = value
                    logger.info(f"使用测试数据输入值: {field_name} = {value}")
                    break
            
            # 如果没有匹配字段，使用第一个测试数据值
            if input_text == "test" and step_test_data:
                input_text = list(step_test_data.values())[0]
                logger.info(f"使用测试数据第一个值: {input_text}")
        
        # 使用智能元素定位（集成AI识别）
        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(
                    text, 
                    step_test_data
                )
                
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            await self.browser.fill(css_selector, input_text)
                            logger.info(f"使用CSS选择器输入: {css_selector} -> {input_text}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器输入失败: {e}")
                    
                    # 使用坐标点击后输入
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    
                    await self.browser.click(x, y)
                    await asyncio.sleep(0.3)
                    
                    await self.browser.execute_javascript("""
                        (function() {
                            var el = document.activeElement;
                            if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                nativeInputValueSetter.call(el, arguments[0]);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        })()
                    """, input_text)
                    logger.info(f"输入文本(坐标方式): {input_text}")
                    return
            except Exception as e:
                logger.warning(f"智能定位输入失败: {e}")
        
        logger.error(f"无法定位输入元素: {text}")
        raise StepExecutionError(f"无法定位输入元素: {text}")
    
    async def _execute_click(self, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        """执行点击操作（使用智能元素定位集成AI识别）"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        
        # 使用智能元素定位（集成AI识别）
        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(
                    text, 
                    step_test_data
                )
                
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            await self.browser.click_element(css_selector)
                            logger.info(f"使用CSS选择器点击: {css_selector}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器点击失败: {e}")
                    
                    # 使用坐标点击
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    
                    await self.browser.click(x, y)
                    logger.info(f"点击元素(坐标方式): ({x}, {y})")
                    return
            except Exception as e:
                logger.warning(f"智能定位点击失败: {e}")
        
        # 最后fallback - 预定义选择器
        selector = self._get_element_selector(text)
        if selector:
            try:
                await self.browser.click_element(selector)
                logger.info(f"使用预定义选择器点击成功: {selector}")
                return
            except Exception as e:
                logger.warning(f"预定义选择器点击失败: {e}")
        
        logger.error(f"无法定位点击元素: {text}")
        raise StepExecutionError(f"无法定位点击元素: {text}")
    
    async def _execute_refresh(self, action_info: Dict[str, Any]) -> None:
        """执行刷新页面操作"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        await self.browser.refresh()
        logger.info("页面刷新完成")
    
    async def _execute_keypress(self, action_info: Dict[str, Any]) -> None:
        """执行按键操作"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        key = self._extract_key(text)
        
        await self.browser.press_key(key)
        logger.info(f"按下按键: {key}")
    
    def _extract_key(self, text: str) -> str:
        """从文本中提取按键名称"""
        if "enter" in text.lower() or "回车" in text:
            return "Enter"
        elif "tab" in text.lower() or "制表" in text:
            return "Tab"
        elif "escape" in text.lower() or "esc" in text.lower():
            return "Escape"
        elif "space" in text.lower() or "空格" in text:
            return "Space"
        else:
            return "Enter"  # 默认按下Enter键
    
    async def _execute_captcha(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        """
        执行验证码识别和输入 - 优化版本
        
        策略：
        1. 首先查找页面上所有输入框
        2. 使用AI识别验证码图片
        3. 找到验证码输入框并输入
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        if not self.vision_model:
            logger.warning("视觉模型未初始化，跳过验证码识别")
            return
        
        text = action_info.get("text", "")
        logger.info(f"开始验证码识别: {text}")
        
        try:
            # 1. 获取页面上所有输入框信息
            all_inputs = await self.browser.get_all_input_elements()
            logger.info(f"页面上找到 {len(all_inputs)} 个输入元素")
            
            # 2. 截取页面截图
            screenshot = await self.browser.take_screenshot()
            
            # 3. 使用AI识别验证码
            prompt = """请仔细分析这个登录页面截图，完成以下任务：

1. 找到验证码图片（通常是一个包含数字/字母/数学运算的图片，位于输入框旁边）
2. 仔细识别验证码内容，特别注意：
   - 数字：0-9
   - 运算符：+（加）、-（减）、*（乘）、/（除）
   - 请仔细辨认每个字符，确保识别准确
3. 如果是数学表达式（如 3+5, 8-2, 4*2），请计算结果
4. 如果是纯数字/字母，直接识别

重要提示：
- 请仔细查看验证码图片中的每个数字和运算符
- 确保识别准确后再进行计算
- 验证码通常是一个简单的数学表达式

请返回JSON格式：
{
    "captcha_type": "math|text",
    "captcha_original": "原始内容（如 '3+5=?'）",
    "captcha_result": "计算或识别结果（如 '8'）",
    "captcha_image_location": {"x": 100, "y": 200, "width": 80, "height": 30},
    "confidence": 0.95
}

如果找不到验证码，返回：
{
    "captcha_result": null,
    "error": "未找到验证码"
}"""
            
            response = self.vision_model.analyze_image(screenshot, prompt)
            logger.info(f"AI验证码识别响应: {response[:200]}...")
            
            # 4. 解析AI响应
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                captcha_text = result.get("captcha_result") or result.get("captcha_text")
                captcha_type = result.get("captcha_type", "text")
                captcha_original = result.get("captcha_original", "")
                
                if captcha_text:
                    if captcha_type == "math":
                        logger.info(f"数学验证码识别成功: {captcha_original} = {captcha_text}")
                    else:
                        logger.info(f"验证码识别成功: {captcha_text}")
                    
                    # 5. 找到验证码输入框并输入
                    # 策略：查找placeholder包含"验证码"的输入框，或者最后一个文本输入框
                    captcha_input = None
                    
                    for input_el in all_inputs:
                        placeholder = input_el.get("placeholder", "")
                        input_type = input_el.get("type", "text")
                        if "验证码" in placeholder or "captcha" in placeholder.lower():
                            captcha_input = input_el
                            break
                    
                    # 如果没找到，尝试使用最后一个文本输入框（通常是验证码）
                    if not captcha_input:
                        text_inputs = [inp for inp in all_inputs if inp.get("type") in ["text", "", None]]
                        if text_inputs:
                            captcha_input = text_inputs[-1]
                    
                    if captcha_input:
                        selector = self._build_css_selector_from_attrs(captcha_input)
                        
                        if selector:
                            try:
                                # 使用Playwright直接输入
                                await self.browser.fill(selector, captcha_text)
                                logger.info(f"验证码输入成功: {captcha_text}")
                                return
                            except Exception as e:
                                logger.warning(f"选择器输入失败: {e}")
                        
                        # 使用坐标点击后输入
                        x = captcha_input.get("x", 0) + captcha_input.get("width", 0) // 2
                        y = captcha_input.get("y", 0) + captcha_input.get("height", 0) // 2
                        
                        await self.browser.click(x, y)
                        await asyncio.sleep(0.3)
                        
                        await self.browser.execute_javascript("""
                            (function() {
                                var el = document.activeElement;
                                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    nativeInputValueSetter.call(el, arguments[0]);
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                    return true;
                                }
                                var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                                for (var i = inputs.length - 1; i >= 0; i--) {
                                    var placeholder = inputs[i].getAttribute('placeholder') || '';
                                    if (placeholder.includes('验证码') || placeholder.includes('captcha')) {
                                        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                        setter.call(inputs[i], arguments[0]);
                                        inputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                                        inputs[i].dispatchEvent(new Event('change', { bubbles: true }));
                                        return true;
                                    }
                                }
                                return false;
                            })()
                        """, captcha_text)
                        logger.info(f"验证码输入完成(坐标方式): {captcha_text}")
                        return
                    else:
                        logger.error("未找到验证码输入框")
                else:
                    logger.warning(f"验证码识别失败: {result.get('error', '未知错误')}")
            else:
                logger.warning("无法解析AI验证码识别结果")
                
        except Exception as e:
            logger.error(f"验证码识别执行失败: {str(e)}")
            raise StepExecutionError(f"验证码识别失败: {str(e)}")
    
    async def _execute_verify(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        """执行验证操作"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        
        # 截取页面截图
        screenshot = await self.browser.take_screenshot()
        
        # 使用AI验证页面状态
        if self.vision_model:
            prompt = f"""请验证以下测试条件是否满足：
{text}

请返回JSON格式：
{{
    "passed": true/false,
    "reason": "验证通过/失败的原因"
}}
"""
            response = self.vision_model.analyze_image(screenshot, prompt)
            
            # 解析结果
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if not result.get("passed", False):
                    raise VerificationError(result.get("reason", "验证失败"))
                logger.info(f"验证通过: {result.get('reason', '')}")
            else:
                logger.warning("无法解析AI验证结果")
        else:
            logger.warning("视觉模型未初始化，跳过AI验证")
    
    async def _execute_wait(self, action_info: Dict[str, Any]) -> None:
        """执行等待操作"""
        text = action_info.get("text", "")
        wait_seconds = self._extract_wait_time(text)
        
        logger.info(f"等待 {wait_seconds} 秒")
        await asyncio.sleep(wait_seconds)
    
    async def _execute_scroll(self, action_info: Dict[str, Any]) -> None:
        """执行滚动操作"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        
        if "下" in text or "down" in text.lower():
            await self.browser.execute_javascript("window.scrollBy(0, 500)")
            logger.info("向下滚动")
        elif "上" in text or "up" in text.lower():
            await self.browser.execute_javascript("window.scrollBy(0, -500)")
            logger.info("向上滚动")
        else:
            await self.browser.execute_javascript("window.scrollBy(0, 500)")
            logger.info("默认向下滚动")
    
    async def _execute_hover(self, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        """执行悬停操作（使用智能元素定位集成AI识别）"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        
        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(
                    text,
                    step_test_data
                )
                
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            safe_selector = css_selector.replace("\\", "\\\\").replace("'", "\\'")
                            await self.browser.execute_javascript(f"""
                                var el = document.querySelector('{safe_selector}');
                                if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                            """)
                            logger.info(f"使用CSS选择器悬停: {css_selector}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器悬停失败: {e}")
                    
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    
                    await self.browser.execute_javascript(f"""
                        var el = document.elementFromPoint({x}, {y});
                        if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                    """)
                    logger.info(f"悬停元素(坐标方式): ({x}, {y})")
                    return
            except Exception as e:
                logger.warning(f"智能定位悬停失败: {e}")
        
        selector = self._get_element_selector(text)
        if selector:
            try:
                safe_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
                await self.browser.execute_javascript(f"""
                    var el = document.querySelector('{safe_selector}');
                    if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                """)
                logger.info(f"使用预定义选择器悬停成功: {selector}")
                return
            except Exception as e:
                logger.warning(f"预定义选择器悬停失败: {e}")
        
        logger.error(f"无法定位悬停元素: {text}")
        raise StepExecutionError(f"无法定位悬停元素: {text}")
    
    async def _execute_select(self, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        """执行选择操作（使用智能元素定位集成AI识别）"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        text = action_info.get("text", "")
        select_value = action_info.get("input_value", "") or self._extract_input_text(text)
        
        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(
                    text,
                    step_test_data
                )
                
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            await self.browser.click_element(css_selector)
                            await asyncio.sleep(0.5)
                            
                            if select_value:
                                safe_css = css_selector.replace("\\", "\\\\").replace("'", "\\'")
                                await self.browser.execute_javascript(f"""
                                    var select = document.querySelector('{safe_css}');
                                    if (select && select.tagName === 'SELECT') {{
                                        var options = select.options;
                                        for (var i = 0; i < options.length; i++) {{
                                            if (options[i].text.includes(arguments[0]) || options[i].value === arguments[0]) {{
                                                select.selectedIndex = i;
                                                select.dispatchEvent(new Event('change', {{bubbles: true}}));
                                                break;
                                            }}
                                        }}
                                    }}
                                """, select_value)
                            logger.info(f"使用CSS选择器选择: {css_selector} -> {select_value}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器选择失败: {e}")
                    
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    
                    await self.browser.click(x, y)
                    await asyncio.sleep(0.5)
                    logger.info(f"点击选择元素(坐标方式): ({x}, {y})")
                    return
            except Exception as e:
                logger.warning(f"智能定位选择失败: {e}")
        
        selector = self._get_element_selector(text)
        if selector:
            try:
                await self.browser.click_element(selector)
                logger.info(f"使用预定义选择器选择成功: {selector}")
                return
            except Exception as e:
                logger.warning(f"预定义选择器选择失败: {e}")
        
        logger.error(f"无法定位选择元素: {text}")
        raise StepExecutionError(f"无法定位选择元素: {text}")
    
    def _extract_url(self, text: str) -> Optional[str]:
        """从文本中提取URL"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]\']+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None
    
    def _extract_input_text(self, text: str) -> str:
        """从动作文本中提取要输入的文本"""
        # 尝试匹配引号中的内容
        matches = re.findall(r'["\']([^"\']+)["\']', text)
        if matches:
            return matches[-1]
        
        # 匹配中文引号
        matches = re.findall(r'[""'']([^""'']+)[""'']', text)
        if matches:
            return matches[-1]
        
        # 尝试匹配 "输入 xxx" 格式
        match = re.search(r'输入\s+(\S+)', text)
        if match:
            return match.group(1)
        
        # 尝试匹配 "填写 xxx" 格式
        match = re.search(r'填写\s+(\S+)', text)
        if match:
            return match.group(1)
        
        logger.warning(f"无法从文本中提取输入内容: {text}，使用默认值")
        return "test"
    
    def _extract_wait_time(self, text: str) -> int:
        """从文本中提取等待时间"""
        match = re.search(r'(\d+)\s*(秒|seconds?)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 2
    
    def _generate_execution_summary(self) -> str:
        """生成执行摘要"""
        total = len(self._step_results)
        passed = sum(1 for r in self._step_results if r.status == ExecutionStatus.PASSED)
        failed = sum(1 for r in self._step_results if r.status == ExecutionStatus.FAILED)
        
        summary = f"执行完成: 总计{total}步, 通过{passed}步, 失败{failed}步"
        
        if failed > 0:
            failed_steps = [r for r in self._step_results if r.status == ExecutionStatus.FAILED]
            summary += f"\n失败步骤: " + ", ".join([f"第{r.step_number}步" for r in failed_steps])
        
        return summary
    
    # ============================================================================
    # AI视觉元素识别（从ai_test_executor.py集成）
    # ============================================================================
    
    async def recognize_element_with_ai(
        self,
        screenshot: bytes,
        action_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        使用AI识别目标元素（从ai_test_executor.py集成）
        
        Args:
            screenshot: 页面截图
            action_description: 操作描述（如"点击登录按钮"）
            
        Returns:
            元素信息（坐标、大小等），识别失败返回None
        """
        if not self.vision_model:
            logger.warning("视觉模型未初始化，跳过AI元素识别")
            return None
        
        prompt = f"""请分析这个页面截图，识别以下操作的目标元素：
操作描述: {action_description}

请返回目标元素的坐标信息（JSON格式）：
{{
    "x": 元素左上角x坐标,
    "y": 元素左上角y坐标,
    "width": 元素宽度,
    "height": 元素高度,
    "confidence": 识别置信度(0-1)
}}

注意：
- x, y 是相对于截图的像素坐标
- 如果无法识别，返回 null
"""
        
        try:
            response = self.vision_model.analyze_image(screenshot, prompt)
            
            # 解析JSON响应
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                element_info = json.loads(json_match.group())
                
                # 检查置信度
                confidence = element_info.get("confidence", 0)
                if confidence < 0.9:
                    logger.warning(f"元素识别置信度较低: {confidence}")
                    return None
                
                logger.info(f"AI识别元素成功: 置信度={confidence}")
                return element_info
            
            return None
            
        except Exception as e:
            logger.error(f"AI元素识别失败: {str(e)}")
            return None
    
    async def verify_execution_result(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes,
        action_description: str,
        expected_result: str
    ) -> bool:
        """
        AI验证执行结果（从ai_test_executor.py集成）
        
        Args:
            before_screenshot: 执行前截图
            after_screenshot: 执行后截图
            action_description: 操作描述
            expected_result: 预期结果
            
        Returns:
            是否通过验证
        """
        if not self.vision_model:
            logger.warning("视觉模型未初始化，跳过AI验证")
            return True
        
        prompt = f"""请分析以下测试步骤的执行结果：

操作: {action_description}
预期结果: {expected_result}

请对比执行前后的页面截图，判断该步骤是否执行成功。

返回格式（JSON）：
{{
    "success": true/false,
    "reason": "判断理由"
}}
"""
        
        try:
            response = self.vision_model.analyze_image(after_screenshot, prompt)
            
            # 解析JSON响应
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                success = result.get("success", False)
                reason = result.get("reason", "")
                logger.info(f"AI验证结果: success={success}, reason={reason}")
                return success
            
            return True  # 默认通过
            
        except Exception as e:
            logger.error(f"AI验证执行失败: {str(e)}")
            return True  # 验证失败时默认通过，避免误判
    
    # ============================================================================
    # 测试数据参数化（从ai_test_executor.py集成）
    # ============================================================================
    
    def _create_parameterizer(self, execution_id: int, case_id: int) -> Optional[TestDataParameterizer]:
        """
        创建参数化解析器
        
        Args:
            execution_id: 执行ID
            case_id: 用例ID
            
        Returns:
            参数化解析器
        """
        if not self.enable_test_data_param or not self.test_data_service:
            return None
        
        context = ParameterContext(
            execution_id=f"EXEC_{execution_id}"
        )
        return TestDataParameterizer(context)
    
    def _generate_step_test_data(
        self,
        step_id: int,
        parameterizer: Optional[TestDataParameterizer] = None
    ) -> Dict[str, str]:
        """
        生成步骤的测试数据
        
        Args:
            step_id: 步骤ID
            parameterizer: 参数化解析器
            
        Returns:
            字段名到值的映射
        """
        if not self.enable_test_data_param or not self.test_data_service:
            return {}
        
        try:
            return self.test_data_service.generate_step_data(step_id, parameterizer)
        except Exception as e:
            logger.warning(f"生成测试数据失败: {e}")
            return {}
    
    def _substitute_parameters_in_action(
        self,
        action: str,
        test_data: Dict[str, str]
    ) -> str:
        """
        替换操作描述中的参数占位符
        
        Args:
            action: 操作描述
            test_data: 测试数据
            
        Returns:
            替换后的操作描述
        """
        if not test_data:
            return action
        
        result = action
        for field_name, value in test_data.items():
            placeholder = f"${{{field_name}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
                logger.info(f"替换参数 {placeholder} -> {value}")
        
        return result
    
    # ============================================================================
    # 智能元素定位（集成AI识别）
    # ============================================================================
    
    async def smart_locate_with_ai_fallback(
        self,
        action_description: str,
        test_data: Optional[Dict[str, str]] = None,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        智能元素定位（集成AI识别作为fallback策略）
        
        策略（按优先级）：
        1. 预定义CSS选择器
        2. ElementLocatorService智能定位
        3. AI视觉识别（从ai_test_executor.py集成）
        4. 坐标点击（最后的fallback）
        
        Args:
            action_description: 操作描述
            test_data: 测试数据（用于替换描述中的占位符）
            max_retries: 最大重试次数
            
        Returns:
            元素定位信息
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        # 替换参数（如果有）
        action_text = self._substitute_parameters_in_action(
            action_description, 
            test_data or {}
        )
        
        logger.info(f"智能元素定位开始: {action_text}")
        
        # 策略1: 预定义选择器
        selector = self._get_element_selector(action_text)
        if selector:
            try:
                element_info = await self._locate_with_selector(selector)
                if element_info:
                    logger.info("策略1成功: 预定义选择器")
                    return element_info
            except Exception as e:
                logger.warning(f"策略1失败: 预定义选择器 - {e}")
        
        # 策略2: ElementLocatorService
        if self.locator_service:
            try:
                page_title = await self.browser.execute_javascript("document.title")
                element_info = await self.locator_service.smart_locate_element(
                    action_description=action_text,
                    page_title=page_title
                )
                if element_info:
                    logger.info("策略2成功: ElementLocatorService")
                    return element_info
            except Exception as e:
                logger.warning(f"策略2失败: ElementLocatorService - {e}")
        
        # 策略3: AI视觉识别（从ai_test_executor.py集成）
        if self.enable_ai_recognition and self.vision_model:
            for attempt in range(max_retries):
                try:
                    screenshot = await self.browser.take_screenshot()
                    element_info = await self.recognize_element_with_ai(
                        screenshot, 
                        action_text
                    )
                    if element_info:
                        logger.info(f"策略3成功: AI识别 (尝试 {attempt + 1}/{max_retries})")
                        # 尝试获取元素属性并生成CSS选择器
                        element_attrs = await self._get_element_attributes_from_coords(
                            element_info.get("x", 0),
                            element_info.get("y", 0),
                            element_info.get("width", 0),
                            element_info.get("height", 0)
                        )
                        if element_attrs:
                            css_selector = self._build_css_selector_from_attrs(element_attrs)
                            if css_selector:
                                element_info['css_selector'] = css_selector
                        return element_info
                except Exception as e:
                    logger.warning(f"策略3尝试 {attempt + 1} 失败: {e}")
        
        logger.warning("所有定位策略失败，无法定位元素")
        return None
    
    def _get_element_selector(self, action_text: str) -> Optional[str]:
        registry = SelectorRegistry()
        return registry.get_selector(None, action_text)

    @staticmethod
    def _build_css_selector_from_attrs(attrs: Dict[str, Any]) -> Optional[str]:
        if not attrs:
            return None
        element_id = attrs.get("id")
        if element_id:
            return f"#{element_id}"
        data_testid = attrs.get("data-testid")
        if data_testid:
            return f"[data-testid='{data_testid}']"
        name = attrs.get("name")
        if name:
            return f"[name='{name}']"
        tag = attrs.get("tag", "")
        element_class = attrs.get("class")
        if element_class and tag:
            classes = element_class.split()[:2]
            return f"{tag}.{'.'.join(classes)}"
        element_type = attrs.get("type")
        if element_type and tag:
            return f"{tag}[type='{element_type}']"
        if tag:
            return tag
        return None
    
    async def _locate_with_selector(self, selector: str) -> Optional[Dict[str, Any]]:
        """使用CSS选择器定位元素"""
        try:
            first_selector = selector.split(',')[0].strip()
            element_info = await self.browser.execute_javascript("""
                (function() {
                    var el = document.querySelector(arguments[0]);
                    if (el) {
                        var rect = el.getBoundingClientRect();
                        return {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            css_selector: arguments[1],
                            confidence: 0.95
                        };
                    }
                    return null;
                })()
            """, first_selector, selector)
            
            if element_info:
                return element_info
            return None
        except Exception as e:
            logger.warning(f"选择器定位失败: {e}")
            return None
    
    async def _get_element_attributes_from_coords(
        self,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Optional[Dict[str, Any]]:
        """通过坐标获取元素属性"""
        center_x = x + width // 2
        center_y = y + height // 2
        
        try:
            attrs = await self.browser.execute_javascript("""
                (function() {
                    var element = document.elementFromPoint(arguments[0], arguments[1]);
                    if (!element) return null;
                    
                    return {
                        tag: element.tagName ? element.tagName.toLowerCase() : '',
                        id: element.id || null,
                        name: element.getAttribute('name') || null,
                        class: element.className || null,
                        type: element.getAttribute('type') || null,
                        placeholder: element.getAttribute('placeholder') || null
                    };
                })()
            """, center_x, center_y)
            return attrs
        except Exception as e:
            logger.warning(f"获取元素属性失败: {e}")
            return None
    

    
    # ============================================================================
    # AI自愈机制（元素定位失败时AI兜底 + 定位器回写）
    # ============================================================================
    
    async def _execute_action_by_type(
        self,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step: TestStep,
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """根据操作类型分发到对应的执行方法（不含自愈逻辑）"""
        if action_type == ActionType.INPUT:
            await self._execute_input(action_info, step.id, step_test_data)
        elif action_type == ActionType.CLICK:
            await self._execute_click(action_info, step.id, step_test_data)
        elif action_type == ActionType.HOVER:
            await self._execute_hover(action_info, step.id, step_test_data)
        elif action_type == ActionType.SELECT:
            await self._execute_select(action_info, step.id, step_test_data)
        else:
            await self._execute_click(action_info, step.id, step_test_data)
    
    async def _get_stagehand(self):
        """
        懒加载Stagehand客户端实例
        
        仅在配置开关开启且Browserbase凭据已配置时创建实例。
        每次调用都重新检查配置，确保运行时配置变更能生效。
        
        Returns:
            Stagehand AsyncStagehand 客户端实例，或 None（未配置时）
        """
        if not settings.AI_SELF_HEALING_ENABLED:
            self._stagehand_client = None
            return None
        
        if not settings.BROWSERBASE_API_KEY or not settings.BROWSERBASE_PROJECT_ID:
            self._stagehand_client = None
            return None
        
        if self._stagehand_client is not None:
            return self._stagehand_client
        
        try:
            from stagehand import AsyncStagehand
            
            self._stagehand_client = AsyncStagehand(
                browserbase_api_key=settings.BROWSERBASE_API_KEY,
                browserbase_project_id=settings.BROWSERBASE_PROJECT_ID,
                model_api_key=settings.DEEPSEEK_API_KEY,
            )
            logger.info("Stagehand客户端初始化成功")
            return self._stagehand_client
        except ImportError:
            logger.warning("stagehand包未安装，Stagehand自愈不可用。请运行: pip install stagehand")
            return None
        except Exception as e:
            logger.error(f"Stagehand客户端初始化失败: {e}")
            return None
    
    async def _get_nl_description(self, step_id: int) -> str:
        """
        获取步骤的自然语言描述
        
        查找策略：
        1. 从TestStep获取action和input_value组合描述
        2. 尝试通过ElementLocator的element_description获取元素描述
        
        Args:
            step_id: 测试步骤ID（对应TestStep.id）
            
        Returns:
            自然语言描述字符串，未找到时返回空字符串
        """
        try:
            test_step = self.db.query(TestStep).filter(
                TestStep.id == step_id
            ).first()
            
            if test_step:
                parts = []
                if test_step.action:
                    parts.append(test_step.action)
                if hasattr(test_step, 'input_value') and test_step.input_value:
                    parts.append(test_step.input_value)
                desc = " ".join(parts).strip()
                if desc:
                    return desc
            
            locator = self.db.query(ElementLocator).filter(
                ElementLocator.step_id == step_id
            ).first()
            
            if locator and locator.element_description:
                return locator.element_description
            
            logger.warning(f"未找到步骤 {step_id} 的自然语言描述")
            return ""
        except Exception as e:
            logger.warning(f"获取步骤 {step_id} 自然语言描述失败: {e}")
            return ""
    
    async def _execute_with_self_healing(
        self,
        step: TestStep,
        locator_record: Optional[ElementLocator],
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """
        带自愈兜底的步骤执行包装器
        
        流程：
        1. 尝试使用 locator_record 的选择器执行操作
        2. 捕获 Playwright 超时/元素不存在异常
        3. 若自愈开关开启，使用AI自愈重试
        4. 自愈成功后回写新定位器到数据库
        
        Args:
            step: 测试步骤对象
            locator_record: 元素定位记录（可为None）
            action_type: 操作类型
            action_info: 操作信息字典
            step_test_data: 测试数据
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        old_selector = None
        if locator_record:
            best = locator_record.get_best_locator()
            if best:
                old_selector = best.get("value")
        
        try:
            await self._execute_action_directly(action_type, action_info, locator_record, step_test_data)
            if locator_record and old_selector:
                ElementLocator.atomic_record_success(self.db, locator_record.id, locator_record.version)
            return
        except Exception as primary_error:
            error_str = str(primary_error).lower()
            is_locator_error = any(kw in error_str for kw in [
                "timeout", "waiting", "not found", "no element",
                "selector", "等待", "超时", "未找到", "不存在",
                "stale", "detached", "not attached"
            ])
            
            if not is_locator_error:
                raise
            
            if not settings.AI_SELF_HEALING_ENABLED:
                logger.info(f"定位器失效但自愈开关已关闭 | 旧选择器: {old_selector}")
                raise
            
            nl_description = await self._get_nl_description(step.id)
            if not nl_description:
                nl_description = action_info.get("text", "")
            
            self._self_healing_attempts += 1
            logger.info(
                f"定位器失效，启动AI自愈 | 旧选择器: {old_selector} | "
                f"步骤描述: {nl_description} | 步骤ID: {step.id}"
            )
            
            try:
                new_selector = await self._ai_self_heal_action(
                    nl_description, action_type, action_info, step_test_data
                )
                
                if new_selector and locator_record:
                    await self._update_locator_after_healing(
                        locator_record.id, new_selector, old_selector
                    )
                
                self._self_healing_successes += 1
                logger.info(f"自愈成功，新选择器已回写 | 新选择器: {new_selector}")
                return
                
            except Exception as heal_error:
                logger.error(
                    f"自愈失败，AI无法解析步骤 | 步骤描述: {nl_description} | "
                    f"自愈错误: {heal_error}"
                )
                raise primary_error
    
    async def _execute_action_directly(
        self,
        action_type: ActionType,
        action_info: Dict[str, Any],
        locator_record: Optional[ElementLocator],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """
        使用已有定位器直接执行操作（不含自愈逻辑）
        
        Args:
            action_type: 操作类型
            action_info: 操作信息
            locator_record: 元素定位记录
            step_test_data: 测试数据
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        
        selector = None
        if locator_record:
            best = locator_record.get_best_locator()
            if best:
                loc_type = best.get("type")
                loc_value = best.get("value")
                
                if loc_type == "css":
                    selector = loc_value
                elif loc_type == "xpath":
                    selector = f"xpath={loc_value}"
                elif loc_type == "id":
                    selector = f"#{loc_value}"
                elif loc_type == "name":
                    selector = f"[name='{loc_value}']"
                elif loc_type == "ai" and isinstance(loc_value, dict):
                    x = loc_value.get("x", 0) + loc_value.get("width", 0) // 2
                    y = loc_value.get("y", 0) + loc_value.get("height", 0) // 2
                    if action_type == ActionType.INPUT:
                        input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
                        await self.browser.click(x, y)
                        await asyncio.sleep(0.3)
                        await self.browser.execute_javascript("""
                            (function() {
                                var el = document.activeElement;
                                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    nativeInputValueSetter.call(el, arguments[0]);
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            })()
                        """, input_text)
                        return
                    else:
                        await self.browser.click(x, y)
                        return
        
        if selector:
            if action_type == ActionType.INPUT:
                input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
                if step_test_data:
                    for field_name, value in step_test_data.items():
                        if field_name in action_info.get("text", "").lower():
                            input_text = value
                            break
                await self.browser.fill(selector, input_text)
                logger.info(f"使用选择器输入: {selector} -> {input_text}")
                return
            elif action_type == ActionType.CLICK:
                await self.browser.click_element(selector)
                logger.info(f"使用选择器点击: {selector}")
                return
            elif action_type == ActionType.HOVER:
                safe_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
                await self.browser.execute_javascript(f"""
                    var el = document.querySelector('{safe_selector}');
                    if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                """)
                return
            elif action_type == ActionType.SELECT:
                await self.browser.click_element(selector)
                return
        
        raise StepExecutionError(f"无法使用定位器执行操作: action_type={action_type}, selector={selector}")
    
    async def _ai_self_heal_action(
        self,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        AI自愈核心：使用AI理解自然语言描述并执行操作
        
        优先使用本地AI（DeepSeek + 视觉模型），可选使用Stagehand云服务。
        
        Args:
            nl_description: 自然语言步骤描述
            action_type: 操作类型
            action_info: 操作信息
            step_test_data: 测试数据
            
        Returns:
            成功自愈后提取的新CSS选择器，失败时抛出异常
        """
        max_retries = settings.AI_SELF_HEALING_MAX_RETRIES
        
        for attempt in range(max_retries):
            try:
                new_selector = await self._local_ai_self_heal(
                    nl_description, action_type, action_info, step_test_data
                )
                if new_selector:
                    return new_selector
            except Exception as e:
                logger.warning(f"本地AI自愈尝试 {attempt + 1}/{max_retries} 失败: {e}")
        
        stagehand = await self._get_stagehand()
        if stagehand:
            try:
                new_selector = await self._stagehand_self_heal(
                    stagehand, nl_description, action_type, action_info
                )
                if new_selector:
                    return new_selector
            except Exception as e:
                logger.warning(f"Stagehand自愈失败: {e}")
        
        raise StepExecutionError(f"AI自愈失败，所有策略均无法解析步骤: {nl_description}")
    
    async def _local_ai_self_heal(
        self,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

        if not hasattr(self, '_mcp_recognizer') or self._mcp_recognizer is None:
            self._mcp_recognizer = MCPRecognizer()

        try:
            action_type_str = action_type.value if isinstance(action_type, ActionType) else str(action_type)
            recognition_result = await self._mcp_recognizer.recognize(
                self.browser, nl_description, action_type_str
            )

            if recognition_result and recognition_result.is_valid:
                logger.info(f"MCP自愈成功，定位类型={recognition_result.locator_type}")
                new_selector = None
                loc_type = recognition_result.locator_type
                loc_value = recognition_result.locator_value

                if loc_type == "css":
                    new_selector = loc_value
                elif loc_type == "xpath":
                    new_selector = f"xpath={loc_value}"
                elif loc_type == "id":
                    new_selector = f"#{loc_value}"
                elif loc_type == "name":
                    new_selector = f"[name='{loc_value}']"
                elif loc_type == "role":
                    new_selector = loc_value
                elif loc_type == "text":
                    new_selector = loc_value
                elif loc_type == "ref":
                    new_selector = loc_value

                if action_type == ActionType.INPUT:
                    input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
                    if step_test_data:
                        for field_name, value in step_test_data.items():
                            if field_name in action_info.get("text", "").lower():
                                input_text = value
                                break
                    await self._mcp_recognizer.execute_action(recognition_result, input_text)
                    logger.info(f"MCP自愈输入成功: {nl_description} -> {input_text}")
                else:
                    await self._mcp_recognizer.execute_action(recognition_result)
                    logger.info(f"MCP自愈执行成功: {nl_description}")

                return new_selector
        except Exception as e:
            logger.warning(f"MCP自愈异常，降级到视觉模型: {e}")

        logger.warning("MCP自愈失败，降级到视觉模型")
        if not self.vision_model:
            raise StepExecutionError("视觉模型未初始化，本地AI自愈不可用")

        screenshot = await self.browser.take_screenshot()

        element_info = await self.recognize_element_with_ai(screenshot, nl_description)
        if not element_info:
            raise StepExecutionError(f"AI视觉识别未找到目标元素: {nl_description}")

        x = element_info.get("x", 0)
        y = element_info.get("y", 0)
        width = element_info.get("width", 0)
        height = element_info.get("height", 0)

        new_selector = None
        element_attrs = await self._get_element_attributes_from_coords(x, y, width, height)
        if element_attrs:
            new_selector = self._build_healed_selector(element_attrs)

        center_x = x + width // 2
        center_y = y + height // 2

        if action_type == ActionType.INPUT:
            input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
            if step_test_data:
                for field_name, value in step_test_data.items():
                    if field_name in action_info.get("text", "").lower():
                        input_text = value
                        break
            
            await self.browser.click(center_x, center_y)
            await asyncio.sleep(0.3)
            await self.browser.execute_javascript("""
                (function() {
                    var el = document.activeElement;
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(el, arguments[0]);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                })()
            """, input_text)
            logger.info(f"本地AI自愈输入成功(坐标方式): ({center_x}, {center_y}) -> {input_text}")
        else:
            await self.browser.click(center_x, center_y)
            logger.info(f"本地AI自愈点击成功(坐标方式): ({center_x}, {center_y})")
        
        return new_selector
    
    async def _stagehand_self_heal(
        self,
        stagehand_client,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any]
    ) -> Optional[str]:
        """
        使用Stagehand云服务进行自愈
        
        ⚠️ 注意：Stagehand在远程Browserbase浏览器上执行操作，
        本地Playwright浏览器状态不会同步更新。
        这意味着后续步骤可能仍在本地浏览器的旧页面上执行。
        建议仅在本地AI自愈不可用时作为最后手段使用。
        
        Args:
            stagehand_client: Stagehand AsyncStagehand 客户端
            nl_description: 自然语言描述
            action_type: 操作类型
            action_info: 操作信息
            
        Returns:
            None（Stagehand在远程浏览器执行，无法提取本地选择器）
        """
        logger.warning(
            "Stagehand自愈将在远程浏览器执行，本地浏览器状态不会同步更新 | "
            f"步骤: {nl_description}"
        )
        try:
            session = await stagehand_client.sessions.start(
                model_name=settings.STAGEHAND_MODEL,
                browser={"type": "browserbase"}
            )
            self._stagehand_session_id = session.id
            
            current_url = ""
            if self.browser:
                try:
                    current_url = await self.browser.execute_javascript("window.location.href")
                except Exception:
                    pass
            
            if current_url:
                await stagehand_client.sessions.navigate(session.id, url=current_url)
            
            action_instruction = nl_description
            if action_type == ActionType.INPUT:
                input_text = action_info.get("input_value", "")
                if input_text:
                    action_instruction = f"{nl_description}，输入内容: {input_text}"
            
            await stagehand_client.sessions.act(
                session.id,
                input=action_instruction,
                stream_response=False,
            )
            
            logger.info(f"Stagehand自愈执行成功 | 指令: {action_instruction}")
            return None
            
        except Exception as e:
            logger.error(f"Stagehand自愈执行失败: {e}")
            raise
        finally:
            if self._stagehand_session_id and stagehand_client:
                try:
                    await stagehand_client.sessions.end(self._stagehand_session_id)
                except Exception:
                    pass
                self._stagehand_session_id = None
    
    @staticmethod
    def _sanitize_css_identifier(value: str) -> str:
        """清理CSS标识符中的特殊字符，防止选择器注入
        
        仅保留字母、数字、下划线和单个连字符（不允许连续--）
        """
        import re as _re
        sanitized = _re.sub(r"[^a-zA-Z0-9_\-]", "", value)
        sanitized = _re.sub(r"-{2,}", "-", sanitized)
        sanitized = sanitized.strip("-_")
        return sanitized
    
    def _build_healed_selector(self, element_attrs: Dict[str, Any]) -> Optional[str]:
        """
        根据元素属性构建自愈后的CSS选择器
        
        优先级: id > name > placeholder > class组合 > tag+type
        
        Args:
            element_attrs: 元素属性字典
            
        Returns:
            CSS选择器字符串，或None
        """
        elem_id = element_attrs.get("id")
        if elem_id:
            safe_id = self._sanitize_css_identifier(elem_id)
            if safe_id:
                return f"#{safe_id}"
        
        elem_name = element_attrs.get("name")
        if elem_name:
            safe_name = self._sanitize_css_identifier(elem_name)
            if safe_name:
                return f"[name='{safe_name}']"
        
        placeholder = element_attrs.get("placeholder")
        if placeholder:
            truncated = placeholder[:10].replace("'", "")
            safe_ph = self._sanitize_css_identifier(truncated)
            if safe_ph:
                return f"[placeholder*='{safe_ph}']"
        
        elem_class = element_attrs.get("class")
        tag = self._sanitize_css_identifier(element_attrs.get("tag", ""))
        elem_type = self._sanitize_css_identifier(element_attrs.get("type", ""))
        
        if elem_class:
            classes = [self._sanitize_css_identifier(c) for c in elem_class.split()[:2]]
            classes = [c for c in classes if c]
            if classes:
                class_selector = "." + ".".join(classes)
                if tag:
                    return f"{tag}{class_selector}"
                return class_selector
        
        if tag and elem_type:
            return f"{tag}[type='{elem_type}']"
        if tag:
            return tag
        
        return None
    
    async def _update_locator_after_healing(
        self,
        locator_record_id: int,
        new_selector: str,
        old_selector: Optional[str] = None
    ) -> bool:
        """
        自愈成功后回写新定位器到数据库（含乐观锁 + 审计历史）
        
        使用乐观锁防止并发更新冲突：
        UPDATE ... WHERE id = ? AND version = ?
        若影响行数为0则放弃更新（说明已被其他进程修改）。
        
        Args:
            locator_record_id: ElementLocator 记录ID
            new_selector: 新的CSS选择器
            old_selector: 旧选择器（用于审计日志）
            
        Returns:
            更新是否成功
        """
        if not new_selector:
            logger.warning("新选择器为空，跳过回写")
            return False
        
        try:
            locator = self.db.query(ElementLocator).filter(
                ElementLocator.id == locator_record_id
            ).first()
            
            if not locator:
                logger.warning(f"定位器记录不存在: {locator_record_id}")
                return False
            
            current_version = locator.version
            
            old_css = locator.css_selector
            
            result = self.db.execute(sql_text(
                "UPDATE element_locators SET css_selector = :new_selector, "
                "source = 'ai_self_healing', "
                "updated_at = UTC_TIMESTAMP(), version = version + 1 "
                "WHERE id = :id AND version = :version"
            ), {
                "new_selector": new_selector,
                "id": locator_record_id,
                "version": current_version
            })
            self.db.commit()
            
            if result.rowcount > 0:
                logger.info(
                    f"定位器回写成功 | ID: {locator_record_id} | "
                    f"旧选择器: {old_css or old_selector} | 新选择器: {new_selector} | "
                    f"版本: {current_version} -> {current_version + 1}"
                )
                return True
            else:
                logger.warning(
                    f"定位器回写失败（乐观锁冲突）| ID: {locator_record_id} | "
                    f"当前版本: {current_version}，可能已被其他进程更新"
                )
                return False
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"定位器回写异常 | ID: {locator_record_id} | 错误: {e}")
            return False
    
    def get_self_healing_summary(self) -> Dict[str, Any]:
        """
        获取自愈统计摘要
        
        Returns:
            包含自愈尝试次数、成功次数、成功率的字典
        """
        success_rate = 0.0
        if self._self_healing_attempts > 0:
            success_rate = self._self_healing_successes / self._self_healing_attempts
        
        return {
            "self_healing_attempts": self._self_healing_attempts,
            "self_healing_successes": self._self_healing_successes,
            "self_healing_success_rate": round(success_rate, 4),
            "self_healing_enabled": settings.AI_SELF_HEALING_ENABLED,
            "stagehand_available": bool(settings.BROWSERBASE_API_KEY and settings.BROWSERBASE_PROJECT_ID)
        }
    
    def get_execution_history(
        self,
        test_case_id: Optional[int] = None,
        limit: int = 10
    ) -> List[TestCaseExecution]:
        """获取执行历史"""
        query = self.db.query(TestCaseExecution)
        if test_case_id:
            query = query.filter(TestCaseExecution.test_case_id == test_case_id)
        return query.order_by(TestCaseExecution.create_time.desc()).limit(limit).all()
    
    # ============================================================================
    # 任务级执行（支持多用例执行）
    # ============================================================================
    
    @handle_execution_errors
    async def execute_test_task(
        self,
        task_id: int,
        global_headless: Optional[bool] = None,
        global_record_video: Optional[bool] = None,
        target_env: str = "test",
        skip_init: bool = False,
        execution_mode: str = "smart",
        mobile_device_id: Optional[str] = None,
        use_mcp: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        执行测试任务（任务级执行，支持多用例）
        
        Args:
            task_id: 测试任务ID
            global_headless: 全局无头模式配置
            global_record_video: 全局视频录制配置
            target_env: 目标环境名称，从 web_env_configs 中选择配置
            skip_init: 是否跳过初始化（仅启动浏览器+导航，不执行登录）
            
        Returns:
            任务执行摘要
        """
        from app.models.test_task import TestTask, TaskStatus
        from app.models.test_result import TestResult
        from app.models.project import Project
        
        logger.info(f"开始执行测试任务: {task_id}")
        
        # 获取测试任务
        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")
        
        # 获取项目信息
        project = self.db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ExecutionError(f"项目不存在: {task.project_id}")
        
        # 更新任务状态为运行中
        task.status = TaskStatus.RUNNING
        task.start_time = utcnow()
        self.db.commit()
        
        task_start_time = utcnow()
        
        try:
            # 执行前置操作
            if self.precondition_service:
                # 从 web_env_configs 中选择目标环境配置（兼容双重编码JSON字符串）
                env_config = {}
                raw_web_cfg = getattr(project, 'web_env_configs', None)
                resolved_web_cfg = None
                if raw_web_cfg:
                    if isinstance(raw_web_cfg, dict):
                        resolved_web_cfg = raw_web_cfg
                    elif isinstance(raw_web_cfg, str):
                        try:
                            parsed = json.loads(raw_web_cfg)
                            if isinstance(parsed, dict):
                                resolved_web_cfg = parsed
                            elif isinstance(parsed, str):
                                inner = json.loads(parsed)
                                if isinstance(inner, dict):
                                    resolved_web_cfg = inner
                        except (json.JSONDecodeError, ValueError, TypeError):
                            pass
                
                if resolved_web_cfg:
                    env_config = resolved_web_cfg.get(target_env, {})
                    if not env_config:
                        available_envs = list(resolved_web_cfg.keys())
                        if available_envs:
                            fallback_env = available_envs[0]
                            env_config = resolved_web_cfg.get(fallback_env, {})
                            logger.warning(f"目标环境 '{target_env}' 不存在，回退到 '{fallback_env}'")
                        else:
                            logger.warning(f"项目无可用环境配置，使用项目默认配置")
                
                await self.precondition_service.read_test_object_info(
                    project,
                    env_config=env_config if env_config else None
                )
                
                headless = global_headless if global_headless is not None else True
                browser = await self.precondition_service.execute_web_precondition(
                    headless=headless,
                    browser_type="chromium",
                    auto_login=(not skip_init)
                )
                if browser:
                    self.browser = browser

                if self.browser and not self.locator_service:
                    from app.services.element_locator_service import ElementLocatorService
                    from app.utils.unified_vision_model import UnifiedVisionModel
                    from app.core.config import settings
                    try:
                        vision_model = UnifiedVisionModel()
                        effective_use_mcp = use_mcp if use_mcp is not None else getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False)
                        self.locator_service = ElementLocatorService.create_locator_service(
                            db=self.db,
                            browser=self.browser,
                            vision_model=vision_model,
                            use_mcp=effective_use_mcp
                        )
                        logger.info("ElementLocatorService 初始化成功")
                    except Exception as e:
                        logger.warning(f"ElementLocatorService 初始化失败: {e}")

            # 获取任务关联的测试用例
            test_results = self.db.query(TestResult).filter(
                TestResult.task_id == task_id
            ).all()
            
            if not test_results:
                logger.warning(f"测试任务 {task_id} 没有关联的测试用例")
                task.status = TaskStatus.PENDING
                task.end_time = utcnow()
                self.db.commit()
                return self._get_task_summary(task_id)
            
            # 统计信息
            total_cases = len(test_results)
            passed_cases = 0
            failed_cases = 0
            
            # 执行每个测试用例
            for test_result in test_results:
                test_case = self.db.query(TestCase).filter(
                    TestCase.id == test_result.case_id
                ).first()
                
                if test_case:
                    try:
                        # 执行单个用例
                        result = await self.execute_test_case(
                            test_case=test_case,
                            project_id=project.id,
                            skip_precondition=False,
                            execution_mode=execution_mode,
                            mobile_device_id=mobile_device_id
                        )
                        
                        # 更新结果状态
                        if result.status == ExecutionStatus.PASSED:
                            test_result.exec_status = 1
                            passed_cases += 1
                        else:
                            test_result.exec_status = 2
                            failed_cases += 1
                        
                        test_result.exec_time = utcnow()
                        test_result.exec_log = result.actual_result or ""
                        
                    except Exception as e:
                        logger.error(f"用例 {test_result.case_id} 执行失败: {e}")
                        test_result.exec_status = 2
                        test_result.exec_time = utcnow()
                        test_result.error_msg = str(e)
                        failed_cases += 1
                    
                    self.db.commit()
            
            # 更新任务状态
            task.status = TaskStatus.COMPLETED if failed_cases == 0 else TaskStatus.FAILED
            task.end_time = utcnow()
            self.db.commit()
            
            logger.info(f"测试任务执行完成: {task_id}, 通过: {passed_cases}, 失败: {failed_cases}")
            
        except Exception as e:
            logger.error(f"测试任务执行失败: {e}")
            task.status = TaskStatus.FAILED
            task.end_time = utcnow()
            self.db.commit()
            raise ExecutionError(f"任务执行失败: {str(e)}") from e
        
        finally:
            # 清理资源
            if self.precondition_service:
                await self.precondition_service.cleanup()
                logger.info("前置操作服务已清理")
        
        return self._get_task_summary(task_id)
    
    def _get_task_summary(self, task_id: int) -> Dict[str, Any]:
        """获取任务执行摘要"""
        from app.models.test_task import TestTask, TaskStatus
        from app.models.test_result import TestResult
        
        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")
        
        results = self.db.query(TestResult).filter(
            TestResult.task_id == task_id
        ).all()
        
        total = len(results)
        passed = len([r for r in results if r.exec_status == 1])
        failed = len([r for r in results if r.exec_status == 2])
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            "task_id": task.id,
            "task_name": task.task_name,
            "status": str(task.status),
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "pass_rate": f"{pass_rate:.2f}%",
            "start_time": task.start_time.strftime("%Y-%m-%d %H:%M:%S") if task.start_time else None,
            "end_time": task.end_time.strftime("%Y-%m-%d %H:%M:%S") if task.end_time else None,
        }
    
    def get_task_execution_summary(self, task_id: int) -> Dict[str, Any]:
        """获取任务执行摘要（兼容旧API）"""
        return self._get_task_summary(task_id)
