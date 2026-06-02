import os
os.environ.setdefault("ENVIRONMENT", "test")
from sqlalchemy import create_engine, text
from app.core.config import settings

TEST_DB_URL = settings.DATABASE_URL.replace("/ai_testmaster", "/ai_testmaster_test") if "/ai_testmaster" in settings.DATABASE_URL else settings.DATABASE_URL
engine = create_engine(TEST_DB_URL)
with engine.connect() as conn:
    result = conn.execute(text("SHOW COLUMNS FROM generation_batches LIKE 'history_asset_ids_json'"))
    if result.fetchone() is None:
        conn.execute(text("ALTER TABLE generation_batches ADD COLUMN history_asset_ids_json JSON NOT NULL COMMENT '本次选择的历史资产ID列表'"))
        conn.commit()
        print("Added history_asset_ids_json column")
    else:
        print("Column already exists")

    result = conn.execute(text("SHOW TABLES LIKE 'history_assets'"))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE history_assets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                user_id INT NOT NULL,
                asset_type VARCHAR(30) NOT NULL COMMENT '资产类型: excel/xmind/system_cases',
                file_path VARCHAR(500) COMMENT '上传文件路径',
                original_filename VARCHAR(255) COMMENT '原始文件名',
                parse_status VARCHAR(30) NOT NULL DEFAULT 'pending' COMMENT '解析状态: pending/parsing/completed/failed',
                parse_error VARCHAR(500) COMMENT '解析失败原因',
                parsed_cases_json JSON COMMENT '解析后的结构化历史用例数据',
                case_count INT NOT NULL DEFAULT 0 COMMENT '解析出的用例数量',
                batch_id INT COMMENT '关联的生成批次ID',
                created_at DATETIME NOT NULL,
                updated_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (batch_id) REFERENCES generation_batches(id) ON DELETE SET NULL,
                INDEX ix_history_asset_project_created (project_id, created_at),
                INDEX ix_history_asset_project_type (project_id, asset_type),
                INDEX ix_history_assets_batch_id (batch_id),
                INDEX ix_history_assets_project_id (project_id),
                INDEX ix_history_assets_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        conn.commit()
        print("Created history_assets table")
    else:
        print("history_assets table already exists")
