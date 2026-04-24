"""
API解析诊断脚本 - 模拟API调用流程排查OCR解析问题
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import asyncio

logger.info("=" * 60)
logger.info("API解析诊断脚本")
logger.info("=" * 60)

logger.info("\n[1] 检查RapidOCR安装...")
try:
    from rapidocr_onnxruntime import RapidOCR
    logger.info("    ✓ RapidOCR已安装")
except ImportError as e:
    logger.error(f"    ✗ RapidOCR未安装: {e}")
    logger.error("    解决方案: pip install rapidocr-onnxruntime")
    sys.exit(1)

logger.info("\n[2] 检查OpenCV安装...")
try:
    import cv2
    logger.info(f"    ✓ OpenCV已安装: {cv2.__version__}")
except ImportError as e:
    logger.error(f"    ✗ OpenCV未安装: {e}")
    sys.exit(1)

logger.info("\n[3] 检查NumPy安装...")
try:
    import numpy as np
    logger.info(f"    ✓ NumPy已安装: {np.__version__}")
except ImportError as e:
    logger.error(f"    ✗ NumPy未安装: {e}")
    sys.exit(1)

logger.info("\n[4] 检查配置文件...")
try:
    from app.core.config import settings
    logger.info(f"    ✓ 配置加载成功")
    logger.info(f"    UPLOAD_DIR: {settings.UPLOAD_DIR}")
    logger.info(f"    UI_PROTOTYPE_UPLOAD_DIR: {getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', '未设置')}")
    logger.info(f"    UI_PARSER_MODE: {getattr(settings, 'UI_PARSER_MODE', '未设置')}")
    logger.info(f"    PARSE_MODE_TEXT: {getattr(settings, 'PARSE_MODE_TEXT', '未设置')}")
except Exception as e:
    logger.error(f"    ✗ 配置加载失败: {e}")
    sys.exit(1)

logger.info("\n[5] 查找测试图片...")
upload_dir = getattr(settings, 'UPLOAD_DIR', None)
ui_prototype_upload_dir = getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', None)

test_paths = []
if upload_dir:
    test_paths.append(upload_dir)
if ui_prototype_upload_dir:
    test_paths.append(ui_prototype_upload_dir)

test_image_path = None
for path in test_paths:
    if os.path.exists(path):
        logger.info(f"    检查目录: {path}")
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                    test_image_path = os.path.join(root, f)
                    logger.info(f"    ✓ 找到测试图片: {test_image_path}")
                    break
            if test_image_path:
                break
    if test_image_path:
        break

if not test_image_path:
    logger.warning("    ✗ 未找到测试图片，跳过后续测试")
    sys.exit(0)

logger.info("\n[6] 测试图片读取（模拟API路径检查）...")
try:
    from app.services.ui_spec_parser import UISpecParser
    parser = UISpecParser()
    
    image_bytes = parser._read_image_bytes(test_image_path)
    if image_bytes:
        logger.info(f"    ✓ 图片读取成功，大小: {len(image_bytes)} bytes")
    else:
        logger.error("    ✗ 图片读取失败！")
        logger.error("    可能原因：")
        logger.error("      1. 路径不在允许的目录中（路径遍历保护）")
        logger.error("      2. 文件不存在或无权限")
        logger.error("      3. 文件格式不支持")
        
        resolved_path = Path(test_image_path).resolve()
        allowed_dirs = [
            Path(settings.UPLOAD_DIR).resolve(),
            Path(getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', '/tmp/ui_prototypes')).resolve(),
            Path('/tmp/ui_prototypes').resolve(),
        ]
        logger.error(f"    图片路径: {resolved_path}")
        logger.error(f"    允许目录: {[str(d) for d in allowed_dirs]}")
        
        is_allowed = any(str(resolved_path).startswith(str(allowed_dir)) for allowed_dir in allowed_dirs)
        logger.error(f"    路径是否在允许目录中: {is_allowed}")
        sys.exit(1)
except Exception as e:
    logger.error(f"    ✗ 图片读取异常: {e}")
    import traceback
    logger.error(f"    堆栈: {traceback.format_exc()}")
    sys.exit(1)

logger.info("\n[7] 测试OCR提取...")
try:
    ocr_text = parser._extract_text_with_ocr(image_bytes)
    if ocr_text:
        logger.info(f"    ✓ OCR提取成功，字符数: {len(ocr_text)}")
        logger.info(f"    前200字符: {ocr_text[:200]}")
    else:
        logger.warning("    ✗ OCR提取结果为空！")
        logger.warning("    可能原因：")
        logger.warning("      1. RapidOCR模型未正确加载")
        logger.warning("      2. 图片中无文字内容")
        logger.warning("      3. 图片质量问题（模糊、对比度低）")
        
        logger.info("\n    使用RapidOCR直接测试...")
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            logger.info(f"    图片解码成功: {img.shape}")
            ocr = RapidOCR()
            result, elapse = ocr(img)
            if result:
                logger.info(f"    RapidOCR直接调用成功，耗时: {elapse}")
                logger.info(f"    识别 {len(result)} 个文本块")
                for i, item in enumerate(result[:5]):
                    logger.info(f"      [{i+1}] {item[1]} (置信度: {item[2]:.2f})")
            else:
                logger.warning("    RapidOCR直接调用结果为空")
        else:
            logger.error("    图片解码失败")
except Exception as e:
    logger.error(f"    ✗ OCR提取异常: {e}")
    import traceback
    logger.error(f"    堆栈: {traceback.format_exc()}")
    sys.exit(1)

logger.info("\n[8] 测试完整解析流程（text模式）...")
try:
    async def test_parse():
        parser.parse_mode = 'text'
        success, ui_spec, error = await parser.parse_single_screen(
            image_path=test_image_path,
            screen_name_hint="test"
        )
        if success:
            logger.info(f"    ✓ 解析成功")
            logger.info(f"    screen_name: {ui_spec.get('screen_name', '未知')}")
            logger.info(f"    elements: {len(ui_spec.get('elements', []))} 个")
        else:
            logger.error(f"    ✗ 解析失败: {error}")
    
    asyncio.run(test_parse())
except Exception as e:
    logger.error(f"    ✗ 解析异常: {e}")
    import traceback
    logger.error(f"    堆栈: {traceback.format_exc()}")

logger.info("\n" + "=" * 60)
logger.info("诊断完成")
logger.info("=" * 60)
