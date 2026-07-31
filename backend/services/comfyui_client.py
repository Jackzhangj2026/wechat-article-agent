"""ComfyUI HTTP 客户端：提交工作流、轮询结果、下载图片

使用 requests + asyncio.to_thread 替代 httpx，
因为 httpx 0.27.x 与 ComfyUI 的 aiohttp 服务器存在兼容性问题（返回 502）。
"""
import asyncio
import json
import time
import uuid
from typing import Optional

import requests

import config


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    """同步 POST JSON 到指定 URL，返回 JSON 响应"""
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_json(url: str, timeout: float) -> dict:
    """同步 GET 指定 URL，返回 JSON 响应"""
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_bytes(url: str, params: dict, timeout: float) -> bytes:
    """同步 GET 下载二进制内容"""
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.content


async def submit_workflow(workflow: dict, client_id: Optional[str] = None) -> str:
    """提交工作流到 /prompt，返回 prompt_id"""
    if client_id is None:
        client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    data = await asyncio.to_thread(
        _post_json, f"{config.COMFYUI_BASE}/prompt", payload, 30.0
    )
    if "prompt_id" in data:
        return data["prompt_id"]
    if "error" in data:
        raise RuntimeError(f"ComfyUI 提交失败：{data}")
    raise RuntimeError(f"ComfyUI 返回未知格式：{data}")


async def poll_result(prompt_id: str, timeout: float = None) -> dict:
    """轮询 /history/{prompt_id}，返回 {filename, subfolder, node_id} 或抛超时"""
    if timeout is None:
        timeout = config.COMFYUI_POLL_TIMEOUT
    deadline = time.time() + timeout
    url = f"{config.COMFYUI_BASE}/history/{prompt_id}"
    while time.time() < deadline:
        try:
            data = await asyncio.to_thread(_get_json, url, 10.0)
            if prompt_id in data:
                prompt_data = data[prompt_id]
                status = prompt_data.get("status", {})
                if status.get("completed", False) or "outputs" in prompt_data:
                    return _extract_output(prompt_data)
                if status.get("status_str") == "error":
                    raise RuntimeError(
                        f"ComfyUI 执行出错：{status.get('messages', '')}"
                    )
        except (requests.RequestException, json.JSONDecodeError):
            pass
        await asyncio.sleep(config.COMFYUI_POLL_INTERVAL)
    raise TimeoutError(f"等待 ComfyUI 结果超时（{timeout}s）")


def _extract_output(prompt_data: dict) -> dict:
    """从 history 响应中提取 SaveImage 节点的输出"""
    outputs = prompt_data.get("outputs", {})
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            img_info = node_output["images"][0]
            return {
                "filename": img_info["filename"],
                "subfolder": img_info.get("subfolder", ""),
                "node_id": node_id,
            }
    raise RuntimeError(f"未在输出中找到图片，outputs={outputs}")


async def download_image(filename: str, subfolder: str = "") -> bytes:
    """从 /view 下载图片字节"""
    params = {"filename": filename, "type": "output"}
    if subfolder:
        params["subfolder"] = subfolder
    return await asyncio.to_thread(
        _get_bytes, f"{config.COMFYUI_BASE}/view", params, 30.0
    )


async def check_connection() -> bool:
    """检查 ComfyUI 是否可达"""
    try:
        data = await asyncio.to_thread(
            _get_json, f"{config.COMFYUI_BASE}/system_stats", 5.0
        )
        return "system" in data
    except (requests.RequestException, json.JSONDecodeError):
        return False