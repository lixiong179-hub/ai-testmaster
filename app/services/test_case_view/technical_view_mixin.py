"""技术视图Mixin - 提供技术视图的查询和导出功能。

技术视图面向测试工程师和自动化执行，展示定位信息、测试数据
和执行参数。支持导出为JSON和Python脚本格式。
"""
import re
from typing import Optional, Dict, Any
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.element_locator import ElementLocator
from app.models.test_data import TestData


class TechnicalViewMixin:

    def get_technical_view(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        """获取测试用例的技术视图，包含定位信息、测试数据和前置条件步骤。

        技术视图数据组装:
            1. 查询is_technical_view=1的步骤
            2. 批量查询步骤关联的定位信息
            3. 批量查询步骤关联的测试数据
            4. 查询前置条件步骤及其定位信息
            5. 计算定位覆盖率
        """
        test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not test_case:
            logger.warning(f"测试用例不存在: {test_case_id}")
            return None

        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id,
            TestStep.is_technical_view == 1
        ).order_by(TestStep.step_number).all()

        step_ids = [s.id for s in steps]
        locators, test_data_map = self._batch_query_step_data(step_ids)

        technical_steps, located_count = self._build_technical_steps(steps, locators, test_data_map)
        locator_coverage = float((located_count / len(steps) * 100) if steps else 0.0)

        precondition_steps_data = self._build_precondition_steps(test_case_id)

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
            "execution_history": []
        }

    def _batch_query_step_data(self, step_ids: list) -> tuple:
        """批量查询步骤的定位信息和测试数据，避免N+1查询。"""
        locators = {}
        test_data_map: Dict[int, list] = {}
        if not step_ids:
            return locators, test_data_map

        locator_list = self.db.query(ElementLocator).filter(
            ElementLocator.step_id.in_(step_ids)
        ).all()
        locators = {l.step_id: l for l in locator_list}

        td_list = self.db.query(TestData).filter(
            TestData.step_id.in_(step_ids)
        ).order_by(TestData.sort_order).all()
        for td in td_list:
            if td.step_id not in test_data_map:
                test_data_map[td.step_id] = []
            test_data_map[td.step_id].append(td.to_dict())

        return locators, test_data_map

    def _build_technical_steps(self, steps, locators: dict, test_data_map: dict) -> tuple:
        """组装技术步骤数据列表。"""
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

        return technical_steps, located_count

    def _build_precondition_steps(self, test_case_id: int) -> list:
        """构建前置条件步骤数据。"""
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
                pc_best = pc_locator.get_best_locator()
                pc_step_data["locator"] = {
                    "css_selector": str(pc_locator.css_selector) if pc_locator.css_selector else None,
                    "xpath": str(pc_locator.xpath) if pc_locator.xpath else None,
                    "element_type": str(pc_locator.element_type) if pc_locator.element_type else None,
                    "ai_coordinate": pc_locator.ai_coordinate,
                    "confidence": float(pc_locator.ai_confidence) if pc_locator.ai_confidence else None,
                    "locator_type": pc_best.get("type") if pc_best else None,
                    "locator_value": str(pc_best.get("value")) if pc_best and pc_best.get("value") is not None else None
                }
            precondition_steps_data.append(pc_step_data)

        return precondition_steps_data

    def export_technical_view_to_json(self, test_case_id: int) -> Dict[str, Any]:
        """导出技术视图为JSON格式，用于自动化执行引擎消费。"""
        view = self.get_technical_view(test_case_id)
        if not view:
            return {}
        return view

    def export_technical_view_to_python(self, test_case_id: int) -> str:
        """导出技术视图为Python自动化测试脚本（Playwright框架）。"""
        view = self.get_technical_view(test_case_id)
        if not view:
            return ""

        lines = [
            "# 自动生成的测试脚本",
            f"# 用例: {view.get('title', '')}",
            f"# 编号: {view.get('case_no', '')}",
            "", "import pytest",
            "from playwright.async_api import async_playwright", "",
            f"@pytest.mark.asyncio",
            f"async def test_{view.get('case_no', 'unknown').lower()}():",
            '    async with async_playwright() as p:',
            '        browser = await p.chromium.launch(headless=False)',
            '        page = await browser.new_page()', ""
        ]

        for step in view.get('steps', []):
            action = step.get('action', '')
            safe_action = action.replace('"', '\\"').replace("'", "\\'")
            lines.append(f"        # 步骤 {step.get('step_number')}: {safe_action}")

            locator = step.get('locator', {}) or {}
            css_selector = locator.get('css_selector') if locator else None

            if step.get('has_locator') and css_selector:
                safe_css = css_selector.replace("'", "\\'").replace('"', '\\"')
                lines.append(f"        # CSS选择器: {safe_css}")
                if "点击" in action or "click" in action.lower():
                    lines.append(f"        await page.click('{safe_css}')")
                elif "输入" in action or "fill" in action.lower():
                    text_match = re.search(r'["\']([^"\']+)["\']', action)
                    text = text_match.group(1) if text_match else "test"
                    safe_text = text.replace("'", "\\'").replace('"', '\\"')
                    lines.append(f"        await page.fill('{safe_css}', '{safe_text}')")
            else:
                lines.append(f"        pass")
            lines.append("")

        lines.extend(["        await browser.close()", ""])
        return "\n".join(lines)
