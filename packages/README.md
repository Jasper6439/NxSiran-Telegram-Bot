# packages/

Telegram Bot 子包 — 命令、消息处理器、Web API、分析、导入器。

## 子包索引

| 子包 | 职责 | 模块数 |
|------|------|--------|
| `handlers/` | Telegram Update 分发与处理（文字/照片/语音/回调） | 5 |
| `commands/` | Bot 命令注册与执行（基础/技能/杂项/导入/研究等） | 12 |
| `web/` | HTTP API 路由 (FastAPI), 页面服务, CORS | 11 |
| `bridge/` | VM 远程命令/文件桥接, MiniApp 消息同步 | 2 |
| `analysis/` | 聊天记录解析与统计分析 | 1 |
| `importers/` | 外部数据导入（微信聊天记录/视频） | 3 |

## handlers/ 模块

| 模块 | 职责 |
|------|------|
| `message.py` | 中央 re-export hub, 聚合所有 handler |
| `text_message.py` | 文字消息处理, 整合所有 Skill |
| `photo.py` | 照片/文档处理, AI 图像分析 |
| `callback.py` | 内联按钮回调分发 |
| `voice.py` | TTS 声音克隆, 音乐/小说/记忆命令 |

## commands/ 模块

| 模块 | 职责 |
|------|------|
| `basic.py` | 基础命令（start, reset, selfie, memory, export） |
| `skills.py` | 技能命令（sticker, analyze, stats） |
| `extra.py` | 图像分析命令（analyze_img, ocr） |
| `misc.py` | 杂项聚合（quota, anniversary, summarize, research, relay, updater） |
| `import_cmds.py` | 聊天记录/视频导入命令 |
| `utils.py` | 公共工具（auto_delete_messages, call_gemini, web_search） |

## web/ 模块

| 模块 | 职责 |
|------|------|
| `routes.py` | 路由注册入口, CORS 中间件 |
| `auth_routes.py` | 用户注册/登录 API |
| `chat_routes.py` | Web 端聊天 + 仪表盘统计 API |
| `character_routes.py` | 角色绑定/切换/配置 API |
| `media_routes.py` | 自拍/照片/TTS 语料管理 API |
| `page_routes.py` | 健康检查, SPA/MiniApp/游戏页面服务 |
| `skills_routes.py` | Skills 列表/切换/安装/卸载 API |
| `sync_routes.py` | Web <-> Telegram 双向消息同步 API |
| `mobile_routes.py` | 移动端触控 API |
| `analysis_routes.py` | 聊天记录/视频分析 API |

## importers/ 模块

| 模块 | 职责 |
|------|------|
| `chatlog.py` | 聊天记录导入（微信/JSON/TXT） |
| `video.py` | 视频分析导入 |
| `video_enhanced.py` | 增强视频分析（更详细的帧提取） |
