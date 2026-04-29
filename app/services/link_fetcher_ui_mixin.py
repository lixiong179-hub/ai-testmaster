"""链接UI Mixin - 从Figma/蓝湖等设计工具链接提取UI原型数据。
"""
from typing import Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from loguru import logger
from app.utils.db_time import utcnow


class LinkFetcherUIMixin:
    def fetch_and_parse_ui_mockup(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        success, content, content_type = self.fetch_content(url, auth_type, auth_config)
        if not success:
            return False, {}, content
        description = {
            "url": url,
            "fetch_time": utcnow().isoformat(),
            "content_type": content_type,
            "title": "",
            "pages": [],
            "elements": [],
            "summary": ""
        }
        if content_type == "html":
            try:
                soup = BeautifulSoup(content, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    description["title"] = title_tag.get_text(strip=True)
                nav_links = soup.find_all('a')
                page_list = []
                for link in nav_links[:20]:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if href and text:
                        page_list.append({"text": text, "href": href})
                description["pages"] = page_list
                tables = soup.find_all('table')
                table_data = []
                for table in tables[:5]:
                    rows = []
                    for row in table.find_all('tr')[:10]:
                        cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
                        if cells:
                            rows.append(cells)
                    if rows:
                        table_data.append(rows)
                if table_data:
                    description["tables"] = table_data
                description["summary"] = self._generate_ui_summary(description, content_type)
            except Exception as e:
                logger.warning(f"UI原型解析失败: {str(e)}")
                description["summary"] = content[:500] if content else "无法解析页面内容"
        else:
            description["summary"] = content[:1000] if content else "无内容"
        return True, description, ""

    def _generate_ui_summary(self, description: Dict[str, Any], content_type: str) -> str:
        summary_parts = []
        if description.get("title"):
            summary_parts.append(f"页面标题: {description['title']}")
        if description.get("pages"):
            page_count = len(description["pages"])
            summary_parts.append(f"包含 {page_count} 个页面链接/导航项")
        if description.get("tables"):
            table_count = len(description["tables"])
            summary_parts.append(f"包含 {table_count} 个表格")
        if not summary_parts:
            summary_parts.append(f"内容类型: {content_type}")
            if description.get("url"):
                summary_parts.append(f"来源: {description['url']}")
        return " | ".join(summary_parts)

    def validate_link_access(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        success, content, message = self.fetch_content(url, auth_type, auth_config)
        if success:
            return True, "链接可正常访问"
        else:
            return False, message

    def extract_auth_config_from_form(self, html_content: str, form_index: int = 0) -> Optional[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forms = soup.find_all('form')
            if form_index >= len(forms):
                return None
            form = forms[form_index]
            action = form.get('action', '')
            inputs = {}
            for inp in form.find_all('input'):
                name = inp.get('name', '')
                inp_type = inp.get('type', 'text')
                value = inp.get('value', '')
                if name and inp_type != 'submit' and inp_type != 'button':
                    inputs[name] = value
            return {
                "form_action": action,
                "form_method": form.get('method', 'get').upper(),
                "fields": inputs
            }
        except Exception as e:
            logger.warning(f"表单提取失败: {str(e)}")
            return None
