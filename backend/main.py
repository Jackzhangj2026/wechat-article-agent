"""FastAPI 入口：挂载路由、CORS、启动初始化"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：创建知识库文章目录 + 初始化 DB
    os.makedirs(config.ARTICLE_DIR, exist_ok=True)
    os.makedirs(config.ARTICLE_ASSETS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    init_db()
    print(f"[启动] 文章目录：{config.ARTICLE_DIR}")
    print(f"[启动] 图片目录：{config.ARTICLE_ASSETS_DIR}")
    print(f"[启动] 数据库：{config.DB_PATH}")
    print(f"[启动] ComfyUI 工作流：{config.COMFYUI_WORKFLOW_PATH} (存在={config.COMFYUI_WORKFLOW_PATH.exists()})")
    if not config.DEEPSEEK_API_KEY:
        print("[警告] 未设置 DEEPSEEK_API_KEY 环境变量，文章生成功能不可用")
    yield


app = FastAPI(title="微信公众号文章智能体", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载图片静态资源（前端可直接访问 /assets/xxx.png）
# 注意：StaticFiles 需要目录预先存在，在 lifespan 中创建
os.makedirs(config.ARTICLE_ASSETS_DIR, exist_ok=True)
app.mount("/assets", StaticFiles(directory=config.ARTICLE_ASSETS_DIR), name="assets")


# 路由导入
from api import topics, articles, images, chat, publish  # noqa: E402

app.include_router(topics.router)
app.include_router(articles.router)
app.include_router(images.router)
app.include_router(chat.router)
app.include_router(publish.router)


@app.get("/")
def root():
    return {"name": "微信公众号文章智能体", "status": "running"}


@app.get("/api/health")
def health():
    return {
        "deepseek_key_set": bool(config.DEEPSEEK_API_KEY),
        "comfyui_workflow_exists": config.COMFYUI_WORKFLOW_PATH.exists(),
        "article_dir": config.ARTICLE_DIR,
    }
