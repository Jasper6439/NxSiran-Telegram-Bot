# 项目知识摘要 (Agent Memory)

> **必读**: 每次开发前请先阅读此文件，了解项目最新变动和关键知识。

---

## [2026-05-15] v1.6.5-hotfix 核心文件更新

**Context**: 紧急更新项目宪法文件，确立 e2-micro 极限优化规范

**Category**: 文档更新, 架构规范

**变更内容**:

| 文件 | 变更 |
|------|------|
| `AGENTS.md` | 重写为中文宪法格式，明确生存红线、工作流协议、记忆固化要求 |
| `design.md` | 新建技术蓝图，定义混合检索架构、部署规范、禁止事项 |

**核心架构原则**:
- 双路混合检索：BM25 (本地) + LightRAG (云端)
- 内存铁律：512MB RSS 上限
- 异步强制：所有网络 I/O 必须异步

**工作流协议要点**:
1. 任务前：先读 `memory.md` → `design.md` → `PROJECT_CONTEXT.md`
2. 任务后：更新 README → 语法验证 → 原子提交 → **记忆固化**

---

## [2025-05-15] v1.6.5 e2-micro 极限性能优化

**Context**: GCP e2-micro (1 vCPU, 1GB RAM) 极限减负，目标零崩溃稳定运行

**Category**: 性能优化, 架构重构

**目标**: 3 AI 竞争 + 1 评委 + LightRAG 深度记忆 + 多模态生成

**开发检查表**:

| 任务 | 状态 | 说明 |
|------|------|------|
| 移除 qdrant-client | ✅ 完成 | 改用 LightRAG 自带存储 |
| 添加 rank-bm25 | ✅ 完成 | 已安装并配置 |
| 内存监控脚本 | ✅ 完成 | `tools/memory_monitor.py` |
| API Key 配置 | ✅ 完成 | `system/config.py` |
| 系统优化脚本 | ✅ 完成 | `optimize_memory.sh` |
| Python 语法验证 | ✅ 完成 | `python -m py_compile` |
| 创建回滚标签 | ✅ 完成 | `git tag rollback-pre-v165` |
| BM25+LightRAG 混合检索 | ✅ 完成 | `characters/retrieval_engine.py` |
| 上下文截断 (1024 tokens) | ✅ 完成 | `characters/token_utils.py` |
| OpenRouter 流式输出 | ✅ 完成 | `call_ai_stream()` |

**架构原则**:
- LLM 核心层 → OpenRouter 云端（`:free` / `:nitro` 模型）
- 数据存储层 → 本地硬盘（LightRAG + BM25）
- 严禁在本地加载任何 LLM 权重
- 所有外部 API 必须异步 (`aiohttp` / `asyncio`)

**关键约束**:
- 内存 > 85%: 自动清理缓存
- 内存 > 95%: 告警 + 自愈重启
- Max Context = 1024 tokens（防止 KV Cache 溢出）

**执行命令**:
```bash
# 创建回滚点
git tag rollback-pre-v165

# 语法验证
python -m py_compile system/*.py characters/*.py game_api/*.py

# 服务器部署后执行内存优化
bash optimize_memory.sh
```

---

## [2025-05-15] v1.6.5 版本更新

**Context**: Agent 完成 v1.6.3-v1.6.5 三个版本开发

**Category**: 代码结构, 代码模式

**Instructions**:
- **游戏状态同步**: `game_api/game_state.py` 是状态管理核心，提供 `serialize_game_state()`, `notify_state_change()`, SSE 推送
- **版本号机制**: 进程级内存存储，重启后重置，前端自动全量拉取
- **多角色加载**: `characters/__init__.py` 自动扫描含 `config.json` 的子目录
- **角色目录标准结构**: `characters/{id}/config.json` + `persona.md` + `memories.md` + `novel.txt`
- **移动端 API**: `/api/mobile/dpad`, `/api/mobile/tap`, `/api/mobile/swipe`, `/api/mobile/config`
- **回滚点**: `rollback-pre-v165` 标签指向 v1.6.5 版本起点

---

## [2025-05-15] 目录重构

**Context**: 将 knowledge/chayewoon/novel.txt 移至 characters/chayewoon/

**Category**: 代码结构

**Instructions**:
- 原著小说作为角色学习素材，应与角色配置放在一起
- 角色自我进化素材路径: `characters/{character_id}/novel.txt`
- LightRAG 知识库初始化时会读取此文件

---

## [2025-05-15] 关键代码模式

**Context**: 项目编码规范总结

**Category**: 代码模式

**Instructions**:
- **导入规范**: 绝对导入 `from system.config import X`，包内相对导入 `from .sibling import Y`
- **数据库**: SQLite + Mixin 模式，`get_db()` 返回线程本地实例
- **API 路由**: `game_api/` 游戏 API，`packages/web/` Web API，统一在 `__init__.py` 注册
- **状态变更通知**: 任何修改游戏状态的操作后必须调用 `notify_state_change(user_id, changed_keys)`
- **角色参数**: API 支持 `character_id` query/body 参数，默认使用 `get_current_character()`
- **e2-micro 约束**: 内存 <512MB，禁止 WebSocket，使用 SSE；算法 O(n log n) 上限

---

## [2025-05-15] AGENTS.md 合规检查

**Context**: 项目治理文件

**Category**: 构建方法

**Instructions**:
- 开发前必须阅读: `PROJECT_CONTEXT.md` + 目标目录 `README.md`
- 新增文件必须在目录 README 中添加条目
- 大重构前创建回滚点: `git tag rollback-pre-v{version}`
- 完成后验证: `python -m py_compile <file>`
- 根 README 检查: 任何结构变更后评估是否需要更新

---

## [2025-05-15] 角色自我进化链条（待验证）

**Context**: 用户质疑自我进化流程完整性

**Category**: 代码模式

**Instructions**:
- 当前组件: `novel_knowledge.py` (LightRAG), `qdrant_memory.py` (向量记忆), `characters/chayewoon.py` (prompt 构建)
- 角色目录: `config.json` → `persona.md` (详细设定) → `memories.md` (共同记忆) → `novel.txt` (原著素材)
- **待确认**: 用户上传资料 → 角色学习 → 写进 persona/memories → 下次对话自动使用
- **待确认**: Qdrant 提取的记忆如何整合到 prompt
- **待确认**: 是否有自动化的"学习-更新"闭环

---

## [2025-05-15] v1.6.4.1 角色自我学习进化

**Context**: 修复角色自我进化链条，实现完整的"用户上传资料 → 角色学习 → 更新 prompt → 下次对话使用"闭环

**Category**: 代码结构, 代码模式

**Instructions**:
- **角色自我进化链条**:
  1. 用户上传资料 → `characters/{id}/novel.txt`
  2. 角色学习 → `POST /api/characters/evolve` 触发 `character_learning.py`
  3. 更新 persona/memories → `CharacterLearning._update_persona_learned()` / `_update_memories_user_profile()`
  4. 下次对话自动使用 → `chayewoon.py` 的 `get_system_prompt()` 自动加载 `persona.md` + `memories.md`
- **核心模块**: `characters/character_learning.py` — `CharacterLearning` 类提供三阶段学习（novel/chat/qdrant）
- **API 端点**: `/api/characters/evolve`, `/api/characters/learn/novel`, `/api/characters/learn/chat`, `/api/characters/learn/qdrant`, `/api/characters/learning/status`
- **Qdrant 记忆整合**: `chayewoon.py` 新增 `_get_relevant_memories()` 方法，可在对话前异步获取相关记忆注入 prompt
- **novel_knowledge 路径**: 已修复为 `characters/{id}/novel.txt`

---

## [2025-05-15] v1.6.4.2 上传与学习链路

**Context**: 实现声音/聊天记录/视频上传的完整学习链路

**Category**: 代码结构, 代码模式

**Instructions**:
- **角色声音管理**: `characters/voice_manager.py` — `VoiceManager` 类管理声音样本，支持 Fish Speech 克隆
  - 存储路径: `characters/{id}/voice/sample_*.mp3`
  - 配置: `characters/{id}/voice/voice_config.json`
  - API: `POST /api/upload/voice`, `POST /api/upload/voice/clone`
- **用户灵魂画像**: `characters/soul_manager.py` — 所有角色共享的 `characters/soul.md`
  - 从聊天记录生成: `generate_soul_from_chatlog()`
  - 画像维度: 性格、沟通风格、情感需求、关系模式、兴趣偏好、敏感点
  - API: `POST /api/upload/chatlog`
- **视频学习**: `packages/importers/video_enhanced.py` — 视频 → 音频/字幕提取 → AI 分析 → 更新 persona
  - 支持: 字幕提取、Whisper/Google 语音识别、AI 分析角色特点
  - API: `POST /api/upload/video`
- **完整学习链路**:
  1. 声音上传 → `characters/{id}/voice/` → TTS 克隆
  2. 聊天记录上传 → AI 分析 → `characters/soul.md`
  3. 视频上传 → 音频/字幕提取 → AI 分析 → `persona.md`

---

*此文件由 Agent 在编码后自动更新，记录项目关键知识和变动。*
