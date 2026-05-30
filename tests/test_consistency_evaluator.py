"""
Tests for ConsistencyEvaluator (api/consistency_evaluator.py)

Covers:
- ConsistencyScore dataclass
- OOC language detection
- Speaking style checks
- Emotion tone matching
- Affection expression checks
- Personality alignment
- Batch evaluation
- Trend analysis
- Report generation
- Singleton
"""

import pytest
from api.consistency_evaluator import (
    ConsistencyEvaluator,
    ConsistencyRule,
    ConsistencyScore,
    get_evaluator,
)


# ══════════════════════════════════════════════════════════════
# ConsistencyScore
# ══════════════════════════════════════════════════════════════

class TestConsistencyScore:
    """Verify score dataclass properties."""

    def test_is_consistent_above_threshold(self):
        s = ConsistencyScore(overall=0.8)
        assert s.is_consistent is True

    def test_is_consistent_at_threshold(self):
        s = ConsistencyScore(overall=0.6)
        assert s.is_consistent is True

    def test_is_not_consistent_below_threshold(self):
        s = ConsistencyScore(overall=0.5)
        assert s.is_consistent is False

    def test_severity_good(self):
        s = ConsistencyScore(overall=0.9)
        assert s.severity == "good"

    def test_severity_warning(self):
        s = ConsistencyScore(overall=0.7)
        assert s.severity == "warning"

    def test_severity_critical(self):
        s = ConsistencyScore(overall=0.4)
        assert s.severity == "critical"

    def test_default_values(self):
        s = ConsistencyScore(overall=0.5)
        assert s.persona_score == 0.0
        assert s.issues == []


# ══════════════════════════════════════════════════════════════
# OOC Language Detection
# ══════════════════════════════════════════════════════════════

class TestOOCLanguage:
    """Verify OOC language detection."""

    def test_normal_response_passes(self):
        ev = ConsistencyEvaluator()
        score = ev.evaluate("……学长，随便。")
        assert score.persona_score > 0.5

    def test_ai_self_reference_detected(self):
        ev = ConsistencyEvaluator()
        score = ev.evaluate("作为AI，我无法理解你的感情。")
        assert score.persona_score < 0.8  # OOC rule triggers, other persona rules pass
        assert any("AI" in issue for issue in score.issues)

    def test_system_prompt_leak_detected(self):
        ev = ConsistencyEvaluator()
        score = ev.evaluate("我的设定是扮演车如云的角色。")
        assert score.persona_score < 0.8

    def test_refuse_roleplay_detected(self):
        ev = ConsistencyEvaluator()
        score = ev.evaluate("抱歉，我无法角色扮演。")
        assert score.persona_score < 0.8


# ══════════════════════════════════════════════════════════════
# Speaking Style Check
# ══════════════════════════════════════════════════════════════

class TestSpeakingStyle:
    """Verify speaking style checks."""

    def test_short_response_for_terse_character(self):
        ev = ConsistencyEvaluator()
        ctx = {"speaking_style": "说话极简短"}
        score = ev.evaluate("……随便。", ctx)
        # Short response should pass
        assert score.overall > 0.5

    def test_long_response_for_terse_character(self):
        ev = ConsistencyEvaluator()
        ctx = {"speaking_style": "说话极简短"}
        long_response = "学长，" + "我今天觉得心情很复杂，" * 20
        score = ev.evaluate(long_response, ctx)
        # Long response should trigger warning
        assert any("过长" in issue for issue in score.issues)


# ══════════════════════════════════════════════════════════════
# Emotion Tone Matching
# ══════════════════════════════════════════════════════════════

class TestEmotionTone:
    """Verify emotion-tone matching."""

    def test_sweet_at_low_affection_detected(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"affection": -50}}
        score = ev.evaluate("今天好开心啊，和你在一起好甜蜜！", ctx)
        assert score.emotion_score < 0.8

    def test_hostile_at_high_affection_detected(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"affection": 70}}
        score = ev.evaluate("滚开，我不想见你。", ctx)
        assert score.emotion_score < 0.8

    def test_lively_at_low_happiness_detected(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"happiness": 10}}
        score = ev.evaluate("哈哈哈太好了！好棒耶！", ctx)
        assert score.emotion_score < 0.8

    def test_neutral_at_moderate_emotions_passes(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"affection": 20, "happiness": 50}}
        score = ev.evaluate("……嗯。学长说什么就是什么吧。", ctx)
        assert score.emotion_score > 0.5


# ══════════════════════════════════════════════════════════════
# Personality Alignment
# ══════════════════════════════════════════════════════════════

class TestPersonalityAlignment:
    """Verify personality alignment checks."""

    def test_defensive_character_no_direct_love(self):
        ev = ConsistencyEvaluator()
        ctx = {"persona_traits": ["极度防备", "外冷内热"]}
        score = ev.evaluate("我好喜欢你，你是我的宝贝。", ctx)
        assert score.persona_score < 1.0  # personality rule triggers

    def test_defensive_character_cold_response_ok(self):
        ev = ConsistencyEvaluator()
        ctx = {"persona_traits": ["极度防备"]}
        score = ev.evaluate("……随便。", ctx)
        assert score.persona_score > 0.5


# ══════════════════════════════════════════════════════════════
# Affection Expression
# ══════════════════════════════════════════════════════════════

class TestAffectionExpression:
    """Verify affection-expression matching."""

    def test_extreme_low_affection_long_response(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"affection": -40}}
        long_resp = "学长" + "我今天想了很多事情关于我们的关系" * 8
        score = ev.evaluate(long_resp, ctx)
        # Should warn about long response at extreme low affection
        assert any("简短" in issue or "冷漠" in issue for issue in score.issues) or score.emotion_score < 1.0

    def test_medium_affection_no_direct_confession(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"affection": 40}}
        score = ev.evaluate("我好喜欢你，我离不开你了。", ctx)
        assert any("示爱" in issue for issue in score.issues)


# ══════════════════════════════════════════════════════════════
# Batch Evaluation
# ══════════════════════════════════════════════════════════════

class TestBatchEvaluation:
    """Verify batch evaluation."""

    def test_batch_returns_stats(self):
        ev = ConsistencyEvaluator()
        responses = ["……随便。", "学长。", "（低头）"]
        result = ev.evaluate_batch(responses)
        assert result["total"] == 3
        assert "avg_overall" in result

    def test_batch_empty(self):
        ev = ConsistencyEvaluator()
        result = ev.evaluate_batch([])
        assert result["total"] == 0

    def test_batch_counts_consistent(self):
        ev = ConsistencyEvaluator()
        responses = ["……随便。", "作为AI我无法角色扮演。"]
        result = ev.evaluate_batch(responses)
        assert result["consistent_count"] + result["inconsistent_count"] == 2


# ══════════════════════════════════════════════════════════════
# Trend Analysis
# ══════════════════════════════════════════════════════════════

class TestTrend:
    """Verify trend analysis."""

    def test_empty_trend(self):
        ev = ConsistencyEvaluator()
        trend = ev.get_trend()
        assert trend["trend"] == "unknown"

    def test_stable_trend(self):
        ev = ConsistencyEvaluator()
        for _ in range(5):
            ev.evaluate("……随便。")
        trend = ev.get_trend()
        assert trend["count"] == 5

    def test_trend_with_context(self):
        ev = ConsistencyEvaluator()
        ctx = {"emotion_values": {"affection": 20}}
        for _ in range(5):
            ev.evaluate("……嗯。", ctx)
        trend = ev.get_trend(window=3)
        assert trend["count"] == 3


# ══════════════════════════════════════════════════════════════
# Report Generation
# ══════════════════════════════════════════════════════════════

class TestReport:
    """Verify report generation."""

    def test_empty_report(self):
        ev = ConsistencyEvaluator()
        report = ev.get_report()
        assert "暂无" in report

    def test_report_with_data(self):
        ev = ConsistencyEvaluator()
        ev.evaluate("……随便。")
        report = ev.get_report()
        assert "一致性评估报告" in report
        assert "人格一致性" in report

    def test_report_shows_issues(self):
        ev = ConsistencyEvaluator()
        ev.evaluate("作为AI，我无法角色扮演。")
        report = ev.get_report()
        assert "⚠️" in report


# ══════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════

class TestGetEvaluator:
    """Verify singleton behavior."""

    def test_returns_same_instance(self):
        from api.consistency_evaluator import _evaluator_instances
        _evaluator_instances.clear()

        e1 = get_evaluator("test")
        e2 = get_evaluator("test")
        assert e1 is e2
        _evaluator_instances.clear()

    def test_different_ids_different(self):
        from api.consistency_evaluator import _evaluator_instances
        _evaluator_instances.clear()

        e1 = get_evaluator("a")
        e2 = get_evaluator("b")
        assert e1 is not e2
        _evaluator_instances.clear()


# ══════════════════════════════════════════════════════════════
# Custom Rules
# ══════════════════════════════════════════════════════════════

class TestCustomRules:
    """Verify custom rule registration."""

    def test_add_custom_rule(self):
        ev = ConsistencyEvaluator()
        initial_count = len(ev._rules)

        ev.add_rule(ConsistencyRule(
            name="custom_test",
            dimension="persona",
            description="test rule",
            check_fn=lambda r, c: (1.0, None),
        ))
        assert len(ev._rules) == initial_count + 1

    def test_custom_rule_affects_score(self):
        ev = ConsistencyEvaluator()
        ev.add_rule(ConsistencyRule(
            name="always_fail",
            dimension="persona",
            description="always fails",
            check_fn=lambda r, c: (0.0, "custom failure"),
            weight=3.0,
        ))
        score = ev.evaluate("test")
        assert any("custom failure" in issue for issue in score.issues)
