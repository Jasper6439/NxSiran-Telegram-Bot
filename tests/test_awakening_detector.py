"""
Tests for api/awakening_detector.py — continuous awakening system.

Covers:
1) AwakeningDetector class initialization
2) check() method reactions and return values
3) Emotion threshold boundaries
4) Edge cases (zero, max, negative, missing keys)
5) Deduplication logic (last_check)
6) Integration with Chayewoon's emotion_defaults
"""

import pytest
import asyncio

from api.awakening_detector import AwakeningDetector


# ══════════════════════════════════════════════════════════════
# 1. Initialization
# ══════════════════════════════════════════════════════════════

class TestAwakeningDetectorInit:
    """AwakeningDetector stores no stage model, only a last_check dict."""

    def test_init_creates_empty_last_check(self):
        det = AwakeningDetector()
        assert det.last_check == {}

    def test_init_has_no_stage_attributes(self):
        det = AwakeningDetector()
        assert not hasattr(det, "stages")
        assert not hasattr(det, "stage_thresholds")


# ══════════════════════════════════════════════════════════════
# 2. check() method — reaction logic
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCheckReactions:
    """Verify the three reaction bands returned by check()."""

    async def test_high_affection_low_awakening_returns_confusion(self):
        det = AwakeningDetector()
        result = await det.check("chayewoon", 1, {
            "affection": 50, "happiness": 30, "awakening": 10,
        })
        assert result is not None
        assert result["type"] == "confusion"
        assert len(result["message"]) > 0

    async def test_medium_awakening_returns_unease(self):
        det = AwakeningDetector()
        result = await det.check("chayewoon", 1, {
            "affection": 0, "happiness": 10, "awakening": 40,
        })
        assert result is not None
        assert result["type"] == "unease"
        assert len(result["message"]) > 0

    async def test_high_awakening_returns_awareness(self):
        det = AwakeningDetector()
        result = await det.check("chayewoon", 1, {
            "affection": 0, "happiness": 10, "awakening": 80,
        })
        assert result is not None
        assert result["type"] == "awareness"
        assert len(result["message"]) > 0

    async def test_no_reaction_when_below_all_thresholds(self):
        det = AwakeningDetector()
        result = await det.check("chayewoon", 1, {
            "affection": 10, "happiness": 5, "awakening": 0,
        })
        assert result is None


# ══════════════════════════════════════════════════════════════
# 3. Threshold boundary checks
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestThresholdBoundaries:
    """Test exact boundary values for each reaction band."""

    # confusion: affection > 30 AND awakening < 20
    async def test_affection_exactly_30_no_confusion(self):
        """affection=30 is NOT > 30, so no confusion."""
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 30, "awakening": 0})
        assert result is None

    async def test_affection_31_awakening_0_returns_confusion(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 31, "awakening": 0})
        assert result is not None
        assert result["type"] == "confusion"

    async def test_awakening_exactly_20_no_confusion(self):
        """awakening=20 is NOT < 20, so no confusion even with high affection."""
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 50, "awakening": 20})
        assert result is None

    async def test_awakening_19_with_high_affection_returns_confusion(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 50, "awakening": 19})
        assert result is not None
        assert result["type"] == "confusion"

    # unease: 30 < awakening < 60
    async def test_awakening_exactly_30_no_unease(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "awakening": 30})
        assert result is None

    async def test_awakening_31_returns_unease(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "awakening": 31})
        assert result is not None
        assert result["type"] == "unease"

    async def test_awakening_exactly_60_no_unease(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "awakening": 60})
        assert result is None

    async def test_awakening_59_returns_unease(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "awakening": 59})
        assert result is not None
        assert result["type"] == "unease"

    # awareness: awakening > 70
    async def test_awakening_exactly_70_no_awareness(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "awakening": 70})
        assert result is None

    async def test_awakening_71_returns_awareness(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "awakening": 71})
        assert result is not None
        assert result["type"] == "awareness"


# ══════════════════════════════════════════════════════════════
# 4. Edge cases
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestEdgeCases:

    async def test_all_zeros_returns_none(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 0, "happiness": 0, "awakening": 0})
        assert result is None

    async def test_max_values_awakening_100(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": 100, "happiness": 100, "awakening": 100})
        assert result is not None
        assert result["type"] == "awareness"

    async def test_negative_affection_no_confusion(self):
        """Negative affection (Chayewoon default) should not trigger confusion."""
        det = AwakeningDetector()
        result = await det.check("c", 1, {"affection": -50, "happiness": 5, "awakening": 0})
        assert result is None

    async def test_missing_keys_default_to_zero(self):
        """check() uses .get(..., 0), so missing keys default to 0."""
        det = AwakeningDetector()
        result = await det.check("c", 1, {})
        assert result is None

    async def test_extra_keys_ignored(self):
        det = AwakeningDetector()
        result = await det.check("c", 1, {
            "affection": 50, "happiness": 50, "awakening": 10, "unknown": 999,
        })
        assert result is not None
        assert result["type"] == "confusion"


# ══════════════════════════════════════════════════════════════
# 5. Deduplication (last_check)
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDeduplication:
    """Same reaction type should not be returned twice in a row."""

    async def test_duplicate_reaction_suppressed(self):
        det = AwakeningDetector()
        emotions = {"affection": 50, "happiness": 30, "awakening": 10}
        first = await det.check("c", 1, emotions)
        second = await det.check("c", 1, emotions)
        assert first is not None
        assert second is None  # suppressed because type unchanged

    async def test_different_user_same_character_not_deduplicated(self):
        det = AwakeningDetector()
        emotions = {"affection": 50, "happiness": 30, "awakening": 10}
        r1 = await det.check("c", 1, emotions)
        r2 = await det.check("c", 2, emotions)
        assert r1 is not None
        assert r2 is not None

    async def test_different_character_same_user_not_deduplicated(self):
        det = AwakeningDetector()
        emotions = {"affection": 50, "happiness": 30, "awakening": 10}
        r1 = await det.check("c1", 1, emotions)
        r2 = await det.check("c2", 1, emotions)
        assert r1 is not None
        assert r2 is not None

    async def test_reaction_type_change_returns_new_reaction(self):
        det = AwakeningDetector()
        # First: confusion
        r1 = await det.check("c", 1, {"affection": 50, "happiness": 30, "awakening": 10})
        assert r1["type"] == "confusion"
        # Then: unease (awakening jumps to 40, affection drops)
        r2 = await det.check("c", 1, {"affection": 0, "happiness": 10, "awakening": 40})
        assert r2 is not None
        assert r2["type"] == "unease"


# ══════════════════════════════════════════════════════════════
# 6. Integration with Chayewoon emotion_defaults
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestChayewoonDefaults:
    """Chayewoon starts at affection=-50, happiness=5, awakening=0."""

    CHAYEWOON_DEFAULTS = {
        "affection": -50,
        "happiness": 5,
        "awakening": 0,
    }

    async def test_chayewoon_initial_state_triggers_nothing(self):
        det = AwakeningDetector()
        result = await det.check("chayewoon", 1, self.CHAYEWOON_DEFAULTS)
        assert result is None

    async def test_chayewoon_min_affection_threshold_met(self):
        """Config says min_affection=30. At affection=30 exactly, no confusion (not > 30)."""
        det = AwakeningDetector()
        emotions = {**self.CHAYEWOON_DEFAULTS, "affection": 30}
        result = await det.check("chayewoon", 1, emotions)
        assert result is None

    async def test_chayewoon_min_happiness_threshold_met(self):
        """Config says min_happiness=20. Happiness alone doesn't trigger a reaction
        (no happiness-only rule), but at affection=31 + awakening=10, confusion appears."""
        det = AwakeningDetector()
        emotions = {
            "affection": 31, "happiness": 20, "awakening": 10,
        }
        result = await det.check("chayewoon", 1, emotions)
        assert result is not None
        assert result["type"] == "confusion"

    async def test_chayewoon_progression_from_default_to_confusion(self):
        """Simulate gradual affection increase from -50."""
        det = AwakeningDetector()
        # Still negative — no reaction
        r1 = await det.check("chayewoon", 1, {"affection": -10, "happiness": 5, "awakening": 0})
        assert r1 is None
        # Crosses 30 — confusion appears
        r2 = await det.check("chayewoon", 1, {"affection": 35, "happiness": 10, "awakening": 0})
        assert r2 is not None
        assert r2["type"] == "confusion"
