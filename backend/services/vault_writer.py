"""写入知识库：文章 Markdown + 图片 + 索引文件"""
import os
import re
from datetime import datetime
from typing import Optional
import config
from models import Article


def save_article_md(article: Article) -> str:
    """将文章写入 40.公众号文章/文章-YYYY-MM-DD-NN.md"""
    os.makedirs(config.ARTICLE_DIR, exist_ok=True)

    # 文件名：文章-2026-07-30-01.md（同日多篇按序号递增）
    # 查找当日已有文件确定序号
    date_str = article.topic_date
    existing = [f for f in os.listdir(config.ARTICLE_DIR) if f.startswith(f"文章-{date_str}-")]
    seq = len(existing) + 1
    # 如果 article 已有文件路径记录，复用
    file_name = f"文章-{date_str}-{seq:02d}.md"
    file_path = os.path.join(config.ARTICLE_DIR, file_name)

    # 将 {{IMG:xxx}} 占位替换为 Obsidian 嵌入语法（若图片已生成）
    content = _replace_placeholders_with_obsidian(article)

    # 生成 frontmatter
    image_count = len(article.image_plan) if article.image_plan else 0
    frontmatter = f"""---
created: {datetime.now().strftime('%Y-%m-%d')}
updated: {datetime.now().strftime('%Y-%m-%dT%H:%M')}
type: 公众号文章
tags:
  - 公众号
  - AI生成
topic_date: {article.topic_date}
topic_index: {article.topic_index}
topic_id: {article.topic_id}
status: {article.status}
humanized: {bool(article.humanized)}
image_count: {image_count}
---

"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + content)

    return file_path


def _replace_placeholders_with_obsidian(article: Article) -> str:
    """将文章中的 {{IMG:xxx}} 占位替换为 ![[img-xxx.png]]（若图片已生成）"""
    content = article.content_md
    if not content:
        return ""

    # 从数据库查图片实际文件名（通过 article.images 关系）
    # 但 Article 对象可能未带 images 关系，这里用占位替换为统一命名
    # 实际文件名在生图完成后由 images API 写入
    def replace(match):
        name = match.group(1)
        # 如果是 cover，用 img-{article_id}-cover
        # 如果是 inline-N，用 img-{article_id}-inline-{N}
        if name == "cover":
            return f"![[img-{article.id}-cover.png]]"
        else:
            return f"![[img-{article.id}-{name}.png]]"

    return re.sub(r"!\[\{\{IMG:(cover|inline-\d+)\}\}\]", replace, content)


def save_image(image_bytes: bytes, article_id: int, role: str, index: int, ext: str = "png") -> str:
    """保存图片到 40.公众号文章/assets/，返回文件名"""
    os.makedirs(config.ARTICLE_ASSETS_DIR, exist_ok=True)
    if role == "cover":
        file_name = f"img-{article_id}-cover.{ext}"
    else:
        file_name = f"img-{article_id}-inline-{index}.{ext}"
    file_path = os.path.join(config.ARTICLE_ASSETS_DIR, file_name)
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    return file_name


def ensure_index_file():
    """确保 40.公众号文章/40.公众号文章.md 索引文件存在"""
    index_path = os.path.join(config.ARTICLE_DIR, "40.公众号文章.md")
    if os.path.exists(index_path):
        return
    content = """---
created: {created}
type: index
tags:
  - moc
  - 公众号文章
---

# 📝 公众号文章库

> 由智能体生成的微信公众号文章，含配图。
> 选题来源：[[31.内容选题|每日内容选题]]

---

## 📅 文章归档

```dataview
TABLE 
  status AS 状态,
  humanized AS 拟人化,
  image_count AS 配图数,
  updated AS 更新时间
FROM "40.公众号文章"
WHERE type = "公众号文章"
SORT file.name DESC
LIMIT 30
```

## 📊 统计

```dataview
TABLE length(rows) AS 文章数
FROM "40.公众号文章"
WHERE type = "公众号文章"
GROUP BY topic_date
SORT topic_date DESC
LIMIT 14
```
""".format(created=datetime.now().strftime('%Y-%m-%d'))
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
