"""DeepSeek API 客户端：同步 + 流式，带重试与稳健错误处理"""
import json
import time
import httpx
from typing import AsyncIterator
import config

MAX_RETRIES = 3
RETRY_DELAY = 2.0  # 秒，指数退避


def _is_retryable_error(exc: Exception) -> bool:
    """判断是否为可重试的网络类异常"""
    retryable = (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.PoolTimeout,
        httpx.RemoteProtocolError,
        httpx.HTTPStatusError,  # 5xx 可重试
    )
    if isinstance(exc, retryable):
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500
        return True
    # "incomplete chunked read" 等 ProtocolError
    if isinstance(exc, httpx.ProtocolError):
        return True
    return False


async def chat_sync(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
    max_tokens: int = 3000,
) -> str:
    """同步调用 DeepSeek，返回完整文本（内部用流式接收，避免大 body chunked read 错误）"""
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY 环境变量")

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 用 stream=True 增量读取，避免非流式大 body 传输中断
            parts: list[str] = []
            async for chunk in _stream_raw(
                system_prompt, user_prompt, temperature, max_tokens
            ):
                parts.append(chunk)
            return "".join(parts)
        except Exception as e:
            last_exc = e
            if _is_retryable_error(e) and attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                print(f"[DeepSeek] Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                await _sleep_async(delay)
            else:
                raise

    raise last_exc  # 全部重试耗尽


async def _stream_raw(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    """底层流式调用，逐 token yield（单次请求，无重试）"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            f"{config.DEEPSEEK_API_BASE}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


async def _sleep_async(seconds: float):
    """异步睡眠（避免 time.sleep 阻塞事件循环）"""
    import asyncio
    await asyncio.sleep(seconds)


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """调用 DeepSeek 并解析 JSON 输出（用于图片规划）"""
    text = await chat_sync(system_prompt, user_prompt, temperature=temperature, max_tokens=max_tokens)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


async def chat_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
    max_tokens: int = 3000,
) -> AsyncIterator[str]:
    """流式调用 DeepSeek，逐 token 返回（带重试）"""
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY 环境变量")

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async for chunk in _stream_raw(
                system_prompt, user_prompt, temperature, max_tokens
            ):
                yield chunk
            return  # 流正常结束
        except Exception as e:
            last_exc = e
            if _is_retryable_error(e) and attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                print(f"[DeepSeek Stream] Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                await _sleep_async(delay)
            else:
                raise

    raise last_exc
