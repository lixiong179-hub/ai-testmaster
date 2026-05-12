"""
OCR文本提取器模块

基于RapidOCR实现图片文字识别，支持两种提取模式：
1. 纯文本提取：返回整页文字内容，按行拼接
2. 带位置提取：返回每个文本区域的位置坐标和置信度

设计要点：
    - 延迟初始化：RapidOCR实例在首次调用时才创建，避免模块导入时的性能开销
    - 可选依赖：RapidOCR未安装时优雅降级，抛出明确的安装提示
    - 高性能：使用ONNXRuntime推理，无需PaddlePaddle

核心类：
    - OCRExtractor: OCR提取器主类
    - OCRExtractorError: OCR相关异常

依赖：
    - rapidocr-onnxruntime: RapidOCR文字识别引擎（基于PP-OCRv4）
    - opencv-python: 图片解码（cv2）
    - numpy: 图片数据转换
"""
from typing import List, Dict, Optional

from loguru import logger

try:
    from rapidocr_onnxruntime import RapidOCR
    _ocr_available = True
except ImportError:
    _ocr_available = False


class OCRExtractorError(Exception):
    """OCR提取器异常基类"""
    pass


class OCRExtractor:
    """OCR文本提取器

    封装RapidOCR引擎，提供图片文字识别能力。
    采用延迟初始化策略，RapidOCR实例在首次调用时才创建，
    避免模块导入时加载大型模型导致的启动延迟。

    RapidOCR使用ONNXRuntime推理，完全兼容Windows，无PaddlePaddle的PIR/oneDNN问题。

    Attributes:
        _ocr: RapidOCR实例（延迟初始化）
    """

    def __init__(self):
        self._ocr: Optional[RapidOCR] = None

    def _init_ocr(self) -> None:
        """延迟初始化RapidOCR实例

        仅在首次调用OCR功能时创建实例，避免不必要的模型加载开销。
        """
        if self._ocr is not None:
            return
        if not _ocr_available:
            raise OCRExtractorError("RapidOCR未安装，请执行 pip install rapidocr-onnxruntime 安装")
        logger.info("初始化RapidOCR实例")
        self._ocr = RapidOCR()
        logger.info("RapidOCR实例初始化完成")

    def _run_ocr(self, image_bytes: bytes) -> List:
        """执行OCR识别的内部方法

        将图片字节数据解码为numpy数组后传入RapidOCR进行识别。

        Args:
            image_bytes: 图片的原始字节数据

        Returns:
            List: RapidOCR原始识别结果，格式为[[[box], text, conf], ...]

        Raises:
            OCRExtractorError: 图片解码失败时抛出
        """
        self._init_ocr()
        import numpy as np
        import cv2

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            logger.error("图片解码失败，无法进行OCR识别")
            raise OCRExtractorError("图片解码失败，请检查图片数据是否有效")

        result, elapse = self._ocr(img)
        logger.info(f"RapidOCR识别完成，耗时: {elapse}")
        return result if result else []

    def extract_text(self, image_bytes: bytes) -> str:
        """提取图片中的纯文本内容

        识别图片中的所有文字，按行拼接为单个字符串返回。

        Args:
            image_bytes: 图片的原始字节数据

        Returns:
            str: 识别到的文本内容，各行以换行符分隔；无识别结果返回空字符串

        Raises:
            OCRExtractorError: RapidOCR未安装时抛出
        """
        try:
            result = self._run_ocr(image_bytes)
            if not result:
                logger.warning("OCR识别结果为空")
                return ""
            lines: List[str] = []
            for item in result:
                text = item[1]
                lines.append(text)
            text_content = "\n".join(lines)
            logger.info(f"OCR文本提取完成，共识别 {len(lines)} 行")
            return text_content
        except OCRExtractorError:
            raise
        except Exception as e:
            logger.error(f"OCR提取异常: {e}")
            return ""

    def extract_text_with_position(self, image_bytes: bytes) -> List[Dict]:
        """提取图片中带位置信息的文本

        识别图片中的所有文字，返回每个文本区域的位置坐标和置信度。

        Args:
            image_bytes: 图片的原始字节数据

        Returns:
            List[Dict]: 文本区域列表，每项包含：
                - text: 识别到的文字
                - x: 左上角x坐标（像素）
                - y: 左上角y坐标（像素）
                - confidence: 识别置信度（0-1）

        Raises:
            OCRExtractorError: RapidOCR未安装时抛出
        """
        try:
            result = self._run_ocr(image_bytes)
            if not result:
                logger.warning("OCR识别结果为空")
                return []
            items: List[Dict] = []
            for item in result:
                box = item[0]
                text = item[1]
                confidence = float(item[2])
                x = int(box[0][0])
                y = int(box[0][1])
                items.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "confidence": confidence
                })
            logger.info(f"OCR带位置文本提取完成，共识别 {len(items)} 个文本区域")
            return items
        except OCRExtractorError:
            raise
        except Exception as e:
            logger.error(f"OCR提取异常: {e}")
            return []


def create_ocr_extractor() -> OCRExtractor:
    """创建OCR提取器实例的工厂函数"""
    return OCRExtractor()
