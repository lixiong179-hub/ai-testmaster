"""识别器子包 - 提供元素识别的多种实现策略。

本子包提供两种元素识别器实现，支持视觉模型和MCP协议两种识别方式。

核心类:
    - VisionRecognizer: 视觉识别器，使用AI视觉模型识别页面元素
    - MCPRecognizer: MCP识别器，通过MCP协议与外部识别服务交互

识别器选择:
    - VisionRecognizer: 适用于本地AI模型，直接分析截图
    - MCPRecognizer: 适用于远程识别服务，通过MCP协议通信
"""
from app.services.recognizers.vision_recognizer import VisionRecognizer
from app.services.recognizers.mcp_recognizer import MCPRecognizer

__all__ = ['VisionRecognizer', 'MCPRecognizer']
