"""网址驱动快速测试 - URL 自动建项。

从用户提供的网址自动创建 Project 并填充三套环境配置，无需用户手填表单。

设计要点：
- 项目名推导：{域名}_{YYYYMMDD}（去 www. 前缀），重名追加 _1/_2 递增序号；
- 三套环境 URL 自动填充：test/staging/prod 均填入用户提供的 URL；
- 标记 project.source = "url_quick_test" 区分传统手动建项；
- URL 校验仅接受 http/https scheme，非法抛 ValueError（上层 API 转 422）；
- 查重使用 SQLAlchemy ORM 参数化查询（LIKE 占位符绑定），杜绝 SQL 注入；
- DB 操作异常捕获并回滚 session 后向上抛出，保证事务一致性。
"""
import json
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy.orm import Session

from app.models.project import Project

# 项目来源标识：url_quick_test 标记由网址驱动快速测试流程创建的项目
SOURCE_URL_QUICK_TEST = "url_quick_test"
# 允许的 URL scheme 白名单，禁止 file/ftp/javascript 等非 http scheme
_ALLOWED_SCHEMES = ("http", "https")
# 三套环境名，与 web_env_configs JSON 结构保持一致
_ENV_NAMES = ("test", "staging", "prod")


class AutoProjectBuilder:
    """URL 自动建项构建器。

    从网址推导项目名、填充三套环境配置并持久化 Project，标记来源为
    url_quick_test。供 QuickLauncher 编排入口在站点探索前调用，
    消除用户手填项目表单的 7 步操作。

    边界场景：
    - 非法 URL（缺 scheme/netloc 或非 http/https）抛 ValueError；
    - 同 user 下重名按 _1/_2 递增去重，跨 user 互不影响；
    - DB 异常回滚 session 后向上抛出，不残留半成品项目。
    """

    def build(
        self,
        url: str,
        description: Optional[str],
        user_id: int,
        session: Session,
    ) -> Project:
        """从 URL 自动创建 Project 并持久化。

        Args:
            url: 被测站点 URL，必须为 http/https 且含域名。
            description: 项目描述，可选；为 None 表示不填描述。
            user_id: 项目所有者用户 ID，用于租户隔离与重名查重。
            session: SQLAlchemy 会话，由调用方管理事务生命周期。

        Returns:
            Project: 已持久化的项目对象（含 id 与刷新后的字段）。

        Raises:
            ValueError: URL 非法（为空/缺 scheme/netloc/scheme 非 http/https）。
            Exception: DB 持久化失败时回滚 session 后向上抛出。
        """
        normalized_url = self._validate_url(url)
        domain = self._extract_domain(normalized_url)
        date_str = datetime.now().strftime("%Y%m%d")
        base_name = f"{domain}_{date_str}"
        final_name = self._dedupe_name(base_name, user_id, session)
        env_configs = self._build_env_configs(normalized_url)

        project = Project(
            name=final_name,
            user_id=user_id,
            description=description,
            project_type="web",
            source=SOURCE_URL_QUICK_TEST,
            web_env_configs=json.dumps(env_configs),
        )
        try:
            session.add(project)
            session.commit()
            session.refresh(project)
        except Exception as exc:
            session.rollback()
            logger.error(
                f"URL 自动建项持久化失败: url={normalized_url} user_id={user_id} err={exc}"
            )
            raise
        logger.info(
            f"URL 自动建项成功: project_id={project.id} name={final_name} user_id={user_id}"
        )
        return project

    @staticmethod
    def _validate_url(url: str) -> str:
        """校验 URL 合法性，仅接受 http/https 且含 netloc。

        Args:
            url: 原始 URL 输入。

        Returns:
            str: 去除首尾空白后的合法 URL。

        Raises:
            ValueError: URL 为空、缺 scheme、netloc 为空或 scheme 非 http/https。
        """
        if not url or not isinstance(url, str) or not url.strip():
            raise ValueError("URL 不能为空")
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.strip()
        if scheme not in _ALLOWED_SCHEMES:
            raise ValueError(f"URL scheme 非法，仅支持 http/https: {scheme or '缺失'}")
        if not netloc:
            raise ValueError("URL 缺少域名（netloc）")
        return url.strip()

    @staticmethod
    def _extract_domain(url: str) -> str:
        """从 URL 提取域名并去掉 www. 前缀与端口/userinfo。

        Args:
            url: 已校验的合法 URL。

        Returns:
            str: 小写域名（去 www. 前缀），如 shop.example.com。
        """
        netloc = urlparse(url).netloc
        host = netloc.split("@")[-1].split(":")[0].lower()
        if host.startswith("www."):
            host = host[4:]
        return host

    @staticmethod
    def _dedupe_name(base_name: str, user_id: int, session: Session) -> str:
        """按 user_id 隔离查重，重名时追加递增序号。

        查询当前用户下 name 以 base_name 开头的项目（ORM LIKE 占位符绑定，
        杜绝 SQL 注入），再在 Python 侧精确匹配 base_name 或 base_name_N
        解析已有最大序号 +1，规避 LIKE 中 _ 通配符误匹配。

        Args:
            base_name: 基础项目名（域名_日期）。
            user_id: 用户 ID，租户隔离查重边界。
            session: SQLAlchemy 会话。

        Returns:
            str: 去重后的最终项目名（无重名则原样返回）。
        """
        pattern = f"{base_name}%"
        rows = (
            session.query(Project.name)
            .filter(
                Project.user_id == user_id,
                Project.name.like(pattern),
            )
            .all()
        )
        existing_names = {row[0] for row in rows if row[0]}
        if base_name not in existing_names:
            return base_name
        max_suffix = 0
        prefix = f"{base_name}_"
        for name in existing_names:
            if name.startswith(prefix):
                suffix = name[len(prefix):]
                if suffix.isdigit():
                    max_suffix = max(max_suffix, int(suffix))
        return f"{base_name}_{max_suffix + 1}"

    @staticmethod
    def _build_env_configs(url: str) -> dict:
        """构建三套环境配置，test/staging/prod 均填入该 URL。

        用户可在后续通过 project_config 端点修改 staging/prod 账号与 URL。
        存储格式与 create_project/update_project_config 端点保持一致
        （经 json.dumps 序列化为 JSON 字符串写入 web_env_configs 列）。

        Args:
            url: 已校验的站点 URL。

        Returns:
            dict: 形如 {"test": {"url": url, "username": None, "password": None}, ...}。
        """
        return {
            env: {"url": url, "username": None, "password": None}
            for env in _ENV_NAMES
        }
