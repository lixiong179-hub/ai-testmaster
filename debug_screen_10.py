"""
调试 screen_id 10 的 OCR 问题
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.utils.ocr_extractor import OCRExtractor
from loguru import logger

logger.info("=" * 60)
logger.info("调查 screen_id 10 的 OCR 问题")
logger.info("=" * 60)

db = PrimarySessionLocal()

try:
    screen = db.query(UIPrototypeScreen).filter_by(id=10).first()
    if not screen:
        logger.error("screen_id 10 不存在")
        sys.exit(1)
    
    logger.info(f"屏幕信息: id={screen.id}, name={screen.screen_name}")
    logger.info(f"原始文件路径: {screen.original_file_path}")
    logger.info(f"文件是否存在: {Path(screen.original_file_path).exists()}")
    file_exists = Path(screen.original_file_path).exists()
    logger.info(f"文件大小: {Path(screen.original_file_path).stat().st_size if file_exists else 'N/A'} bytes")
    logger.info(f"当前解析状态: {screen.parse_status}")
    
    # 尝试读取图片并使用 OCR 直接处理
    if screen.original_file_path and file_exists:
        logger.info("\n" + "=" * 60)
        logger.info("直接使用 OCRExtractor 测试")
        logger.info("=" * 60)
        
        extractor = OCRExtractor()
        logger.info("OCRExtractor 初始化成功")
        
        # 读取文件字节
        with open(screen.original_file_path, "rb") as f:
            image_bytes = f.read()
        
        logger.info(f"图片读取成功: {len(image_bytes)} bytes")
        
        # 测试 extract_text
        try:
            result = extractor.extract_text(image_bytes)
            logger.info(f"extract_text 结果: '{result}'")
            logger.info(f"长度: {len(result)}")
        except Exception as e:
            logger.error(f"extract_text 异常: {e}")
        
        # 测试 extract_text_with_position
        try:
            result_pos = extractor.extract_text_with_position(image_bytes)
            logger.info(f"extract_text_with_position 结果: {result_pos}")
            if result_pos:
                logger.info(f"提取到 {len(result_pos)} 个区域")
                for i, block in enumerate(result_pos):
                    logger.info(f"区域 {i+1}: 文本='{block.get('text', '')}', 位置={block.get('x', 0)},{block.get('y', 0)}")
        except Exception as e:
            logger.error(f"extract_text_with_position 异常: {e}")
    
finally:
    db.close()

logger.info("=" * 60)
logger.info("调试完成")
logger.info("=" * 60)
