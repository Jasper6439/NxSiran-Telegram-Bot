# characters/

角色系统模块 — 角色定义、AI 调用、情感分析、对话引擎、记忆管理、多媒体生成。

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 角色注册表，多角色自动发现与动态加载 | `get_current_character`, `set_current_character`, `list_characters`, `get_all_character_ids`, `load_characters_from_dir` |
| `base.py` | CharacterBase 抽象基类, CharacterConfig 数据类 | `CharacterBase`, `CharacterConfig` |
| `chayewoon.py` | 车如云角色实现（完整蒸馏版） | `Character` |
| `ai_client.py` | AI API 统一调用层, 模型 fallback 机制 | `call_ai`, `MAX_HISTORY_MESSAGES` |
| `ai_core.py` | AI 调用核心逻辑, 系统提示词组装, 记忆提取 | `call_ai`, `summarize_and_save_memory` |
| `ai_compete.py` | AI 竞争模块, 规则引擎评分 + 互评 + Qdrant 缓存 + 超时熔断 | `compete_ai` |
| `chat_engine.py` | 统一对话处理入口, Prompt 构建, 情感/觉醒/记忆整合 | `process_message` |
| `chat_history.py` | 聊天历史持久化, 加载, 迁移 | `load_chat_history`, `append_user_message`, `append_bot_message` |
| `emotion.py` | 情绪识别, 表情反应, 亲密度计算, 主动行为系统 | `detect_emotion`, `get_reaction` |
| `emotion_analyzer.py` | 对话情感分析, 好感度/幸福度/觉醒度变化量计算 | `analyze_emotion` |
| `memory_legacy.py` | 旧版 JSON 记忆系统, 语义记忆, 自我改进 | `save_memory_entry`, `search_memory` |
| `qdrant_memory.py` | Qdrant Cloud 向量记忆, 语义搜索 | `QdrantMemory` |
| `image_gen.py` | 图片生成, 场景检测, AI 图像分析 | `generate_sticker_url`, `analyze_image_with_gemini` |
| `tts_engine.py` | TTS 语音合成, GPT-SoVITS/Edge TTS/Fish Speech 三后端 | `TTSEngine` |
| `music_skill.py` | 音乐搜索（yt-dlp）, 角色化评价 | `search_music` |
| `novel_knowledge.py` | LightRAG 知识库, 小说剧情查询 | `NovelKnowledge` |
| `weather.py` | 天气查询（wttr.in）, 天气上下文生成 | `get_seoul_weather`, `get_weather_context` |
| `anniversary.py` | 纪念日管理, 在一起天数, 随机生活事件 | `load_anniversaries`, `add_anniversary`, `get_upcoming_anniversary` |
| `stats.py` | 聊天统计, 额度追踪, 报告系统 | `load_quota_usage`, `save_quota_usage`, `format_quota_report` |

## 依赖关系

- `ai_client.py` / `ai_core.py` → `config.py`, `httpx`
- `chat_engine.py` → `ai_client`, `emotion`, `emotion_analyzer`, `memory_legacy`, `qdrant_memory`
- `qdrant_memory.py` → `lightrag`, Qdrant Cloud
- `tts_engine.py` → GPT-SoVITS / Edge TTS / Fish Speech 外部 API
