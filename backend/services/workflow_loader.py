"""加载用户的 z-image 工作流 API JSON，并参数化注入字段"""
import json
import copy
import random
import re
from typing import Optional
import config
from services.size_presets import get_size, validate_size

# 高分辨率禁用词（小写匹配）—— 双重保险，防止旧数据或直接API调用绕过 article_agent 的过滤
_HIGHRES_WORDS = [
    "4k", "8k", "16k", "ultra hd", "ultra resolution", "highres",
    "high resolution", "ultra detailed", "extremely detailed",
    "hyper detailed", "masterpiece resolution", "huge image", "large scale",
    "highly detailed",
]
_HIGHRES_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _HIGHRES_WORDS) + r")\b",
    re.IGNORECASE,
)


def _sanitize_prompt(text: str) -> str:
    """清理正向 prompt 中的高分辨率词"""
    cleaned = _HIGHRES_PATTERN.sub("", text)
    parts = [re.sub(r"\s{2,}", " ", p).strip() for p in cleaned.split(",")]
    parts = [p for p in parts if p]
    return ", ".join(parts)


def _ensure_negative_keywords(negative: str) -> str:
    """确保负向 prompt 包含 highres, 4k, 8k"""
    neg_lower = negative.lower()
    for w in ["highres", "4k", "8k"]:
        if w not in neg_lower:
            negative = negative.rstrip(", ") + f", {w}"
    return negative


class WorkflowError(Exception):
    pass


def load_workflow_template() -> dict:
    """读取 z-image-api.json 原始工作流"""
    if not config.COMFYUI_WORKFLOW_PATH.exists():
        raise WorkflowError(
            f"未找到 ComfyUI 工作流文件：{config.COMFYUI_WORKFLOW_PATH}\n"
            "请在 ComfyUI 中加载 z-image 工作流，菜单 → 保存（API 格式），"
            "将导出的 JSON 覆盖该文件。"
        )
    with open(config.COMFYUI_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 跳过占位说明文件（含 _说明 字段）
    if "_说明" in data:
        raise WorkflowError(
            f"{config.COMFYUI_WORKFLOW_PATH} 是占位说明文件，尚未替换为真实工作流。\n"
            "请在 ComfyUI 中加载 z-image 工作流，菜单 → 保存（API 格式），覆盖该文件。"
        )
    return data


def _detect_nodes(workflow: dict) -> dict:
    """探测工作流中的关键节点 ID：sampler / positive_clip / negative_clip / latent / save_image"""
    result = {
        "sampler": None,
        "positive_clip": None,
        "negative_clip": None,
        "latent": None,
        "save_image": None,
    }
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type", "")
        if cls in ("KSampler", "KSamplerAdvanced"):
            result["sampler"] = node_id
        elif cls == "SaveImage":
            result["save_image"] = node_id
        elif cls in ("EmptyLatentImage", "EmptySD3LatentImage", "EmptyHunyuanLatentVideo"):
            result["latent"] = node_id
    # 通过 sampler 的 positive/negative 输入追溯到 CLIPTextEncode
    if result["sampler"]:
        sampler = workflow[result["sampler"]]
        inputs = sampler.get("inputs", {})
        pos_ref = inputs.get("positive")  # ["6", 0]
        neg_ref = inputs.get("negative")
        if isinstance(pos_ref, list) and len(pos_ref) >= 1:
            pos_node_id = str(pos_ref[0])
            if pos_node_id in workflow and workflow[pos_node_id].get("class_type") == "CLIPTextEncode":
                result["positive_clip"] = pos_node_id
        if isinstance(neg_ref, list) and len(neg_ref) >= 1:
            neg_node_id = str(neg_ref[0])
            if neg_node_id in workflow and workflow[neg_node_id].get("class_type") == "CLIPTextEncode":
                result["negative_clip"] = neg_node_id

    # 校验必需节点
    if not result["latent"]:
        raise WorkflowError("工作流未包含 EmptyLatentImage 类节点，本系统仅支持纯文生图工作流")
    if not result["sampler"]:
        raise WorkflowError("工作流未包含 KSampler 节点")
    if not result["positive_clip"] or not result["negative_clip"]:
        raise WorkflowError("无法通过 KSampler 的 positive/negative 输入追溯到 CLIPTextEncode 节点")
    if not result["save_image"]:
        raise WorkflowError("工作流未包含 SaveImage 节点")
    return result


def inject_params(
    workflow: dict,
    positive: str,
    negative: str,
    size_preset: str,
    seed: Optional[int] = None,
    filename_prefix: str = "article",
) -> dict:
    """深拷贝工作流并注入参数，返回新工作流"""
    new_wf = copy.deepcopy(workflow)
    nodes = _detect_nodes(new_wf)

    # 注入正向 prompt（先清理高分辨率词）
    safe_positive = _sanitize_prompt(positive)
    new_wf[nodes["positive_clip"]]["inputs"]["text"] = safe_positive
    # 注入负向 prompt（确保包含 highres/4k/8k 负向关键词）
    safe_negative = _ensure_negative_keywords(negative)
    new_wf[nodes["negative_clip"]]["inputs"]["text"] = safe_negative
    # 注入尺寸
    size = get_size(size_preset)
    if not validate_size(size["width"], size["height"]):
        raise WorkflowError(f"尺寸 {size['width']}x{size['height']} 超过上限 {config.MAX_PIXELS}")
    new_wf[nodes["latent"]]["inputs"]["width"] = size["width"]
    new_wf[nodes["latent"]]["inputs"]["height"] = size["height"]
    new_wf[nodes["latent"]]["inputs"]["batch_size"] = 1
    # 注入 seed（保留 steps/cfg/sampler_name/scheduler 不变）
    if seed is None:
        seed = random.randint(0, 2**63 - 1)
    new_wf[nodes["sampler"]]["inputs"]["seed"] = seed
    # 修改 SaveImage 的 filename_prefix
    new_wf[nodes["save_image"]]["inputs"]["filename_prefix"] = filename_prefix

    return new_wf


def get_workflow_info() -> dict:
    """获取工作流探测信息（用于调试和健康检查）"""
    try:
        wf = load_workflow_template()
        nodes = _detect_nodes(wf)
        return {
            "loaded": True,
            "nodes": nodes,
            "node_count": len(wf),
            "error": None,
        }
    except WorkflowError as e:
        return {"loaded": False, "nodes": None, "node_count": 0, "error": str(e)}
