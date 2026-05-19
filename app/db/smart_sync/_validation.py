import re


class _ValidationMixin:
    COLUMN_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    COLUMN_TYPE_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_() ,.]*$')
    SQL_INJECTION_PATTERN = re.compile(r'[;\'"\\-]', re.IGNORECASE)

    def _validate_column_name(self, name: str) -> bool:
        if not name or not isinstance(name, str):
            return False
        return bool(self.COLUMN_NAME_PATTERN.match(name))
