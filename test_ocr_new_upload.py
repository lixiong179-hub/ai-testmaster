"""测试新上传文件的OCR提取"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.utils.ocr_extractor import OCRExtractor
import cv2
import numpy as np

image_path = r"D:\PythonFile\ai-testmaster\uploads\ui_prototypes\100426\AI听写首页_20260421133803_0.jpg"

logger.info("=" * 60)
logger.info("测试新上传文件的OCR提取")
logger.info("=" * 60)

import os
actual_size = os.path.getsize(image_path)
logger.info(f"\n文件: {image_path}")
logger.info(f"实际大小: {actual_size} bytes ({actual_size/1024:.2f} KB)")

logger.info("\n[1] 读取图片...")
with open(image_path, "rb") as f:
    image_bytes = f.read()
logger.info(f"  读取成功: {len(image_bytes)} bytes")

logger.info("\n[2] OpenCV解码...")
nparr = np.frombuffer(image_bytes, np.uint8)
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
if img is not None:
    logger.info(f"  ✓ 解码成功: {img.shape}")
else:
    logger.error("  ✗ 解码失败")
    sys.exit(1)

logger.info("\n[3] RapidOCR识别...")
extractor = OCRExtractor()
try:
    result = extractor.extract_text(image_bytes)
    if result:
        logger.info(f"  ✓ OCR提取成功")
        logger.info(f"  字符数: {len(result)}")
        logger.info(f"\n提取内容:")
        logger.info(result)
    else:
        logger.warning("  ✗ OCR提取结果为空")
        
        logger.info("\n[4] 尝试带位置提取...")
        positioned = extractor.extract_text_with_position(image_bytes)
        if positioned:
            logger.info(f"  ✓ 带位置提取成功: {len(positioned)} 个文本块")
            for item in positioned[:10]:
                logger.info(f"    [{item.get('y', 0)}px] {item.get('text', '')}")
        else:
            logger.warning("  ✗ 带位置提取也为空")
            
            logger.info("\n[5] 直接使用RapidOCR测试...")
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()
            raw_result, elapse = ocr(img)
            if raw_result:
                logger.info(f"  ✓ RapidOCR直接调用成功")
                logger.info(f"  耗时: {elapse}")
                logger.info(f"  识别 {len(raw_result)} 个文本块:")
                for i, item in enumerate(raw_result):
                    logger.info(f"    [{i+1}] {item[1]} (置信度: {item[2]:.2f})")
            else:
                logger.warning("  ✗ RapidOCR直接调用结果为空")
                logger.info("\n  可能原因：")
                logger.info("    - 图片中确实没有可识别的文字")
                logger.info("    - 图片质量太差（模糊、对比度低）")
                logger.info("    - 文字太小或字体特殊")
except Exception as e:
    logger.error(f"  OCR提取异常: {e}")
    import traceback
    logger.error(traceback.format_exc())

logger.info("\n" + "=" * 60)
