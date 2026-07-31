"""Markdown → 微信公众号富文本（内联样式 HTML）"""
import re
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup

_md = MarkdownIt("commonmark", {"html": False, "breaks": True, "linkify": True})

# 微信公众号内联样式
STYLES = {
    "h1": "font-size:24px;font-weight:bold;color:#1a1a1a;margin:24px 0 16px;padding-left:12px;border-left:4px solid #07c160;line-height:1.4;",
    "h2": "font-size:20px;font-weight:bold;color:#1a1a1a;margin:28px 0 14px;padding-bottom:6px;border-bottom:1px solid #e8e8e8;line-height:1.4;",
    "h3": "font-size:17px;font-weight:bold;color:#333;margin:20px 0 10px;line-height:1.4;",
    "p": "font-size:16px;color:#333;line-height:1.75;margin:0 0 16px;letter-spacing:0.5px;",
    "strong": "font-weight:bold;color:#07c160;",
    "em": "font-style:italic;color:#555;",
    "blockquote": "margin:16px 0;padding:12px 16px;background:#f7f7f7;border-left:3px solid #ddd;color:#666;font-size:15px;line-height:1.7;",
    "code": "font-family:Consolas,Monaco,monospace;background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:14px;color:#c7254e;",
    "pre": "background:#2d2d2d;color:#f8f8f2;padding:16px;border-radius:6px;overflow-x:auto;margin:16px 0;font-size:14px;line-height:1.5;",
    "ul": "margin:12px 0;padding-left:24px;font-size:16px;color:#333;line-height:1.75;",
    "ol": "margin:12px 0;padding-left:24px;font-size:16px;color:#333;line-height:1.75;",
    "li": "margin:6px 0;",
    "a": "color:#07c160;text-decoration:none;border-bottom:1px solid #07c160;",
    "hr": "border:none;border-top:1px solid #e8e8e8;margin:24px 0;",
    "img": "max-width:100%;height:auto;border-radius:8px;margin:12px 0;display:block;",
}


def markdown_to_wechat_html(md_text: str, image_base_url: str = "") -> str:
    """将 Markdown 转为微信公众号兼容的内联样式 HTML

    Args:
        md_text: 文章 Markdown（含 ![[img-xxx.png]] Obsidian 嵌入语法）
        image_base_url: 图片 URL 前缀，如 http://localhost:8000/assets/
    """
    # 替换 Obsidian 图片嵌入 ![[xxx.png]] 为标准 ![](url)
    def replace_obsidian_img(match):
        filename = match.group(1)
        url = f"{image_base_url}/{filename}" if image_base_url else filename
        return f"![{filename}]({url})"

    text = re.sub(r"!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|webp))\]\]", replace_obsidian_img, md_text)

    # 替换 {{IMG:xxx}} 占位为提示文字（未生成图片时显示）
    text = re.sub(
        r"!\[\{\{IMG:(cover|inline-\d+)\}\}\]",
        lambda m: f"*[图片占位：{m.group(1)}，待生成]*",
        text,
    )

    # Markdown → HTML
    html = _md.render(text)

    # 用 BeautifulSoup 注入内联样式
    soup = BeautifulSoup(html, "html.parser")
    for tag_name, style in STYLES.items():
        for tag in soup.find_all(tag_name):
            existing = tag.get("style", "")
            tag["style"] = f"{existing} {style}".strip() if existing else style

    # 处理 pre > code
    for pre in soup.find_all("pre"):
        pre["style"] = STYLES["pre"]
        code = pre.find("code")
        if code:
            code["style"] = "background:none;color:inherit;padding:0;"

    return str(soup)


def extract_image_files(md_text: str) -> list[str]:
    """从 Markdown 中提取所有图片文件名（Obsidian 嵌入语法）"""
    files = re.findall(r"!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|webp))\]\]", md_text)
    return files
