"""测试用例视图服务 - 支持业务视图和技术视图的双视图管理。

本模块实现测试用例的双视图管理体系，业务视图面向产品经理和业务人员，
技术视图面向测试工程师和自动化执行。同时提供多种导出格式和Excel导入功能。

核心类:
    - TestCaseViewService: 视图服务主类
    - BusinessStepView: 业务视图步骤数据类
    - TechnicalStepView: 技术视图步骤数据类
    - BusinessTestCaseView: 业务视图用例数据类
    - TechnicalTestCaseView: 技术视图用例数据类

视图体系设计:
    业务视图:
        - 面向产品经理、业务人员、第三方验收
        - 仅展示操作步骤和预期结果
        - 支持导出为Markdown/HTML格式
        - 步骤通过is_business_view字段控制可见性

    技术视图:
        - 面向测试工程师、自动化执行
        - 展示定位信息、测试数据、执行参数
        - 支持导出为JSON/Python脚本格式
        - 步骤通过is_technical_view字段控制可见性
        - 包含定位覆盖率统计

依赖关系:
    - app.models.test_case: TestCase/TestStep/TestCasePreconditionStep ORM模型
    - app.models.element_locator: ElementLocator ORM模型
    - app.models.test_data: TestData ORM模型
    - app.models.enums: LocatorStatus枚举
    - app.models.project: Project ORM模型

安全设计:
    - HTML导出时对所有文本内容进行HTML转义，防止XSS
    - Excel导入时严格项目隔离，防止数据越权
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re
from sqlalchemy.orm import Session
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.models.project import Project
from app.models.test_data import TestData


@dataclass
class BusinessStepView:
    """业务视图步骤 - 面向非技术人员的步骤展示。

    仅包含操作描述和预期结果，不暴露技术细节。
    """
    step_number: int
    action: str
    expected_result: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应序列化。"""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "expected_result": self.expected_result
        }


@dataclass
class TechnicalStepView:
    """技术视图步骤 - 面向测试工程师的步骤展示。

    包含定位信息、元素类型和AI坐标等技术细节，
    用于自动化执行和定位调试。
    """
    step_number: int
    action: str
    expected_result: str
    has_locator: bool
    locator_status: str
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    ai_coordinate: Optional[Dict[str, float]] = None
    element_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，仅包含非空的技术字段。"""
        result = {
            "step_number": self.step_number,
            "action": self.action,
            "expected_result": self.expected_result,
            "has_locator": self.has_locator,
            "locator_status": self.locator_status
        }
        if self.css_selector:
            result["css_selector"] = self.css_selector
        if self.xpath:
            result["xpath"] = self.xpath
        if self.ai_coordinate:
            result["ai_coordinate"] = self.ai_coordinate
        if self.element_type:
            result["element_type"] = self.element_type
        return result


@dataclass
class BusinessTestCaseView:
    """业务视图测试用例 - 面向非技术人员的用例展示。

    包含用例基本信息和业务步骤列表，不暴露技术细节。
    """
    case_id: int
    case_no: str
    title: str
    description: Optional[str]
    precondition: Optional[str]
    steps: List[BusinessStepView] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，包含步骤总数统计。"""
        return {
            "case_id": self.case_id,
            "case_no": self.case_no,
            "title": self.title,
            "description": self.description,
            "precondition": self.precondition,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": len(self.steps)
        }


@dataclass
class TechnicalTestCaseView:
    """技术视图测试用例 - 面向测试工程师的用例展示。

    包含技术步骤列表和定位覆盖率统计。
    """
    case_id: int
    case_no: str
    title: str
    steps: List[TechnicalStepView] = field(default_factory=list)
    locator_coverage: float = 0.0  # 定位覆盖率百分比

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，覆盖率保留一位小数。"""
        return {
            "case_id": self.case_id,
            "case_no": self.case_no,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": len(self.steps),
            "locator_coverage": f"{self.locator_coverage:.1f}%"
        }


class TestCaseViewService:
    """测试用例视图服务 - 提供业务视图和技术视图的查询、导出与导入功能。

    职责:
        - 业务视图查询与导出（Markdown/HTML）
        - 技术视图查询与导出（JSON/Python脚本）
        - 视图配置管理（步骤可见性控制）
        - Excel导入导出（标准格式/功能用例格式）
        - 定位覆盖率统计

    使用场景:
        - 用例详情页展示双视图
        - 用例导出为不同格式
        - 第三方用例Excel导入
        - 视图可见性批量配置

    设计意图:
        视图服务与CRUD层职责划分:
        - TestCaseViewService: 视图逻辑（数据组装、格式转换、导出）
        - test_case CRUD: 数据持久化（创建、查询、更新、删除）
    """

    def __init__(self, db: Session):
        """初始化视图服务。

        Args:
            db: 数据库会话，贯穿视图查询生命周期。
        """
        self.db = db

    # ==================== 业务视图方法 ====================

    def get_business_view(self, test_case_id: int) -> Optional[BusinessTestCaseView]:
        """获取测试用例的业务视图，仅展示is_business_view=1的步骤。

        Args:
            test_case_id: 测试用例ID。

        Returns:
            BusinessTestCaseView实例，用例不存在时返回None。
        """
        test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not test_case:
            logger.warning(f"测试用例不存在: {test_case_id}")
            return None

        # 查询业务视图可见的步骤
        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id,
            TestStep.is_business_view == 1
        ).order_by(TestStep.step_number).all()

        business_steps = [
            BusinessStepView(
                step_number=int(s.step_number),
                action=str(s.action),
                expected_result=str(s.expected_result)
            )
            for s in steps
        ]

        return BusinessTestCaseView(
            case_id=int(test_case.id),
            case_no=str(test_case.case_no),
            title=str(test_case.title),
            description=str(getattr(test_case, 'description', test_case.title)),
            precondition=str(test_case.precondition) if test_case.precondition else None,
            steps=business_steps
        )

    def export_business_view_to_markdown(self, test_case_id: int) -> str:
        """导出业务视图为Markdown格式文档。

        Args:
            test_case_id: 测试用例ID。

        Returns:
            Markdown格式的业务视图文档，用例不存在时返回空字符串。
        """
        view = self.get_business_view(test_case_id)
        if not view:
            return ""

        lines = [
            f"# {view.title}",
            "",
            f"**用例编号:** {view.case_no}",
            f"**用例ID:** {view.case_id}",
            ""
        ]

        if view.description:
            lines.extend(["## 描述", "", view.description, ""])

        if view.precondition:
            lines.extend(["## 前置条件", "", view.precondition, ""])

        lines.extend(["## 测试步骤", ""])

        for step in view.steps:
            lines.extend([
                f"### 步骤 {step.step_number}",
                "",
                f"**操作:** {step.action}",
                f"**预期结果:** {step.expected_result}",
                ""
            ])

        return "\n".join(lines)

    def export_business_view_to_html(self, test_case_id: int) -> str:
        """导出业务视图为HTML格式文档，所有文本内容经HTML转义防止XSS。

        Args:
            test_case_id: 测试用例ID。

        Returns:
            HTML格式的业务视图文档，用例不存在时返回空字符串。
        """
        import html as html_module

        view = self.get_business_view(test_case_id)
        if not view:
            return ""

        # 构建步骤HTML，所有文本内容进行HTML转义
        steps_html = ""
        for step in view.steps:
            action_escaped = html_module.escape(step.action)
            expected_escaped = html_module.escape(step.expected_result)
            steps_html += f"""
            <div class="step">
                <h3>步骤 {step.step_number}</h3>
                <p><strong>操作:</strong> {action_escaped}</p>
                <p><strong>预期结果:</strong> {expected_escaped}</p>
            </div>
            """

        # HTML转义所有动态内容
        title_escaped = html_module.escape(view.title)
        case_no_escaped = html_module.escape(view.case_no)
        description_escaped = html_module.escape(view.description) if view.description else ""
        precondition_escaped = html_module.escape(view.precondition) if view.precondition else ""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title_escaped}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .step {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .step h3 {{ margin-top: 0; color: #666; }}
            </style>
        </head>
        <body>
            <h1>{title_escaped}</h1>
            <p><strong>用例编号:</strong> {case_no_escaped}</p>
            <p><strong>用例ID:</strong> {view.case_id}</p>
            {f'<h2>描述</h2><p>{description_escaped}</p>' if view.description else ''}
            {f'<h2>前置条件</h2><p>{precondition_escaped}</p>' if view.precondition else ''}
            <h2>测试步骤</h2>
            {steps_html}
        </body>
        </html>
        """

        return html

    # ==================== 技术视图方法 ====================

    def get_technical_view(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """获取测试用例的技术视图，包含定位信息、测试数据和前置条件步骤。

        技术视图数据组装:
            1. 查询is_technical_view=1的步骤
            2. 批量查询步骤关联的定位信息
            3. 批量查询步骤关联的测试数据
            4. 查询前置条件步骤及其定位信息
            5. 计算定位覆盖率

        Args:
            test_case_id: 测试用例ID。

        Returns:
            技术视图数据字典，包含:
                - case_id/case_no/title: 用例基本信息
                - module/precondition/expected_result: 用例属性
                - priority/case_type: 优先级和类型
                - precondition_steps: 前置条件步骤列表（含定位信息）
                - steps: 技术步骤列表（含定位信息和测试数据）
                - locator_coverage: 定位覆盖率百分比
                - execution_history: 执行历史（预留）
            用例不存在时返回None。
        """
        test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not test_case:
            logger.warning(f"测试用例不存在: {test_case_id}")
            return None

        # 查询技术视图可见的步骤
        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id,
            TestStep.is_technical_view == 1
        ).order_by(TestStep.step_number).all()

        # 批量查询定位信息，避免N+1查询
        step_ids = [s.id for s in steps]
        locators = {}
        test_data_map: Dict[int, list] = {}
        if step_ids:
            locator_list = self.db.query(ElementLocator).filter(
                ElementLocator.step_id.in_(step_ids)
            ).all()
            locators = {l.step_id: l for l in locator_list}

            # 批量查询测试数据
            td_list = self.db.query(TestData).filter(
                TestData.step_id.in_(step_ids)
            ).order_by(TestData.sort_order).all()
            for td in td_list:
                if td.step_id not in test_data_map:
                    test_data_map[td.step_id] = []
                test_data_map[td.step_id].append(td.to_dict())

        # 组装技术步骤数据
        technical_steps = []
        located_count = 0

        for step in steps:
            locator = locators.get(step.id)

            if step.has_locator:
                located_count += 1

            step_data = {
                "step_id": step.id,
                "step_number": int(step.step_number),
                "action": str(step.action),
                "expected_result": str(step.expected_result),
                "action_type": str(step.action_type) if step.action_type else "",
                "input_value": str(step.input_value) if step.input_value else "",
                "target_element": str(step.target_element) if step.target_element else "",
                "has_locator": bool(step.has_locator == 1),
                "locator_status": str(step.locator_status),
                "locator": None,
                "test_data": test_data_map.get(step.id, [])
            }

            # 附加定位信息
            if locator:
                best_locator = locator.get_best_locator()
                step_data["locator"] = {
                    "css_selector": str(locator.css_selector) if locator.css_selector else None,
                    "xpath": str(locator.xpath) if locator.xpath else None,
                    "element_type": str(locator.element_type) if locator.element_type else None,
                    "ai_coordinate": locator.ai_coordinate,
                    "confidence": float(locator.ai_confidence) if locator.ai_confidence else None,
                    "locator_type": best_locator.get("type") if best_locator else None,
                    "locator_value": str(best_locator.get("value")) if best_locator and best_locator.get("value") is not None else None
                }

            technical_steps.append(step_data)

        # 计算定位覆盖率
        locator_coverage = float((located_count / len(steps) * 100) if steps else 0.0)

        # 查询前置条件步骤及定位信息
        pc_steps = self.db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.test_case_id == test_case_id
        ).order_by(TestCasePreconditionStep.step_number).all()

        pc_step_ids = [s.id for s in pc_steps]
        pc_locators = {}
        if pc_step_ids:
            pc_locator_list = self.db.query(ElementLocator).filter(
                ElementLocator.precondition_step_id.in_(pc_step_ids)
            ).all()
            pc_locators = {l.precondition_step_id: l for l in pc_locator_list}

        # 组装前置条件步骤数据
        precondition_steps_data = []
        for pc_step in pc_steps:
            pc_locator = pc_locators.get(pc_step.id)
            pc_step_data = {
                "id": pc_step.id,
                "step_number": int(pc_step.step_number),
                "action": str(pc_step.action),
                "expected_result": str(pc_step.expected_result),
                "action_type": str(pc_step.action_type) if pc_step.action_type else "",
                "input_value": str(pc_step.input_value) if pc_step.input_value else "",
                "target_element": str(pc_step.target_element) if pc_step.target_element else "",
                "has_locator": bool(pc_step.has_locator == 1),
                "locator_status": str(pc_step.locator_status),
                "locator": None
            }
            if pc_locator:
                pc_best_locator = pc_locator.get_best_locator()
                pc_step_data["locator"] = {
                    "css_selector": str(pc_locator.css_selector) if pc_locator.css_selector else None,
                    "xpath": str(pc_locator.xpath) if pc_locator.xpath else None,
                    "element_type": str(pc_locator.element_type) if pc_locator.element_type else None,
                    "ai_coordinate": pc_locator.ai_coordinate,
                    "confidence": float(pc_locator.ai_confidence) if pc_locator.ai_confidence else None,
                    "locator_type": pc_best_locator.get("type") if pc_best_locator else None,
                    "locator_value": str(pc_best_locator.get("value")) if pc_best_locator and pc_best_locator.get("value") is not None else None
                }
            precondition_steps_data.append(pc_step_data)

        return {
            "case_id": int(test_case.id),
            "case_no": str(test_case.case_no),
            "title": str(test_case.title),
            "module": str(test_case.module) if test_case.module else None,
            "precondition": str(test_case.precondition) if test_case.precondition else None,
            "expected_result": str(test_case.expected_result) if test_case.expected_result else None,
            "priority": int(test_case.priority) if test_case.priority else None,
            "case_type": str(test_case.case_type) if test_case.case_type else None,
            "precondition_steps": precondition_steps_data,
            "steps": technical_steps,
            "locator_coverage": locator_coverage,
            "execution_history": []  # 预留执行历史字段
        }

    def export_technical_view_to_json(self, test_case_id: int) -> Dict[str, Any]:
        """导出技术视图为JSON格式，用于自动化执行引擎消费。

        Args:
            test_case_id: 测试用例ID。

        Returns:
            JSON格式的技术视图数据字典，用例不存在时返回空字典。
        """
        view = self.get_technical_view(test_case_id)
        if not view:
            return {}
        return view

    def export_technical_view_to_python(self, test_case_id: int) -> str:
        """导出技术视图为Python自动化测试脚本（Playwright框架）。

        根据步骤的定位信息和操作类型生成对应的Playwright代码:
            - 点击操作 -> page.click()
            - 输入操作 -> page.fill()
            - 无定位信息 -> pass占位

        Args:
            test_case_id: 测试用例ID。

        Returns:
            Python自动化测试脚本字符串，用例不存在时返回空字符串。
        """
        view = self.get_technical_view(test_case_id)
        if not view:
            return ""

        lines = [
            "# 自动生成的测试脚本",
            f"# 用例: {view.get('title', '')}",
            f"# 编号: {view.get('case_no', '')}",
            "",
            "import pytest",
            "from playwright.async_api import async_playwright",
            "",
            f"@pytest.mark.asyncio",
            f"async def test_{view.get('case_no', 'unknown').lower()}():",
            '    async with async_playwright() as p:',
            '        browser = await p.chromium.launch(headless=False)',
            '        page = await browser.new_page()',
            ""
        ]

        for step in view.get('steps', []):
            lines.append(f"        # 步骤 {step.get('step_number')}: {step.get('action')}")

            # 从locator对象获取CSS选择器
            locator = step.get('locator', {}) or {}
            css_selector = locator.get('css_selector') if locator else None

            if step.get('has_locator') and css_selector:
                lines.append(f"        # CSS选择器: {css_selector}")
                if "点击" in step.get('action', '') or "click" in step.get('action', '').lower():
                    lines.append(f"        await page.click('{css_selector}')")
                elif "输入" in step.get('action', '') or "fill" in step.get('action', '').lower():
                    # 从操作描述中提取输入文本
                    text_match = re.search(r'["\']([^"\']+)["\']', step.get('action', ''))
                    text = text_match.group(1) if text_match else "test"
                    lines.append(f"        await page.fill('{css_selector}', '{text}')")
            else:
                lines.append(f"        pass")

            lines.append("")

        lines.extend([
            "        await browser.close()",
            ""
        ])

        return "\n".join(lines)

    # ==================== 视图管理方法 ====================

    def update_step_view_config(
        self,
        step_id: int,
        is_business_view: Optional[int] = None,
        is_technical_view: Optional[int] = None
    ) -> bool:
        """更新单个步骤的视图可见性配置。

        Args:
            step_id: 步骤ID。
            is_business_view: 是否在业务视图显示（0/1），可选。
            is_technical_view: 是否在技术视图显示（0/1），可选。

        Returns:
            更新成功返回True，步骤不存在返回False。
        """
        step = self.db.query(TestStep).filter(TestStep.id == step_id).first()
        if not step:
            logger.warning(f"步骤不存在: {step_id}")
            return False

        if is_business_view is not None:
            step.is_business_view = is_business_view

        if is_technical_view is not None:
            step.is_technical_view = is_technical_view

        self.db.commit()
        logger.info(f"更新步骤 {step_id} 视图配置成功")
        return True

    def batch_update_view_config(
        self,
        test_case_id: int,
        view_type: str,
        visible: bool
    ) -> int:
        """批量更新测试用例所有步骤的视图可见性配置。

        Args:
            test_case_id: 测试用例ID。
            view_type: 视图类型，'business'或'technical'。
            visible: 是否可见。

        Returns:
            更新的步骤数量，视图类型无效时返回0。
        """
        value = 1 if visible else 0

        if view_type == "business":
            count = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).update({"is_business_view": value})
        elif view_type == "technical":
            count = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).update({"is_technical_view": value})
        else:
            logger.error(f"未知的视图类型: {view_type}")
            return 0

        self.db.commit()
        logger.info(f"批量更新测试用例 {test_case_id} 的 {view_type} 视图配置: {count} 个步骤")
        return count

    def get_view_statistics(self, test_case_id: int) -> Dict[str, Any]:
        """获取测试用例的视图统计信息。

        Args:
            test_case_id: 测试用例ID。

        Returns:
            统计信息字典，包含:
                - total_steps: 总步骤数
                - business_view_steps: 业务视图可见步骤数
                - technical_view_steps: 技术视图可见步骤数
                - located_steps: 已定位步骤数
                - locator_coverage: 定位覆盖率百分比
        """
        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id
        ).all()

        total = len(steps)
        business_visible = sum(1 for s in steps if s.is_business_view == 1)
        technical_visible = sum(1 for s in steps if s.is_technical_view == 1)
        has_locator_count = sum(1 for s in steps if s.has_locator == 1)

        return {
            "total_steps": total,
            "business_view_steps": business_visible,
            "technical_view_steps": technical_visible,
            "located_steps": has_locator_count,
            "locator_coverage": f"{has_locator_count / total * 100:.1f}%" if total > 0 else "0%"
        }

    def get_locator_coverage(self, test_case_id: int) -> Dict[str, Any]:
        """获取测试用例的定位覆盖率统计。

        Args:
            test_case_id: 测试用例ID。

        Returns:
            覆盖率统计字典，包含:
                - total_steps: 总步骤数
                - located_steps: 已定位步骤数
                - pending_steps: 待定位步骤数
                - failed_steps: 定位失败步骤数
                - coverage_percentage: 覆盖率百分比
        """
        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id
        ).all()

        total = len(steps)
        located = sum(1 for s in steps if s.has_locator == 1)
        pending = sum(1 for s in steps if s.locator_status == LocatorStatus.PENDING.value)
        failed = sum(1 for s in steps if s.locator_status == LocatorStatus.FAILED.value)

        return {
            "total_steps": total,
            "located_steps": located,
            "pending_steps": pending,
            "failed_steps": failed,
            "coverage_percentage": (located / total * 100) if total > 0 else 0.0
        }

    # ==================== Excel导入导出方法 ====================

    def export_to_excel(self, test_case_id: int, file_path: str) -> bool:
        """导出测试用例为Excel格式（双Sheet：用例信息+测试步骤）。

        Args:
            test_case_id: 测试用例ID。
            file_path: 导出文件路径。

        Returns:
            导出成功返回True，失败返回False。
        """
        try:
            import pandas as pd

            test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
            if not test_case:
                logger.warning(f"测试用例不存在: {test_case_id}")
                return False

            # 查询所有步骤
            steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).order_by(TestStep.step_number).all()

            # 准备步骤数据
            data = []
            for step in steps:
                # 查询定位信息
                locator = self.db.query(ElementLocator).filter(
                    ElementLocator.step_id == step.id
                ).first()

                row = {
                    "步骤编号": step.step_number,
                    "操作步骤": step.action,
                    "预期结果": step.expected_result,
                    "业务视图": "是" if step.is_business_view == 1 else "否",
                    "技术视图": "是" if step.is_technical_view == 1 else "否",
                    "已定位": "是" if step.has_locator == 1 else "否",
                    "定位状态": step.locator_status,
                    "CSS选择器": locator.css_selector if locator else "",
                    "XPath": locator.xpath if locator else "",
                    "元素类型": locator.element_type if locator else "",
                }
                data.append(row)

            # 创建DataFrame
            df = pd.DataFrame(data)

            # 写入Excel（双Sheet格式）
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='测试步骤', index=False)

                case_info = pd.DataFrame([{
                    "用例编号": test_case.case_no,
                    "用例标题": test_case.title,
                    "所属模块": test_case.module,
                    "前置条件": test_case.precondition or "",
                    "预期结果": test_case.expected_result or "",
                    "优先级": test_case.priority,
                    "总步骤数": len(steps)
                }])
                case_info.to_excel(writer, sheet_name='用例信息', index=False)

            logger.info(f"测试用例 {test_case_id} 导出Excel成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return False

    def export_to_functional_excel(self, test_case_ids: List[int], file_path: str) -> bool:
        """导出测试用例为第三方公司功能用例Excel格式。

        格式特点:
            - 单Sheet格式
            - 纯功能描述，无技术定位信息
            - 步骤使用【序号】格式合并
            - 优先级转换为P0/P1/P2/P3格式

        Args:
            test_case_ids: 测试用例ID列表。
            file_path: 导出文件路径。

        Returns:
            导出成功返回True，失败返回False。
        """
        try:
            import pandas as pd

            test_cases = self.db.query(TestCase).filter(
                TestCase.id.in_(test_case_ids)
            ).all()

            if not test_cases:
                logger.warning(f"未找到测试用例: {test_case_ids}")
                return False

            data = []
            for tc in test_cases:
                steps = self.db.query(TestStep).filter(
                    TestStep.test_case_id == tc.id
                ).order_by(TestStep.step_number).all()

                # 构建功能用例格式的步骤描述
                step_desc = self._build_functional_steps(steps)
                expected = self._build_functional_expected(steps)

                # 优先级转换：1/2/3/4 -> P0/P1/P2/P3
                priority_map = {1: 'P0', 2: 'P1', 3: 'P2', 4: 'P3'}
                priority = priority_map.get(tc.priority, 'P2')

                # 用例类型转换
                case_type = 'UI自动化' if tc.case_type in ('ui_automation', 'UI', '功能', '功能测试', 'functional') else 'API自动化'

                row = {
                    "标题": tc.title,
                    "执行用例ID": tc.case_no,
                    "所属模块": tc.module or "默认模块",
                    "前置条件": tc.precondition or "",
                    "步骤描述": step_desc,
                    "预期结果": expected or tc.expected_result or "",
                    "用例类型": case_type,
                    "用例等级": priority,
                    "用例执行": ""
                }
                data.append(row)

            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='测试用例', index=False)

            logger.info(f"导出功能用例Excel成功: {file_path}, 共{len(data)}条用例")
            return True

        except Exception as e:
            logger.error(f"导出功能用例Excel失败: {e}")
            return False

    def _build_functional_steps(self, steps: List[TestStep]) -> str:
        """将步骤列表构建为功能用例格式的步骤描述（【序号】格式）。

        Args:
            steps: 步骤列表。

        Returns:
            功能用例格式的步骤描述，如"【1】打开页面\n【2】点击按钮"。
        """
        if not steps:
            return ""

        parts = []
        for step in steps:
            parts.append(f"【{step.step_number}】{step.action}")

        return "\n".join(parts)

    def _build_functional_expected(self, steps: List[TestStep]) -> str:
        """将步骤列表构建为功能用例格式的预期结果（【序号】格式）。

        Args:
            steps: 步骤列表。

        Returns:
            功能用例格式的预期结果，跳过无预期结果的步骤。
        """
        if not steps:
            return ""

        parts = []
        for step in steps:
            if step.expected_result:
                parts.append(f"【{step.step_number}】{step.expected_result}")

        return "\n".join(parts)

    def import_from_excel(self, file_path: str, project_id: int, user_id: int = 1) -> Optional[int]:
        """从标准格式Excel导入测试用例，严格项目隔离。

        支持的标准Excel格式:
            - Sheet1(用例信息): 用例编号、标题、模块、前置条件等
            - Sheet2(测试步骤): 步骤编号、操作步骤、预期结果等

        数据隔离规则:
            1. 用例编号全局唯一，重复时自动添加后缀
            2. 所有数据关联到指定的project_id
            3. 导入失败时自动回滚，不产生脏数据

        Args:
            file_path: Excel文件路径。
            project_id: 项目ID（必须，确保数据隔离）。
            user_id: 用户ID，默认1。

        Returns:
            导入的测试用例ID，失败返回None。
        """
        try:
            import pandas as pd

            # 验证项目是否存在
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return None

            # 读取Excel双Sheet
            case_info_df = pd.read_excel(file_path, sheet_name='用例信息')
            steps_df = pd.read_excel(file_path, sheet_name='测试步骤')

            if case_info_df.empty or steps_df.empty:
                logger.error("Excel文件格式不正确，缺少必要的数据")
                return None

            case_info = case_info_df.iloc[0]

            # 生成项目内唯一的用例编号
            original_case_no = str(case_info.get('用例编号', ''))
            case_no = self._generate_unique_case_no(project_id, original_case_no)

            # 创建测试用例，严格关联项目
            test_case = TestCase(
                project_id=project_id,
                case_no=case_no,
                module=str(case_info.get('所属模块', '默认模块')),
                title=str(case_info.get('用例标题', '未命名用例')),
                precondition=str(case_info.get('前置条件', '')),
                expected_result=str(case_info.get('预期结果', '')),
                priority=int(case_info.get('优先级', 2)),
                case_type="ui_automation",
                generate_status=1,
                steps_json=[]
            )
            self.db.add(test_case)
            self.db.flush()

            # 创建测试步骤
            for _, row in steps_df.iterrows():
                step = TestStep(
                    test_case_id=test_case.id,
                    step_number=int(row.get('步骤编号', 1)),
                    action=str(row.get('操作步骤', '')),
                    expected_result=str(row.get('预期结果', '')),
                    is_business_view=1 if str(row.get('业务视图', '是')) == '是' else 0,
                    is_technical_view=1 if str(row.get('技术视图', '是')) == '是' else 0,
                    has_locator=1 if str(row.get('已定位', '否')) == '是' else 0,
                    locator_status=str(row.get('定位状态', LocatorStatus.PENDING.value))
                )
                self.db.add(step)

                # 如果有定位信息，创建定位记录
                import math
                css_val = row.get('CSS选择器', '')
                xpath_val = row.get('XPath', '')
                type_val = row.get('元素类型', '')

                # 处理NaN值
                css_selector = str(css_val) if pd.notna(css_val) and css_val != '' else ''
                xpath = str(xpath_val) if pd.notna(xpath_val) and xpath_val != '' else ''
                element_type = str(type_val) if pd.notna(type_val) and type_val != '' else ''

                if css_selector or xpath:
                    self.db.flush()
                    locator = ElementLocator(
                        step_id=step.id,
                        css_selector=css_selector if css_selector else None,
                        xpath=xpath if xpath else None,
                        element_type=element_type if element_type else None
                    )
                    self.db.add(locator)

            self.db.commit()
            logger.info(f"从Excel导入测试用例成功: {test_case.id} (项目: {project_id})")
            return test_case.id

        except Exception as e:
            self.db.rollback()
            logger.error(f"从Excel导入失败: {e}")
            return None

    def _generate_unique_case_no(self, project_id: int, original_case_no: str) -> str:
        """生成全局唯一的用例编号，处理编号冲突。

        策略:
            1. 原编号不存在 -> 直接使用
            2. 原编号已存在 -> 添加项目ID和序号后缀
            3. 无原编号 -> 自动生成时间戳编号

        Args:
            project_id: 项目ID。
            original_case_no: 原始用例编号。

        Returns:
            全局唯一的用例编号。
        """
        if not original_case_no:
            import time
            timestamp = int(time.time())
            return f"TC{project_id}_{timestamp}"

        # 全局唯一性检查
        existing = self.db.query(TestCase).filter(
            TestCase.case_no == original_case_no
        ).first()

        if not existing:
            return original_case_no

        # 编号冲突时添加后缀
        counter = 1
        while True:
            new_case_no = f"{original_case_no}_{project_id}_{counter}"
            existing = self.db.query(TestCase).filter(
                TestCase.case_no == new_case_no
            ).first()
            if not existing:
                logger.info(f"用例编号 '{original_case_no}' 已存在，自动重命名为 '{new_case_no}'")
                return new_case_no
            counter += 1

    def validate_excel_format(self, file_path: str) -> Dict[str, Any]:
        """验证标准格式Excel文件是否正确。

        检查项:
            - 文件是否存在
            - 是否包含"用例信息"和"测试步骤"两个Sheet
            - 必要列是否存在

        Args:
            file_path: Excel文件路径。

        Returns:
            验证结果字典，包含valid/errors/warnings字段。
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": []
        }

        try:
            import pandas as pd
            import os

            if not os.path.exists(file_path):
                result["errors"].append("文件不存在")
                return result

            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names

            # 检查必要的Sheet
            if '用例信息' not in sheet_names:
                result["errors"].append("缺少'用例信息'sheet")

            if '测试步骤' not in sheet_names:
                result["errors"].append("缺少'测试步骤'sheet")

            if result["errors"]:
                return result

            # 检查用例信息Sheet的必要列
            case_info_df = pd.read_excel(file_path, sheet_name='用例信息')
            if case_info_df.empty:
                result["errors"].append("'用例信息'sheet为空")
            else:
                required_case_columns = ['用例标题']
                for col in required_case_columns:
                    if col not in case_info_df.columns:
                        result["errors"].append(f"'用例信息'sheet缺少'{col}'列")

            # 检查测试步骤Sheet的必要列
            steps_df = pd.read_excel(file_path, sheet_name='测试步骤')
            if steps_df.empty:
                result["errors"].append("'测试步骤'sheet为空")
            else:
                required_step_columns = ['步骤编号', '操作步骤', '预期结果']
                for col in required_step_columns:
                    if col not in steps_df.columns:
                        result["errors"].append(f"'测试步骤'sheet缺少'{col}'列")

            if not result["errors"]:
                result["valid"] = True
                result["case_count"] = len(case_info_df)
                result["step_count"] = len(steps_df)

            return result

        except Exception as e:
            result["errors"].append(f"验证失败: {str(e)}")
            return result

    def import_functional_excel(self, file_path: str, project_id: int, module: str = "默认模块") -> Optional[int]:
        """从第三方公司功能用例格式Excel导入测试用例。

        格式特点:
            - 单Sheet格式（测试用例）
            - 纯功能描述，无技术定位信息
            - 支持多步骤合并（步骤描述使用【序号】格式）
            - 必要字段：标题、步骤描述、预期结果

        Args:
            file_path: Excel文件路径。
            project_id: 项目ID。
            module: 默认模块名称，默认"默认模块"。

        Returns:
            导入的第一个测试用例ID，失败返回None。
        """
        try:
            import pandas as pd

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return None

            # 读取单Sheet Excel
            df = pd.read_excel(file_path, sheet_name=0)

            if df.empty:
                logger.error("Excel文件为空")
                return None

            # 标准化列名（处理可能的空格）
            df.columns = [str(col).strip() for col in df.columns]

            imported_cases = []

            for _, row in df.iterrows():
                title = str(row.get('标题', '')).strip()
                if not title:
                    continue

                case_no = str(row.get('执行用例ID', '')).strip()
                if not case_no:
                    case_no = f"TC{project_id}_{int(datetime.now().timestamp())}"

                # 生成唯一编号
                case_no = self._generate_unique_case_no(project_id, case_no)

                # 解析各字段
                group = str(row.get('所属模块', row.get('所属分组', module))).strip()
                precondition = str(row.get('前置条件', '')).strip()
                step_desc = str(row.get('步骤描述', '')).strip()
                expected = str(row.get('预期结果', '')).strip()
                case_type = str(row.get('用例类型', 'UI自动化')).strip()
                priority_str = str(row.get('用例等级', 'P2')).strip()

                # 优先级转换：P0/P1/P2/P3 -> 1/2/3/4
                priority_map = {'P0': 1, 'P1': 2, 'P2': 3, 'P3': 4}
                priority = priority_map.get(priority_str.upper(), 2)

                # 解析步骤描述和预期结果
                steps = self._parse_functional_steps(step_desc, expected)

                # 创建测试用例
                test_case = TestCase(
                    project_id=project_id,
                    case_no=case_no,
                    module=group,
                    title=title,
                    precondition=precondition,
                    expected_result=expected.replace('\\n', '\n'),
                    priority=priority,
                    case_type="ui_automation" if case_type in ('UI自动化', '功能测试', 'UI', '功能') else "api_automation",
                    generate_status=1,
                    steps_json=[s.to_dict() for s in steps]
                )
                self.db.add(test_case)
                self.db.flush()

                # 创建测试步骤
                for i, step_info in enumerate(steps, 1):
                    step = TestStep(
                        test_case_id=test_case.id,
                        step_number=i,
                        action=step_info.action,
                        expected_result=step_info.expected_result,
                        is_business_view=1,  # 纯功能用例，只显示在业务视图
                        is_technical_view=0,  # 不显示在技术视图
                        has_locator=0,
                        locator_status=LocatorStatus.PENDING.value
                    )
                    self.db.add(step)

                imported_cases.append(test_case.id)

            self.db.commit()
            logger.info(f"从功能用例Excel导入成功: {len(imported_cases)}条用例")
            return imported_cases[0] if imported_cases else None

        except Exception as e:
            self.db.rollback()
            logger.error(f"从功能用例Excel导入失败: {e}")
            return None

    def _parse_functional_steps(self, step_desc: str, expected: str) -> List[BusinessStepView]:
        """解析功能用例的步骤描述和预期结果。

        支持两种格式:
            1. 【序号】格式：如"【1】步骤1【2】步骤2"
            2. 换行分隔格式：如"步骤1\n步骤2\n步骤3"

        Args:
            step_desc: 步骤描述文本。
            expected: 预期结果文本。

        Returns:
            解析后的BusinessStepView列表，无法解析时返回单条默认步骤。
        """
        steps = []

        # 尝试按【序号】格式解析
        step_pattern = r'【(\d+)】([^【]*?)(?=【\d+】|$)'
        expected_pattern = r'【(\d+)】([^【]*?)(?=【\d+】|$)'

        step_matches = re.findall(step_pattern, step_desc, re.DOTALL)
        expected_matches = re.findall(expected_pattern, expected, re.DOTALL)

        if step_matches:
            # 使用【序号】格式，按序号匹配步骤和预期结果
            expected_dict = {int(m[0]): m[1].strip() for m in expected_matches}

            for num, action in step_matches:
                step_num = int(num)
                action = action.strip().replace('\\n', '\n')
                exp = expected_dict.get(step_num, '').replace('\\n', '\n')

                steps.append(BusinessStepView(
                    step_number=step_num,
                    action=action,
                    expected_result=exp
                ))
        else:
            # 按换行符分割
            import re as regex
            step_lines = [s.strip() for s in regex.split(r'\r?\n', step_desc) if s.strip()]
            expected_lines = [s.strip() for s in regex.split(r'\r?\n', expected) if s.strip()]

            for i, action in enumerate(step_lines, 1):
                exp = expected_lines[i-1] if i <= len(expected_lines) else ''
                steps.append(BusinessStepView(
                    step_number=i,
                    action=action,
                    expected_result=exp
                ))

        return steps if steps else [BusinessStepView(1, step_desc, expected)]

    def validate_functional_excel(self, file_path: str) -> Dict[str, Any]:
        """验证第三方公司功能用例Excel格式是否正确。

        检查项:
            - 文件是否存在
            - Excel是否为空
            - 必要列（标题、步骤描述、预期结果）是否存在

        Args:
            file_path: Excel文件路径。

        Returns:
            验证结果字典，包含valid/errors/warnings/format_type字段。
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "format_type": "functional"
        }

        try:
            import pandas as pd
            import os

            if not os.path.exists(file_path):
                result["errors"].append("文件不存在")
                return result

            df = pd.read_excel(file_path, sheet_name=0)

            if df.empty:
                result["errors"].append("Excel文件为空")
                return result

            # 标准化列名
            df.columns = [str(col).strip() for col in df.columns]

            # 检查必要字段
            required_columns = ['标题', '步骤描述', '预期结果']
            for col in required_columns:
                if col not in df.columns:
                    result["errors"].append(f"缺少必要列: '{col}'")

            # 检查可选字段
            optional_columns = ['执行用例ID', '所属模块', '前置条件', '用例类型', '用例等级']
            for col in optional_columns:
                if col not in df.columns:
                    result["warnings"].append(f"缺少可选列: '{col}'")

            if not result["errors"]:
                result["valid"] = True
                result["case_count"] = len(df)

            return result

        except Exception as e:
            result["errors"].append(f"验证失败: {str(e)}")
            return result
