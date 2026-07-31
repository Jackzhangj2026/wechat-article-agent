"""全局配置：路径、ComfyUI、DeepSeek、SQLite"""
import os
from pathlib import Path

# ===== 加载 .env 文件（手动解析，无需第三方库，始终覆盖环境变量）=====
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
        if _k:
            os.environ[_k] = _v  # 始终覆盖，确保 .env 优先级最高

# ===== 知识库路径 =====
VAULT_ROOT = r"d:\Users\Administrator\Documents\Obsidian Vault\new Vault"
TOPIC_DIR = os.path.join(VAULT_ROOT, "31.内容选题")
HOTSPOT_DIR = os.path.join(VAULT_ROOT, "30.每日热点")
ARTICLE_DIR = os.path.join(VAULT_ROOT, "40.公众号文章")
ARTICLE_ASSETS_DIR = os.path.join(ARTICLE_DIR, "assets")

# ===== ComfyUI =====
COMFYUI_BASE = "http://127.0.0.1:8188"
COMFYUI_WORKFLOW_PATH = Path(__file__).parent / "workflows" / "z-image-api.json"
COMFYUI_POLL_INTERVAL = 2.0      # 轮询间隔（秒）
COMFYUI_POLL_TIMEOUT = 180.0     # 单张图片最长等待（秒）

# ===== DeepSeek =====
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# ===== SQLite =====
DB_PATH = Path(__file__).parent / "data" / "articles.db"

# ===== 图片尺寸硬约束 =====
MAX_PIXELS = 1024 * 1024

# ===== 文章图片占位标记 =====
IMG_PLACEHOLDER_PATTERN = r"!\[\{\{IMG:(cover|inline-\d+)\}\}\]"
