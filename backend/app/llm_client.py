"""
LLM 客户端抽象层 — 统一封装 OpenAI/DeepSeek/Ollama 等大语言模型调用

支持两种模式：
1. 外部 API 模式：通过 OpenAI 兼容 API 调用（OpenAI / DeepSeek）
2. 本地模型模式：通过 Ollama 本地部署的模型调用

所有提供商均兼容 OpenAI API 格式，统一通过 aiohttp 异步调用。
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


class LLMError(Exception):
    """LLM 调用异常"""

    def __init__(self, message: str, provider: str = "", status_code: int = 0):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(self.message)


class LLMClient:
    """
    LLM 客户端 — 统一封装大语言模型调用

    通过 OpenAI 兼容 API 格式，支持 OpenAI、DeepSeek、Ollama 等提供商。
    内置错误处理和指数退避重试机制。
    """

    # 各提供商的默认 API 地址
    DEFAULT_BASE_URLS: Dict[LLMProvider, str] = {
        LLMProvider.OPENAI: "https://api.openai.com/v1",
        LLMProvider.DEEPSEEK: "https://api.deepseek.com/v1",
        LLMProvider.OLLAMA: "http://localhost:11434/v1",
    }

    # 各提供商的默认模型名称
    DEFAULT_MODELS: Dict[LLMProvider, str] = {
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.DEEPSEEK: "deepseek-chat",
        LLMProvider.OLLAMA: "qwen2.5:7b",
    }

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.DEEPSEEK,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化 LLM 客户端

        Args:
            provider: LLM 提供商（OPENAI / DEEPSEEK / OLLAMA）
            api_key: API 密钥（Ollama 本地部署可留空）
            base_url: API 基础地址（留空则使用默认地址）
            model_name: 模型名称（留空则使用默认模型）
            timeout: 请求超时秒数
            max_retries: 最大重试次数
            retry_delay: 重试初始延迟（秒），采用指数退避
        """
        self.provider = provider
        self.api_key = api_key or ""
        self.base_url = (base_url or self.DEFAULT_BASE_URLS[provider]).rstrip("/")
        self.model_name = model_name or self.DEFAULT_MODELS[provider]
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Ollama 本地部署通常不需要 API Key
        if provider == LLMProvider.OLLAMA and not self.api_key:
            self.api_key = "ollama"

        logger.info(
            f"LLM 客户端初始化: provider={provider.value}, "
            f"model={self.model_name}, base_url={self.base_url}"
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> str:
        """
        统一聊天接口 — 调用 OpenAI 兼容 API

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 采样温度（0-2，越高越随机）
            max_tokens: 最大生成 token 数
            **kwargs: 其他可选参数（如 top_p, frequency_penalty 等）

        Returns:
            模型生成的文本内容

        Raises:
            LLMError: 调用失败时抛出
        """
        # 构建请求体
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # 合并额外参数
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in kwargs:
                payload[key] = kwargs[key]

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        status = resp.status

                        if status == 200:
                            data = await resp.json()
                            content = data["choices"][0]["message"]["content"]
                            # 记录 token 使用情况
                            usage = data.get("usage", {})
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)
                            logger.debug(
                                f"LLM 调用成功: prompt_tokens={prompt_tokens}, "
                                f"completion_tokens={completion_tokens}"
                            )
                            return content.strip()

                        # 可重试的服务端错误
                        if status in (429, 500, 502, 503, 504):
                            error_text = await resp.text()
                            logger.warning(
                                f"LLM 可重试错误 (attempt {attempt}/{self.max_retries}): "
                                f"status={status}, error={error_text[:200]}"
                            )
                            last_error = LLMError(
                                f"HTTP {status}: {error_text[:200]}",
                                provider=self.provider.value,
                                status_code=status,
                            )
                            if attempt < self.max_retries:
                                delay = self.retry_delay * (2 ** (attempt - 1))
                                await asyncio.sleep(delay)
                            continue

                        # 不可重试的客户端错误
                        error_text = await resp.text()
                        logger.error(
                            f"LLM 调用失败: status={status}, error={error_text[:200]}"
                        )
                        raise LLMError(
                            f"HTTP {status}: {error_text[:200]}",
                            provider=self.provider.value,
                            status_code=status,
                        )

            except LLMError:
                raise
            except asyncio.TimeoutError:
                logger.warning(
                    f"LLM 请求超时 (attempt {attempt}/{self.max_retries})"
                )
                last_error = LLMError(
                    f"请求超时 ({self.timeout.total}s)",
                    provider=self.provider.value,
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
            except aiohttp.ClientError as e:
                logger.warning(
                    f"LLM 连接错误 (attempt {attempt}/{self.max_retries}): {e}"
                )
                last_error = LLMError(
                    f"连接错误: {e}",
                    provider=self.provider.value,
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"LLM 未知错误: {e}", exc_info=True)
                raise LLMError(
                    f"未知错误: {e}",
                    provider=self.provider.value,
                )

        # 所有重试均失败
        raise last_error or LLMError(
            "所有重试均失败",
            provider=self.provider.value,
        )

    async def chat_with_system(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> str:
        """
        带系统提示词的聊天接口

        Args:
            system_prompt: 系统提示词（定义 AI 角色和行为规则）
            user_message: 用户消息
            temperature: 采样温度
            max_tokens: 最大生成 token 数
            **kwargs: 其他可选参数

        Returns:
            模型生成的文本内容
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ):
        """
        流式聊天接口 — 逐 token 返回生成内容

        Args:
            messages: 消息列表
            temperature: 采样温度
            max_tokens: 最大生成 token 数
            **kwargs: 其他可选参数

        Yields:
            每次生成的文本片段
        """
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in kwargs:
                payload[key] = kwargs[key]

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise LLMError(
                        f"流式调用失败 HTTP {resp.status}: {error_text[:200]}",
                        provider=self.provider.value,
                        status_code=resp.status,
                    )

                async for line in resp.content:
                    line_text = line.decode("utf-8").strip()
                    if not line_text or not line_text.startswith("data: "):
                        continue
                    data_str = line_text[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (KeyError, IndexError, json.JSONDecodeError):
                        continue

    def __repr__(self) -> str:
        return (
            f"<LLMClient provider={self.provider.value} "
            f"model={self.model_name}>"
        )
