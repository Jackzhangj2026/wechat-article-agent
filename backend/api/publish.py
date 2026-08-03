"""发布 API：生成微信公众号富文本 HTML"""
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db import get_db
from models import Article, Image
from services import wechat_formatter

router = APIRouter(prefix="/api/publish", tags=["publish"])

IMAGE_BASE_URL = "http://localhost:8001/assets"


class PublishRequest(BaseModel):
    article_id: int


def _replace_img_placeholders(content_md: str, images: list[Image]) -> str:
    """将 ![{{IMG:cover}}] 或 ![{{IMG:inline-N}}] 替换为 ![[实际文件名.png]]"""
    img_map: dict[str, str] = {}
    for img in images:
        if img.index == 0:
            img_map["cover"] = img.file_path
        else:
            img_map[f"inline-{img.index}"] = img.file_path

    def _replacer(m):
        key = m.group(1)
        fname = img_map.get(key)
        if fname:
            return f"![[{fname}]]"
        return m.group(0)  # 保持原样

    # 匹配完整的 ![{{IMG:xxx}}] 或单独的 {{IMG:xxx}}
    return re.sub(r"!?\[?\{\{IMG:(cover|inline-\d+)\}\}\]?", _replacer, content_md)


@router.post("/richtext")
def generate_richtext(req: PublishRequest, db: Session = Depends(get_db)):
    """生成微信公众号兼容的富文本 HTML（内联样式）"""
    article = db.query(Article).filter(Article.id == req.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 1. 将 {{IMG:xxx}} 占位替换为实际图片文件名
    images = db.query(Image).filter(
        Image.article_id == req.article_id,
        Image.status == "done",
        Image.file_path != "",
    ).all()
    content_md = _replace_img_placeholders(article.content_md, images)

    # 2. 将标题加回 Markdown 内容（确保标题在富文本中显示）
    if article.title and not content_md.startswith("# "):
        content_md = f"# {article.title}\n\n{content_md}"

    # 3. 生成富文本 HTML
    html = wechat_formatter.markdown_to_wechat_html(content_md, IMAGE_BASE_URL)

    # 4. 提取所有图片文件名
    image_files = wechat_formatter.extract_image_files(content_md)

    return {
        "article_id": article.id,
        "title": article.title,
        "html": html,
        "images": [{"filename": f, "url": f"{IMAGE_BASE_URL}/{f}"} for f in image_files],
        "image_count": len(image_files),
    }
