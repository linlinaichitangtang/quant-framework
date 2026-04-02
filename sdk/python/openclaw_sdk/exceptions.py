"""
OpenClaw 量化交易平台 Python SDK - 自定义异常
"""


class OpenClawError(Exception):
    """OpenClaw SDK 基础异常"""

    def __init__(self, message: str, code: int = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        result = self.message
        if self.code:
            result = f"[{self.code}] {result}"
        return result


class AuthenticationError(OpenClawError):
    """认证失败异常"""

    def __init__(self, message: str = "认证失败，请检查 API Key 和 Secret", **kwargs):
        super().__init__(message=message, code=401, **kwargs)


class RateLimitError(OpenClawError):
    """限流异常"""

    def __init__(self, message: str = "请求频率超限，请稍后重试", retry_after: int = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(message=message, code=429, **kwargs)


class APIError(OpenClawError):
    """API 错误异常"""

    def __init__(self, message: str = "API 请求错误", status_code: int = None, **kwargs):
        self.status_code = status_code
        super().__init__(message=message, code=status_code, **kwargs)


class ConnectionError(OpenClawError):
    """连接错误异常"""

    def __init__(self, message: str = "无法连接到 OpenClaw 服务", **kwargs):
        super().__init__(message=message, code=0, **kwargs)
