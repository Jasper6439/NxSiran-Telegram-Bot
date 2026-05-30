"""
Tests for NarrativeArc (api/narrative_arc.py)

Covers:
- EmotionalZone detection
- get_available_beats filtering
- trigger_beat lifecycle
- get_narrative_context output
- has_triggered / get_story_summary
- get_narrative_arc singleton
"""

import pytest
from api.narrative_arc import (
    EmotionalZone,
    NarrativeArc,
    NarrativeBeat,
    NARRATIVE_BEATS,
    StoryEvent,
    get_narrative_arc,
)


# ══════════════════════════════════════════════════════════════
# EmotionalZone Detection
# ══════════════════════════════════════════════════════════════

class TestGetZone:
    """Verify zone detection from emotion values."""

    def test_hostile_zone(self):
        assert NarrativeArc.get_zone({"affection": -50}) == EmotionalZone.HOSTILE

    def test_cold_zone(self):
        assert NarrativeArc.get_zone({"affection": -10}) == EmotionalZone.COLD

    def test_warming_zone(self):
        assert NarrativeArc.get_zone({"affection": 20, "awakening": 5}) == EmotionalZone.WARMING

    def test_connected_zone(self):
        assert NarrativeArc.get_zone({"affection": 50, "awakening": 5}) == EmotionalZone.CONNECTED

    def test_questioning_zone(self):
        assert NarrativeArc.get_zone({"affection": 50, "awakening": 40}) == EmotionalZone.QUESTIONING

    def test_awakening_zone(self):
        assert NarrativeArc.get_zone({"affection": 50, "awakening": 65}) == EmotionalZone.AWAKENING

    def test_transcendent_zone(self):
        assert NarrativeArc.get_zone({"affection": 80, "awakening": 85}) == EmotionalZone.TRANSCENDENT

    def test_awakening_overrides_affection(self):
        """High awakening pushes to higher zone regardless of affection."""
        zone = NarrativeArc.get_zone({"affection": -30, "awakening": 85})
        assert zone == EmotionalZone.TRANSCENDENT

    def test_chayewoon_initial_state(self):
        """Chayewoon starts at affection=-50, happiness=5, awakening=0 → HOSTILE."""
        zone = NarrativeArc.get_zone({"affection": -50, "happiness": 5, "awakening": 0})
        assert zone == EmotionalZone.HOSTILE

    def test_missing_keys_default_zero(self):
        """Default affection=0 → COLD zone."""
        assert NarrativeArc.get_zone({}) == EmotionalZone.COLD

    def test_boundary_affection_minus_20(self):
        """-21 is HOSTILE (< -20), -20 is COLD (not < -20).
        Note: happiness=50 neutralizes the modifier.
        """
        assert NarrativeArc.get_zone({"affection": -21, "happiness": 50}) == EmotionalZone.HOSTILE
        assert NarrativeArc.get_zone({"affection": -20, "happiness": 50}) == EmotionalZone.COLD

    def test_boundary_affection_10(self):
        """9 is COLD, 10 is WARMING (if awakening < 20).
        Note: happiness=50 neutralizes the modifier.
        """
        assert NarrativeArc.get_zone({"affection": 9, "happiness": 50, "awakening": 0}) == EmotionalZone.COLD
        assert NarrativeArc.get_zone({"affection": 10, "happiness": 50, "awakening": 0}) == EmotionalZone.WARMING

    def test_boundary_affection_40(self):
        """39 is WARMING, 40 is CONNECTED (if awakening < 30).
        Note: happiness=50 neutralizes the modifier.
        """
        assert NarrativeArc.get_zone({"affection": 39, "happiness": 50, "awakening": 0}) == EmotionalZone.WARMING
        assert NarrativeArc.get_zone({"affection": 40, "happiness": 50, "awakening": 0}) == EmotionalZone.CONNECTED


# ══════════════════════════════════════════════════════════════
# get_available_beats
# ══════════════════════════════════════════════════════════════

class TestGetAvailableBeats:
    """Verify beat filtering by zone and thresholds."""

    def test_hostile_zone_has_beats(self):
        arc = NarrativeArc()
        beats = arc.get_available_beats({"affection": -50})
        assert len(beats) > 0
        assert all(b.trigger_zone == EmotionalZone.HOSTILE for b in beats)

    def test_cold_zone_beats(self):
        arc = NarrativeArc()
        beats = arc.get_available_beats({"affection": 0})
        assert all(b.trigger_zone == EmotionalZone.COLD for b in beats)

    def test_warming_zone_beats(self):
        arc = NarrativeArc()
        beats = arc.get_available_beats({"affection": 20, "awakening": 5})
        assert all(b.trigger_zone == EmotionalZone.WARMING for b in beats)

    def test_filtered_by_min_affection(self):
        arc = NarrativeArc()
        # Warming zone with affection=10 — some beats need affection>=20
        beats = arc.get_available_beats({"affection": 10, "awakening": 0})
        for b in beats:
            assert 10 >= b.min_affection

    def test_sorted_by_priority(self):
        arc = NarrativeArc()
        beats = arc.get_available_beats({"affection": -50})
        priorities = [b.priority for b in beats]
        assert priorities == sorted(priorities, reverse=True)

    def test_excludes_triggered_non_repeatable(self):
        arc = NarrativeArc()
        # Trigger a non-repeatable beat
        arc.trigger_beat("defensive_wall", {"affection": -50})
        beats = arc.get_available_beats({"affection": -50})
        assert not any(b.name == "defensive_wall" for b in beats)

    def test_repeatable_beat_stays_available(self):
        arc = NarrativeArc()
        # jealousy_moment is repeatable
        arc.trigger_beat("jealousy_moment", {"affection": 25, "awakening": 5})
        beats = arc.get_available_beats({"affection": 25, "awakening": 5})
        assert any(b.name == "jealousy_moment" for b in beats)

    def test_empty_for_impossible_state(self):
        arc = NarrativeArc()
        # All beats need specific zones — very high affection with very high awakening
        # should be in TRANSCENDENT, which has its own beats
        beats = arc.get_available_beats({"affection": 80, "awakening": 85})
        assert len(beats) > 0  # TRANSCENDENT has beats


# ══════════════════════════════════════════════════════════════
# trigger_beat
# ══════════════════════════════════════════════════════════════

class TestTriggerBeat:
    """Verify beat triggering lifecycle."""

    def test_trigger_valid_beat(self):
        arc = NarrativeArc()
        event = arc.trigger_beat("defensive_wall", {"affection": -50})
        assert event is not None
        assert event.beat_name == "defensive_wall"

    def test_trigger_records_emotion_snapshot(self):
        arc = NarrativeArc()
        emotions = {"affection": -50, "happiness": 5, "awakening": 0}
        event = arc.trigger_beat("defensive_wall", emotions)
        assert event.emotion_snapshot == emotions

    def test_trigger_unknown_beat_returns_none(self):
        arc = NarrativeArc()
        event = arc.trigger_beat("nonexistent_beat", {})
        assert event is None

    def test_non_repeatable_cannot_retrigger(self):
        arc = NarrativeArc()
        arc.trigger_beat("defensive_wall", {"affection": -50})
        event2 = arc.trigger_beat("defensive_wall", {"affection": -50})
        assert event2 is None

    def test_repeatable_can_retrigger(self):
        arc = NarrativeArc()
        arc.trigger_beat("jealousy_moment", {"affection": 25, "awakening": 5})
        event2 = arc.trigger_beat("jealousy_moment", {"affection": 30, "awakening": 5})
        assert event2 is not None

    def test_has_triggered(self):
        arc = NarrativeArc()
        assert not arc.has_triggered("defensive_wall")
        arc.trigger_beat("defensive_wall", {"affection": -50})
        assert arc.has_triggered("defensive_wall")

    def test_events_accumulate(self):
        arc = NarrativeArc()
        arc.trigger_beat("defensive_wall", {"affection": -50})
        arc.trigger_beat("accidental_vulnerability", {"affection": -40, "happiness": 15})
        summary = arc.get_story_summary()
        assert summary["total_events"] == 2


# ══════════════════════════════════════════════════════════════
# get_narrative_context
# ══════════════════════════════════════════════════════════════

class TestGetNarrativeContext:
    """Verify narrative context generation for LLM prompt."""

    def test_contains_zone_name(self):
        arc = NarrativeArc()
        ctx = arc.get_narrative_context({"affection": -50})
        assert "hostile" in ctx

    def test_contains_beat_descriptions(self):
        arc = NarrativeArc()
        ctx = arc.get_narrative_context({"affection": -50})
        assert "defensive_wall" in ctx or "防线" in ctx

    def test_limits_to_three_beats(self):
        arc = NarrativeArc()
        ctx = arc.get_narrative_context({"affection": 20, "awakening": 5})
        # Count beat names in context
        beat_count = sum(1 for b in NARRATIVE_BEATS if b.name in ctx)
        assert beat_count <= 3

    def test_includes_recent_events(self):
        arc = NarrativeArc()
        arc.trigger_beat("defensive_wall", {"affection": -50, "happiness": 15})
        ctx = arc.get_narrative_context({"affection": -50, "happiness": 15})
        # Should have recent events section even if no more beats available
        assert "defensive_wall" in ctx or "最近" in ctx or "accidental_vulnerability" in ctx

    def test_empty_for_no_beats(self):
        arc = NarrativeArc()
        # Create a state where no beats are available
        # This shouldn't normally happen, but test graceful handling
        ctx = arc.get_narrative_context({"affection": -100, "happiness": 0, "awakening": 0})
        # Should still return something since HOSTILE has beats
        assert isinstance(ctx, str)


# ══════════════════════════════════════════════════════════════
# get_story_summary
# ══════════════════════════════════════════════════════════════

class TestGetStorySummary:
    """Verify story summary output."""

    def test_empty_summary(self):
        arc = NarrativeArc("test_char")
        summary = arc.get_story_summary()
        assert summary["character_id"] == "test_char"
        assert summary["total_events"] == 0
        assert summary["triggered_beats"] == []

    def test_summary_with_events(self):
        arc = NarrativeArc()
        arc.trigger_beat("defensive_wall", {"affection": -50})
        arc.trigger_beat("reluctant_tolerance", {"affection": 0})
        summary = arc.get_story_summary()
        assert summary["total_events"] == 2
        assert "defensive_wall" in summary["triggered_beats"]
        assert len(summary["recent_events"]) == 2

    def test_recent_events_limited(self):
        arc = NarrativeArc()
        for i in range(10):
            arc.trigger_beat("jealousy_moment", {"affection": 25, "awakening": 5})
        summary = arc.get_story_summary()
        assert len(summary["recent_events"]) <= 5


# ══════════════════════════════════════════════════════════════
# get_narrative_arc Singleton
# ══════════════════════════════════════════════════════════════

class TestGetNarrativeArc:
    """Verify singleton behavior."""

    def test_returns_same_instance(self):
        from api.narrative_arc import _arc_instances
        _arc_instances.clear()

        a1 = get_narrative_arc("test")
        a2 = get_narrative_arc("test")
        assert a1 is a2
        _arc_instances.clear()

    def test_different_ids_different_instances(self):
        from api.narrative_arc import _arc_instances
        _arc_instances.clear()

        a1 = get_narrative_arc("char_a")
        a2 = get_narrative_arc("char_b")
        assert a1 is not a2
        _arc_instances.clear()

    def test_default_character_id(self):
        from api.narrative_arc import _arc_instances
        _arc_instances.clear()

        arc = get_narrative_arc()
        assert arc.character_id == "chayewoon"
        _arc_instances.clear()


# ══════════════════════════════════════════════════════════════
# NARRATIVE_BEATS Consistency
# ══════════════════════════════════════════════════════════════

class TestNarrativeBeatsConsistency:
    """Verify the predefined beats are well-formed."""

    def test_all_beats_have_unique_names(self):
        names = [b.name for b in NARRATIVE_BEATS]
        assert len(names) == len(set(names))

    def test_all_beats_have_descriptions(self):
        for beat in NARRATIVE_BEATS:
            assert beat.description, f"{beat.name} missing description"

    def test_all_beats_have_valid_zone(self):
        for beat in NARRATIVE_BEATS:
            assert beat.trigger_zone in EmotionalZone

    def test_beats_cover_all_zones(self):
        zones = {b.trigger_zone for b in NARRATIVE_BEATS}
        # At least HOSTILE, COLD, WARMING, CONNECTED should be covered
        assert EmotionalZone.HOSTILE in zones
        assert EmotionalZone.COLD in zones
        assert EmotionalZone.WARMING in zones
        assert EmotionalZone.CONNECTED in zones

    def test_total_beat_count(self):
        """Ensure we have a reasonable number of beats."""
        assert len(NARRATIVE_BEATS) >= 10
