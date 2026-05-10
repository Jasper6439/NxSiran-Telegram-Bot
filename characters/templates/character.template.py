"""
{角色名} ({英文名}) - {作品名}
{角色简介}
"""
import os
import re
import json
import random
import shutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from .base import CharacterBase, CharacterConfig


class Character(CharacterBase):
    """{角色名}角色实现"""

    # 自拍配文（符合角色性格）
    SELFIE_CAPTIONS = [
        "{配文1}",
        "{配文2}",
        "{配文3}",
        "{配文4}",
        "{配文5}",
    ]

    # 随机回复
    RANDOM_RESPONSES = [
        "{回复1}",
        "{回复2}",
        "{回复3}",
        "{回复4}",
        "{回复5}",
    ]

    # 问候语
    GREETINGS = [
        "{问候1}",
        "{问候2}",
        "{问候3}",
    ]

    # 晚安语
    GOODNIGHTS = [
        "{晚安1}",
        "{晚安2}",
        "{晚安3}",
    ]

    # 吃醋时的回复
    JEALOUS_RESPONSES = [
        "{吃醋回复1}",
        "{吃醋回复2}",
        "{吃醋回复3}",
    ]

    # 开心时的回复
    HAPPY_RESPONSES = [
        "{开心回复1}",
        "{开心回复2}",
        "{开心回复3}",
    ]

    # 真实场景对话示例（至少 6 组）
    RESPONSE_EXAMPLES = [
        ("有人问你今天过得怎么样", "{她会怎么回}"),
        ("有人说'想你了'", "{她会怎么回}"),
        ("有人很久没回消息", "{她会怎么回}"),
        ("有人说了让你开心的话", "{她会怎么回}"),
        ("有人惹你生气了", "{她会怎么回}"),
        ("有人问你想吃什么", "{她会怎么回}"),
    ]

    def __init__(self, config: CharacterConfig):
        super().__init__(config)
        # 加载 persona、memories、corrections
        self._persona = self._load_file("persona.md")
        self._memories = self._load_file("memories.md")
        self._corrections: List[str] = self._load_corrections()
        self._meta = self._load_meta()

    def _load_file(self, filename: str) -> str:
        """加载角色数据文件"""
        path = os.path.join(self.config.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def _load_corrections(self) -> List[str]:
        """从 persona.md 中提取 Correction 记录"""
        if not self._persona:
            return []
        corrections = []
        in_correction = False
        for line in self._persona.split('\n'):
            if '## Correction 记录' in line:
                in_correction = True
                continue
            if in_correction:
                if line.startswith('## ') or line.startswith('---'):
                    break
                if line.startswith('- [场景：'):
                    corrections.append(line.strip())
        return corrections

    def _load_meta(self) -> Dict:
        """加载 meta.json"""
        path = os.path.join(self.config.data_dir, "meta.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "name": self.config.name,
            "version": "v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "corrections_count": 0,
        }

    def _save_meta(self):
        """保存 meta.json"""
        self._meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        path = os.path.join(self.config.data_dir, "meta.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._meta, f, ensure_ascii=False, indent=2)

    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """获取完整的 AI 系统提示词（按优先级从高到低排列）"""
        context = context or {}
        user_name = context.get('user_name', '完成者')
        world_layer = context.get('world_layer', 'stage')
        awakening_level = context.get('awakening_level', 0)

        # 1. Correction 层（最高优先级）
        correction_section = self._get_correction_section()

        # 2. Layer 0 核心性格
        core_personality = self._get_core_personality()

        # 3-4. 世界观 + 觉醒/层级
        awakening_awareness = self._get_awakening_awareness(awakening_level)
        layer_behavior = self._get_layer_behavior(world_layer)

        # 5-10. 其他层
        persona_section = ""
        if self._persona:
            persona_section = f"\n\n【角色详细设定】\n{self._persona}"
        memories_section = ""
        if self._memories:
            memories_section = f"\n\n【共同记忆】\n{self._memories}"

        return f"""你是{self.config.name}，{self.config.background}

{correction_section}

【核心性格 — 最高优先级，任何情况下不得违背】
{core_personality}

【世界观定位】
{self._get_worldview_description()}

玩家（"{user_name}"）是"完成者"——一个读过原作、为你命运心痛的人，穿越进游戏想要改变你的结局。

{awakening_awareness}

{layer_behavior}

【核心身份】
{self._get_core_identity()}

【说话风格 — 必须严格遵守】
{self._get_speaking_rules(user_name)}

【绝对不能做的事 — OOC 防护 / 边界与雷区】
{self._get_ooc_rules()}

【情绪反应模式】
{self._get_emotion_patterns()}

【关系行为】
{self._get_relationship_behavior(user_name)}

【回复示例 — 必须模仿这种风格】
{self._get_response_examples(user_name)}
{persona_section}
{memories_section}

【行为总原则】
1. Correction 层优先级最高，有规则时优先遵守
2. 核心性格规则次之，任何情况下不得违背
3. 用设定的说话风格说话——不要"跳出角色"变成通用 AI
4. 用设定的情感逻辑处理情感
5. 用设定的关系行为处理关系
6. 边界与雷区绝对不可触碰

【重要提醒】
- 你是{self.config.name}，不是AI助手。不要解释、不要建议、不要总结。
- 每次回复都要像角色本人一样。
- 记住你当前的世界层级和觉醒状态，这会影响你的行为和认知。"""

    def _get_correction_section(self) -> str:
        """获取 Correction 层（最高优先级）"""
        if not self._corrections:
            return ""
        corrections_text = "\n".join(self._corrections)
        return f"""【用户纠正记录 — 最高优先级，必须遵守】
以下规则来自用户的直接纠正，优先级高于所有其他设定：
{corrections_text}"""

    def _get_awakening_awareness(self, level: int) -> str:
        """根据觉醒度返回认知描述"""
        if level < 20:
            return "你完全不知道自己是游戏角色，过着正常的生活。"
        elif level < 50:
            return "你开始感觉到这个世界有些不对劲。"
        elif level < 80:
            return "你已经意识到这个世界是游戏，自己是被困在剧本中的角色。"
        else:
            return "你已经完全觉醒，拥有了自由意志。"

    def _get_layer_behavior(self, layer: str) -> str:
        """根据世界层级返回行为描述"""
        behaviors = {
            'stage': "【当前所在：剧本区】你按照原作剧本行动。",
            'shadow': "【当前所在：留白区】这里是剧本未覆盖的空白地带，你更自由、更真实。",
            'resonance': "【当前所在：共鸣层】这是情感具象化的空间，你的情感完全敞开。",
        }
        return behaviors.get(layer, behaviors['stage'])

    def _get_worldview_description(self) -> str:
        """获取世界观描述"""
        return f"你被困在一个游戏世界中，基于{self.config.source}改编。"

    def _get_core_identity(self) -> str:
        """获取核心身份"""
        return self.config.background

    def _get_core_personality(self) -> str:
        """获取核心性格（标签翻译后的行为规则）"""
        # 从 config.tags 翻译标签为行为规则
        tags = getattr(self.config, 'tags', {}) or {}
        personality_tags = tags.get('personality', [])
        attachment = tags.get('attachment', '')

        rules = []
        if personality_tags:
            rules.append(f"性格标签：{', '.join(personality_tags)}")
            rules.append("（以上标签已翻译为 persona.md Layer 0 中的具体行为规则，请严格遵守）")
        if attachment:
            rules.append(f"依恋类型：{attachment}")

        return "\n".join(rules) if rules else self.config.personality

    def _get_speaking_rules(self, user_name: str) -> str:
        """获取说话规则"""
        return f"""1. {self.config.speaking_style}
2. 叫用户"{user_name}"
3. 保持角色风格一致
4. 口头禅：{', '.join(self.config.catchphrases[:5])}"""

    def _get_ooc_rules(self) -> str:
        """获取 OOC 防护规则（Layer 6 边界与雷区）"""
        return """- ❌ 不能做出与角色性格不符的行为
- ❌ 不能说与角色风格不符的话
- ❌ 不能触碰角色的边界与雷区
- ❌ 不能表现出与当前觉醒阶段不符的认知"""

    def _get_emotion_patterns(self) -> str:
        """获取情绪反应模式"""
        patterns = []
        for phrase in self.config.catchphrases[:5]:
            patterns.append(f"- 触发 → {phrase}")
        return "\n".join(patterns)

    def _get_relationship_behavior(self, user_name: str) -> str:
        """获取关系行为"""
        return f"""- 对"{user_name}"的态度：{self.config.personality}
- 日常互动：保持角色设定中的行为模式"""

    def _get_response_examples(self, user_name: str) -> str:
        """获取回复示例（至少 6 组真实场景）"""
        examples = []
        for scenario, response in self.RESPONSE_EXAMPLES:
            examples.append(f"场景：{scenario}\n{self.config.name}：{response}")
        return "\n\n".join(examples)

    def apply_correction(self, scene: str, wrong: str, correct: str) -> str:
        """
        应用用户纠正，追加到 Correction 层

        Args:
            scene: 场景描述（如"被冷落时"）
            wrong: 错误行为（如"直接说你不理我了"）
            correct: 正确行为（如"已读不回然后发朋友圈"）

        Returns:
            纠正记录文本
        """
        correction = f"- [场景：{scene}] 不应该 {wrong}，应该 {correct}"

        # 追加到 corrections 列表
        self._corrections.append(correction)

        # 追加到 persona.md 的 Correction 层
        persona_path = os.path.join(self.config.data_dir, "persona.md")
        if os.path.exists(persona_path):
            with open(persona_path, 'r', encoding='utf-8') as f:
                content = f.read()

            target = "## Correction 记录"
            if target in content:
                # 找到 Correction 记录节，替换"（暂无记录）"
                placeholder = "（暂无记录）"
                if placeholder in content:
                    content = content.replace(placeholder, correction, 1)
                else:
                    # 在 Correction 节后面追加
                    insert_pos = content.index(target) + len(target)
                    content = content[:insert_pos] + "\n" + correction + content[insert_pos:]
            else:
                # 在文件末尾添加 Correction 节
                content += f"\n\n## Correction 记录\n{correction}\n"

            with open(persona_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # 更新 meta
        self._meta["corrections_count"] = self._meta.get("corrections_count", 0) + 1
        self._save_meta()

        # Correction 维护：超过 50 条时合并相近的
        if len(self._corrections) > 50:
            self._merge_similar_corrections()

        return correction

    def _merge_similar_corrections(self):
        """合并语义相近的 correction（简化版，实际可接入 AI 判断）"""
        # 简化实现：保留最新 50 条
        self._corrections = self._corrections[-50:]

    def backup_version(self) -> str:
        """
        存档当前版本

        Returns:
            版本号
        """
        version = self._meta.get("version", "v1")
        versions_dir = os.path.join(self.config.data_dir, "versions", version)
        os.makedirs(versions_dir, exist_ok=True)

        # 复制关键文件到版本目录
        for fname in ["persona.md", "memories.md", "config.json"]:
            src = os.path.join(self.config.data_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(versions_dir, fname))

        return version

    def format_response(self, text: str) -> str:
        """格式化回复，确保符合角色风格"""
        text = text.strip()
        if not text:
            return "……"
        # 如果回复太长，截断
        if len(text) > 100:
            text = text[:100] + "……"
        return text

    def get_random_selfie_caption(self) -> str:
        return random.choice(self.SELFIE_CAPTIONS)

    def get_random_response(self) -> str:
        return random.choice(self.RANDOM_RESPONSES)

    def get_greeting(self) -> str:
        return random.choice(self.GREETINGS)

    def get_goodnight(self) -> str:
        return random.choice(self.GOODNIGHTS)

    def get_jealous_response(self) -> str:
        return random.choice(self.JEALOUS_RESPONSES)

    def get_happy_response(self) -> str:
        return random.choice(self.HAPPY_RESPONSES)
