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
        import httpx

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
    "summary": "用2-3句话总结这个用户的灵魂特质"
}}

只返回JSON，不要其他内容。"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
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

## 灵魂摘要

{soul_data.get('summary', '待分析')}

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
