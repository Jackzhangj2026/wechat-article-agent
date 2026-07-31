"""选题相关 API"""
from fastapi import APIRouter, HTTPException
from services.topic_reader import list_topic_dates, get_topics_by_date

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/dates")
def get_dates():
    """列出所有可用选题日期（降序）"""
    return {"dates": list_topic_dates()}


@router.get("")
def get_topics(date: str):
    """读取指定日期的微信公众号选题"""
    data = get_topics_by_date(date)
    if data is None:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的选题文件")
    return data


@router.get("/{topic_id}")
def get_topic_by_id(topic_id: str):
    """按 topic_id（如 topic-20260730-01）查询单个选题详情"""
    # 解析 topic_id: topic-YYYYMMDD-NN
    parts = topic_id.split("-")
    if len(parts) != 3 or parts[0] != "topic" or len(parts[1]) != 8:
        raise HTTPException(status_code=400, detail="topic_id 格式应为 topic-YYYYMMDD-NN")
    date_compact = parts[1]
    date_str = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
    idx = parts[2]

    data = get_topics_by_date(date_str)
    if data is None:
        raise HTTPException(status_code=404, detail=f"未找到 {date_str} 的选题")
    for t in data["topics"]:
        if t["index"] == idx:
            return t
    raise HTTPException(status_code=404, detail=f"未找到选题 {topic_id}")
