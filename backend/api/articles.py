"""文章相关 API：生成、查询、列表、保存"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from db import get_db
from models import Article, Image, ChatMessage
from services import article_agent, topic_reader, vault_writer

router = APIRouter(prefix="/api/articles", tags=["articles"])


class GenerateRequest(BaseModel):
    topic_id: str
    force: bool = False  # 强制重新生成（覆盖已有文章）


class UpdateArticleRequest(BaseModel):
    content_md: str
    title: Optional[str] = None


@router.post("/generate")
async def generate_article(req: GenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """根据选题 ID 生成文章（三段式：初稿 + 去AI味 + 图片规划）"""
    # 查找选题
    topic = topic_reader.get_topic_by_id(req.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"未找到选题 {req.topic_id}")

    # 检查是否已生成过
    existing = db.query(Article).filter(Article.topic_id == req.topic_id).first()
    if existing and not req.force:
        return {"article_id": existing.id, "message": "该选题已有文章", "status": existing.status}

    # 强制重新生成时，删除旧记录及其图片和对话
    if existing and req.force:
        db.query(Image).filter(Image.article_id == existing.id).delete()
        db.query(ChatMessage).filter(ChatMessage.article_id == existing.id).delete()
        db.delete(existing)
        db.commit()

    # 创建占位记录
    article = Article(
        title=topic["title"],
        topic_date=topic["id"].split("-")[1],
        topic_index=topic["index"],
        topic_id=req.topic_id,
        content_md="",
        status="improving",
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    # 同步生成（DEMO 版直接 await，正式版可改后台任务）
    try:
        result = await article_agent.generate_article(topic)
        article.title = result["title"]
        article.content_md = result["content_md"]
        article.image_plan = result["image_plan"]
        article.humanized = 1
        article.status = "ready"
        db.commit()

        # 写入知识库 Markdown 文件
        vault_writer.save_article_md(article)

        return {"article_id": article.id, "status": "ready", "message": "文章生成完成"}
    except Exception as e:
        article.status = "draft"
        article.content_md = f"生成失败：{str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"生成失败：{str(e)}")


@router.get("")
def list_articles(db: Session = Depends(get_db)):
    """文章列表"""
    articles = db.query(Article).order_by(Article.created_at.desc()).all()
    return {
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "topic_id": a.topic_id,
                "topic_date": a.topic_date,
                "status": a.status,
                "humanized": a.humanized,
                "image_count": len(a.image_plan) if a.image_plan else 0,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in articles
        ]
    }


@router.get("/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)):
    """获取文章详情（含图片列表）"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    images = db.query(Image).filter(Image.article_id == article_id).order_by(Image.index).all()
    return {
        "id": article.id,
        "title": article.title,
        "topic_id": article.topic_id,
        "topic_date": article.topic_date,
        "topic_index": article.topic_index,
        "content_md": article.content_md,
        "image_plan": article.image_plan or [],
        "status": article.status,
        "humanized": article.humanized,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        "images": [
            {
                "id": img.id,
                "index": img.index,
                "role": img.role,
                "section": img.section,
                "description": img.description,
                "prompt": img.prompt,
                "negative_prompt": img.negative_prompt,
                "size_preset": img.size_preset,
                "width": img.width,
                "height": img.height,
                "seed": img.seed,
                "file_path": img.file_path,
                "status": img.status,
                "error": img.error,
            }
            for img in images
        ],
    }


@router.put("/{article_id}")
def update_article(article_id: int, req: UpdateArticleRequest, db: Session = Depends(get_db)):
    """保存手动编辑"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    article.content_md = req.content_md
    if req.title:
        article.title = req.title
    db.commit()

    # 同步更新知识库文件
    vault_writer.save_article_md(article)

    return {"message": "已保存", "article_id": article_id}
