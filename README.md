# NxSiran - 恋爱至上主义区域

> AI 角色扮演对话系统，基于 Telegram Bot + Web，支持多角色、多模型竞争、语义记忆、情绪系统。

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│  Telegram Bot  │  Web App  │  Telegram Mini App     │
└────────┬────────┴─────┬────┴───────────┬────────────┘
         │              │                │
┌────────▼──────────────▼────────────────▼────────────┐
│                   API 路由层                          │
│  认证 │ 聊天 │ 角色 │ 媒体 │ 游戏 │ 技能 │ 分析      │
└────────┬──────────────┬────────────────┬────────────┘
         │              │                │
┌────────▼──────────────▼────────────────▼────────────┐
│                   核心引擎层                          │
│  AI竞争 │ 规则引擎 │ 角色系统 │ 情绪系统 │ 记忆系统  │
└────────┬──────────────┬────────────────┬────────────┘
         │              │                │
┌────────▼──────────────▼────────────────▼────────────┐
│                   基础设施层                          │
│  OpenRouter AI │ Qdrant │ SQLite │ Gmail SMTP       │
└─────────────────────────────────────────────────────┘
```

## 核心功能

### AI 多模型竞争

4 个免费 AI 模型轮换竞争，规则引擎 + 按需互评选出最佳回复：

```
用户发言 → Qdrant缓存 → 3模型并行生成 → 规则引擎评分 → 按需互评 → 返回最佳
```

- **规则引擎**（<1ms）：角色专属规则，一票否决 + 扣分制
- **轮换评委**：4 模型轮换参赛/评委，公平竞争
- **权重系统**：获胜 +0.1，失败 -0.05，持久化存储
- **Qdrant 缓存**：语义相似度 > 0.92 直接返回，毫秒级响应
- **超时熔断**：总链路 60s，自动降级

### 角色系统

可扩展的多角色框架，每个角色独立配置：

| 配置项 | 说明 |
|--------|------|
| `persona.md` | 分层角色设定（世界观→硬规则→身份→风格→情感→关系） |
| `config.json` | 角色属性、情绪默认值、觉醒条件、**AI 规则** |
| `memories.md` | 共同记忆、关系时间线、偏好习惯 |
| `ai_rules` | 规则引擎配置（长度、格式、语言、禁用词等） |

已实现角色：**车如云**（恋爱至上主义区域）

### 记忆系统

- **长期记忆**：JSON 持久化，支持搜索/删除/导出
- **语义记忆**：Qdrant 向量数据库，语义相似度搜索
- **自我改进**：用户纠正 → 学习 → 更新行为模式
- **小说知识库**：LightRAG + 原作小说文本

### 情绪系统

- 三维情感值：好感度（affection）、幸福感（happiness）、觉醒度（awakening）
- 觉醒条件系统：满足最低情感值 + 触发关键事件
- 世界层级：stage → shadow → resonance

### 多媒体

- **AI 换脸**：Gemini 2.5 Flash，用户上传照片 → AI 生成角色自拍
- **表情包生成**：Pollinations AI
- **TTS 语音合成**：韩语男声 + 声音克隆
- **图片分析**：Gemini Vision
- **OCR**：文档文字识别

### 农场游戏

DOM 渲染的农场经营小游戏，与角色互动：

- 种植/收获/烹饪系统
- 多地图探索
- 角色位置追踪
- 觉醒事件触发
- 每日签到

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.10+ / aiohttp |
| AI | OpenRouter（多模型）/ Gemini 2.5 Flash |
| 向量数据库 | Qdrant |
| 关系数据库 | SQLite |
| 前端 | 原生 HTML/CSS/JS + Telegram Mini App |
| 部署 | Docker / systemd / Webhook 自动部署 |
| 邮件 | Gmail SMTP |

## 项目结构

```
├── bot.py                  # Telegram Bot 主入口
├── ai_compete.py           # AI 多模型竞争引擎
├── ai_client.py            # AI API 调用封装
├── ai_core.py              # AI 对话核心
├── image_gen.py            # 图片生成（换脸/表情包）
├── auth.py                 # 用户认证系统
├── config.py               # 全局配置
├── characters/             # 角色系统
│   ├── base.py             # 角色基类 + 配置数据类
│   ├── __init__.py         # 角色注册表
│   ├── chayewoon/          # 车如云角色数据
│   │   ├── config.json     # 角色配置（含 ai_rules）
│   │   ├── persona.md      # 分层角色设定
│   │   └── memories.md     # 共同记忆
│   └── templates/          # 新角色模板
├── packages/
│   ├── web/                # Web API 路由
│   ├── commands/           # Telegram 命令
│   ├── handlers/           # 消息处理器
│   ├── bridge/             # VM Bridge
│   └── analysis/           # 聊天记录分析
├── game_api/               # 农场游戏 API
├── database/               # SQLite 数据层
├── static/                 # 静态资源（游戏/Mini App）
├── templates/              # HTML 模板
├── knowledge/              # 小说知识库
├── email_sender.py         # Gmail SMTP 邮件发送
├── qdrant_memory.py        # Qdrant 语义记忆
├── tts_engine.py           # 语音合成
├── emotion.py              # 情绪系统
└── webhook_server.py       # Webhook 自动部署
```

## 快速开始

### 环境要求

- Python 3.10+
- Telegram Bot Token（从 [@BotFather](https://t.me/BotFather) 获取）
- OpenRouter API Key（从 [openrouter.ai](https://openrouter.ai) 获取，免费）
- Qdrant（Docker 一键部署）

### 安装

```bash
git clone https://github.com/Jasper6439/NxSiran-Telegram-Bot.git
cd NxSiran-Telegram-Bot
pip install -r requirements.txt
```

### 配置

1. 复制配置模板：
```bash
cp config.example.json data/config.json
```

2. 编辑 `data/config.json`：
```json
{
    "telegram_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "ai_api_key": "YOUR_OPENROUTER_KEY",
    "ai_api_base": "https://openrouter.ai/api/v1"
}
```

3. （可选）配置 Gmail SMTP 用于发送验证码邮件：
```json
{
    "smtp_email": "your@gmail.com",
    "smtp_password": "your-app-specific-password"
}
```

### 启动

```bash
# 启动 Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 启动 Bot
python bot.py
```

### Docker 部署

```bash
docker-compose up -d
```

## Telegram 命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始对话 |
| `/reset` | 重置对话 |
| `/selfie` | 查看自拍相册 |
| `/genface` | AI 换脸生成 |
| `/memory` | 查看记忆 |
| `/stats` | 统计数据 |
| `/analyze` | 对话模式分析 |
| `/sticker` | 表情包生成 |
| `/tts` | 语音合成 |
| `/novel` | 小说知识查询 |
| `/version` | 版本信息 |

## 添加新角色

1. 使用模板创建角色目录：
```bash
python tools/create_character.py --id my_character --name "角色名"
```

2. 编辑 `characters/my_character/` 下的配置文件：
   - `config.json` — 角色属性 + `ai_rules` 规则引擎配置
   - `persona.md` — 分层角色设定
   - `memories.md` — 共同记忆

3. 在 `characters/my_character.py` 实现角色类（继承 `CharacterBase`）

### ai_rules 配置示例

```json
{
    "ai_rules": {
        "max_length": 80,
        "require_ellipsis": true,
        "require_action_parentheses": true,
        "disqualify_positive_emotions": true,
        "positive_emotions": ["我好喜欢你", "我爱你"],
        "disallow_emoji": true,
        "min_cjk_ratio": 0.2,
        "languages": ["zh", "ko"],
        "judge_prompt_extra": "该角色是傲娇性格，话极少"
    }
}
```

## Web API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |
| `/api/chat` | POST | 发送聊天消息 |
| `/api/characters` | GET | 角色列表 |
| `/api/characters/switch` | POST | 切换角色 |
| `/api/upload-selfies` | POST | 上传照片 |
| `/api/generate-face` | POST | AI 换脸 |
| `/api/config` | GET/POST | 管理员配置 |

## 许可证

MIT License
