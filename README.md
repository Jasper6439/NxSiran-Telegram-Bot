# LoveSupremacy Universe — 恋爱至上主义区域

> AI 角色扮演恋爱模拟 RPG，基于 Telegram Bot + Web App，支持多模型竞争、语义记忆、情绪系统、角色进化、农场经营。

**版本**: v1.9.3 | **架构**: FastAPI + React 19 + SQLite

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│  Telegram Bot  │  Web App (React 19)  │  PWA Mini App│
└────────┬────────┴─────┬────────────┴───────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   API 路由层 (FastAPI)                │
│  认证 │ 聊天 │ 角色 │ 媒体 │ 游戏 │ 世界 │ 同步      │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   核心引擎层                          │
│  AI竞争 │ 角色系统 │ 情绪系统 │ 记忆系统 │ 进化系统   │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   服务层 (Services)                   │
│  TTS语音 │ 图像生成 │ 角色进化 │ 知识库检索           │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   基础设施层                          │
│  OpenRouter AI │ LightRAG │ SQLite │ Redis │ SMTP   │
└─────────────────────────────────────────────────────┘
```

## 核心功能

### 🤖 AI 多模型竞争

4 个免费 AI 模型轮换竞争，规则引擎 + 按需互评选出最佳回复：

```
用户发言 → 语义缓存 → 3模型并行生成 → 规则引擎评分 → 按需互评 → 返回最佳
```

- **规则引擎**（<1ms）：角色专属规则，一票否决 + 扣分制
- **轮换评委**：4 模型轮换参赛/评委，公平竞争
- **权重系统**：获胜 +0.1，失败 -0.05，持久化存储
- **语义缓存**：LightRAG 本地向量存储，语义相似度检索
- **超时熔断**：总链路 60s，自动降级

### 🎭 角色系统

可扩展的多角色框架，每个角色独立配置：

| 配置项 | 说明 |
|--------|------|
| `persona.md` | 分层角色设定（世界观→硬规则→身份→风格→情感→关系） |
| `config.json` | 角色属性、情绪默认值、觉醒条件、AI 规则 |
| `memories.md` | 共同记忆、关系时间线、偏好习惯 |

已实现角色：**车如云**（恋爱至上主义区域）

### 🧠 记忆系统

- **长期记忆**：JSON 持久化，支持搜索/删除/导出
- **语义记忆**：LightRAG 本地向量存储，语义相似度搜索
- **角色进化记忆**：`character_memory` 表，自动提取用户喜好/事件/情感
- **自我改进**：用户纠正 → 学习 → 更新行为模式
- **小说知识库**：LightRAG + 原作小说文本

### 🎭 情绪系统

- 三维情感值：好感度（affection）、幸福感（happiness）、觉醒度（awakening）
- 觉醒条件系统：满足最低情感值 + 触发关键事件
- 世界层级：stage → shadow → resonance

### 🧬 角色进化系统（v1.9.3 新增）

- **记忆提取**：每次对话结束后，LLM 自动提取关键记忆
- **情绪跟踪**：效价（valence）+ 唤醒度（arousal）二维模型
- **进化点数**：积累到阈值后更新角色系统提示词，实现性格进化
- **专属记忆**：每个用户独立记忆，AI 回复时自动注入上下文

### 🎨 多媒体

- **AI 换脸**：Gemini 2.5 Flash，用户上传照片 → AI 生成角色自拍
- **意图生图**：检测视觉意图（"发张照片"）→ 自动生成场景图片
- **表情包生成**：Pollinations AI
- **TTS 语音合成**：Edge TTS / GPT-SoVITS / CosyVoice（可插拔）
- **图片分析**：Gemini Vision
- **OCR**：文档文字识别

### 🌾 农场游戏

Phaser.js 渲染的农场经营小游戏，与角色互动：

- 种植/收获/烹饪系统
- 6 地图探索（好感度解锁）
- 角色位置追踪
- 觉醒事件触发
- 每日签到
- SSE 实时状态同步 + 增量 diff

### 🔗 Bridge 远程命令执行

通过 Webhook 服务的 Bridge 功能，可从外部向 VM 发送命令：

```
外部 (SOLO) → POST /bridge/send → VM 端轮询客户端 → 执行 → 回传结果
```

- **统一端口 8082**：与 Webhook 服务共用
- **安全认证**：Token 验证，仅授权请求可执行

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / python-telegram-bot |
| AI | OpenRouter（多模型）/ Gemini 2.5 Flash |
| 向量存储 | LightRAG（本地） |
| 关系数据库 | SQLite |
| 缓存 | Redis（可选） |
| 前端 | React 19 + TypeScript + Vite 8 + Tailwind + Zustand + Phaser 4 |
| 路由 | React Router 7 + Framer Motion |
| PWA | vite-plugin-pwa + Workbox |
| 部署 | GCP e2-micro / systemd / Cloudflare Tunnel |
| CI/CD | GitHub Webhook → deploy.sh → git pull + systemctl restart |

## 项目结构

```
main.py                          # 生产入口 (FastAPI + Telegram Bot)
├── api/                        # FastAPI 路由层
│   ├── __init__.py             # 应用工厂 (create_app)
│   ├── deps.py                 # 依赖注入 (认证/数据库)
│   ├── routes_game.py          # 游戏路由 (农场/角色/地图/同步/媒体/学习/上传)
│   ├── routes_user.py          # 用户认证路由
│   ├── routes_chat.py          # 聊天路由
│   ├── routes_character.py     # 角色管理路由
│   ├── routes_sync.py          # SSE 同步路由
│   ├── routes_media.py         # 媒体路由
│   ├── routes_world.py         # 世界系统路由
│   ├── routes_static.py        # 静态文件 + SPA Fallback
│   ├── game_state.py           # 游戏状态序列化 + 版本管理
│   └── awakening_detector.py   # 觉醒检测模块
├── services/                   # 服务层 (v1.9.3 新增)
│   ├── tts_service.py          # TTS 语音合成 (GPT-SoVITS/CosyVoice/Edge TTS)
│   ├── image_service.py        # 意图驱动图像生成 (OpenRouter/SenseNova/SiliconFlow)
│   └── evolution_service.py    # 角色进化与记忆系统
├── system/                     # 系统级模块
│   ├── config.py               # 全局配置、环境变量、版本号
│   ├── prompts.py              # 通用提示词模板、文本处理
│   ├── auth.py                 # 用户认证 (邮箱注册/密码登录/Session)
│   ├── scheduler.py            # 后台定时任务
│   ├── email_sender.py         # Gmail SMTP
│   ├── webhook_server.py       # Webhook + Bridge 服务 (port 8082)
│   └── *.service               # systemd 服务文件
├── characters/                 # 角色系统
│   ├── base.py                 # CharacterBase 抽象基类
│   ├── chayewoon.py            # 车如云角色 (含世界观/觉醒系统)
│   ├── ai_client.py            # AI API 统一调用层 (含图像生成)
│   ├── ai_core.py              # call_ai + 记忆提取
│   ├── ai_compete.py           # 多模型竞争选优
│   ├── chat_engine.py          # 统一对话引擎
│   ├── emotion.py              # 情绪系统
│   ├── image_gen.py            # 图片生成 (换脸/自拍/表情包)
│   ├── tts_engine.py           # TTS 语音合成引擎
│   ├── memory.py               # 语义记忆 (LightRAG)
│   ├── memory_legacy.py        # 长期记忆 (JSON)
│   ├── novel_knowledge.py      # 小说知识库 (LightRAG)
│   ├── character_learning.py   # 角色学习进化
│   ├── soul_manager.py         # 角色灵魂管理
│   ├── voice_manager.py        # 声音管理
│   └── ...                     # weather, music, anniversary, stats
├── core/                       # 核心业务模块
│   ├── farming_cooking.py      # 农场/料理系统
│   ├── memory.py               # 记忆管理
│   └── notification.py         # 通知系统
├── database/                   # SQLite 数据层
│   ├── base.py                 # 连接管理 + Schema
│   ├── auth.py                 # API Token 管理
│   ├── farm.py                 # 农场 CRUD
│   ├── relationship.py         # 关系/情感/觉醒
│   ├── world.py                # 世界系统
│   └── data/                   # 数据文件
│       ├── game.db             # SQLite 数据库
│       ├── game_schema.sql     # 主 Schema
│       └── migration_v20_evolution.sql  # 角色进化表
├── packages/                   # Telegram Bot 子包
│   ├── handlers/               # 消息处理 (text/photo/callback/voice)
│   ├── commands/               # Bot 命令
│   ├── analysis/               # 聊天记录分析
│   ├── importers/              # 数据导入 (聊天记录/视频)
│   └── web/                    # 旧版 Web 路由 (aiohttp)
├── web-v2/                     # React 19 前端 (SPA + PWA)
│   ├── src/                    # 源码
│   │   ├── features/           # 页面 (home/chat/game/settings)
│   │   ├── stores/             # Zustand 状态管理
│   │   └── components/         # UI 组件
│   └── dist/                   # 构建产物
├── tools/                      # 运维工具脚本
├── docs/                       # 项目文档
├── deploy.sh                   # 一键部署脚本
├── docker-compose.yml          # Docker 部署
├── Dockerfile                  # 容器构建
└── .env.example                # 环境变量模板
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（前端构建）
- AI API Key（从 [openrouter.ai](https://openrouter.ai) 获取，免费）
- Telegram Bot Token（可选，从 [@BotFather](https://t.me/BotFather) 获取）

### 安装

```bash
git clone https://github.com/Jasper6439/LoveSupremacy_Universe.git
cd LoveSupremacy_Universe

# 后端
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 AI_API_KEY（TELEGRAM_TOKEN 为可选）

# 前端（如需本地开发）
cd web-v2 && npm install && npm run build && cd ..

# 启动
python main.py
```

> 未配置 `TELEGRAM_TOKEN` 时，仅启动 Web 服务（端口 8080），Telegram Bot 功能跳过。

### 一键部署（GCP e2-micro）

```bash
sudo bash deploy.sh
```

自动完成：代码拉取 → 依赖安装 → systemd 配置 → 服务启动 → 健康检查

### Docker 部署

```bash
docker-compose up -d
```

### e2-micro (1GB RAM) 优化

```bash
sudo bash tools/optimize_e2micro.sh
```

- 2GB Swap + swappiness=60 + systemd 内存控制

## 环境变量

| 变量 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `TELEGRAM_TOKEN` | 可选 | Telegram Bot Token | (空) |
| `AI_API_KEY` | **必填** | OpenRouter API Key | (空) |
| `AI_API_BASE` | 可选 | AI API 地址 | `https://openrouter.ai/api/v1` |
| `AI_MODEL` | 可选 | 默认 AI 模型 | `google/gemini-2.0-flash-exp:free` |
| `GEMINI_API_KEY` | 可选 | Gemini API (图片分析) | (空) |
| `DATA_DIR` | 可选 | 数据存储目录 | `/opt/NxSiran-Telegram-Bot/data` |
| `PORT` | 可选 | Web 服务端口 | `8080` |
| `PUBLIC_URL` | 可选 | 公网 URL | (空) |
| `ADMIN_USERNAME` | 可选 | 管理员用户名 | (空) |
| `REDIS_URL` | 可选 | Redis 连接 | `redis://localhost:6379/0` |
| `GITHUB_WEBHOOK_SECRET` | 可选 | GitHub 自动部署密钥 | (空) |
| `TTS_BACKEND` | 可选 | TTS 后端 (sovits/cosyvoice/edge) | `sovits` |
| `LOCAL_TTS_URL` | 可选 | 本地 TTS 服务地址 | `http://127.0.0.1:9880` |
| `SENSENOVA_API_KEY` | 可选 | 商汤生图 API | (空) |
| `SILICONFLOW_API_KEY` | 可选 | SiliconFlow API | (空) |
| `EVOLUTION_MODEL` | 可选 | 进化分析模型 | `deepseek/deepseek-r1:free` |

## Telegram 命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始对话 |
| `/reset` | 重置对话 |
| `/selfie` | 查看自拍相册 |
| `/genface` | AI 换脸生成 |
| `/memory` | 查看记忆 |
| `/forget` | 删除记忆 |
| `/stats` | 统计数据 |
| `/analyze` | 对话模式分析 |
| `/sticker` | 表情包生成 |
| `/tts` | 语音合成开关 |
| `/novel` | 小说知识查询 |
| `/version` | 版本信息 |

## Web API

### 认证

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |

### 聊天

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送聊天消息 |

### 角色

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/characters` | GET | 角色列表 |
| `/api/characters/switch` | POST | 切换角色 |
| `/api/characters/evolve` | POST | 角色学习进化 |
| `/api/characters/learn/memory` | POST | 从向量记忆学习 |
| `/api/characters/learn/novel` | POST | 从小说学习 |
| `/api/characters/learn/chat` | POST | 从聊天记录学习 |

### 游戏

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/game/state/sse` | GET | SSE 实时状态推送 |
| `/api/game/state/diff` | GET | 增量状态差异 |
| `/api/mobile/dpad` | POST | 移动端方向键移动 |
| `/api/mobile/tap` | POST | 移动端点击交互 |

### 媒体上传

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/upload/voice` | POST | 上传角色声音样本 |
| `/api/upload/chatlog` | POST | 上传聊天记录 |
| `/api/upload/video` | POST | 上传角色视频学习 |
| `/api/upload-selfies` | POST | 上传照片 |
| `/api/generate-face` | POST | AI 换脸 |

### Webhook / Bridge（端口 8082）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/bridge/send` | POST | 发送命令到 VM |
| `/bridge/poll` | POST | VM 轮询获取命令 |
| `/bridge/result/{id}` | GET | 查询命令执行结果 |
| `/deploy` | GET/POST | 手动触发部署 |
| `/health` | GET | 健康检查 |

## 许可证

MIT License
