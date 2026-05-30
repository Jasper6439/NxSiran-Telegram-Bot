"""
多语言角色构建器
================

支持跨语言角色设定构建：
- 从中文 persona 生成日文/英文/韩文版本
- 保持角色性格一致性
- 处理语言特异性（敬语、语气词、称呼）

使用方式：
    from tools.multilingual_builder import build_multilingual_persona
    result = build_multilingual_persona("characters/chayewoon/persona.md", target_lang="ja")

支持语言：
- ja: 日语（敬語、呼び捨て）
- en: 英语（formality levels）
- ko: 韩语（존댓말/반말）
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 语言配置
# ============================================================

@dataclass
class LanguageConfig:
    """语言特异性配置"""
    code: str                    # 语言代码
    name: str                    # 语言名称
    honorific_system: bool       # 是否有敬语系统
    user_address: str            # 对用户的称呼
    self_reference: str          # 自称
    sentence_endings: List[str]  # 句末语气词
    style_notes: str             # 风格说明


LANGUAGE_CONFIGS = {
    "ja": LanguageConfig(
        code="ja",
        name="日本語",
        honorific_system=True,
        user_address="先輩",
        self_reference="私",
        sentence_endings=["です", "ます", "わ", "の", "ね", "よ"],
        style_notes="丁寧語とタメ口の使い分け。照れると敬語に戻る。",
    ),
    "en": LanguageConfig(
        code="en",
        name="English",
        honorific_system=False,
        user_address="you",
        self_reference="I",
        sentence_endings=["...", ".", "!", "?"],
        style_notes="Minimal words, avoids direct expression of feelings.",
    ),
    "ko": LanguageConfig(
        code="ko",
        name="한국어",
        honorific_system=True,
        user_address="선배",
        self_reference="나",
        sentence_endings=["요", "야", "지", "잖아", "인데"],
        style_notes="존댓말과 반말의 혼용。수줍으면 존댓말로 돌아간다。",
    ),
}


# ============================================================
# 角色设定翻译模板
# ============================================================

# 车如云特异性翻译映射
CHAYEWOON_TRANSLATIONS = {
    "ja": {
        "catchphrases": ["…先輩。", "（俯く）", "…どうでも。"],
        "personality": "外面は冷たいが内面は熱い。極度に警戒心が強い。",
        "speaking_style": "非常に簡潔な話し方。感情を直接表に出さない。",
        "background": "18歳。陸上短距離選手。祖母と二人暮らし。",
        "user_nickname": "先輩",
        "emotional_expressions": {
            "冷淡/回避": "……。",
            "困惑/依存": "先輩、なんで…",
            "抵抗": "…やだ。",
            "従順/受入": "…うん。",
        },
    },
    "en": {
        "catchphrases": ["...senior.", "(looks down)", "...whatever."],
        "personality": "Cold on the outside, warm on the inside. Extremely guarded.",
        "speaking_style": "Extremely terse. Never expresses emotions directly.",
        "background": "18 years old. Track sprinter. Lives with grandmother.",
        "user_nickname": "senior",
        "emotional_expressions": {
            "冷淡/回避": "...",
            "困惑/依存": "Senior, why...",
            "抵抗": "...don't want to.",
            "従順/受入": "...yeah.",
        },
    },
    "ko": {
        "catchphrases": ["...선배.", "(고개를 숙임)", "...상관없어."],
        "personality": "겉은 차갑지만 속은 따뜻하다. 극도로 경계심이 강하다.",
        "speaking_style": "매우 간결한 말투. 감정을 직접 드러내지 않는다.",
        "background": "18세. 육상 단거리 선수. 할머니와 둘이 산다.",
        "user_nickname": "선배",
        "emotional_expressions": {
            "冷淡/回避": "…….",
            "困惑/依存": "선배, 왜...",
            "抵抗": "…싫어.",
            "従順/受入": "…응.",
        },
    },
}


# ============================================================
# 多语言构建器
# ============================================================

class MultilingualBuilder:
    """多语言角色设定构建器"""

    def __init__(self, character_id: str = "chayewoon"):
        self.character_id = character_id
        self._translations = CHAYEWOON_TRANSLATIONS  # 可扩展其他角色

    def build_persona(
        self,
        source_path: str,
        target_lang: str,
        output_path: Optional[str] = None,
    ) -> str:
        """从中文 persona 生成目标语言版本。

        Args:
            source_path: 中文 persona.md 路径
            target_lang: 目标语言代码 (ja/en/ko)
            output_path: 输出路径（None 则不写文件）

        Returns:
            翻译后的 persona 文本
        """
        if target_lang not in LANGUAGE_CONFIGS:
            raise ValueError(f"Unsupported language: {target_lang}")

        config = LANGUAGE_CONFIGS[target_lang]
        translations = self._translations.get(target_lang, {})

        # 读取源文件
        source_text = Path(source_path).read_text(encoding="utf-8")

        # 构建翻译后的内容
        sections = []
        sections.append(f"# {translations.get('name', self.character_id)} 角色設定")
        sections.append(f"# ({config.name} version)")
        sections.append("")

        # Layer 0: 基本信息
        sections.append("## Layer 0: 基本情報" if target_lang == "ja" else "## Layer 0: Basic Info")
        sections.append(f"- 性格: {translations.get('personality', 'N/A')}")
        sections.append(f"- 話し方: {translations.get('speaking_style', 'N/A')}" if target_lang == "ja"
                        else f"- Speaking style: {translations.get('speaking_style', 'N/A')}")
        sections.append(f"- 背景: {translations.get('background', 'N/A')}")
        sections.append("")

        # 口頭禅
        sections.append("## 口癖" if target_lang == "ja" else "## Catchphrases")
        for cp in translations.get("catchphrases", []):
            sections.append(f"- {cp}")
        sections.append("")

        # 情感表达
        sections.append("## 感情表現" if target_lang == "ja" else "## Emotional Expressions")
        for emotion, expr in translations.get("emotional_expressions", {}).items():
            sections.append(f"- {emotion}: {expr}")
        sections.append("")

        # 言語特有の注意事項
        sections.append("## 言語特有の注意" if target_lang == "ja" else "## Language Notes")
        sections.append(config.style_notes)

        result = "\n".join(sections)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(result, encoding="utf-8")
            logger.info(f"[Multilingual] Generated {config.name} persona → {output_path}")

        return result

    def build_config_override(
        self,
        target_lang: str,
    ) -> Dict[str, Any]:
        """为目标语言生成 config.json 覆盖字段。

        Args:
            target_lang: 目标语言代码

        Returns:
            覆盖字段字典
        """
        config = LANGUAGE_CONFIGS.get(target_lang)
        translations = self._translations.get(target_lang, {})

        if not config or not translations:
            return {}

        return {
            "catchphrases": translations.get("catchphrases", []),
            "user_nickname": translations.get("user_nickname", ""),
            "speaking_style": translations.get("speaking_style", ""),
            "language": target_lang,
            "honorific_system": config.honorific_system,
            "self_reference": config.self_reference,
        }


# ============================================================
# 便捷函数
# ============================================================

def build_multilingual_persona(
    source_path: str,
    target_lang: str,
    character_id: str = "chayewoon",
    output_path: Optional[str] = None,
) -> str:
    """一键构建多语言角色设定。

    Args:
        source_path: 中文 persona.md 路径
        target_lang: 目标语言 (ja/en/ko)
        character_id: 角色 ID
        output_path: 输出路径

    Returns:
        翻译后的 persona 文本
    """
    builder = MultilingualBuilder(character_id)
    return builder.build_persona(source_path, target_lang, output_path)


def get_supported_languages() -> List[Dict[str, str]]:
    """获取支持的语言列表"""
    return [
        {"code": lang.code, "name": lang.name, "honorific": lang.honorific_system}
        for lang in LANGUAGE_CONFIGS.values()
    ]
