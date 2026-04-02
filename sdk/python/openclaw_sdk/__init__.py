"""
OpenClaw 量化交易平台 Python SDK

自定义异常模块
"""

from .exceptions import (
    OpenClawError,
    AuthenticationError,
    RateLimitError,
    APIError,
    ConnectionError,
)
from .client import OpenClawClient

__version__ = "2.0.0"
__all__ = [
    "OpenClawClient",
    "OpenClawError",
    "AuthenticationError",
    "RateLimitError",
    "APIError",
    "ConnectionError",
    "__version__",
]
