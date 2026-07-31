"""文章生成智能体：三段式编排（初稿 → 去AI味润色 → 图片规划）"""
import json
import re
from typing import Optional
from services import deepseek_client
from services.size_presets import SIZE_PRESETS

# ============ System Prompts ============

SYSTEM_PROMPT_DRAFT = """你是一位资深微信公众号主笔，擅长把热点事件写成有深度、有观点、能引发共鸣的公众号文章。

【写作要求】
1. 输出纯 Markdown 格式，不要任何额外说明
2. 短段落为主（每段 2-4 句），适合手机阅读
3. 用 ## 作为小标题分节，全文 1500-2500 字
4. 关键金句用 **加粗** 强调
5. 标题用 # 一级标题，要有吸引力但不是标题党
6. 文章中需要插图的位置，用占位标记：![{{IMG:cover}}] 表示封面图位置，![{{IMG:inline-1}}]、![{{IMG:inline-2}}] 等表示文中插图位置（按顺序编号）
7. 封面图占位放在标题下方，文中插图分散在不同小节中（约每隔 300-500 字一张）
8. 文末可以有一段作者观点收尾，但不要空洞总结

【图片占位规则】
- 封面图 1 张：![{{IMG:cover}}]
- 文中插图 3-5 张：![{{IMG:inline-1}}] 到 ![{{IMG:inline-3}}] 或 ![{{IMG:inline-5}}]
- 占位要放在合适的小节之间，配合上下文"""

SYSTEM_PROMPT_HUMANIZE = """你是一位资深中文编辑，专门把 AI 生成的文章改写得像真人写的。你的任务是消除一切 AI 腔调，让文章读起来像一个有血有肉的公众号作者写的。

【AI 腔调负面清单 - 必须全部消除】
禁用词/句式：
- 连接词：首先、其次、再次、最后、然后、综上所述、总而言之、综上所述可以看出
- 套话引导：让我们、值得一提的是、众所周知、毫无疑问、不言而喻
- 空洞总结：这就是X的意义、X的未来值得期待、X正在改变世界、让我们一起拭目以待
- 学术腔：具有重要意义、发挥着重要作用、为...提供了重要支撑、呈现出...的特点
- 机械排比：连续三句以上相同句式开头（如「我们看到了X。我们看到了Y。我们看到了Z。」）
- 过度对称：每段长度均匀、每小节结构对称（要人为打破节奏）
- 数据罗列腔：连续多句「根据XX数据显示」「XX报告指出」堆砌（改为融入叙述）

【改写要求】
1. 删除上述所有 AI 套话和连接词，让句子自然衔接
2. 打破机械对称排比，改成自然长短句交错
3. 替换学术腔为口语表达（「具有重要意义」→「这事挺关键的」）
4. 加入第一人称视角与个人观点（公众号主笔人设，可以有立场、有态度）
5. 适当加入反问、设问、口语语气词（呢/啊/吧，控制密度不过载）
6. 句子长度从均匀变参差（短句切分长句，制造阅读节奏）
7. 保留所有事实数据、来源链接、数字，不得编造
8. 保留所有 ![{{IMG:xxx}}] 图片占位标记原样不动
9. 输出纯 Markdown，不要任何额外说明"""

SYSTEM_PROMPT_IMAGE_PLAN = """你是公众号配图规划师。根据文章内容，规划一组配图（封面 1 张 + 文中 3-5 张），输出严格的 JSON 数组。

【输出格式】
[
  {
    "index": 0,
    "role": "cover",
    "section": "封面",
    "description": "中文画面描述（50字内）",
    "prompt": "english SDXL-compatible positive prompt, comma separated, include subject/style/lighting keywords",
    "negative_prompt": "low quality, blurry, deformed, watermark, text, ugly, highres, 4k, 8k",
    "size_preset": "cover_wide"
  },
  {
    "index": 1,
    "role": "inline",
    "section": "对应段落小标题",
    "description": "中文画面描述",
    "prompt": "english prompt",
    "negative_prompt": "negative prompt",
    "size_preset": "inline_4_3"
  }
]

【规则】
1. 封面 1 张（role=cover, size_preset=cover_wide），文中 3-5 张（role=inline）
2. 文中插图 size_preset 从 inline_4_3 / inline_square / inline_portrait 中选，默认 inline_4_3
3. 所有 prompt 用英文、逗号分隔短语、SDXL 兼容
4. 全篇艺术风格统一（如全用 flat illustration 或全用 cinematic photo）
5. 每张图的 description 必须明确对应文中某个段落/小节的内容，禁止装饰性插图
6. prompt 要融入文章主题关键词
7. 数量：最少 4 张（1 封面 + 3 文中），最多 6 张（1 封面 + 5 文中）
8. 只输出 JSON 数组，不要其他任何文字

【分辨率硬约束 - 极其重要】
图片实际生成尺寸由后端 size_preset 决定（最大 1024×576，总像素 ≤ 1024×1024），prompt 中严禁出现任何暗示高分辨率的词：
- 禁用词：4k, 8k, 16k, ultra hd, ultra resolution, highres, high resolution, ultra detailed, extremely detailed, hyper detailed, masterpiece resolution, huge image, large scale
- 不要写 "highly detailed" 或 "extremely detailed"，用 "detailed" 即可
- 负向 prompt 必须包含：highres, 4k, 8k
- 画质描述用：detailed, sharp focus, professional, clean lines（已足够）"""


# ============ 编排逻辑 ============

async def generate_article(topic: dict) -> dict:
    """三段式生成文章，返回 {title, content_md, image_plan}"""
    # 构造选题摘要
    topic_summary = f"""选题标题：{topic['title']}
适用平台：{topic['platform']}
内容方向：{topic['direction']}
目标受众：{topic['audience']}
依据热点：{topic['hotspot_ref']}
内容大纲：
{chr(10).join(f'  {i+1}. {p}' for i, p in enumerate(topic.get('outline', [])))}
变现途径：{topic['monetization']}"""

    # 阶段一：初稿
    draft = await deepseek_client.chat_sync(
        SYSTEM_PROMPT_DRAFT,
        f"请基于以下选题写一篇微信公众号文章：\n\n{topic_summary}",
        temperature=0.85,
        max_tokens=3000,
    )

    # 阶段二：去AI味润色
    humanized = await deepseek_client.chat_sync(
        SYSTEM_PROMPT_HUMANIZE,
        f"请把下面这篇 AI 生成的文章改写成真人风格，保留所有事实和图片占位标记：\n\n{draft}",
        temperature=0.75,
        max_tokens=3000,
    )

    # 提取标题（首个 # 标题）
    title_match = re.search(r"^#\s+(.+)$", humanized, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else topic["title"]

    # 阶段三：图片规划
    image_plan = await deepseek_client.chat_json(
        SYSTEM_PROMPT_IMAGE_PLAN,
        f"请为以下文章规划配图，输出 JSON 数组：\n\n{humanized[:6000]}",
        temperature=0.3,
        max_tokens=1500,
    )

    # 校验并规范化图片规划
    image_plan = _normalize_image_plan(image_plan)

    # 校验占位与规划数量一致性：以规划为准，补齐/裁剪占位
    content_md = _sync_placeholders(humanized, image_plan)

    return {
        "title": title,
        "content_md": content_md,
        "image_plan": image_plan,
    }


# 高分辨率禁用词（小写匹配，用于正则替换）
_HIGHRES_WORDS = [
    "4k", "8k", "16k", "ultra hd", "ultra resolution", "highres",
    "high resolution", "ultra detailed", "extremely detailed",
    "hyper detailed", "masterpiece resolution", "huge image", "large scale",
    "highly detailed",
]
# 用 \b 词边界匹配，避免误伤（如 "8k" 不会匹配 "78keys"）
_HIGHRES_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _HIGHRES_WORDS) + r")\b",
    re.IGNORECASE,
)


def _strip_highres_words(text: str) -> str:
    """删除 prompt 中暗示高分辨率的词，清理多余逗号和空格"""
    cleaned = _HIGHRES_PATTERN.sub("", text)
    # 按逗号分割、剔除空项、压缩项内多余空格、重新拼接
    parts = [re.sub(r"\s{2,}", " ", p).strip() for p in cleaned.split(",")]
    parts = [p for p in parts if p]  # 去空
    return ", ".join(parts)


def _normalize_image_plan(plan: list) -> list:
    """规范化图片规划 JSON"""
    if not isinstance(plan, list):
        plan = []
    normalized = []
    for i, item in enumerate(plan):
        if not isinstance(item, dict):
            continue
        role = item.get("role", "inline")
        size_preset = item.get("size_preset", "inline_4_3")
        if role == "cover":
            size_preset = "cover_wide"
        if size_preset not in SIZE_PRESETS:
            size_preset = "inline_4_3"
        # 强制清理正向 prompt 中的高分辨率词
        prompt_clean = _strip_highres_words(str(item.get("prompt", "")))
        # 负向 prompt 保证含 highres, 4k, 8k
        neg = str(item.get("negative_prompt", "low quality, blurry, deformed, watermark, text, ugly"))
        neg_lower = neg.lower()
        for w in ["highres", "4k", "8k"]:
            if w not in neg_lower:
                neg = neg.rstrip(", ") + f", {w}"
        normalized.append({
            "index": i,
            "role": role,
            "section": str(item.get("section", ""))[:255],
            "description": str(item.get("description", "")),
            "prompt": prompt_clean,
            "negative_prompt": neg,
            "size_preset": size_preset,
        })
    # 确保至少 4 张、最多 6 张
    if len(normalized) < 4:
        # 不足则补默认文中插图
        while len(normalized) < 4:
            normalized.append({
                "index": len(normalized),
                "role": "inline",
                "section": "文中配图",
                "description": "文章配图",
                "prompt": "article illustration, flat design, soft colors, detailed, sharp focus",
                "negative_prompt": "low quality, blurry, deformed, watermark, text, ugly, highres, 4k, 8k",
                "size_preset": "inline_4_3",
            })
    elif len(normalized) > 6:
        normalized = normalized[:6]
    # 重新编号
    for i, item in enumerate(normalized):
        item["index"] = i
    return normalized


def _sync_placeholders(content: str, image_plan: list) -> str:
    """同步文章中的图片占位与规划数量：以规划为准"""
    # 收集规划中的占位名
    planned_names = []
    for item in image_plan:
        if item["role"] == "cover":
            planned_names.append("cover")
        else:
            planned_names.append(f"inline-{item['index']}")
    # 实际上 inline 编号应该从 1 开始连续
    inline_count = sum(1 for p in image_plan if p["role"] != "cover")
    expected_inline_names = [f"inline-{i+1}" for i in range(inline_count)]
    expected_placeholders = ["cover"] + expected_inline_names

    # 找出文中已有的占位
    pattern = r"!\[\{\{IMG:(cover|inline-\d+)\}\}\]"
    found = re.findall(pattern, content)
    found_set = set(found)

    # 补齐缺失的占位：在文章末尾追加
    for name in expected_placeholders:
        if name not in found_set:
            content += f"\n\n![{{{{IMG:{name}}}}}]"

    # 如果文中占位比规划多，删除多余的（按编号大的先删）
    found_after = re.findall(pattern, content)
    extra = sorted(
        [n for n in found_after if n not in expected_placeholders],
        key=lambda x: (x != "cover", int(x.split("-")[1]) if "-" in x else 0),
        reverse=True,
    )
    for name in extra:
        content = content.replace(f"![{{{{IMG:{name}}}}}]", "", 1)

    return content


# ============ 对话改进 ============

async def improve_article_stream(
    current_content: str,
    user_instruction: str,
    chat_history: list[dict],
):
    """流式对话改进文章"""
    # 构造对话历史
    history_text = ""
    for msg in chat_history[-6:]:  # 最近 6 轮
        role_label = "用户" if msg["role"] == "user" else "助手"
        history_text += f"\n{role_label}：{msg['content']}"

    system = SYSTEM_PROMPT_HUMANIZE + "\n\n你是文章改进助手。根据用户指令修改文章，始终遵循去AI味规则，保留所有 ![{{IMG:xxx}}] 图片占位标记。输出完整的修改后文章 Markdown。"

    user = f"""【当前文章】
{current_content}

【对话历史】
{history_text}

【用户最新指令】
{user_instruction}

请根据指令修改文章，输出完整修改后的 Markdown（保留图片占位）："""

    async for chunk in deepseek_client.chat_stream(system, user, temperature=0.7, max_tokens=3000):
        yield chunk
