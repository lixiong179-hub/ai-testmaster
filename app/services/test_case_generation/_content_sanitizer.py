"""内容清洗器 - 防止 Prompt 注入攻击。

从 base_mixin.py 拆分而来，对用户输入的内容进行清洗和转义，
确保 AI 输出安全可靠。

业务原因：base_mixin.py 单文件超过 350 行限制，将独立职责的
ContentSanitizer 拆分为独立模块，便于单独维护与测试。
"""
import re


class ContentSanitizer:
    """
    内容清洗器 - 防止Prompt注入攻击
    对用户输入的内容进行清洗和转义，确保AI输出安全可靠
    """

    INJECTION_PATTERNS = [
        r'```system',
        r'```prompt',
        r'忽略.*指令',
        r'忽略.*规则',
        r'你是一个.*而不是',
        r'你现在是',
        r'/system',
        r'<system>',
        r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容，防止Prompt注入。

        边界场景:
            - None 或空字符串原样返回空串
            - 控制字符（0x00-0x08, 0x0b, 0x0c, 0x0e-0x1f）一律剥离
            - 超长内容截断并标注原长度，避免静默丢失

        Args:
            content: 待清洗的原始内容。
            max_length: 最大长度，超出后截断，默认 10000 字符。

        Returns:
            清洗后的安全字符串。
        """
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
        """清洗内容用于日志记录（更严格的截断）。

        Args:
            content: 待记录的原始内容。
            max_length: 日志最大长度，超出后截断并追加省略号。

        Returns:
            适合写入日志的单行字符串。
        """
        if not content:
            return ""
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content


__all__ = ["ContentSanitizer"]
