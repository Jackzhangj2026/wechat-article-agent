"""图片尺寸预设（均 ≤ 1024×1024，防显存溢出）"""
import config

SIZE_PRESETS = {
    "cover_wide":      {"width": 1024, "height": 576, "ratio": "16:9"},   # 封面横图
    "inline_4_3":      {"width": 768,  "height": 576, "ratio": "4:3"},    # 文中横图（默认）
    "inline_square":   {"width": 768,  "height": 768, "ratio": "1:1"},    # 文中方图
    "inline_portrait": {"width": 576,  "height": 768, "ratio": "3:4"},    # 文中竖图
}


def get_size(size_preset: str) -> dict:
    """获取尺寸，未知 preset 回退到 inline_4_3"""
    return SIZE_PRESETS.get(size_preset, SIZE_PRESETS["inline_4_3"])


def validate_size(width: int, height: int) -> bool:
    """校验尺寸不超过硬上限"""
    return width * height <= config.MAX_PIXELS
