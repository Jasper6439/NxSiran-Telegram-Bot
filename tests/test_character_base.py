"""
Tests for CharacterBase (characters/base.py)

Covers:
- File loading (persona.md, exemplars.md, world.md, etc.)
- Hook method defaults
- get_system_prompt() assembly
- IMMUTABLE_FILES protection
- Shared world loading
- Soul profile loading
"""

import os
import pathlib
import pytest

from characters.base import CharacterBase, CharacterConfig
from tests.conftest import ConcreteCharacter


# ══════════════════════════════════════════════════════════════
# File Loading
# ══════════════════════════════════════════════════════════════

class TestFileLoading:
    """Verify that __init__ loads all character data files."""

    def test_persona_loaded(self, character):
        assert "不可变的角色设定" in character._persona

    def test_exemplars_loaded(self, character):
        assert "随便" in character._exemplars

    def test_world_loaded(self, character):
        assert "游戏世界" in character._world

    def test_mutable_loaded(self, character):
        assert "可变状态" in character._mutable or "Correction" in character._mutable

    def test_memories_loaded(self, character):
        # memories.md was empty in fixture
        assert character._memories == ""

    def test_missing_files_return_empty_string(self, empty_character):
        assert empty_character._persona == ""
        assert empty_character._exemplars == ""
        assert empty_character._world == ""
        assert empty_character._mutable == ""
        assert empty_character._memories == ""


# ══════════════════════════════════════════════════════════════
# Hook Method Defaults
# ══════════════════════════════════════════════════════════════

class TestHookDefaults:
    """Verify base-class hook defaults when not overridden."""

    def test_get_character_identity_contains_name(self, character):
        identity = character.get_character_identity()
        assert "车如云" in identity

    def test_get_character_personality_default(self, empty_character):
        # Empty config has no personality set → falls back to placeholder
        result = empty_character.get_character_personality()
        assert result  # non-empty fallback

    def test_get_speaking_style_rules_default(self, character):
        result = character.get_speaking_style_rules()
        assert result  # non-empty from config

    def test_get_ooc_rules_default(self, empty_character):
        result = empty_character.get_ooc_rules()
        assert "角色" in result  # default OOC rule

    def test_get_emotion_patterns_default(self, empty_character):
        result = empty_character.get_emotion_patterns()
        assert result  # non-empty fallback

    def test_get_world_building_default(self, empty_character):
        result = empty_character.get_world_building()
        assert result == ""  # default is empty

    def test_get_awakening_awareness_default(self, empty_character):
        result = empty_character.get_awakening_awareness()
        assert result == ""  # default is empty

    def test_get_layer_behavior_default(self, empty_character):
        result = empty_character.get_layer_behavior()
        assert result == ""  # default is empty

    def test_format_response_abstract(self):
        """ConcreteCharacter.format_response strips whitespace."""
        cfg = CharacterConfig(id="t", name="T", source="S")
        c = ConcreteCharacter(cfg)
        assert c.format_response("  hello  ") == "hello"
        assert c.format_response("") == "……"


# ══════════════════════════════════════════════════════════════
# get_system_prompt() Assembly
# ══════════════════════════════════════════════════════════════

class TestSystemPromptAssembly:
    """Verify get_system_prompt() assembles all sections."""

    def test_contains_core_identity(self, character):
        prompt = character.get_system_prompt()
        assert "【核心身份】" in prompt

    def test_contains_core_personality(self, character):
        prompt = character.get_system_prompt()
        assert "【核心性格】" in prompt

    def test_contains_speaking_style(self, character):
        prompt = character.get_system_prompt()
        assert "【说话风格】" in prompt

    def test_contains_ooc_protection(self, character):
        prompt = character.get_system_prompt()
        assert "【OOC 防护】" in prompt

    def test_contains_emotion_patterns(self, character):
        prompt = character.get_system_prompt()
        assert "【情绪反应模式】" in prompt

    def test_contains_important_reminder(self, character):
        prompt = character.get_system_prompt()
        assert "【重要提醒】" in prompt

    def test_contains_persona_section(self, character):
        prompt = character.get_system_prompt()
        assert "角色详细设定" in prompt

    def test_contains_exemplars_section(self, character):
        prompt = character.get_system_prompt()
        assert "回复示例" in prompt

    def test_contains_realtime_info(self, character):
        prompt = character.get_system_prompt()
        assert "当前时间" in prompt

    def test_empty_character_prompt_still_valid(self, empty_character):
        prompt = empty_character.get_system_prompt()
        assert "【核心身份】" in prompt
        assert "【核心性格】" in prompt

    def test_prompt_with_context(self, character):
        ctx = {
            "user_name": "测试者",
            "world_layer": "shadow",
            "awakening_level": 30,
        }
        prompt = character.get_system_prompt(ctx)
        assert prompt  # non-empty


# ══════════════════════════════════════════════════════════════
# IMMUTABLE_FILES Protection
# ══════════════════════════════════════════════════════════════

class TestImmutableProtection:
    """Verify IMMUTABLE_FILES contains the expected entries."""

    def test_immutable_set_contains_persona_md(self):
        assert "persona.md" in CharacterBase.IMMUTABLE_FILES

    def test_immutable_set_contains_exemplars_md(self):
        assert "exemplars.md" in CharacterBase.IMMUTABLE_FILES

    def test_immutable_set_contains_config_json(self):
        assert "config.json" in CharacterBase.IMMUTABLE_FILES

    def test_immutable_is_frozenset(self):
        assert isinstance(CharacterBase.IMMUTABLE_FILES, frozenset)

    def test_immutable_cannot_be_modified(self):
        with pytest.raises(AttributeError):
            CharacterBase.IMMUTABLE_FILES.add("new_file.md")

    def test_persona_mutable_not_in_immutable(self):
        """persona_mutable.md is explicitly NOT in IMMUTABLE_FILES."""
        assert "persona_mutable.md" not in CharacterBase.IMMUTABLE_FILES


# ══════════════════════════════════════════════════════════════
# Shared World Loading
# ══════════════════════════════════════════════════════════════

class TestSharedWorldLoading:
    """Verify _load_shared_world() reads from data/world/."""

    def test_shared_world_returns_dict(self, character):
        # Without data/world/ directory, should return empty dict
        assert isinstance(character._shared_world, dict)

    def test_shared_world_with_files(self, tmp_path, sample_config_data):
        """Create data/world/ with a test file and verify loading."""
        # Layout: characters/chayewoon/  and  data/world/
        char_dir = tmp_path / "characters" / "chayewoon"
        char_dir.mkdir(parents=True)
        world_dir = tmp_path / "data" / "world"
        world_dir.mkdir(parents=True)

        # Write a world file
        (world_dir / "locations.md").write_text(
            "## 📍 新叶男子高中\n\n学校描述\n", encoding="utf-8"
        )

        # Write config.json
        import json
        (char_dir / "config.json").write_text(
            json.dumps(sample_config_data, ensure_ascii=False), encoding="utf-8"
        )

        cfg = CharacterConfig.from_dict(
            sample_config_data, id="chayewoon", data_dir=str(char_dir)
        )
        c = ConcreteCharacter(cfg)
        assert "locations" in c._shared_world
        assert "新叶男子高中" in c._shared_world["locations"]


# ══════════════════════════════════════════════════════════════
# Soul Profile Loading
# ══════════════════════════════════════════════════════════════

class TestSoulProfileLoading:
    """Verify _load_soul_profile() reads characters/soul.md."""

    def test_soul_empty_when_no_file(self, character):
        # soul.md is expected at characters/soul.md (parent of chayewoon/)
        # In temp dir there's no such file
        assert character._soul == ""

    def test_soul_loaded_when_present(self, tmp_path, sample_config_data):
        """Create characters/soul.md and verify it loads."""
        import json
        char_dir = tmp_path / "characters" / "chayewoon"
        char_dir.mkdir(parents=True)

        # Write soul.md at characters/ level (sibling of chayewoon/)
        soul_path = tmp_path / "characters" / "soul.md"
        soul_path.write_text(
            "## 基础信息\n\n用户喜欢草莓。\n\n## 性格特质\n\n内向。\n",
            encoding="utf-8",
        )

        (char_dir / "config.json").write_text(
            json.dumps(sample_config_data, ensure_ascii=False), encoding="utf-8"
        )

        cfg = CharacterConfig.from_dict(
            sample_config_data, id="chayewoon", data_dir=str(char_dir)
        )
        c = ConcreteCharacter(cfg)
        assert "用户喜欢草莓" in c._soul
