"""test_case_generation 内容清洗器（防 Prompt 注入）。"""
import re


# ── 内容清洗器（防 Prompt 注入） ──
class ContentSanitizer:
    """内容清洗器 - 防止 Prompt 注入攻击，对用户输入清洗转义。"""

    INJECTION_PATTERNS = [
        r'```system', r'```prompt', r'忽略.*指令', r'忽略.*规则',
        r'你是一个.*而不是', r'你现在是', r'/system', r'<system>', r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容防止 Prompt 注入。空串原样返回，控制字符剥离，超长截断标注。"""
        if not content:
            return ""
        content = re.sub(r'```(?:json|yaml|xml|markdown|prompt|system)', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
        for pattern in cls.INJECTION_PATTERNS:
            content = re.sub(pattern, '[已过滤]', content, flags=re.IGNORECASE)
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n[内容已截断，原长度: {len(content)}字符]"
        return content

    @classmethod
    def sanitize_for_log(cls, content: str, max_length: int = 200) -> str:
        """清洗内容用于日志记录（更严格截断，单行化）。"""
        if not content:
            return ""
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content
