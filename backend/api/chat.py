"""WebSocket 对话改进 API"""
import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from db import SessionLocal
from models import Article, ChatMessage
from services import article_agent

router = APIRouter(tags=["chat"])


@router.websocket("/api/articles/{article_id}/chat")
async def article_chat(websocket: WebSocket, article_id: int):
    """WebSocket 对话改进文章"""
    await websocket.accept()
    db: Session = SessionLocal()
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            await websocket.send_json({"type": "error", "message": "文章不存在"})
            await websocket.close()
            return

        while True:
            # 接收用户消息
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                user_msg = data.get("message", "").strip()
            except json.JSONDecodeError:
                user_msg = raw.strip()

            if not user_msg:
                continue

            # 保存用户消息
            db.add(ChatMessage(article_id=article_id, role="user", content=user_msg))
            db.commit()

            # 加载对话历史
            history = [
                {"role": m.role, "content": m.content}
                for m in db.query(ChatMessage)
                .filter(ChatMessage.article_id == article_id)
                .order_by(ChatMessage.id.desc())
                .limit(12)
                .all()[::-1]
            ]

            # 流式返回
            await websocket.send_json({"type": "start", "message": "开始生成"})
            full_response = ""
            try:
                async for chunk in article_agent.improve_article_stream(
                    article.content_md, user_msg, history
                ):
                    full_response += chunk
                    await websocket.send_json({"type": "chunk", "content": chunk})
            except Exception as e:
                await websocket.send_json({"type": "error", "message": f"生成失败：{str(e)}"})
                continue

            # 更新文章内容
            article.content_md = full_response
            db.add(ChatMessage(article_id=article_id, role="assistant", content= full_response))
            db.commit()

            # 同步知识库文件
            from services import vault_writer
            vault_writer.save_article_md(article)

            await websocket.send_json({"type": "done", "message": "生成完成"})

    except WebSocketDisconnect:
        pass
    finally:
        db.close()
