"""
日志配置模块
提供统一的 logger 实例
"""
import logging
import sys


def setup_logger(name: str = "quant", level: int = logging.INFO) -> logging.Logger:
    """创建并配置 logger"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# 默认 logger 实例
logger = setup_logger("quant")
