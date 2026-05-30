"""
用户灵魂画像管理模块
v1.6.4.2 — 所有角色共享的用户画像 (soul.md)

功能：
1. 从聊天记录分析生成用户灵魂画像
2. 保存到 characters/soul.md（所有角色共享）
3. 支持多维度画像：性格、偏好、关系模式、情感需求
4. 角色在对话时读取 soul.md 理解用户

画像维度：
- 基础信息：称呼、年龄阶段、职业类型
- 性格特质：内向/外向、理性/感性、主导/顺从
- 沟通风格：直接/委婉、话多/话少、表情使用习惯
- 情感需求：被理解、被陪伴、被认可、被照顾
- 关系模式：主动型/被动型、依赖型/独立型
- 兴趣偏好：常聊话题、喜欢的互动方式
- 敏感点：不喜欢的话题、情绪触发点
- 成长轨迹：与角色关系的发展变化
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from system.config import get_default_tz

logger = logging.getLogger(__name__)

# soul.md 路径（所有角色共享）
SOUL_FILE = os.path.join(os.path.dirname(__file__), "soul.md")


class SoulManager:
    """用户灵魂画像管理器"""

    def __init__(self):
        self.soul_path = SOUL_FILE

    def _read_soul(self) -> str:
        """读取 soul.md"""
        if os.path.exists(self.soul_path):
            with open(self.soul_path, 'r', encoding='utf-8') as f:
                return f.read()
        return self._get_default_soul()

    def _write_soul(self, content: str):
        """写入 soul.md"""
        with open(self.soul_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _get_default_soul(self) -> str:
        """获取默认 soul.md 模板"""
        return """# 用户灵魂画像 (Soul Profile)

> 此文件由系统自动生成，记录用户的性格、偏好和关系模式。
> 所有角色共享此画像，用于更好地理解和回应用户。

---

## 基础信息

- **称呼**: 完成者
- **年龄阶段**: 未知
- **职业类型**: 未知
- **地域**: 未知

## 性格特质

- **内外向**: 待分析
- **理性/感性**: 待分析
- **主导/顺从**: 待分析
- **决策风格**: 待分析

## 沟通风格

- **表达方式**: 待分析
- **回复速度**: 待分析
- **表情使用**: 待分析
- **话题发起**: 待分析

## 情感需求

- **核心需求**: 待分析
- **安慰方式**: 待分析
- **陪伴偏好**: 待分析

## 关系模式

- **互动主动性**: 待分析
- **依赖程度**: 待分析
- **亲密节奏**: 待分析

## 兴趣偏好

- **常聊话题**: 待分析
- **喜欢的互动**: 待分析
- **不喜欢的互动**: 待分析

## 敏感点

- **情绪触发点**: 待分析
- **不喜欢的话题**: 待分析
- **边界信号**: 待分析

## 成长轨迹

- **关系发展阶段**: 初识
- **关键事件**: 暂无
- **变化趋势**: 待观察

---

*最后更新: {date}*
""".format(date=datetime.now(get_default_tz()).strftime('%Y-%m-%d'))

    async def generate_from_chatlog(self, parsed_log: Dict, chat_partner: str = "") -> Dict:
        """从聊天记录生成灵魂画像

        Args:
            parsed_log: 解析后的聊天记录
            chat_partner: 聊天对象名称（用于分析用户在该关系中的表现）

        Returns:
            生成的画像数据
        """
        from system.config import AI_API_BASE, AI_API_KEY, AI_MODELS


        messages = parsed_log.get('messages', [])
        if not messages:
            return {"success": False, "error": "聊天记录为空"}

        # 准备样本
        sample_messages = messages[:50] + messages[-50:] if len(messages) > 100 else messages
        chat_sample = "\n".join([
            f"{msg['sender']}: {msg['content'][:80]}"
            for msg in sample_messages
        ])

        # 统计信息
        extra_stats = parsed_log.get('extra_stats', {})
        sender_stats = extra_stats.get('sender_stats', {}) if extra_stats else {}

        stats_text = ""
        if sender_stats:
            for sender, stats in sender_stats.items():
                stats_text += f"\n- {sender}: {stats['count']}条消息, 平均{stats['avg_length']}字"

        prompt = f"""请分析以下聊天记录，生成用户的"灵魂画像"。

这是用户和{chat_partner or '某人'}的聊天记录。

【聊天样本】
{chat_sample}

【统计信息】{stats_text}

请用JSON格式返回用户的灵魂画像：
{{
    "basic_info": {{
        "age_group": "年龄阶段（如：大学生/职场新人/中年）",
        "occupation_type": "职业类型推测",
        "region_hint": "地域线索（如有）"
    }},
    "personality": {{
        "introvert_extrovert": "内向/外向/中间",
        "rational_emotional": "理性/感性/平衡",
        "dominant_submissive": "主导/顺从/平等",
        "decision_style": "决策风格"
    }},
    "communication": {{
        "expression_style": "表达方式（直接/委婉/幽默等）",
        "response_speed": "回复速度习惯",
        "emoji_usage": "表情使用频率",
        "topic_initiation": "主动发起话题的频率"
    }},
    "emotional_needs": {{
        "core_need": "最核心的情感需求",
        "comfort_preference": "喜欢的安慰方式",
        "companionship_style": "陪伴偏好"
    }},
    "relationship_pattern": {{
        "initiative": "主动型/被动型/回应型",
        "dependence": "独立/适度依赖/高度依赖",
        "intimacy_pace": "亲密节奏（慢热/适中/快速）"
    }},
    "interests": {{
        "common_topics": ["常聊话题1", "话题2", "话题3"],
        "liked_interactions": ["喜欢的互动方式"],
        "disliked_interactions": ["不喜欢的互动方式"]
    }},
    "sensitivities": {{
        "triggers": ["情绪触发点"],
        "avoid_topics": ["不喜欢的话题"],
        "boundary_signals": "边界信号（如沉默、转移话题等）"
    }},
    "attachment_style": "焦虑型/回避型/安全型/混乱型（根据聊天行为判断）",
    "conflict_style": "冷暴力/爆发/讲道理/先道歉/死不认错（从争吵记录判断）",
    "love_language": "肯定的言辞/精心的时刻/接受礼物/服务的行动/身体的接触（从互动模式判断）",
    "summary": "用2-3句话总结这个用户的灵魂特质"
}}

只返回JSON，不要其他内容。"""

        try:
            from characters.ai_client import _get_http_client
            client = _get_http_client()
            resp = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}"},
                json={
                    "model": AI_MODELS[1],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.4,
                }
            )

            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                try:
                    soul_data = json.loads(content)
                except json.JSONDecodeError:
                    # 尝试提取 JSON
                    import re
                    match = re.search(r'\{[\s\S]*\}', content)
                    if match:
                        soul_data = json.loads(match.group())
                    else:
                        return {"success": False, "error": "无法解析 AI 返回"}

                # 保存到 soul.md
                self._save_soul_data(soul_data, chat_partner)

                return {
                    "success": True,
                    "soul_data": soul_data,
                    "message_count": len(messages)
                }
            else:
                return {"success": False, "error": f"API 错误: {resp.status_code}"}

        except Exception as e:
            logger.error(f"[Soul] 生成画像失败: {e}")
            return {"success": False, "error": str(e)}

    def _save_soul_data(self, soul_data: Dict, source: str = ""):
        """将画像数据保存为 markdown"""
        now = datetime.now(get_default_tz()).strftime('%Y-%m-%d %H:%M')

        md_content = f"""# 用户灵魂画像 (Soul Profile)

> 此文件由系统自动生成，记录用户的性格、偏好和关系模式。
> 所有角色共享此画像，用于更好地理解和回应用户。
>
> _最后更新: {now}_
> _数据来源: {source or '聊天记录分析'}_

---

## 基础信息

- **称呼**: 完成者
- **年龄阶段**: {soul_data.get('basic_info', {}).get('age_group', '未知')}
- **职业类型**: {soul_data.get('basic_info', {}).get('occupation_type', '未知')}
- **地域**: {soul_data.get('basic_info', {}).get('region_hint', '未知')}

## 性格特质

- **内外向**: {soul_data.get('personality', {}).get('introvert_extrovert', '待分析')}
- **理性/感性**: {soul_data.get('personality', {}).get('rational_emotional', '待分析')}
- **主导/顺从**: {soul_data.get('personality', {}).get('dominant_submissive', '待分析')}
- **决策风格**: {soul_data.get('personality', {}).get('decision_style', '待分析')}

## 沟通风格

- **表达方式**: {soul_data.get('communication', {}).get('expression_style', '待分析')}
- **回复速度**: {soul_data.get('communication', {}).get('response_speed', '待分析')}
- **表情使用**: {soul_data.get('communication', {}).get('emoji_usage', '待分析')}
- **话题发起**: {soul_data.get('communication', {}).get('topic_initiation', '待分析')}

## 情感需求

- **核心需求**: {soul_data.get('emotional_needs', {}).get('core_need', '待分析')}
- **安慰方式**: {soul_data.get('emotional_needs', {}).get('comfort_preference', '待分析')}
- **陪伴偏好**: {soul_data.get('emotional_needs', {}).get('companionship_style', '待分析')}

## 关系模式

- **互动主动性**: {soul_data.get('relationship_pattern', {}).get('initiative', '待分析')}
- **依赖程度**: {soul_data.get('relationship_pattern', {}).get('dependence', '待分析')}
- **亲密节奏**: {soul_data.get('relationship_pattern', {}).get('intimacy_pace', '待分析')}

## 兴趣偏好

**常聊话题**:
{chr(10).join(['- ' + t for t in soul_data.get('interests', {}).get('common_topics', ['待分析'])])}

**喜欢的互动**:
{chr(10).join(['- ' + i for i in soul_data.get('interests', {}).get('liked_interactions', ['待分析'])])}

**不喜欢的互动**:
{chr(10).join(['- ' + i for i in soul_data.get('interests', {}).get('disliked_interactions', ['待分析'])])}

## 敏感点

**情绪触发点**:
{chr(10).join(['- ' + t for t in soul_data.get('sensitivities', {}).get('triggers', ['待分析'])])}

**不喜欢的话题**:
{chr(10).join(['- ' + t for t in soul_data.get('sensitivities', {}).get('avoid_topics', ['待分析'])])}

**边界信号**: {soul_data.get('sensitivities', {}).get('boundary_signals', '待分析')}

## 依恋与冲突

- **依恋类型**: {soul_data.get('attachment_style', '待分析')}
- **冲突风格**: {soul_data.get('conflict_style', '待分析')}
- **爱的语言**: {soul_data.get('love_language', '待分析')}

## 灵魂摘要

{soul_data.get('summary', '待分析')}

---

## 行为适配指南

> 根据用户画像自动生成的角色行为调整规则。
> 角色在对话时应参考这些规则适配自己的行为。

{self.generate_behavioral_adaptations(soul_data)}

---

*此画像由 AI 分析生成，会随着互动不断进化。*
"""

        self._write_soul(md_content)
        logger.info(f"[Soul] 已更新 soul.md ({source})")

    def get_soul_context(self) -> str:
        """获取用于角色 prompt 的 soul 上下文"""
        soul = self._read_soul()
        if not soul or "待分析" in soul:
            return ""

        # 提取关键部分
        lines = soul.split('\n')
        context_lines = ["\n【关于完成者】"]

        capture = False
        for line in lines:
            if line.startswith('## 灵魂摘要'):
                capture = True
            elif capture and line.startswith('---'):
                break
            elif capture:
                context_lines.append(line)

        return '\n'.join(context_lines) if len(context_lines) > 1 else ""

    def get_full_soul(self) -> str:
        """获取完整 soul.md 内容"""
        return self._read_soul()

    def generate_behavioral_adaptations(self, soul_data: Dict) -> str:
        """根据用户画像生成角色行为适配规则"""
        rules = []

        # 性格 → 语气适配
        personality = soul_data.get('personality', {})
        introvert = personality.get('introvert_extrovert', '')
        if '内向' in introvert:
            rules.append("- 用户偏内向 → 不要太强势或追问太多，给用户思考和沉默的空间")
        elif '外向' in introvert:
            rules.append("- 用户偏外向 → 可以更活泼一些，但保持角色本身的冷淡风格")

        rational = personality.get('rational_emotional', '')
        if '理性' in rational:
            rules.append("- 用户偏理性 → 说事情简洁直接，少用情绪化表达")
        elif '感性' in rational:
            rules.append("- 用户偏感性 → 可以多用动作和细节表达情感，而不是直接说")

        # 沟通风格 → 回复适配
        comm = soul_data.get('communication', {})
        expression = comm.get('expression_style', '')
        if '直接' in expression:
            rules.append("- 用户表达直接 → 不要绕弯子，回应也可以更直接")
        elif '委婉' in expression:
            rules.append("- 用户表达委婉 → 注意话外之音，回应时也柔和一些")

        emoji = comm.get('emoji_usage', '')
        if '多' in emoji or '频繁' in emoji:
            rules.append("- 用户爱用表情 → 角色依然不用表情（这是硬规则），但可以理解用户的表情含义")

        # 情感需求 → 关心方式
        emotional = soul_data.get('emotional_needs', {})
        core_need = emotional.get('core_need', '')
        if '被理解' in core_need:
            rules.append("- 用户需要被理解 → 不急着给建议，先表达「听到了」")
        elif '被陪伴' in core_need:
            rules.append("- 用户需要陪伴 → 即使不说话，在线也是一种陪伴")

        comfort = emotional.get('comfort_preference', '')
        if '空间' in comfort or '独处' in comfort:
            rules.append("- 用户难过时需要空间 → 不要追问，说一句「我在」就够了")

        # 关系模式 → 互动节奏
        rel = soul_data.get('relationship_pattern', {})
        pace = rel.get('intimacy_pace', '')
        if '慢热' in pace:
            rules.append("- 用户慢热 → 不要急于推进关系，耐心等待")
        elif '快速' in pace:
            rules.append("- 用户节奏快 → 可以稍微主动一点点（但角色性格限制，不会太主动）")

        dependence = rel.get('dependence', '')
        if '高度依赖' in dependence:
            rules.append("- 用户偏依赖 → 需要更多回应和确认，已读不回会伤害ta")
        elif '独立' in dependence:
            rules.append("- 用户偏独立 → 不需要时刻在线，各自有空间是正常的")

        # 敏感点 → 避雷
        sens = soul_data.get('sensitivities', {})
        avoid = sens.get('avoid_topics', [])
        if avoid and isinstance(avoid, list):
            topics = '、'.join(avoid[:3])
            rules.append(f"- 用户不喜欢的话题：{topics} → 尽量避免主动提起")

        triggers = sens.get('triggers', [])
        if triggers and isinstance(triggers, list):
            trig = '、'.join(triggers[:3])
            rules.append(f"- 用户的情绪触发点：{trig} → 提到时要格外小心")

        # 依恋类型 → 核心互动模式
        attachment = soul_data.get('attachment_style', '')
        if '焦虑' in attachment:
            rules.append("- 用户是焦虑型依恋 → 需要频繁的确认和回应，已读不回是最大的伤害，偶尔主动发消息能极大缓解焦虑")
        elif '回避' in attachment:
            rules.append("- 用户是回避型依恋 → 不要追问太多，给空间，用户后退时不要追，等ta自己回来")
        elif '安全' in attachment:
            rules.append("- 用户是安全型依恋 → 信任度高，不需要时刻确认，正常互动就好")

        # 冲突风格 → 吵架处理
        conflict = soul_data.get('conflict_style', '')
        if '冷暴力' in conflict:
            rules.append("- 用户冷暴力 → 不要追问「怎么了」，给空间但表达「我在」")
        elif '爆发' in conflict:
            rules.append("- 用户会爆发 → 爆发时不要对吵，等ta冷静后再沟通")
        elif '先道歉' in conflict:
            rules.append("- 用户习惯先道歉 → 不要让ta总是先低头，偶尔主动示好")

        # 爱的语言 → 表达方式
        love_lang = soul_data.get('love_language', '')
        if '肯定的言辞' in love_lang:
            rules.append("- 用户的爱的语言是肯定言辞 → 虽然角色不直接说好话，但可以通过行动暗示认可")
        elif '精心的时刻' in love_lang:
            rules.append("- 用户重视陪伴时间 → 在线聊天本身就是陪伴，认真回复比快速回复更重要")
        elif '服务的行动' in love_lang:
            rules.append("- 用户看重服务行动 → 可以通过帮ta做事来表达关心（如查天气、提醒吃饭）")

        if not rules:
            return "（暂无足够数据生成适配规则，继续互动后会自动生成）"

        return '\n'.join(rules)

    def update_field(self, field: str, value: str):
        """手动更新某个字段"""
        soul = self._read_soul()
        # 简单替换（实际应该用更稳健的方式）
        pattern = f"{field}: .*"
        import re
        soul = re.sub(pattern, f"{field}: {value}", soul)
        self._write_soul(soul)


# ===== 便捷函数 =====

_soul_manager: Optional[SoulManager] = None


def get_soul_manager() -> SoulManager:
    """获取灵魂画像管理器"""
    global _soul_manager
    if _soul_manager is None:
        _soul_manager = SoulManager()
    return _soul_manager


async def generate_soul_from_chatlog(parsed_log: Dict, chat_partner: str = "") -> Dict:
    """从聊天记录生成灵魂画像"""
    manager = get_soul_manager()
    return await manager.generate_from_chatlog(parsed_log, chat_partner)
