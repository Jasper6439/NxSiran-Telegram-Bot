# characters/

角色系统模块 — 角色定义、AI 调用、情感分析、对话引擎、记忆管理、多媒体生成。

## 角色目录结构

每个角色拥有独立目录，包含：

```
characters/{character_id}/
├── config.json          # 角色配置（必须）：名称、性格、说话风格等
├── persona.md           # 不可变层：Layer 0-5 原作设定（不可被进化修改）
├── persona_mutable.md   # 可变层：corrections、用户偏好、进化状态
├── exemplars.md         # 示例对话：原作代表性台词（few-shot prompting）
├── world.md             # 角色与游戏世界的特有关联（动态注入）
├── memories.md          # 共同记忆：关系时间线、偏好习惯、重要事件
└── novel.txt            # 原著小说（可选）：角色学习素材
```

## 蒸馏架构（Distillation Architecture）

### 三层分离原则

```
┌─────────────────────────────────────────┐
│  IMMUTABLE（不可变层）                    │
│  persona.md — 原作设定 Layer 0-5        │
│  exemplars.md — 原作示例对话             │
│  ⛔ 进化系统/学习系统不能修改             │
├─────────────────────────────────────────┤
│  MUTABLE（可变层）                       │
│  persona_mutable.md — corrections       │
│                   — 学习到的用户偏好      │
│                   — 进化状态              │
│  memories.md — 共同记忆                  │
│  ✅ 系统自动维护                          │
├─────────────────────────────────────────┤
│  DYNAMIC（动态层）                       │
│  data/world/*.md — 共享游戏世界          │
│  characters/<id>/world.md — 角色特有     │
│  🔄 按需注入，根据玩家上下文裁剪          │
└─────────────────────────────────────────┘
```

### 不可变文件保护

`character_learning.py` 和 `evolution_service.py` 中有 `IMMUTABLE_FILES` 列表：
- `persona.md`、`exemplars.md`、`config.json` 不可被自动系统修改
- 写入这些文件会被拒绝并记录 warning

## 游戏世界观架构（Layer 0.5）

```
data/world/                        ← 共享层（所有角色共用）
├── locations.md                   ← 场景地图
├── systems.md                     ← 日常系统（农场/烹饪/签到/送礼）
├── environment.md                 ← 环境感知（天气/时间）
└── interactions.md                ← 场景联动规则

characters/<id>/world.md           ← 角色层（仅该角色）
└── 角色与场景/系统/环境的特有关联
```

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 角色注册表，多角色自动发现与动态加载 | `get_current_character`, `set_current_character`, `list_characters` |
| `base.py` | 角色基类与配置模型 | `CharacterBase`, `CharacterConfig` |
| `character_learning.py` | 角色自我学习进化系统（带不可变保护） | `CharacterLearning` |
| `chayewoon.py` | 车如云角色实现（完整蒸馏版） | `Character` |
| `ai_client.py` | AI API 统一调用层, 模型 fallback | `call_ai`, `stream_chat_completion` |
| `chat_engine.py` | 统一对话处理入口, Prompt 构建 | `process_message` |
| `emotion.py` | 情绪识别, 表情反应, 亲密度计算 | `detect_emotion`, `get_reaction` |
| `memory.py` | LightRAG 向量记忆, 语义搜索 | `MemoryManager` |
| `novel_knowledge.py` | LightRAG 知识库, 小说剧情查询 | `NovelKnowledge` |
| `weather.py` | 天气查询, 天气上下文生成 | `get_seoul_weather` |

## 创建新角色

```bash
python tools/create_character.py --name "新角色" --source "来源作品"
```

自动生成：config.json + persona.md + persona_mutable.md + exemplars.md + memories.md

下一步：
1. 编辑 persona.md（不可变层：从原作蒸馏）
2. 编辑 exemplars.md（从原作提取 10-20 组示例对话）
3. 编辑 world.md（角色与游戏世界的特有关联）
4. 实现角色代码文件
