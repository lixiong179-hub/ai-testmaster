"""测试完整解析流程（模拟API调用）"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import asyncio
from app.services.ui_spec_parser import UISpecParser

image_path = r"D:\PythonFile\ai-testmaster\uploads\ui_prototypes\100426\AI听写首页_20260421133803_0.jpg"

logger.info("=" * 60)
logger.info("测试完整解析流程")
logger.info("=" * 60)

parser = UISpecParser(parse_mode='text')

async def test_parse():
    logger.info(f"\n开始解析: {image_path}")
    logger.info(f"解析模式: {parser.parse_mode}")
    
    success, ui_spec, error = await parser.parse_single_screen(
        image_path=image_path,
        screen_name_hint="AI听写首页"
    )
    
    if success:
        logger.info(f"\n✓ 解析成功!")
        logger.info(f"  screen_name: {ui_spec.get('screen_name', '未知')}")
        logger.info(f"  purpose: {ui_spec.get('purpose', '未知')}")
        logger.info(f"  elements: {len(ui_spec.get('elements', []))} 个")
        
        elements = ui_spec.get('elements', [])[:5]
        for elem in elements:
            logger.info(f"    - [{elem.get('type')}] {elem.get('label', '')}")
    else:
        logger.error(f"\n✗ 解析失败: {error}")

asyncio.run(test_parse())
