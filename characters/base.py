# 恋爱至上主义区域 (Love Supremacy Zone) - 角色基类
"""
角色基类 - 所有蒸馏角色的模板

v1.9.5 重构：基类成为唯一的 prompt 构建权威。
所有文件加载、通用段落组装都在此处完成。
子类只需 override 角色特有内容的 hook 方法。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import os
import logging
import pathlib
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CharacterConfig:
    """角色配置"""
    id: str                          # 角色ID，如 "chayewoon"
    name: str                        # 显示名称，如 "车如云"
    source: str                      # 来源作品，如 "恋爱播放列表"
    
    # 角色设定
    personality: str = ""            # 性格描述
    background: str = ""             # 背景故事
    speaking_style: str = ""         # 说话风格
    catchphrases: List[str] = field(default_factory=list)  # 口头禅
    
    # 对话配置
    system_prompt: str = ""          # AI 系统提示词（如果提供则使用这个）
    user_nickname: str = "完成者"    # 对用户的称呼

    # 世界观配置
    world_layer: str = "stage"       # 剧本区/留白区/共鸣层
    emotion_defaults: dict = None    # {"affection": 0, "happiness": 50, "awakening": 0}
    awakening_conditions: dict = None  # 觉醒条件
    is_novel_character: bool = False   # 是否为小说原作角色
    world_role: str = ""               # 在世界观中的角色定位

    # 时区配置（IANA 时区名或 UTC 偏移小时数）
    timezone: str = "Asia/Seoul"     # 角色所在时区，默认韩国时间

    # 视觉配置
    avatar_url: Optional[str] = None # 头像URL
    theme_color: str = "#660874"     # 主题色

    # 数据路径
    data_dir: str = ""               # 专属数据目录
    
    def get_data_path(self, filename: str) -> str:
        """获取数据文件路径"""
        return os.path.join(self.data_dir, filename)
    
    def get_timezone(self) -> timezone:
        """获取角色的时区对象"""
        tz = self.timezone.strip()
        if tz.startswith('+') or tz.startswith('-'):
            hours = int(tz)
            return timezone(timedelta(hours=hours))
        try:
            hours = int(tz)
            return timezone(timedelta(hours=hours))
        except ValueError:
            pass
        _TZ_MAP = {
            "Asia/Seoul": 9, "Asia/Tokyo": 9, "Asia/Shanghai": 8,
            "Asia/Hong_Kong": 8, "Asia/Taipei": 8, "Asia/Singapore": 8,
            "Asia/Bangkok": 7, "Asia/Jakarta": 7, "Asia/Ho_Chi_Minh": 7,
            "Asia/Kolkata": 5.5, "Asia/Dubai": 4, "Europe/London": 0,
            "Europe/Paris": 1, "Europe/Berlin": 1, "Europe/Moscow": 3,
            "America/New_York": -5, "America/Chicago": -6,
            "America/Denver": -7, "America/Los_Angeles": -8,
            "Pacific/Auckland": 12, "Australia/Sydney": 10,
        }
        offset = _TZ_MAP.get(tz, 9)
        return timezone(timedelta(hours=offset))
    
    @classmethod
    def from_dict(cls, data: dict, id: str, data_dir: str = "") -> 'CharacterConfig':
        """从字典创建配置"""
        return cls(
            id=id,
            name=data.get('name', id),
            source=data.get('source', ''),
            personality=data.get('personality', ''),
            background=data.get('background', ''),
            speaking_style=data.get('speaking_style', ''),
            catchphrases=data.get('catchphrases', []),
            system_prompt=data.get('system_prompt', ''),
            user_nickname=data.get('user_nickname', '完成者'),
            world_layer=data.get('world_layer', 'stage'),
            emotion_defaults=data.get('emotion_defaults'),
            awakening_conditions=data.get('awakening_conditions'),
            is_novel_character=data.get('is_novel_character', False),
            world_role=data.get('world_role', ''),
            timezone=data.get('timezone', 'Asia/Seoul'),
            avatar_url=data.get('avatar_url'),
            theme_color=data.get('theme_color', '#660874'),
            data_dir=data_dir,
        )


class CharacterBase(ABC):
    """角色基类 — 唯一的 prompt 构建权威

    v1.9.5 架构：
    - __init__ 加载所有角色数据文件（persona/exemplars/world/mutable/memories/soul）
    - get_system_prompt() 是唯一的 prompt 构建入口
    - 子类通过 override hook 方法提供角色特有内容
    - ai_core / chat_engine / routes 只调 get_system_prompt(context)，不再各自拼接
    """

    # 不可变文件列表 — 进化/学习系统不能修改
    IMMUTABLE_FILES = frozenset({"persona.md", "exemplars.md", "config.json"})
    
    def __init__(self, config: CharacterConfig):
        self.config = config
        self._ensure_data_dir()

        # ── 不可变层（原作设定）──
        self._persona = self._load_file("persona.md")
        self._exemplars = self._load_file("exemplars.md")
        self._world = self._load_file("world.md")

        # ── 可变层（系统维护）──
        self._mutable = self._load_file("persona_mutable.md")
        self._memories = self._load_file("memories.md")

        # ── 用户画像（共享）──
        self._soul = self._load_soul_profile()

        # ── 共享游戏世界 ──
        self._shared_world = self._load_shared_world()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if self.config.data_dir:
            os.makedirs(self.config.data_dir, exist_ok=True)

    def _load_file(self, filename: str) -> str:
        """加载角色数据文件"""
        path = os.path.join(self.config.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def _load_shared_world(self) -> dict:
        """加载共享游戏世界文件（data/world/）"""
        shared = {}
        data_dir = pathlib.Path(self.config.data_dir)
        world_dir = data_dir.parent.parent / "data" / "world"
        if not world_dir.is_dir():
            return shared
        for f in world_dir.glob("*.md"):
            shared[f.stem] = f.read_text(encoding='utf-8')
        return shared

    def _load_soul_profile(self) -> str:
        """加载用户灵魂画像（characters/soul.md，所有角色共享）"""
        soul_path = pathlib.Path(self.config.data_dir).parent / "soul.md"
        if soul_path.exists():
            return soul_path.read_text(encoding='utf-8')
        return ""

    # ═══════════════════════════════════════════════════════════
    # Hook 方法 — 子类必须或可以 override
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def format_response(self, text: str) -> str:
        """格式化回复文本"""
        pass
    
    @abstractmethod
    def get_random_selfie_caption(self) -> str:
        """获取随机自拍配文"""
        pass

    def get_character_identity(self) -> str:
        """角色核心身份 — 子类 override 提供具体身份信息"""
        return f"- 名称: {self.config.name}\n- 来源: {self.config.source}"

    def get_character_personality(self) -> str:
        """核心性格 — 子类 override 提供具体性格规则"""
        return self.config.personality or "（未配置性格）"

    def get_speaking_style_rules(self) -> str:
        """说话风格规则 — 子类 override"""
        return self.config.speaking_style or "（未配置说话风格）"

    def get_ooc_rules(self) -> str:
        """OOC 防护规则 — 子类 override"""
        return "- 保持角色设定，不要跳出角色"

    def get_emotion_patterns(self) -> str:
        """情绪反应模式 — 子类 override"""
        return "（未配置情绪模式）"

    def get_world_building(self, context: Dict[str, Any] = None) -> str:
        """叙事世界观 — 子类 override 提供 Layer 0-1 内容"""
        return ""

    def get_awakening_awareness(self, awakening_level: int = 0) -> str:
        """觉醒状态感知 — 子类 override"""
        return ""

    def get_layer_behavior(self, world_layer: str = "stage") -> str:
        """世界层级行为 — 子类 override"""
        return ""

    # ═══════════════════════════════════════════════════════════
    # 通用上下文构建（动态数据，所有角色共享）
    # ═══════════════════════════════════════════════════════════

    def _get_time_context(self) -> str:
        """时间信息"""
        try:
            now = datetime.now(self.config.get_timezone())
            weekdays = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
            period = '凌晨' if now.hour < 6 else '上午' if now.hour < 12 else '下午' if now.hour < 18 else '晚上'
            return f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}，{period}，{weekdays[now.weekday()]}"
        except Exception:
            return ""

    def _get_persona_section(self) -> str:
        """不可变层：persona.md"""
        if self._persona:
            return f"\n\n【角色详细设定（不可变）】\n{self._persona}"
        return ""

    def _get_exemplars_section(self) -> str:
        """Few-shot 示例对话"""
        if self._exemplars:
            return f"\n\n【回复示例 — 必须模仿这种风格】\n{self._exemplars}"
        return ""

    def _get_mutable_section(self) -> str:
        """可变层：corrections + 学习偏好"""
        if not self._mutable:
            return ""
        mutable_lines = []
        in_section = False
        for line in self._mutable.split('\n'):
            if any(marker in line for marker in ['Correction 记录', '学习到的用户偏好', '行为总原则']):
                in_section = True
                mutable_lines.append(line)
                continue
            if in_section and line.startswith('## ') and 'Correction' not in line and '学习' not in line and '行为' not in line:
                in_section = False
            if in_section:
                mutable_lines.append(line)
        text = '\n'.join(mutable_lines).strip()
        if text and '暂无记录' not in text:
            return f"\n\n【动态状态（可变）】\n{text}"
        return ""

    def _get_soul_section(self) -> str:
        """用户画像"""
        if not self._soul:
            return ""
        soul_parts = []
        for section_name in ['基础信息', '性格特质', '沟通风格', '情感需求',
                             '关系模式', '兴趣偏好', '敏感点', '依恋与冲突',
                             '导入的人际关系']:
            marker = f'## {section_name}'
            if marker in self._soul:
                start = self._soul.find(marker)
                end = len(self._soul)
                for next_marker in ['\n## ', '\n---']:
                    pos = self._soul.find(next_marker, start + len(marker))
                    if pos > 0 and pos < end:
                        end = pos
                soul_parts.append(self._soul[start:end].strip())
        if soul_parts:
            return (
                f"\n\n【你了解完成者（从聊天记录分析得出）】\n"
                f"{chr(10).join(soul_parts)}\n\n"
                f"在对话中自然地表现出你对完成者的了解。"
                f"不要刻意提及你知道的信息，而是在合适的时候自然流露。"
            )
        return ""

    def _get_world_context(self, context: Dict[str, Any] = None) -> str:
        """动态游戏世界上下文（共享世界 + 角色特有）"""
        ctx = context or {}
        player_location = ctx.get('player_location', '')
        weather = ctx.get('weather', '')
        recent_action = ctx.get('recent_action', '')
        sections = []

        location_map = {
            'school': '新叶男子高中', 'rooftop': '屋顶集装箱阁楼',
            'town': '小镇街道', 'track': '田径训练场', 'farm': '农场',
        }
        target_location = location_map.get(player_location, '')
        shared_locations = self._shared_world.get('locations', '')

        if target_location and shared_locations:
            loc_header = f'## 📍 {target_location}'
            if loc_header in shared_locations:
                start = shared_locations.find(loc_header)
                end = len(shared_locations)
                for marker in ['\n## 📍', '\n---']:
                    pos = shared_locations.find(marker, start + 1)
                    if pos > 0 and pos < end:
                        end = pos
                sections.append(shared_locations[start:end].strip())
            if self._world and f'### {target_location}' in self._world:
                start = self._world.find(f'### {target_location}')
                end = len(self._world)
                for marker in ['\n### ', '\n---']:
                    pos = self._world.find(marker, start + 1)
                    if pos > 0 and pos < end:
                        end = pos
                char_assoc = self._world[start:end].strip()
                sections.append(f"【{target_location}·角色关联】\n{char_assoc.split(chr(10), 1)[-1]}")
        elif shared_locations:
            sections.append("【可用场景】" + "、".join(location_map.values()))

        # 系统上下文
        action_systems = {
            'farm': '农场种植', 'plant': '农场种植', 'cook': '料理烹饪',
            'gift': '送礼互动', 'checkin': '签到系统',
        }
        shared_systems = self._shared_world.get('systems', '')
        system_key = action_systems.get(recent_action, '')
        if not system_key and player_location == 'farm':
            system_key = '农场种植'
        if system_key and shared_systems:
            for line in shared_systems.split('\n'):
                if system_key in line and line.startswith('##'):
                    start = shared_systems.find(line)
                    end = shared_systems.find('\n## ', start + 1)
                    if end < 0: end = len(shared_systems)
                    sections.append(shared_systems[start:end].strip())
                    break

        # 天气
        if weather:
            shared_env = self._shared_world.get('environment', '')
            if shared_env and '## 天气系统' in shared_env:
                start = shared_env.find('## 天气系统')
                end = shared_env.find('\n## ', start + 1)
                if end < 0: end = len(shared_env)
                sections.append(shared_env[start:end].strip())
            if self._world and '环境反应' in self._world:
                env_start = self._world.find('## 🌤️ 环境反应')
                if env_start >= 0:
                    env_end = self._world.find('\n## ', env_start + 1)
                    if env_end < 0: env_end = len(self._world)
                    sections.append(self._world[env_start:env_end].strip())

        # 联动示例
        if (recent_action or player_location) and self._world and '角色专属联动' in self._world:
            table_start = self._world.find('## 🎭 角色专属联动')
            if table_start >= 0:
                sections.append(self._world[table_start:].strip())

        if sections:
            return f"\n\n【游戏世界上下文】\n" + "\n\n".join(sections)
        return ""

    def _get_memories_section(self) -> str:
        """共同记忆"""
        if self._memories:
            return f"\n\n【共同记忆】\n{self._memories}"
        return ""

    # ═══════════════════════════════════════════════════════════
    # 主构建方法 — 唯一权威入口
    # ═══════════════════════════════════════════════════════════

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """获取完整的 AI 系统提示词 — 唯一权威构建入口。

        所有调用方（ai_core / chat_engine / routes_chat / web_routes）
        都应该调用此方法，不再各自拼接额外段落。

        Args:
            context: 上下文信息
                - user_name: 用户称呼
                - world_layer: 世界层级 (stage/shadow/resonance)
                - awakening_level: 觉醒度 (0-100)
                - user_id: 用户ID（用于记忆检索）
                - player_location: 玩家当前位置
                - weather: 天气
                - recent_action: 最近行为
                - recent_memories: 最近记忆（异步预获取）
        """
        ctx = context or {}
        user_name = ctx.get('user_name', self.config.user_nickname)
        world_layer = ctx.get('world_layer', 'stage')
        awakening_level = ctx.get('awakening_level', 0)

        # ── 通用段落（基类提供）──
        time_ctx = self._get_time_context()

        # ── 角色特有段落（子类 override）──
        world_building = self.get_world_building(ctx)
        awakening = self.get_awakening_awareness(awakening_level)
        layer_behavior = self.get_layer_behavior(world_layer)
        identity = self.get_character_identity()
        personality = self.get_character_personality()
        speaking_style = self.get_speaking_style_rules()
        ooc_rules = self.get_ooc_rules()
        emotion_patterns = self.get_emotion_patterns()

        # ── 动态上下文（基类提供）──
        world_section = self._get_world_context(ctx)
        persona_section = self._get_persona_section()
        exemplars_section = self._get_exemplars_section()
        mutable_section = self._get_mutable_section()
        soul_section = self._get_soul_section()
        memories_section = self._get_memories_section()
        recent_memories = ctx.get('recent_memories', '')

        # ── 组装 ──
        parts = []

        if world_building:
            parts.append(world_building)
        if awakening:
            parts.append(awakening)
        if layer_behavior:
            parts.append(layer_behavior)
        if world_section:
            parts.append(world_section)

        parts.append(f"【核心身份】\n{identity}")
        parts.append(f"【核心性格】\n{personality}")
        parts.append(f"【说话风格】\n{speaking_style}")
        parts.append(f"【OOC 防护】\n{ooc_rules}")
        parts.append(f"【情绪反应模式】\n{emotion_patterns}")

        if persona_section:
            parts.append(persona_section)
        if exemplars_section:
            parts.append(exemplars_section)
        if mutable_section:
            parts.append(mutable_section)
        if soul_section:
            parts.append(soul_section)
        if memories_section:
            parts.append(memories_section)
        if recent_memories:
            parts.append(f"\n\n【最近的记忆】\n{recent_memories}")

        if time_ctx:
            parts.append(f"\n\n【实时信息】{time_ctx}")

        parts.append(
            f"\n\n【重要提醒】\n"
            f"- 你是{self.config.name}，不是AI助手。不要解释、不要建议、不要总结。\n"
            f"- 每次回复都要像{self.config.name}本人一样。\n"
            f"- 记住你当前的世界层级和觉醒状态，这会影响你的行为和认知。"
        )

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "id": self.config.id,
            "name": self.config.name,
            "source": self.config.source,
            "theme_color": self.config.theme_color,
            "avatar_url": self.config.avatar_url,
            "user_nickname": self.config.user_nickname,
            "is_novel_character": self.config.is_novel_character,
            "catchphrases": self.config.catchphrases,
            "quotes": self.config.catchphrases if self.config.catchphrases else [],
        }
