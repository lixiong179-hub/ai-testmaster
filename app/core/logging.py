"""
loguru日志配置模块

统一配置loguru日志，包括控制台输出、文件轮转、格式化和级别控制。
替代Python标准库的logging，提供统一的日志基础设施。
"""
import sys
import os
from pathlib import Path
from loguru import logger


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = None,
    rotation: str = "50 MB",
    retention: str = "7 days",
    compression: str = "zip",
    enable_file_logging: bool = True
) -> None:
    """
    初始化loguru日志配置
    
    Args:
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        log_dir: 日志文件目录，默认使用项目根目录下的logs文件夹
        rotation: 日志轮转策略（文件大小或时间间隔）
        retention: 日志保留时间
        compression: 日志压缩格式
        enable_file_logging: 是否启用文件日志
    """
    logger.remove()
    
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    if enable_file_logging:
        if log_dir is None:
            project_root = Path(__file__).parent.parent.parent
            log_dir = str(project_root / "logs")
        
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "app_{time:YYYY-MM-DD}.log")
        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            enqueue=True,
            backtrace=True,
            diagnose=False,
            encoding="utf-8"
        )
        
        error_file = os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log")
        logger.add(
            error_file,
            format=log_format,
            level="ERROR",
            rotation=rotation,
            retention=retention,
            compression=compression,
            enqueue=True,
            backtrace=True,
            diagnose=False,
            encoding="utf-8"
        )
    
    _redirect_uvicorn_logs()
    
    logger.info(f"日志系统初始化完成，级别: {log_level}, 文件日志: {'启用' if enable_file_logging else '禁用'}")


def _redirect_uvicorn_logs() -> None:
    """
    将Uvicorn的logging日志重定向到loguru
    """
    import logging
    
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logger_opt = logger.opt(depth=6, exception=record.exc_info)
            logger_opt.log(record.levelname, record.getMessage())
    
    uvicorn_loggers = ["uvicorn", "uvicorn.error", "uvicorn.access"]
    for logger_name in uvicorn_loggers:
        _logger = logging.getLogger(logger_name)
        _logger.handlers = [InterceptHandler()]
        _logger.setLevel(logging.INFO)
        _logger.propagate = False


def get_logger(name: str = None) -> logger:
    """
    获取loguru logger实例
    
    Args:
        name: 模块名称，用于标识日志来源
    
    Returns:
        loguru logger实例
    """
    return logger
