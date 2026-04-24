"""
重新解析 screen_id 10 并更新数据库
"""
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.services.ui_spec_parser import UISpecParser
from app.crud.ui_prototype_screen_mutate import update_ui_screen_parse_result
from app.core.config import settings
from loguru import logger

async def main():
    logger.info("=" * 60)
    logger.info("重新解析 screen_id 10 并更新数据库")
    logger.info("=" * 60)
    
    db = PrimarySessionLocal()
    
    try:
        screen = db.query(UIPrototypeScreen).filter_by(id=10).first()
        if not screen:
            logger.error("screen_id 10 不存在")
            return
        
        logger.info(f"屏幕信息: id={screen.id}, name={screen.screen_name}")
        logger.info(f"原始文件路径: {screen.original_file_path}")
        logger.info(f"当前解析状态: {screen.parse_status}")
        
        # 初始化解析器并解析
        parser = UISpecParser(parse_mode=settings.PARSE_MODE_TEXT)
        
        success, ui_spec, msg = await parser.parse_single_screen(screen.original_file_path, screen.screen_name)
        
        logger.info(f"解析结果: success={success}, msg={msg}")
        
        if success:
            elements = ui_spec.get('elements', [])
            buttons = [e for e in elements if e.get('type') == 'button']
            
            update_ui_screen_parse_result(
                db, screen.id, 
                ui_spec=ui_spec,
                parse_model=settings.TEXT_MODEL_NAME,
                summary=ui_spec.get('purpose', ''),
                element_count=len(elements),
                button_count=len(buttons),
                input_count=len([e for e in elements if e.get('type') == 'input']),
                layout_checks=ui_spec.get('layout_constraints', []),
                navigation_flow=ui_spec.get('flows', {}),
                is_entry_point=screen.screen_order == 0,
                is_end_point=len(ui_spec.get('flows', {}).get('expected_next_screens', [])) == 0
            )
            logger.info(f"✅ 更新成功！元素数: {len(elements)}, 按钮数: {len(buttons)}")
        else:
            logger.error(f"❌ 解析失败: {msg}")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
