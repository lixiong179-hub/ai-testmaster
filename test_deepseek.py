
"""
测试 DeepSeek API 调用
"""
import sys
from pathlib import Path

# 确保能导入模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.ai_client_core import get_ai_client
from app.core.config import settings
from loguru import logger

logger.info("测试 DeepSeek API 调用")

try:
    client = get_ai_client()
    logger.info(f"API URL: {client.base_url}")
    logger.info(f"API Key: {client.api_key[:10] if client.api_key else 'None'}...")
    logger.info(f"Model: {client.model_name}")
    
    # 测试调用
    response = client.chat.completions.create(
        model=client.model_name,
        messages=[
            {"role": "user", "content": "你好，请回复 '测试成功'"}
        ],
        temperature=0.7,
        max_tokens=100
    )
    
    result = response.choices[0].message.content
    logger.info(f"API 调用成功: {result}")
    
except Exception as e:
    logger.error(f"API 调用失败: {e}", exc_info=True)

