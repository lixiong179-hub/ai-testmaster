"""
Task 6 双视图管理完整单元测试
严禁使用Mock，必须使用真实MySQL数据库测试
覆盖率要求>=95%
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

import unittest
from datetime import datetime
import json
import pytest

# pytestmark = pytest.mark.skip(reason="数据库DDL不兼容")  # 临时移除排查

# 导入所有模型
from app.models.element_locator import ElementLocator
from app.db.database import PrimarySessionLocal
from app.services.test_case_view_service import TestCaseViewService
from app.models.project import Project
from app.models.test_case import TestCase, TestStep


class TestDualViewComplete(unittest.TestCase):
    """双视图管理完整测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.db = PrimarySessionLocal()
        cls.service = TestCaseViewService(cls.db)
        
        # 创建测试项目
        cls.test_project = Project(
            name=f"双视图测试项目_{int(datetime.now().timestamp())}",
            description="用于测试双视图功能",
            status=1,
            user_id=1
        )
        cls.db.add(cls.test_project)
        cls.db.commit()
        cls.db.refresh(cls.test_project)
        print(f"\n✅ 创建测试项目: {cls.test_project.name} (ID: {cls.test_project.id})")
        
        # 创建测试用例（双视图）
        cls.test_case = TestCase(
            project_id=cls.test_project.id,
            case_no=f"TC_DUAL_{int(datetime.now().timestamp())}",
            module="双视图测试模块",
            title="双视图功能测试用例",
            precondition="1. 系统已登录\n2. 网络连接正常",
            expected_result="操作成功，页面跳转正确",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        cls.db.add(cls.test_case)
        cls.db.flush()
        
        # 创建双视图步骤
        steps_data = [
            # 业务视图 + 技术视图
            {
                "action": "打开登录页面",
                "expected": "页面加载成功",
                "is_business": 1,
                "is_technical": 1,
                "has_locator": 1,
                "locator_status": "located",
                "css": "input#username",
                "xpath": "//input[@id='username']",
                "elem_type": "input"
            },
            # 仅业务视图
            {
                "action": "验证页面标题",
                "expected": "标题显示正确",
                "is_business": 1,
                "is_technical": 0,
                "has_locator": 0,
                "locator_status": "pending",
                "css": None,
                "xpath": None,
                "elem_type": None
            },
            # 业务视图 + 技术视图（无定位）
            {
                "action": "点击登录按钮",
                "expected": "登录成功",
                "is_business": 1,
                "is_technical": 1,
                "has_locator": 0,
                "locator_status": "pending",
                "css": None,
                "xpath": None,
                "elem_type": None
            },
            # 仅技术视图
            {
                "action": "检查网络请求",
                "expected": "请求成功",
                "is_business": 0,
                "is_technical": 1,
                "has_locator": 1,
                "locator_status": "located",
                "css": "button#login",
                "xpath": "//button[@id='login']",
                "elem_type": "button"
            }
        ]
        
        for i, data in enumerate(steps_data, 1):
            step = TestStep(
                test_case_id=cls.test_case.id,
                step_number=i,
                action=data["action"],
                expected_result=data["expected"],
                is_business_view=data["is_business"],
                is_technical_view=data["is_technical"],
                has_locator=data["has_locator"],
                locator_status=data["locator_status"]
            )
            cls.db.add(step)
            cls.db.flush()
            
            # 为有定位的步骤添加定位信息
            if data["has_locator"] == 1:
                locator = ElementLocator(
                    step_id=step.id,
                    css_selector=data["css"],
                    xpath=data["xpath"],
                    element_type=data["elem_type"],
                    ai_confidence=0.95
                )
                cls.db.add(locator)
        
        cls.db.commit()
        cls.db.refresh(cls.test_case)
        print(f"✅ 创建测试用例: {cls.test_case.title} (ID: {cls.test_case.id})")
        print(f"   - 4个步骤（2个双视图 + 1个仅业务 + 1个仅技术）")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        try:
            # 删除定位信息
            steps = cls.db.query(TestStep).filter(
                TestStep.test_case_id == cls.test_case.id
            ).all()
            for step in steps:
                cls.db.query(ElementLocator).filter(
                    ElementLocator.step_id == step.id
                ).delete()
                cls.db.delete(step)
            
            # 删除测试数据
            cls.db.delete(cls.test_case)
            cls.db.delete(cls.test_project)
            cls.db.commit()
            print("✅ 清理测试数据完成")
        except Exception as e:
            cls.db.rollback()
            print(f"⚠️ 清理测试数据失败: {e}")
        finally:
            cls.db.close()
    
    # ==================== 业务视图测试 ====================
    
    def test_01_get_business_view(self):
        """测试1: 获取业务视图"""
        view = self.service.get_business_view(self.test_case.id)
        
        self.assertIsNotNone(view)
        self.assertEqual(view.case_id, self.test_case.id)
        self.assertEqual(view.title, self.test_case.title)
        
        # 业务视图应显示3个步骤（is_business_view=1）
        self.assertEqual(len(view.steps), 3)
        
        # 验证步骤编号
        step_numbers = [s.step_number for s in view.steps]
        self.assertIn(1, step_numbers)  # 双视图
        self.assertIn(2, step_numbers)  # 仅业务
        self.assertIn(3, step_numbers)  # 双视图
        self.assertNotIn(4, step_numbers)  # 仅技术，不应显示
        
        print("✅ 测试1通过: 获取业务视图")
    
    def test_02_export_business_markdown(self):
        """测试2: 导出业务视图为Markdown"""
        markdown = self.service.export_business_view_to_markdown(self.test_case.id)
        
        self.assertIsNotNone(markdown)
        self.assertIn(self.test_case.title, markdown)
        self.assertIn("前置条件", markdown)
        self.assertIn("测试步骤", markdown)
        
        print("✅ 测试2通过: 导出业务视图Markdown")
    
    def test_03_export_business_html(self):
        """测试3: 导出业务视图为HTML"""
        html = self.service.export_business_view_to_html(self.test_case.id)
        
        self.assertIsNotNone(html)
        self.assertIn("<html", html)
        self.assertIn(self.test_case.title, html)
        
        print("✅ 测试3通过: 导出业务视图HTML")
    
    # ==================== 技术视图测试 ====================
    
    def test_04_get_technical_view(self):
        """测试4: 获取技术视图"""
        view_data = self.service.get_technical_view(self.test_case.id)
        
        self.assertIsNotNone(view_data)
        self.assertEqual(view_data["case_id"], self.test_case.id)
        self.assertEqual(view_data["title"], self.test_case.title)
        
        # 技术视图应显示3个步骤（is_technical_view=1）
        self.assertEqual(len(view_data["steps"]), 3)
        
        # 验证步骤编号
        step_numbers = [s["step_number"] for s in view_data["steps"]]
        self.assertIn(1, step_numbers)  # 双视图
        self.assertNotIn(2, step_numbers)  # 仅业务，不应显示
        self.assertIn(3, step_numbers)  # 双视图
        self.assertIn(4, step_numbers)  # 仅技术
        
        # 验证定位信息
        step1 = next(s for s in view_data["steps"] if s["step_number"] == 1)
        self.assertTrue(step1["has_locator"])
        self.assertIsNotNone(step1["locator"])
        self.assertEqual(step1["locator"]["css_selector"], "input#username")
        
        # 验证无定位的步骤
        step3 = next(s for s in view_data["steps"] if s["step_number"] == 3)
        self.assertFalse(step3["has_locator"])
        self.assertIsNone(step3["locator"])
        
        print("✅ 测试4通过: 获取技术视图")
    
    def test_05_get_locator_coverage(self):
        """测试5: 获取定位覆盖率"""
        coverage = self.service.get_locator_coverage(self.test_case.id)
        
        self.assertEqual(coverage["total_steps"], 4)
        self.assertEqual(coverage["located_steps"], 2)  # 步骤1和4
        self.assertEqual(coverage["pending_steps"], 2)  # 步骤2和3
        self.assertEqual(coverage["failed_steps"], 0)
        self.assertAlmostEqual(coverage["coverage_percentage"], 50.0, places=1)
        
        print("✅ 测试5通过: 获取定位覆盖率")
    
    # ==================== Excel导入导出测试 ====================
    
    def test_06_export_to_functional_excel(self):
        """测试6: 导出为功能用例Excel"""
        import pandas as pd

        output_file = "test_export_functional.xlsx"
        success = self.service.export_to_functional_excel(
            [self.test_case.id],
            output_file
        )

        self.assertTrue(success)
        self.assertTrue(os.path.exists(output_file))

        # 验证导出内容
        # 导出格式: 第1行=表头, 第2行=模块分隔行(merged), 第3行=用例数据
        # pandas 读取后: 表头作为 columns, 模块行+用例行作为 data
        df = pd.read_excel(output_file, sheet_name=0)
        self.assertEqual(len(df), 2)  # 模块分隔行 + 用例数据行
        # 用例数据在第二行（iloc[1]），第一行是模块分隔
        # 列名按导出定义: 用例序号/优先级/用例描述/初始条件/操作步骤/期望结果/测试结果/测试人
        self.assertEqual(df.iloc[1]["用例描述"], self.test_case.title)
        self.assertEqual(df.iloc[1]["优先级"], "P0")  # priority=1 -> P0

        # 清理
        os.remove(output_file)

        print("✅ 测试6通过: 导出功能用例Excel")
    
    def test_07_import_functional_excel(self):
        """测试7: 导入功能用例Excel"""
        import pandas as pd
        
        # 创建测试Excel
        df = pd.DataFrame([{
            "标题": "导入测试用例",
            "执行用例ID": "TC_IMPORT_TEST",
            "所属模块": "导入测试模块",
            "前置条件": "导入前置条件",
            "步骤描述": "【1】步骤A\n【2】步骤B",
            "预期结果": "【1】预期A\n【2】预期B",
            "用例类型": "功能测试",
            "用例等级": "P1",
            "用例执行": ""
        }])
        
        test_file = "test_import.xlsx"
        df.to_excel(test_file, sheet_name='测试用例', index=False)
        
        try:
            case_ids = self.service.import_functional_excel(
                test_file,
                self.test_project.id
            )
            
            self.assertTrue(len(case_ids) > 0)
            
            # 验证导入的数据
            imported_case = self.db.query(TestCase).filter(TestCase.id == case_ids[0]).first()
            self.assertEqual(imported_case.title, "导入测试用例")
            self.assertEqual(imported_case.priority, 1)  # P1 -> 1 (P0/P1 同为最高优先级)
            
            # 验证步骤
            steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == case_ids[0]
            ).all()
            self.assertEqual(len(steps), 2)
            
            # 清理导入的数据
            for step in steps:
                self.db.delete(step)
            self.db.delete(imported_case)
            self.db.commit()
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
        
        print("✅ 测试7通过: 导入功能用例Excel")
    
    # ==================== 双视图对比测试 ====================
    
    def test_08_business_vs_technical_view(self):
        """测试8: 对比业务视图和技术视图的差异"""
        business_view = self.service.get_business_view(self.test_case.id)
        technical_data = self.service.get_technical_view(self.test_case.id)
        
        # 业务视图：3个步骤（1,2,3）
        self.assertEqual(len(business_view.steps), 3)
        
        # 技术视图：3个步骤（1,3,4）
        self.assertEqual(len(technical_data["steps"]), 3)
        
        # 业务视图包含步骤2（仅业务）
        business_step_numbers = [s.step_number for s in business_view.steps]
        self.assertIn(2, business_step_numbers)
        
        # 技术视图包含步骤4（仅技术）
        technical_step_numbers = [s["step_number"] for s in technical_data["steps"]]
        self.assertIn(4, technical_step_numbers)
        
        # 两者都包含步骤1和3（双视图）
        self.assertIn(1, business_step_numbers)
        self.assertIn(1, technical_step_numbers)
        self.assertIn(3, business_step_numbers)
        self.assertIn(3, technical_step_numbers)
        
        print("✅ 测试8通过: 业务视图vs技术视图对比")
    
    def test_09_view_statistics(self):
        """测试9: 视图统计信息"""
        stats = self.service.get_view_statistics(self.test_case.id)
        
        self.assertEqual(stats["total_steps"], 4)
        self.assertEqual(stats["business_view_steps"], 3)
        self.assertEqual(stats["technical_view_steps"], 3)
        self.assertEqual(stats["located_steps"], 2)
        
        print("✅ 测试9通过: 视图统计信息")
    
    # ==================== 边界条件测试 ====================
    
    def test_10_empty_case_views(self):
        """测试10: 空用例的视图处理"""
        # 创建空用例
        empty_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_EMPTY_{int(datetime.now().timestamp())}",
            module="空用例模块",
            title="空用例测试",
            precondition="",
            expected_result="",
            priority=2,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(empty_case)
        self.db.commit()
        self.db.refresh(empty_case)
        
        try:
            # 业务视图
            business_view = self.service.get_business_view(empty_case.id)
            self.assertEqual(len(business_view.steps), 0)
            
            # 技术视图
            technical_data = self.service.get_technical_view(empty_case.id)
            self.assertEqual(len(technical_data["steps"]), 0)
            self.assertEqual(technical_data["locator_coverage"], 0.0)
            
            # 覆盖率
            coverage = self.service.get_locator_coverage(empty_case.id)
            self.assertEqual(coverage["total_steps"], 0)
            self.assertEqual(coverage["coverage_percentage"], 0.0)
            
        finally:
            self.db.delete(empty_case)
            self.db.commit()
        
        print("✅ 测试10通过: 空用例视图处理")
    
    def test_11_nonexistent_case(self):
        """测试11: 不存在用例的处理"""
        # 业务视图
        business_view = self.service.get_business_view(999999)
        self.assertIsNone(business_view)
        
        # 技术视图
        technical_data = self.service.get_technical_view(999999)
        self.assertIsNone(technical_data)
        
        # 覆盖率
        coverage = self.service.get_locator_coverage(999999)
        self.assertEqual(coverage["total_steps"], 0)
        
        print("✅ 测试11通过: 不存在用例处理")
    
    def test_12_all_steps_business_only(self):
        """测试12: 所有步骤仅业务视图"""
        # 创建仅业务视图的用例
        business_only_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_BUS_ONLY_{int(datetime.now().timestamp())}",
            module="仅业务模块",
            title="仅业务视图用例",
            precondition="",
            expected_result="",
            priority=2,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(business_only_case)
        self.db.flush()
        
        # 添加仅业务视图的步骤
        for i in range(1, 3):
            step = TestStep(
                test_case_id=business_only_case.id,
                step_number=i,
                action=f"业务步骤{i}",
                expected_result=f"业务预期{i}",
                is_business_view=1,
                is_technical_view=0,
                has_locator=0,
                locator_status="pending"
            )
            self.db.add(step)
        
        self.db.commit()
        self.db.refresh(business_only_case)
        
        try:
            # 业务视图应有2个步骤
            business_view = self.service.get_business_view(business_only_case.id)
            self.assertEqual(len(business_view.steps), 2)
            
            # 技术视图应有0个步骤
            technical_data = self.service.get_technical_view(business_only_case.id)
            self.assertEqual(len(technical_data["steps"]), 0)
            
        finally:
            # 清理
            steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == business_only_case.id
            ).all()
            for step in steps:
                self.db.delete(step)
            self.db.delete(business_only_case)
            self.db.commit()
        
        print("✅ 测试12通过: 仅业务视图步骤")


if __name__ == '__main__':
    unittest.main(verbosity=2)
