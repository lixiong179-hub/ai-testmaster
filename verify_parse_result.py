import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from loguru import logger
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen

logger.info("查询screen_id=14的解析结果...")

db = PrimarySessionLocal()
try:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 14).first()
    if screen:
        logger.info(f"找到屏幕: id={screen.id}, name={screen.screen_name}")
        logger.info(f"  parse_status: {screen.parse_status}")
        logger.info(f"  ui_spec 是否存在: {bool(screen.ui_spec)}")
        if screen.ui_spec:
            logger.info(f"  ui_spec 内容: {screen.ui_spec}")
        else:
            logger.warning("  ui_spec 为空！")
        logger.info(f"  parse_model: {screen.parse_model}")
        logger.info(f"  element_count: {screen.element_count}")
        logger.info(f"  button_count: {screen.button_count}")
        logger.info(f"  update_time: {screen.update_time}")
    else:
        logger.error("未找到screen_id=14")
except Exception as e:
    logger.error(f"查询失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
