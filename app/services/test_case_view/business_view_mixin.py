"""业务视图Mixin - 提供业务视图的查询和导出功能。

业务视图面向产品经理和业务人员，仅展示操作步骤和预期结果，
不暴露技术细节。支持导出为Markdown和HTML格式。
"""
from typing import Optional
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.services.test_case_view.models import BusinessStepView, BusinessTestCaseView


class BusinessViewMixin:

    def get_business_view(self, test_case_id: int) -> Optional[BusinessTestCaseView]:
        """获取测试用例的业务视图，仅展示is_business_view=1的步骤。"""
        test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not test_case:
            logger.warning(f"测试用例不存在: {test_case_id}")
            return None

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
        """导出业务视图为Markdown格式文档。"""
        view = self.get_business_view(test_case_id)
        if not view:
            return ""

        lines = [f"# {view.title}", "", f"**用例编号:** {view.case_no}", f"**用例ID:** {view.case_id}", ""]

        if view.description:
            lines.extend(["## 描述", "", view.description, ""])
        if view.precondition:
            lines.extend(["## 前置条件", "", view.precondition, ""])

        lines.extend(["## 测试步骤", ""])
        for step in view.steps:
            lines.extend([
                f"### 步骤 {step.step_number}", "",
                f"**操作:** {step.action}", f"**预期结果:** {step.expected_result}", ""
            ])

        return "\n".join(lines)

    def export_business_view_to_html(self, test_case_id: int) -> str:
        """导出业务视图为HTML格式文档，所有文本内容经HTML转义防止XSS。"""
        import html as html_module

        view = self.get_business_view(test_case_id)
        if not view:
            return ""

        steps_html = ""
        for step in view.steps:
            action_escaped = html_module.escape(step.action)
            expected_escaped = html_module.escape(step.expected_result)
            steps_html += (
                f'<div class="step"><h3>步骤 {step.step_number}</h3>'
                f'<p><strong>操作:</strong> {action_escaped}</p>'
                f'<p><strong>预期结果:</strong> {expected_escaped}</p></div>'
            )

        title_escaped = html_module.escape(view.title)
        case_no_escaped = html_module.escape(view.case_no)
        desc_escaped = html_module.escape(view.description) if view.description else ""
        prec_escaped = html_module.escape(view.precondition) if view.precondition else ""

        desc_section = f'<h2>描述</h2><p>{desc_escaped}</p>' if view.description else ''
        prec_section = f'<h2>前置条件</h2><p>{prec_escaped}</p>' if view.precondition else ''

        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{title_escaped}</title>'
            f'<style>body{{font-family:Arial,sans-serif;margin:40px}}h1{{color:#333}}'
            f'.step{{margin:20px 0;padding:15px;border:1px solid #ddd;border-radius:5px}}'
            f'.step h3{{margin-top:0;color:#666}}</style></head>'
            f'<body><h1>{title_escaped}</h1>'
            f'<p><strong>用例编号:</strong> {case_no_escaped}</p>'
            f'<p><strong>用例ID:</strong> {view.case_id}</p>'
            f'{desc_section}{prec_section}'
            f'<h2>测试步骤</h2>{steps_html}</body></html>'
        )
