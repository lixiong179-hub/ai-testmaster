"""
OCR诊断脚本 - 测试PaddleOCR是否正常工作
"""
import sys
import os

print("=" * 60)
print("OCR 诊断测试")
print("=" * 60)

# 1. 检查PaddleOCR是否安装
print("\n[1] 检查PaddleOCR安装...")
try:
    import paddleocr
    print(f"    ✓ PaddleOCR已安装: {paddleocr.__version__}")
except ImportError as e:
    print(f"    ✗ PaddleOCR未安装: {e}")
    print("    解决方案: pip install paddleocr paddlepaddle")
    sys.exit(1)

# 2. 检查OpenCV是否安装
print("\n[2] 检查OpenCV安装...")
try:
    import cv2
    print(f"    ✓ OpenCV已安装: {cv2.__version__}")
except ImportError as e:
    print(f"    ✗ OpenCV未安装: {e}")
    sys.exit(1)

# 3. 检查NumPy是否安装
print("\n[3] 检查NumPy安装...")
try:
    import numpy as np
    print(f"    ✓ NumPy已安装: {np.__version__}")
except ImportError as e:
    print(f"    ✗ NumPy未安装: {e}")
    sys.exit(1)

# 4. 测试OCR初始化
print("\n[4] 测试OCR初始化...")
try:
    from paddleocr import PaddleOCR
    print("    正在初始化PaddleOCR (首次可能需要下载模型)...")
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
    print("    ✓ PaddleOCR初始化成功")
except Exception as e:
    print(f"    ✗ PaddleOCR初始化失败: {e}")
    sys.exit(1)

# 5. 测试图片解码
print("\n[5] 测试图片解码...")
test_image_path = os.path.join(os.path.dirname(__file__), "uploads", "ui_prototypes", "1")
if os.path.exists(test_image_path):
    # 找到第一个图片文件
    for f in os.listdir(test_image_path):
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
            full_path = os.path.join(test_image_path, f)
            print(f"    找到测试图片: {full_path}")

            with open(full_path, 'rb') as img_file:
                image_bytes = img_file.read()

            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is not None:
                print(f"    ✓ 图片解码成功: {img.shape}")
            else:
                print(f"    ✗ 图片解码失败")
            break
else:
    print(f"    ⚠ 目录不存在: {test_image_path}")
    print("    跳过图片解码测试")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
