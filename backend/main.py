"""FastAPI 入口：挂载路由、CORS、启动初始化"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

import config
from models import init_db
from migrate import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：创建知识库文章目录 + 初始化 DB + 执行迁移
    os.makedirs(config.ARTICLE_DIR, exist_ok=True)
    os.makedirs(config.ARTICLE_ASSETS_DIR, exist_ok=True)
    os.makedirs(config.PRODUCT_DIR, exist_ok=True)
    os.makedirs(config.PRODUCT_ASSETS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    init_db()
    migrated = run_migrations()
    print(f"[启动] 文章目录：{config.ARTICLE_DIR}")
    print(f"[启动] 图片目录：{config.ARTICLE_ASSETS_DIR}")
    print(f"[启动] 产品目录：{config.PRODUCT_DIR}")
    print(f"[启动] 数据库：{config.DB_PATH}")
    print(f"[启动] ComfyUI 工作流：{config.COMFYUI_WORKFLOW_PATH} (存在={config.COMFYUI_WORKFLOW_PATH.exists()})")
    print(f"[启动] Seedream API：{config.SEEDREAM_API_BASE} (默认引擎={'是' if config.SEEDREAM_DEFAULT_ENGINE else '否'})")
    if migrated:
        print(f"[启动] 数据库迁移：执行 {len(migrated)} 条")
    if not config.DEEPSEEK_API_KEY:
        print("[警告] 未设置 DEEPSEEK_API_KEY 环境变量，文章生成功能不可用")
    yield


app = FastAPI(title="微信公众号文章智能体", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载图片静态资源（前端可直接访问 /assets/xxx.png）
os.makedirs(config.ARTICLE_ASSETS_DIR, exist_ok=True)
os.makedirs(config.PRODUCT_ASSETS_DIR, exist_ok=True)
app.mount("/assets", StaticFiles(directory=config.ARTICLE_ASSETS_DIR), name="assets")
app.mount("/product-assets", StaticFiles(directory=config.PRODUCT_ASSETS_DIR), name="product-assets")

# 挂载前端静态资源（frontend 目录）
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
FRONTEND_DIR = os.path.normpath(FRONTEND_DIR)
if os.path.isdir(FRONTEND_DIR):
    # /app/ 路径访问前端页面
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# 路由导入
from api import topics, articles, images, chat, publish, products  # noqa: E402

app.include_router(topics.router)
app.include_router(articles.router)
app.include_router(images.router)
app.include_router(chat.router)
app.include_router(publish.router)
app.include_router(products.router)


@app.get("/")
def root():
    """根路径重定向到前端页面"""
    return RedirectResponse(url="/app/index.html")


@app.get("/index.html")
def index_html():
    return RedirectResponse(url="/app/index.html")


@app.get("/api/health")
def health():
    return {
        "deepseek_key_set": bool(config.DEEPSEEK_API_KEY),
        "comfyui_workflow_exists": config.COMFYUI_WORKFLOW_PATH.exists(),
        "article_dir": config.ARTICLE_DIR,
        "product_dir": config.PRODUCT_DIR,
    }
