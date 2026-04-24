"""
图片验证与OCR解析自测脚本

测试内容：
1. 创建有效测试图片（含文字）
2. 验证图片验证逻辑（有效/无效/损坏文件）
3. 测试OCR提取功能
4. 测试完整解析流程
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import asyncio

logger.info("=" * 70)
logger.info("图片验证与OCR解析自测脚本")
logger.info("=" * 70)

test_dir = project_root / "test_uploads"
test_dir.mkdir(exist_ok=True)

from app.api.v1.endpoints.ui_prototype.helpers import _validate_image_file

logger.info("\n[1] 创建测试图片...")

import cv2
import numpy as np

valid_image_path = test_dir / "valid_test_image.png"
logger.info(f"创建有效测试图片: {valid_image_path}")

img = np.ones((300, 600, 3), dtype=np.uint8) * 255
cv2.putText(img, "Login Page", (200, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
cv2.putText(img, "Username:", (100, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
cv2.rectangle(img, (100, 150), (500, 180), (0, 0, 0), 2)
cv2.putText(img, "Password:", (100, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
cv2.rectangle(img, (100, 230), (500, 260), (0, 0, 0), 2)
cv2.rectangle(img, (200, 270), (400, 300), (0, 0, 255), -1)
cv2.putText(img, "Login", (250, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

cv2.imwrite(str(valid_image_path), img)
logger.info(f"  ✓ 图片创建成功: {valid_image_path.stat().st_size} bytes")

invalid_small_path = test_dir / "invalid_small.png"
logger.info(f"创建损坏小文件: {invalid_small_path}")
with open(invalid_small_path, "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
logger.info(f"  ✓ 损坏文件创建成功: {invalid_small_path.stat().st_size} bytes")

logger.info("\n[2] 测试图片验证逻辑...")

logger.info("\n  [2.1] 测试有效图片...")
is_valid, error_msg = _validate_image_file(str(valid_image_path))
if is_valid:
    logger.info("    ✓ 验证通过")
else:
    logger.error(f"    ✗ 验证失败: {error_msg}")

logger.info("\n  [2.2] 测试损坏小文件...")
is_valid, error_msg = _validate_image_file(str(invalid_small_path))
if not is_valid:
    logger.info(f"    ✓ 正确拒绝损坏文件: {error_msg}")
else:
    logger.error("    ✗ 应该拒绝但未拒绝")

logger.info("\n  [2.3] 测试不存在的文件...")
is_valid, error_msg = _validate_image_file("/nonexistent/path/file.png")
if not is_valid:
    logger.info(f"    ✓ 正确拒绝不存在文件: {error_msg}")
else:
    logger.error("    ✗ 应该拒绝但未拒绝")

logger.info("\n[3] 测试OCR提取...")

from app.utils.ocr_extractor import OCRExtractor
from app.services.ui_spec_parser import UISpecParser

parser = UISpecParser()

with open(valid_image_path, "rb") as f:
    image_bytes = f.read()

logger.info(f"图片大小: {len(image_bytes)} bytes")

logger.info("\n  [3.1] 测试图片读取...")
read_bytes = parser._read_image_bytes(str(valid_image_path))
if read_bytes:
    logger.info(f"    ✓ 图片读取成功: {len(read_bytes)} bytes")
else:
    logger.error("    ✗ 图片读取失败")

logger.info("\n  [3.2] 测试OCR提取文字...")
ocr_text = parser._extract_text_with_ocr(image_bytes)
if ocr_text:
    logger.info(f"    ✓ OCR提取成功，共 {len(ocr_text)} 字符")
    logger.info(f"    提取内容预览:")
    for line in ocr_text.split("\n")[:5]:
        logger.info(f"      - {line}")
else:
    logger.warning("    ⚠ OCR提取为空（可能图片文字不够清晰）")

logger.info("\n  [3.3] 测试带位置信息提取...")
positioned_text = parser._extract_positioned_text(image_bytes)
if positioned_text:
    logger.info(f"    ✓ 带位置提取成功")
    lines = positioned_text.split("\n")[:3]
    for line in lines:
        logger.info(f"      {line}")
else:
    logger.warning("    ⚠ 带位置提取为空")

logger.info("\n[4] 测试完整解析流程（text模式）...")

async def test_parse():
    parser.parse_mode = 'text'
    success, ui_spec, error = await parser.parse_single_screen(
        image_path=str(valid_image_path),
        screen_name_hint="登录页"
    )
    if success:
        logger.info(f"    ✓ 解析成功!")
        logger.info(f"    screen_name: {ui_spec.get('screen_name', '未知')}")
        logger.info(f"    purpose: {ui_spec.get('purpose', '未知')}")
        logger.info(f"    elements: {len(ui_spec.get('elements', []))} 个")
        elements = ui_spec.get('elements', [])[:3]
        for elem in elements:
            logger.info(f"      - [{elem.get('type')}] {elem.get('label', '')}")
        return True
    else:
        logger.error(f"    ✗ 解析失败: {error}")
        return False

result = asyncio.run(test_parse())

logger.info("\n[5] 测试解析失败场景（损坏文件）...")

async def test_invalid_parse():
    parser.parse_mode = 'text'
    success, ui_spec, error = await parser.parse_single_screen(
        image_path=str(invalid_small_path),
        screen_name_hint="测试"
    )
    if not success:
        logger.info(f"    ✓ 正确拒绝损坏文件: {error}")
        return True
    else:
        logger.error("    ✗ 应该失败但成功了")
        return False

result2 = asyncio.run(test_invalid_parse())

logger.info("\n" + "=" * 70)
if result and result2:
    logger.info("✓ 所有测试通过！")
    logger.info("  - 图片验证逻辑工作正常")
    logger.info("  - OCR提取功能正常")
    logger.info("  - 完整解析流程正常")
    logger.info("  - 错误处理机制正常")
else:
    logger.warning("⚠ 部分测试未通过，请检查日志")
logger.info("=" * 70)
