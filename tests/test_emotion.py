"""
Tests for the emotion system.

Covers:
- emotion_defaults from character config
- Three emotion dimensions (affection, happiness, awakening)
- Chayewoon's initial affection at -50

Note: The runtime emotion module (characters/emotion.py) depends on
`telegram` and `system.prompts`, so we test the config-level emotion
data and the CharacterBase integration here.
"""

import json
import pytest

from characters.base import CharacterBase, CharacterConfig


# ══════════════════════════════════════════════════════════════
# Emotion Defaults from Config
# ══════════════════════════════════════════════════════════════

class TestEmotionDefaults:
    """Verify emotion_defaults are loaded from config.json."""

    def test_config_has_emotion_defaults(self, sample_config_data):
        assert "emotion_defaults" in sample_config_data

    def test_emotion_defaults_is_dict(self, sample_config_data):
        assert isinstance(sample_config_data["emotion_defaults"], dict)


# ══════════════════════════════════════════════════════════════
# Three Emotion Dimensions
# ══════════════════════════════════════════════════════════════

class TestThreeDimensions:
    """The emotion system tracks three dimensions:
    affection, happiness, awakening.
    """

    def test_emotion_defaults_has_affection(self, sample_config_data):
        assert "affection" in sample_config_data["emotion_defaults"]

    def test_emotion_defaults_has_happiness(self, sample_config_data):
        assert "happiness" in sample_config_data["emotion_defaults"]

    def test_emotion_defaults_has_awakening(self, sample_config_data):
        assert "awakening" in sample_config_data["emotion_defaults"]

    def test_dimensions_are_numeric(self, sample_config_data):
        for key in ("affection", "happiness", "awakening"):
            val = sample_config_data["emotion_defaults"][key]
            assert isinstance(val, (int, float)), f"{key} should be numeric, got {type(val)}"

    def test_config_from_dict_preserves_emotion_defaults(self, sample_config_data):
        """CharacterConfig.from_dict should keep emotion_defaults."""
        cfg = CharacterConfig.from_dict(sample_config_data, id="test")
        assert cfg.emotion_defaults is not None
        assert cfg.emotion_defaults["affection"] == -50
        assert cfg.emotion_defaults["happiness"] == 5
        assert cfg.emotion_defaults["awakening"] == 0


# ══════════════════════════════════════════════════════════════
# Chayewoon Specific: affection starts at -50
# ══════════════════════════════════════════════════════════════

class TestChayewoonAffection:
    """Chayewoon's affection starts at -50 (distrustful by default)."""

    def test_affection_starts_at_negative_fifty(self, sample_config_data):
        assert sample_config_data["emotion_defaults"]["affection"] == -50

    def test_affection_is_negative(self, sample_config_data):
        """Chayewoon starts with negative affection (distrustful)."""
        assert sample_config_data["emotion_defaults"]["affection"] < 0

    def test_happiness_starts_low(self, sample_config_data):
        """Happiness starts at 5 (barely above zero)."""
        assert sample_config_data["emotion_defaults"]["happiness"] == 5

    def test_awakening_starts_at_zero(self, sample_config_data):
        """Awakening starts at 0 (completely unaware)."""
        assert sample_config_data["emotion_defaults"]["awakening"] == 0

    def test_character_config_reflects_defaults(self, character_config):
        """Verify the loaded CharacterConfig has correct emotion defaults."""
        assert character_config.emotion_defaults is not None
        assert character_config.emotion_defaults["affection"] == -50

    def test_real_config_json_matches(self, tmp_data_dir):
        """Load the actual config.json from disk and verify emotion defaults."""
        cfg_path = tmp_data_dir / "config.json"
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["emotion_defaults"]["affection"] == -50
        assert data["emotion_defaults"]["happiness"] == 5
        assert data["emotion_defaults"]["awakening"] == 0


# ══════════════════════════════════════════════════════════════
# Awakening Conditions
# ══════════════════════════════════════════════════════════════

class TestAwakeningConditions:
    """Verify awakening_conditions config structure."""

    def test_awakening_conditions_present(self, sample_config_data):
        assert "awakening_conditions" in sample_config_data

    def test_min_affection_threshold(self, sample_config_data):
        conds = sample_config_data["awakening_conditions"]
        assert conds["min_affection"] == 30

    def test_min_happiness_threshold(self, sample_config_data):
        conds = sample_config_data["awakening_conditions"]
        assert conds["min_happiness"] == 20

    def test_required_events_is_list(self, sample_config_data):
        conds = sample_config_data["awakening_conditions"]
        assert isinstance(conds["required_events"], list)
