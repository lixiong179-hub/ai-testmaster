
"""
查看 screen 9 的 UI 规格数据
"""
import sys
from pathlib import Path

# 确保能导入模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from loguru import logger
import json

logger.info("查看 screen 9 的 UI 规格数据")

db = PrimarySessionLocal()

try:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 9).first()
    
    if screen:
        logger.info("=" * 60)
        logger.info(f"屏幕基本信息:")
        logger.info(f"  ID: {screen.id}")
        logger.info(f"  屏幕名称: {screen.screen_name}")
        logger.info(f"  解析状态: {screen.parse_status}")
        logger.info(f"  解析模型: {screen.parse_model}")
        logger.info(f"  元素总数: {screen.element_count}")
        logger.info(f"  按钮数: {screen.button_count}")
        logger.info(f"  输入框数: {screen.input_count}")
        logger.info("=" * 60)
        
        logger.info("\n【摘要】")
        logger.info(screen.summary)
        
        logger.info("\n【UI 规格完整数据】")
        if screen.ui_spec:
            logger.info(json.dumps(screen.ui_spec, ensure_ascii=False, indent=2))
        else:
            logger.warning("没有 UI 规格数据")
            
        logger.info("\n【布局校验】")
        logger.info(screen.layout_checks)
        
        logger.info("\n【导航流程】")
        logger.info(screen.navigation_flow)
        
    else:
        logger.error("找不到 screen 9")
        
finally:
    db.close()

