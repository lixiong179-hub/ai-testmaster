"""选择器注册表 - 管理页面元素选择器的注册与查询。
"""
import json
import os
from typing import Optional, Dict, List
from loguru import logger


class SelectorRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._selectors: Dict[str, Dict[str, str]] = {}
        self._keyword_mapping: Dict[str, List[str]] = {}
        self._load_default_selectors()
        self._load_custom_selectors()

    def _load_default_selectors(self):
        self._selectors = {
            "洪恩管理系统": {
                "用户名": "input[type=text]:first-of-type, .el-input__inner:first-of-type, input[name=username], input[id=username]",
                "密码": "input[type=password], .el-input__inner[type=password], input[name=password], input[id=password]",
                "验证码": "input[placeholder*=验证码], .el-input__inner[placeholder*=验证码], input[name=captcha], input[name=code]",
                "登录按钮": ".el-button--primary, button[type=submit], .login-btn, .btn-primary",
                "提交按钮": "button[type=submit], .el-button--primary, .submit-btn",
                "保存按钮": ".el-button--primary, button:has-text('保存'), .save-btn",
            },
            "default": {
                "用户名": "input[name=username], input[id=username], input[type=text]:first-of-type, .el-input__inner:first-of-type",
                "密码": "input[name=password], input[id=password], input[type=password], .el-input__inner[type=password]",
                "验证码": "input[name=captcha], input[name=code], input[placeholder*=验证码], .el-input__inner[placeholder*=验证码]",
                "登录按钮": "button[type=submit], .login-btn, .btn-primary, .el-button--primary",
                "提交按钮": "button[type=submit], .el-button--primary, .submit-btn",
                "保存按钮": ".el-button--primary, button:has-text('保存'), .save-btn",
            },
        }

        self._keyword_mapping = {
            "用户名": ["用户名", "账号", "account", "username"],
            "密码": ["密码", "password", "口令"],
            "验证码": ["验证码", "captcha", "code", "校验码"],
            "登录按钮": ["登录", "login", "登陆", "signin"],
            "提交按钮": ["提交", "submit", "确认", "confirm"],
            "保存按钮": ["保存", "save", "储存"],
        }

    def _load_custom_selectors(self):
        config_path = os.environ.get("SELECTOR_CONFIG_PATH", "config/selectors.json")
        if not os.path.isabs(config_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, config_path)

        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                custom_config = json.load(f)

            if not isinstance(custom_config, dict):
                logger.warning(f"自定义选择器配置格式错误: {config_path}")
                return

            for page_title, selectors in custom_config.items():
                if not isinstance(selectors, dict):
                    continue
                if page_title not in self._selectors:
                    self._selectors[page_title] = {}
                for keyword, selector in selectors.items():
                    self._selectors[page_title][keyword] = selector

            keyword_config = custom_config.get("_keyword_mapping")
            if isinstance(keyword_config, dict):
                for key, aliases in keyword_config.items():
                    if isinstance(aliases, list):
                        self._keyword_mapping[key] = aliases

            logger.info(f"已加载自定义选择器配置: {config_path}")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"加载自定义选择器配置失败: {e}")

    def _match_keyword(self, action_description: str) -> Optional[str]:
        for keyword, aliases in self._keyword_mapping.items():
            for alias in aliases:
                if alias.lower() in action_description.lower():
                    return keyword
        return None

    def get_selector(self, page_title: Optional[str], action_description: str) -> Optional[str]:
        keyword = self._match_keyword(action_description)
        if not keyword:
            return None

        if page_title and page_title in self._selectors:
            page_selectors = self._selectors[page_title]
            if keyword in page_selectors:
                return page_selectors[keyword]

        default_selectors = self._selectors.get("default", {})
        return default_selectors.get(keyword)

    def get_all_selectors(self, page_title: Optional[str] = None) -> Dict[str, str]:
        if page_title and page_title in self._selectors:
            page_selectors = self._selectors[page_title]
            default_selectors = self._selectors.get("default", {})
            merged = dict(default_selectors)
            merged.update(page_selectors)
            return merged
        return dict(self._selectors.get("default", {}))

    def register_selector(self, page_title: str, keyword: str, selector: str) -> None:
        if page_title not in self._selectors:
            self._selectors[page_title] = {}
        self._selectors[page_title][keyword] = selector

    def register_keyword_alias(self, keyword: str, alias: str) -> None:
        if keyword not in self._keyword_mapping:
            self._keyword_mapping[keyword] = []
        if alias not in self._keyword_mapping[keyword]:
            self._keyword_mapping[keyword].append(alias)
