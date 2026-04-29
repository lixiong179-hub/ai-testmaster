"""
真实项目测试 - V2优化版本

测试洪恩管理系统登录流程
优化内容：
1. 使用BrowserControllerV2减少闪屏
2. 优化验证码识别和输入
3. 固定窗口大小避免坐标变化
4. 添加详细的执行日志
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.services.precondition_service import PreconditionService
from app.services.element_locator_service import ElementLocatorService
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.utils.browser_controller_v2 import create_browser_controller_v2
from app.utils.unified_vision_model import UnifiedVisionModel
# from app.db.base import Base  # 模块不存在，使用database模块

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("test_execution_v2.log", rotation="10 MB", level="DEBUG")

# 数据库配置 - 使用项目配置
from app.core.config import settings
DB_URL = settings.DATABASE_URL

# 真实项目配置
PROJECT_CONFIG = {
    "name": "洪恩管理系统",
    "description": "洪恩后台管理系统登录测试",
    "base_url": "https://admin-jxw-panda-test.ihumand.com",
    "test_object_type": "web",
    "test_object_info": {
        "url": "https://admin-jxw-panda-test.ihumand.com",
        "username": "admin123",
        "password": "admin123"
    }
}

TEST_CASE_CONFIG = {
    "title": "洪恩管理系统登录测试",
    "description": "测试使用正确的用户名、密码和验证码登录系统",
    "priority": "high",
    "steps": [
        {
            "step_number": 1,
            "action": "导航到登录页面 'https://admin-jxw-panda-test.ihumand.com'",
            "expected_result": "页面加载成功，显示登录表单"
        },
        {
            "step_number": 2,
            "action": "等待页面完全加载",
            "expected_result": "页面元素全部渲染完成"
        },
        {
            "step_number": 3,
            "action": "输入用户名 'admin123'",
            "expected_result": "用户名输入框显示 admin123"
        },
        {
            "step_number": 4,
            "action": "输入密码 'admin123'",
            "expected_result": "密码输入框显示圆点"
        },
        {
            "step_number": 5,
            "action": "识别并输入验证码",
            "expected_result": "验证码输入框显示识别的验证码"
        },
        {
            "step_number": 6,
            "action": "点击登录按钮",
            "expected_result": "触发登录请求"
        },
        {
            "step_number": 7,
            "action": "按下Enter键",
            "expected_result": "提交登录表单"
        },
        {
            "step_number": 8,
            "action": "等待5秒后验证页面已跳转到产品线清单页面",
            "expected_result": "页面显示洪恩管理系统产品线清单内容"
        }
    ]
}


async def setup_test_data(db):
    """设置测试数据"""
    logger.info("设置测试数据...")
    
    # 创建项目
    import json
    project = Project(
        name=PROJECT_CONFIG["name"],
        description=PROJECT_CONFIG["description"],
        user_id=1,  # 默认用户ID
        test_object_type=PROJECT_CONFIG["test_object_type"],
        test_object_url=PROJECT_CONFIG["test_object_info"]["url"],
        test_object_username=PROJECT_CONFIG["test_object_info"]["username"],
        test_object_password=PROJECT_CONFIG["test_object_info"]["password"],
        test_object_device_info=json.dumps(PROJECT_CONFIG["test_object_info"]),
        status=1  # 1=正常
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info(f"创建项目: {project.name}, ID: {project.id}")
    
    # 创建测试用例
    test_case = TestCase(
        project_id=project.id,
        case_no=f"TC{project.id:04d}001",
        module="登录模块",
        title=TEST_CASE_CONFIG["title"],
        precondition="系统正常运行，用户可以访问登录页面",
        steps_json=[
            {"step": i+1, "action": step["action"], "param": ""}
            for i, step in enumerate(TEST_CASE_CONFIG["steps"])
        ],
        expected_result="登录成功，跳转到首页",
        priority=1 if TEST_CASE_CONFIG["priority"] == "high" else 2,
        case_type="UI",
        generate_status=1
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    logger.info(f"创建测试用例: {test_case.case_no}, ID: {test_case.id}")
    
    # 创建测试步骤
    for step_config in TEST_CASE_CONFIG["steps"]:
        step = TestStep(
            test_case_id=test_case.id,
            step_number=step_config["step_number"],
            action=step_config["action"],
            expected_result=step_config["expected_result"]
        )
        db.add(step)
    
    db.commit()
    logger.info(f"创建 {len(TEST_CASE_CONFIG['steps'])} 个测试步骤")
    
    return project, test_case


async def cleanup_test_data(db, project_id):
    """清理测试数据"""
    logger.info(f"清理测试数据，项目ID: {project_id}")
    
    try:
        # 删除测试用例和步骤
        test_cases = db.query(TestCase).filter(TestCase.project_id == project_id).all()
        for tc in test_cases:
            db.query(TestStep).filter(TestStep.test_case_id == tc.id).delete()
            db.delete(tc)
        
        # 删除项目
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
        
        db.commit()
        logger.info("测试数据清理完成")
    except Exception as e:
        logger.error(f"清理测试数据失败: {e}")
        db.rollback()


async def run_test():
    """运行测试"""
    logger.info("=" * 60)
    logger.info("开始执行真实项目测试 - V2优化版本")
    logger.info("=" * 60)
    
    # 创建数据库连接
    engine = create_engine(DB_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    project = None
    browser = None
    
    try:
        # 设置测试数据
        project, test_case = await setup_test_data(db)
        
        # 初始化浏览器控制器V2 - 使用Chromium + Stealth模式
        logger.info("初始化浏览器控制器V2...")
        browser = await create_browser_controller_v2(
            browser_type="chromium",
            headless=False,  # 显示浏览器窗口
            viewport_width=1920,
            viewport_height=1080,
            window_maximized=True,
            disable_animations=True  # 禁用动画减少闪屏
        )
        logger.info("浏览器控制器V2初始化完成")
        
        # 初始化视觉模型
        logger.info("初始化视觉模型...")
        from app.utils.unified_vision_model import UnifiedVisionModel, VisionModelType
        from app.core.config import settings
        
        # 根据配置选择模型类型
        model_type_map = {
            "kimi": VisionModelType.KIMI,
            "qwen": VisionModelType.QWEN,
            "zhipu": VisionModelType.ZHIPU,
            "baidu": VisionModelType.BAIDU,
            "doubao": VisionModelType.DOUBAO,
        }
        default_model = settings.VISION_MODEL_DEFAULT.lower()
        model_type = model_type_map.get(default_model, VisionModelType.QWEN)
        
        logger.info(f"使用视觉模型: {default_model}")
        vision_model = UnifiedVisionModel(model_type=model_type)
        
        # 初始化元素定位服务
        logger.info("初始化元素定位服务...")
        locator_service = ElementLocatorService(
            db=db,
            browser=browser,
            vision_model=vision_model
        )
        
        # 初始化前置条件服务
        logger.info("初始化前置条件服务...")
        precondition_service = PreconditionService()
        precondition_service.browser_controller = browser
        precondition_service.vision_model = vision_model
        
        # 初始化测试执行引擎V2
        logger.info("初始化测试执行引擎V2...")
        execution_engine = TestExecutionEngineV2(
            db=db,
            precondition_service=precondition_service,
            locator_service=locator_service,
            browser=browser,
            vision_model=vision_model
        )
        
        # 执行测试用例
        logger.info("=" * 60)
        logger.info(f"开始执行测试用例: {test_case.case_no}")
        logger.info("=" * 60)
        
        result = await execution_engine.execute_test_case(
            test_case=test_case,
            project_id=project.id,
            skip_precondition=True  # 跳过前置条件，直接使用已初始化的浏览器
        )
        
        # 输出执行结果
        logger.info("=" * 60)
        logger.info("测试执行完成")
        logger.info("=" * 60)
        logger.info(f"执行ID: {result.execution_id}")
        logger.info(f"测试用例ID: {result.test_case_id}")
        logger.info(f"执行状态: {result.status.value}")
        logger.info(f"执行时间: {result.duration_ms}ms")
        logger.info(f"实际结果: {result.actual_result}")
        
        if result.error_message:
            logger.error(f"错误信息: {result.error_message}")
        
        # 输出每个步骤的结果
        logger.info("-" * 60)
        logger.info("步骤执行详情:")
        logger.info("-" * 60)
        for step_result in result.step_results:
            status_icon = "✓" if step_result.status.value == "passed" else "✗"
            logger.info(f"步骤 {step_result.step_number}: {status_icon} {step_result.status.value.upper()}")
            logger.info(f"  动作: {step_result.action}")
            logger.info(f"  耗时: {step_result.duration_ms}ms")
            if step_result.error_message:
                logger.error(f"  错误: {step_result.error_message}")
            logger.info("")
        
        # 最终验证
        logger.info("=" * 60)
        logger.info("最终验证")
        logger.info("=" * 60)
        
        # 获取当前页面信息
        page_info = await browser.get_page_info()
        logger.info(f"当前页面标题: {page_info.get('title', 'Unknown')}")
        logger.info(f"当前页面URL: {page_info.get('url', 'Unknown')}")
        
        # 判断是否登录成功
        current_url = page_info.get('url', '')
        if '/index' in current_url and 'login' not in current_url.lower():
            logger.info("✓ 登录成功！已跳转到首页")
        else:
            logger.warning("✗ 可能未登录成功，仍在登录页面")
        
        # 保存最终截图
        final_screenshot = await browser.take_screenshot()
        with open("final_screenshot_v2.png", "wb") as f:
            f.write(final_screenshot)
        logger.info("最终截图已保存到 final_screenshot_v2.png")
        
        return result
        
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
        
    finally:
        # 关闭浏览器
        if browser:
            logger.info("关闭浏览器...")
            await browser.close()
        
        # 清理测试数据
        if project:
            await cleanup_test_data(db, project.id)
        
        db.close()
        logger.info("测试完成")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(run_test())
