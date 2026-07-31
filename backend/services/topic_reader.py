"""解析 31.内容选题/选题-YYYY-MM-DD.md，返回结构化选题 JSON"""
import os
import re
import yaml
from datetime import datetime
from typing import Optional
from markdown_it import MarkdownIt

import config

_md = MarkdownIt()


def list_topic_dates() -> list[str]:
    """列出所有可用选题日期，降序"""
    dates = []
    if not os.path.isdir(config.TOPIC_DIR):
        return dates
    for name in os.listdir(config.TOPIC_DIR):
        m = re.match(r"选题-(\d{4}-\d{2}-\d{2})\.md$", name)
        if m:
            dates.append(m.group(1))
    dates.sort(reverse=True)
    return dates


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """分离 YAML frontmatter 与正文"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
                return fm, parts[2]
            except yaml.YAMLError:
                pass
    return {}, text


def _parse_topic_details(body: str) -> dict[str, dict]:
    """解析「### 选题 NN：标题」段落，返回 {index: 详情dict}"""
    details = {}
    # 按二级标题切分
    sections = re.split(r"\n###\s+选题\s+(\d+)\s*[：:]\s*(.+?)\n", body)
    # sections: [前导, index1, title1, content1, index2, title2, content2, ...]
    i = 1
    while i + 2 < len(sections):
        idx = sections[i].strip()
        title = sections[i + 1].strip()
        content = sections[i + 2]
        # 提取字段（以「- **字段**：」开头的列表项）
        fields = {}
        # 处理多行字段（如大纲要点）
        current_key = None
        current_lines = []
        for line in content.splitlines():
            m = re.match(r"\s*-\s+\*\*(.+?)\*\*\s*[：:]\s*(.*)", line)
            if m:
                if current_key:
                    fields[current_key] = " ".join(current_lines).strip()
                current_key = m.group(1).strip()
                current_lines = [m.group(2).strip()]
            elif current_key and line.strip():
                # 续行（如大纲子项）
                sub = re.match(r"\s+(\d+\.|-\s|•)\s*(.*)", line)
                if sub:
                    current_lines.append(sub.group(2).strip())
                else:
                    current_lines.append(line.strip())
        if current_key:
            fields[current_key] = " ".join(current_lines).strip()

        # 大纲要点转列表
        if "内容大纲要点" in fields:
            outline = re.split(r"\s*\d+\.\s*", fields["内容大纲要点"])
            fields["内容大纲要点"] = [s.strip() for s in outline if s.strip()]

        # 提取来源链接
        source_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", fields.get("依据热点", ""))
        if source_links:
            fields["source_links"] = [{"text": t, "url": u} for t, u in source_links]

        details[idx] = {
            "index": idx,
            "title": title,
            "platform": fields.get("适用平台", ""),
            "direction": fields.get("内容方向/角度", fields.get("内容方向", "")),
            "hotspot_ref": fields.get("依据热点", ""),
            "audience": fields.get("目标受众", ""),
            "outline": fields.get("内容大纲要点", []),
            "monetization": fields.get("变现途径", ""),
            "source_links": fields.get("source_links", []),
        }
        i += 3
    return details


def _parse_overview_table(body: str) -> list[dict]:
    """解析选题总览表"""
    # 找到「## 选题总览表」之后的第一个 markdown 表格
    m = re.search(r"##\s*选题总览表\s*\n(.*?)(?=\n##\s|\Z)", body, re.DOTALL)
    if not m:
        return []
    table_block = m.group(1)
    rows = []
    lines = [l.strip() for l in table_block.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].strip("|").split("|")]
    for line in lines[1:]:
        # 跳过分隔行 |---|---|
        if re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= len(headers):
            row = dict(zip(headers, cells))
            rows.append(row)
    return rows


def get_topics_by_date(date_str: str) -> Optional[dict]:
    """读取指定日期的选题，返回 {date, topics: [...]}"""
    file_path = os.path.join(config.TOPIC_DIR, f"选题-{date_str}.md")
    if not os.path.isfile(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    fm, body = _parse_frontmatter(text)
    overview_rows = _parse_overview_table(body)
    details = _parse_topic_details(body)

    topics = []
    # 用总览表作为主序，详情作为补充
    for row in overview_rows:
        idx = row.get("编号", "").strip()
        if not idx:
            continue
        # 编号可能是 "01" 或 "1"，统一为两位
        idx_padded = idx.zfill(2)
        detail = details.get(idx_padded, details.get(idx, {}))
        platform = detail.get("platform") or row.get("适用平台", "")

        # 显示所有选题（不再按平台过滤，原过滤逻辑保留作注释参考）
        # if "微信公众号" not in platform:
        #     continue

        # 解析打分
        score_str = row.get("建议打分", "")
        try:
            score = float(score_str)
        except (ValueError, TypeError):
            score = 0.0

        topic = {
            "id": f"topic-{date_str.replace('-', '')}-{idx_padded}",
            "index": idx_padded,
            "title": row.get("选题标题", detail.get("title", "")).strip(),
            "platform": platform,
            "monetization": row.get("变现途径", detail.get("monetization", "")),
            "score": score,
            "hotspot_ref": row.get("依据热点", detail.get("hotspot_ref", "")),
            "direction": detail.get("direction", ""),
            "audience": detail.get("audience", ""),
            "outline": detail.get("outline", []),
            "source_links": detail.get("source_links", []),
        }
        topics.append(topic)

    return {"date": date_str, "topics": topics}


def get_topic_by_id(topic_id: str):
    """按 topic_id（如 topic-20260730-01）查询单个选题详情，返回 dict 或 None"""
    parts = topic_id.split("-")
    if len(parts) != 3 or parts[0] != "topic" or len(parts[1]) != 8:
        return None
    date_compact = parts[1]
    date_str = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
    idx = parts[2]

    data = get_topics_by_date(date_str)
    if data is None:
        return None
    for t in data["topics"]:
        if t["index"] == idx:
            return t
    return None
