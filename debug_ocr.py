
"""
OCR 功能调试脚本
"""
import sys
from pathlib import Path

# 确保能导入模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.ocr_extractor import OCRExtractor, OCRExtractorError
from loguru import logger
import base64

logger.info("开始 OCR 功能调试")

# 初始化 OCR 提取器
extractor = OCRExtractor()

# 查找上传目录
upload_dir = project_root / "uploads" / "ui_prototypes"
logger.info(f"上传目录: {upload_dir}")

# 查找图片
if upload_dir.exists():
    image_files = list(upload_dir.rglob("*.png")) + list(upload_dir.rglob("*.jpg")) + list(upload_dir.rglob("*.jpeg"))
    logger.info(f"找到 {len(image_files)} 张图片")
    
    if image_files:
        # 测试第一张图片
        test_img = image_files[0]
        logger.info(f"测试图片: {test_img}")
        
        try:
            # 读取图片
            with open(test_img, "rb") as f:
                img_data = f.read()
            
            logger.info("尝试 OCR 提取...")
            
            # 测试位置信息提取
            positioned_text = extractor.extract_text_with_position(img_data)
            logger.info(f"带位置文本结果: {len(positioned_text)} 个文本块")
            
            if positioned_text:
                logger.info("带位置文本内容:")
                for item in positioned_text:
                    logger.info(f"  [{item['y']}px: {item['text']}")
            else:
                logger.warning("没有提取到带位置文本")
            
            # 测试纯文本提取
            plain_text = extractor.extract_text(img_data)
            logger.info(f"纯文本结果: '{plain_text}'")
            
            if not plain_text:
                logger.warning("OCR 提取的文本为空")
                
        except OCRExtractorError as e:
            logger.error(f"OCR 错误: {e}")
        except Exception as e:
            logger.error(f"其他错误: {e}", exc_info=True)
    else:
        logger.warning("上传目录中没有找到图片")
else:
    logger.warning("上传目录不存在")

