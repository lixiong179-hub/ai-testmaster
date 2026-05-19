"""
报告工具模块

提供测试报告的生成和导出功能，支持HTML和PDF两种输出格式。
HTML报告包含测试摘要、结果分布饼图、用例详情表格和环境信息。

核心类：
    - ReportUtils: 报告工具类，所有方法均为静态方法

报告生成流程：
    1. generate_html_report: 根据报告数据生成HTML内容
    2. generate_pdf_report: 将HTML转换为PDF（依赖weasyprint）
    3. export_report: 统一导出入口，根据格式选择HTML或PDF

可选依赖：
    - weasyprint: PDF生成引擎，未安装时调用generate_pdf_report会抛出ImportError
    - matplotlib: 饼图生成引擎，未安装时使用透明占位图替代

依赖：
    - loguru.logger: 日志记录（通过延迟导入避免循环依赖）
"""
from datetime import datetime
from typing import Dict, Any
from io import BytesIO
import base64

# 完全避免模块级别导入weasyprint，防止安装缺失导致整个模块无法加载


class ReportUtils:
    """报告工具类

    提供测试报告的HTML生成、PDF转换和统一导出功能。
    所有方法均为静态方法，无需实例化即可使用。

    报告结构：
        - 测试摘要：总用例数、通过/失败/跳过数、通过率
        - 结果分布图：matplotlib饼图（base64嵌入HTML）
        - 用例详情：表格展示每个用例的ID、名称、状态和错误信息
        - 环境信息：生成时间、平台、版本
    """

    # 1x1透明PNG的base64编码 — 当matplotlib未安装时作为图表的安全占位符
    _TRANSPARENT_PNG_BASE64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/x8AAwMB/6X+0bQAAAAASUVORK5CYII="
    )

    @staticmethod
    def generate_html_report(report_data: Dict[str, Any], report_name: str) -> str:
        """生成HTML格式报告

        将报告数据填充到HTML模板中，生成包含测试摘要、饼图、
        用例详情表格和环境信息的完整HTML页面。

        Args:
            report_data: 报告数据字典，包含：
                - statistics: 测试统计（total/passed/failed/skipped/pass_rate）
                - test_cases: 测试用例列表（case_id/case_name/status/error_message）
                - summary: 报告摘要文本
                - environment: 环境信息（generate_time/platform/version）
            report_name: 报告名称，显示在页面标题

        Returns:
            str: 完整的HTML字符串
        """
        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{report_name}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; text-align: center; }
                h2 { color: #555; margin-top: 30px; }
                .summary { background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 30px; }
                .stats { display: flex; justify-content: space-around; margin: 20px 0; }
                .stat-item { text-align: center; padding: 15px; background-color: #e8f4f8; border-radius: 5px; }
                .stat-value { font-size: 24px; font-weight: bold; }
                .stat-label { font-size: 14px; color: #666; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .status-passed { color: green; font-weight: bold; }
                .status-failed { color: red; font-weight: bold; }
                .status-skipped { color: orange; font-weight: bold; }
                .chart-container { margin: 30px 0; text-align: center; }
                .error-message { background-color: #ffebee; padding: 10px; margin: 5px 0; border-left: 4px solid #f44336; }
            </style>
        </head>
        <body>
            <h1>{report_name}</h1>
            <div class="summary">
                <h2>测试摘要</h2>
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value">{total}</div>
                        <div class="stat-label">总用例数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{passed}</div>
                        <div class="stat-label">通过</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{failed}</div>
                        <div class="stat-label">失败</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{skipped}</div>
                        <div class="stat-label">跳过</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{pass_rate}%</div>
                        <div class="stat-label">通过率</div>
                    </div>
                </div>
                <p>{summary}</p>
            </div>
            
            <div class="chart-container">
                <h2>测试结果分布</h2>
                <img src="data:image/png;base64,{chart_base64}" alt="测试结果分布图">
            </div>
            
            <h2>测试用例详情</h2>
            <table>
                <tr>
                    <th>用例ID</th>
                    <th>用例名称</th>
                    <th>状态</th>
                    <th>错误信息</th>
                </tr>
                {test_cases_rows}
            </table>
            
            <h2>环境信息</h2>
            <p>生成时间: {generate_time}</p>
            <p>平台: {platform}</p>
            <p>版本: {version}</p>
        </body>
        </html>
        """

        # 准备数据
        statistics = report_data.get('statistics', {})
        test_cases = report_data.get('test_cases', [])
        environment = report_data.get('environment', {})

        # 生成测试用例行
        test_cases_rows = []
        for case in test_cases:
            status_class = f"status-{case['status']}"
            error_message = case.get('error_message', '')
            error_html = f"<div class='error-message'>{error_message}</div>" if error_message else "-"
            row = f"""
            <tr>
                <td>{case['case_id']}</td>
                <td>{case['case_name']}</td>
                <td class="{status_class}">{case['status']}</td>
                <td>{error_html}</td>
            </tr>
            """
            test_cases_rows.append(row)

        # 生成图表
        chart_base64 = ReportUtils._generate_pie_chart(
            [statistics.get('passed', 0), statistics.get('failed', 0), statistics.get('skipped', 0)],
            ['通过', '失败', '跳过']
        )

        # 填充模板
        replacements = {
            '{report_name}': report_name,
            '{total}': str(statistics.get('total', 0)),
            '{passed}': str(statistics.get('passed', 0)),
            '{failed}': str(statistics.get('failed', 0)),
            '{blocked}': str(statistics.get('blocked', 0)),
            '{pass_rate}': str(statistics.get('pass_rate', 0)),
            '{summary}': report_data.get('summary', ''),
            '{chart_base64}': chart_base64,
            '{test_cases_rows}': ''.join(test_cases_rows),
            '{generate_time}': environment.get('generate_time', datetime.now().isoformat()),
            '{platform}': environment.get('platform', 'AI TestMaster'),
            '{version}': environment.get('version', '1.0.0'),
        }
        html_content = html_template
        for placeholder, value in replacements.items():
            html_content = html_content.replace(placeholder, value)

        return html_content

    @staticmethod
    def generate_pdf_report(html_content: str) -> bytes:
        """将HTML内容转换为PDF格式

        使用weasyprint引擎将HTML渲染为PDF，并注入中文字体支持。
        weasyprint为可选依赖，未安装时抛出ImportError。

        Args:
            html_content: HTML格式的内容字符串

        Returns:
            bytes: PDF文件的字节数据

        Raises:
            ImportError: weasyprint未安装时抛出
        """
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise ImportError("weasyprint is not available, cannot generate PDF reports")
        
        # 添加中文字体支持
        css = CSS(string="""
            @font-face {
                font-family: 'SimHei';
                src: local('SimHei'), local('黑体');
            }
            body {
                font-family: 'SimHei', Arial, sans-serif;
            }
        """)
        
        # 生成PDF
        pdf_bytes = HTML(string=html_content).write_pdf(stylesheets=[css])
        return pdf_bytes

    @staticmethod
    def _generate_pie_chart(data: list, labels: list) -> str:
        """生成饼图并返回base64编码

        使用matplotlib生成测试结果分布饼图，将图片编码为base64字符串
        嵌入HTML的img标签中。matplotlib为可选依赖，未安装时返回透明占位图。

        Args:
            data: 饼图数据列表（如[通过数, 失败数, 跳过数]）
            labels: 对应的标签列表（如['通过', '失败', '跳过']）

        Returns:
            str: base64编码的PNG图片字符串
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            # Optional dependency not available; keep report generation working.
            return ReportUtils._TRANSPARENT_PNG_BASE64

        # 创建饼图
        plt.figure(figsize=(8, 6))
        colors = ['#4CAF50', '#F44336', '#FF9800']
        plt.pie(data, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')  # 保证饼图是圆的

        # 保存到内存
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close()

        # 转换为base64
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return image_base64

    @staticmethod
    def export_report(report_data: Dict[str, Any], report_name: str, format: str) -> tuple:
        """导出报告
        
        Args:
            report_data: 报告数据
            report_name: 报告名称
            format: 导出格式，支持 'pdf' 和 'html'
            
        Returns:
            (content, content_type, filename): 报告内容、内容类型、文件名
        """
        if format == 'html':
            content = ReportUtils.generate_html_report(report_data, report_name)
            content_type = 'text/html'
            filename = f"{report_name}.html"
        elif format == 'pdf':
            html_content = ReportUtils.generate_html_report(report_data, report_name)
            content = ReportUtils.generate_pdf_report(html_content)
            content_type = 'application/pdf'
            filename = f"{report_name}.pdf"
        else:
            raise ValueError(f"Unsupported format: {format}")

        return content, content_type, filename
