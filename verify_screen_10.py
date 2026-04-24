"""
验证 screen_id 10 最终状态
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from loguru import logger

logger.info("=" * 60)
logger.info("验证 screen_id 10 最终状态")
logger.info("=" * 60)

db = PrimarySessionLocal()

try:
    screen = db.query(UIPrototypeScreen).filter_by(id=10).first()
    if not screen:
        logger.error("screen_id 10 不存在")
        sys.exit(1)
    
    logger.info(f"✅ 屏幕信息: id={screen.id}, name={screen.screen_name}")
    logger.info(f"✅ 解析状态: {screen.parse_status}")
    logger.info(f"✅ 使用模型: {screen.parse_model}")
    logger.info(f"✅ 元素数: {screen.element_count}")
    logger.info(f"✅ 按钮数: {screen.button_count}")
    logger.info(f"✅ 摘要: {screen.summary}")
    
finally:
    db.close()
