# 微信公众号文章智能体 (DEMO)

基于 Obsidian 知识库每日选题，自动生成微信公众号文章 + ComfyUI 配图，对话式改进，一键复制富文本到公众号后台。

## 功能

1. **选题库浏览**：从 `31.内容选题/` 导入每日选题，作者点选创作
2. **三段式文章生成**：DeepSeek 初稿 → 去AI味润色 → 图片规划（封面1 + 文中3-5张）
3. **ComfyUI 生图**：调用本地 z-image 工作流，自动注入 prompt 与尺寸（≤1024×1024）
4. **对话改进**：WebSocket 流式对话，修改文章/图片/拟人度
5. **一键发布**：生成公众号兼容内联样式富文本，复制粘贴即可发布
6. **知识库集成**：文章和图片写入 `40.公众号文章/`，可在 Obsidian 中浏览

## 项目结构

```
wechat-article-agent/
├── backend/                # FastAPI 后端
│   ├── config.py           # 配置
│   ├── main.py             # 入口
│   ├── db.py / models.py   # SQLite
│   ├── api/                # 路由
│   ├── services/           # 业务逻辑
│   └── workflows/
│       └── z-image-api.json  # 用户从 ComfyUI 导出的工作流
├── frontend/               # Vue3 前端（CDN 单文件，无需 npm）
│   ├── index.html
│   └── app.js
└── README.md
```

## 启动准备

### 1. 配置 DeepSeek API Key

```powershell
# 在系统环境变量中设置，或在启动命令前临时设置
$env:DEEPSEEK_API_KEY = "你的DeepSeek API Key"
```

### 2. 导出 ComfyUI z-image 工作流

1. 打开 ComfyUI，加载你的 z-image 文生图工作流
2. 菜单 → **保存（API 格式）** / Save (API Format)
3. 将导出的 JSON 内容覆盖 `backend/workflows/z-image-api.json` 全部内容

> 工作流必须为纯文生图结构（含 EmptyLatentImage 类节点和 KSampler 节点）。

### 3. 启动 ComfyUI

确保 ComfyUI 运行在 `http://127.0.0.1:8188`。

## 启动方式

### 启动后端（终端 1）

```powershell
cd "d:\Users\Administrator\Documents\Obsidian Vault\new Vault\wechat-article-agent\backend"
$env:DEEPSEEK_API_KEY = "你的Key"  # 若未在系统变量中设置
uvicorn main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档。

### 启动前端（终端 2）

```powershell
cd "d:\Users\Administrator\Documents\Obsidian Vault\new Vault\wechat-article-agent\frontend"
npx http-server . -p 5173 -c-1 --cors
```

访问 http://localhost:5173 使用应用。

## 使用流程

1. 打开前端 → 选题库 → 选择日期 → 点选选题卡片 → 点「以此选题创作」
2. 等待三段式生成完成（约 1-2 分钟）
3. 在工作区点「🎨 一键生成全部图片」
4. 在右侧对话框输入改进指令（如「标题改短」「第二段加案例」「封面换赛博风」）
5. 点「📋 发布」→ 「复制富文本」→ 粘贴到微信公众号后台
6. 在 Obsidian 中打开 `40.公众号文章/` 查看归档

## 图片尺寸预设（均 ≤ 1024×1024）

| size_preset | 比例 | 像素 | 用途 |
|---|---|---|---|
| cover_wide | 16:9 | 1024×576 | 封面横图 |
| inline_4_3 | 4:3 | 768×576 | 文中横图（默认） |
| inline_square | 1:1 | 768×768 | 文中方图 |
| inline_portrait | 3:4 | 576×768 | 文中竖图 |

## 技术栈

- 后端：FastAPI + SQLAlchemy + httpx + websockets
- 前端：Vue3 + Element Plus + marked（CDN 加载，无需构建）
- AI：DeepSeek API（文章生成）+ ComfyUI（本地生图）
- 存储：SQLite（元数据）+ 知识库 Markdown 文件（文章正文与图片）

## 注意事项

- DEMO 版文章生成是同步阻塞的，前端会显示 loading，正式版可改后台任务
- ComfyUI 工作流未配置时，生图 API 会返回明确错误提示
- 图片复制到公众号后台时，外部图片不会自动转存，需手动下载后上传
