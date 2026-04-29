"""
真实项目执行测试 - 洪恩管理系统

项目配置：
- URL: https://admin-jxw-panda-test.ihumand.com/#/index
- 账号: admin123
- 密码: admin321
"""
import asyncio
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.models.project import Project
from app.models.user import User
from app.models.test_case import TestCase, TestStep
from app.services.test_execution_engine_v2 import (
    TestExecutionEngineV2 as TestExecutionEngine,
    ExecutionStatus,
    ActionType
)
from app.services.precondition_service import PreconditionService
from app.services.element_locator_service import ElementLocatorService
from app.utils.browser_controller import create_browser_controller
from app.utils.unified_vision_model import get_default_vision_model
from loguru import logger


async def test_real_project_login():
    """真实项目测试：洪恩管理系统登录流程"""
    
    print("\n" + "="*80)
    print("开始真实项目测试：洪恩管理系统")
    print("="*80)
    
    # 1. 创建数据库连接
    print("\n[1/6] 连接MySQL数据库...")
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    print("✓ 数据库连接成功")
    
    try:
        # 2. 创建测试用户
        print("\n[2/6] 创建测试用户...")
        test_user = db.query(User).filter(User.id == 99999).first()
        if not test_user:
            test_user = User(
                id=99999,
                username="real_test_user",
                email="realtest@example.com",
                password_hash="test_hash"
            )
            db.add(test_user)
            db.commit()
        print("✓ 测试用户创建成功")
        
        # 3. 创建真实项目配置
        print("\n[3/6] 创建真实项目配置...")
        project = Project(
            id=99999,
            name="洪恩管理系统",
            user_id=99999,
            description="真实项目测试 - 洪恩管理系统",
            test_object_type="web",
            test_object_url="https://admin-jxw-panda-test.ihumand.com/#/index",
            test_object_username="admin123",
            test_object_password="admin321"
        )
        db.add(project)
        db.commit()
        print(f"✓ 项目创建成功")
        print(f"  - URL: {project.test_object_url}")
        print(f"  - 登录账号: {project.test_object_username}")
        
        # 4. 创建测试用例 - 登录流程
        print("\n[4/6] 创建测试用例...")
        test_case = TestCase(
            id=99999,
            case_no="REAL-001",
            project_id=99999,
            module="登录模块",
            title="洪恩管理系统登录测试",
            precondition="系统可访问",
            steps_json='[]',
            expected_result="登录成功，进入首页",
            priority=1,
            case_type="UI"
        )
        db.add(test_case)
        db.commit()
        
        # 创建测试步骤（包含验证码识别）
        steps = [
            TestStep(
                id=99991,
                test_case_id=99999,
                step_number=1,
                action="导航到 https://admin-jxw-panda-test.ihumand.com/#/index",
                expected_result="页面加载成功，显示登录表单"
            ),
            TestStep(
                id=99992,
                test_case_id=99999,
                step_number=2,
                action="等待 2 秒",
                expected_result="页面完全加载"
            ),
            TestStep(
                id=99993,
                test_case_id=99999,
                step_number=3,
                action="输入用户名 'admin123'",
                expected_result="用户名输入成功"
            ),
            TestStep(
                id=99994,
                test_case_id=99999,
                step_number=4,
                action="输入密码 'admin321'",
                expected_result="密码输入成功"
            ),
            TestStep(
                id=99995,
                test_case_id=99999,
                step_number=5,
                action="识别并输入验证码",
                expected_result="验证码识别并输入成功"
            ),
            TestStep(
                id=99996,
                test_case_id=99999,
                step_number=6,
                action="点击登录按钮",
                expected_result="登录成功，跳转到首页"
            ),
            TestStep(
                id=99997,
                test_case_id=99999,
                step_number=7,
                action="等待 3 秒",
                expected_result="首页加载完成"
            ),
            TestStep(
                id=99998,
                test_case_id=99999,
                step_number=8,
                action="验证页面包含 '洪恩管理系统'",
                expected_result="页面验证通过"
            )
        ]
        for step in steps:
            db.add(step)
        db.commit()
        print(f"✓ 测试用例创建成功，共 {len(steps)} 个步骤")
        
        # 初始化浏览器和服务
        print("\n[5/6] 初始化浏览器和服务...")
        # 使用 headless=True 避免闪屏问题，同时保留截图功能
        browser = await create_browser_controller(headless=True)
        vision_model = get_default_vision_model()
        precondition_service = PreconditionService()
        precondition_service.browser_controller = browser
        precondition_service.vision_model = vision_model
        locator_service = ElementLocatorService(db, browser, vision_model)
        
        execution_engine = TestExecutionEngine(
            db=db,
            precondition_service=precondition_service,
            locator_service=locator_service,
            browser=browser,
            vision_model=vision_model
        )
        print("✓ 浏览器和服务初始化成功")
        print("  - 浏览器模式: 无界面（避免闪屏，保留截图）")
        
        # 6. 执行测试
        print("\n[6/6] 开始执行测试...")
        print("-" * 80)
        
        start_time = datetime.utcnow()
        result = await execution_engine.execute_test_case(
            test_case=test_case,
            project_id=99999,
            skip_precondition=False  # 执行前置条件（自动登录）
        )
        end_time = datetime.utcnow()
        
        print("-" * 80)
        print("\n" + "="*80)
        print("测试执行完成")
        print("="*80)
        
        # 7. 输出执行结果
        print(f"\n执行摘要:")
        print(f"  - 执行ID: {result.execution_id}")
        print(f"  - 测试用例: {test_case.case_no} - {test_case.title}")
        print(f"  - 执行状态: {result.status.value.upper()}")
        print(f"  - 执行时间: {(end_time - start_time).total_seconds():.2f} 秒")
        print(f"  - 步骤数量: {len(result.step_results)}")
        
        print(f"\n步骤执行详情:")
        for i, step_result in enumerate(result.step_results, 1):
            status_icon = "✓" if step_result.status == ExecutionStatus.PASSED else "✗"
            print(f"  步骤 {step_result.step_number}: {status_icon} {step_result.action[:50]}...")
            print(f"           状态: {step_result.status.value}, 耗时: {step_result.duration_ms}ms")
            if step_result.error_message:
                print(f"           错误: {step_result.error_message}")
        
        print(f"\n实际结果:")
        print(f"  {result.actual_result}")
        
        if result.error_message:
            print(f"\n错误信息:")
            print(f"  {result.error_message}")
        
        # 8. 保存截图
        print(f"\n保存执行截图...")
        for i, step_result in enumerate(result.step_results):
            if step_result.screenshot:
                screenshot_path = f"screenshot_step_{step_result.step_number}_{result.execution_id}.png"
                with open(screenshot_path, "wb") as f:
                    f.write(step_result.screenshot)
                print(f"  ✓ 步骤 {step_result.step_number} 截图已保存: {screenshot_path}")
        
        # 9. 清理
        print("\n清理测试数据...")
        db.query(TestCase).filter(TestCase.id == 99999).delete()
        db.query(Project).filter(Project.id == 99999).delete()
        db.query(User).filter(User.id == 99999).delete()
        db.commit()
        await browser.close()
        print("✓ 清理完成")
        
        print("\n" + "="*80)
        print("测试结束")
        print("="*80 + "\n")
        
        return result
        
    except Exception as e:
        print(f"\n✗ 测试执行失败: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # 运行真实项目测试
    result = asyncio.run(test_real_project_login())
    
    # 输出最终结果
    print("\n最终执行结果:")
    print(f"  状态: {result.status.value}")
    print(f"  通过步骤: {sum(1 for r in result.step_results if r.status == ExecutionStatus.PASSED)}")
    print(f"  失败步骤: {sum(1 for r in result.step_results if r.status == ExecutionStatus.FAILED)}")
