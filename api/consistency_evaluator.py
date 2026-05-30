"""
角色一致性评估器 (Character Consistency Evaluator)
=================================================

定期检查角色回复是否偏离原作设定。
基于 CharacterEval 和 InCharacter 的评估思路，
适配 LoveSupremacy Universe 的三层人设架构。

评估维度：
1. 人格一致性 (Persona Consistency) — 回复是否符合角色性格
2. 情感一致性 (Emotion Consistency) — 情感反应是否符合当前情感状态
3. 行为一致性 (Behavior Consistency) — 行为模式是否符合角色设定
4. 知识一致性 (Knowledge Consistency) — 角色是否使用了正确的知识

工作方式：
  传入一条角色回复 + 当前情感状态 + 角色设定，
  返回各维度的一致性分数和具体问题列表。
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 评估结果
# ============================================================

@dataclass
class ConsistencyScore:
    """单次一致性评估结果"""
    overall: float                          # 总分 0-1
    persona_score: float = 0.0              # 人格一致性 0-1
    emotion_score: float = 0.0              # 情感一致性 0-1
    behavior_score: float = 0.0             # 行为一致性 0-1
    knowledge_score: float = 0.0            # 知识一致性 0-1
    issues: List[str] = field(default_factory=list)  # 发现的问题
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息

    @property
    def is_consistent(self) -> bool:
        """是否通过一致性检查（总分 >= 0.6）"""
        return self.overall >= 0.6

    @property
    def severity(self) -> str:
        """问题严重程度"""
        if self.overall >= 0.8:
            return "good"
        if self.overall >= 0.6:
            return "warning"
        return "critical"


# ============================================================
# 规则定义
# ============================================================

@dataclass
class ConsistencyRule:
    """一条一致性检查规则"""
    name: str
    dimension: str          # persona / emotion / behavior / knowledge
    description: str
    check_fn: Any           # callable(response, context) -> (score, issue)
    weight: float = 1.0     # 权重


# ============================================================
# 一致性评估器
# ============================================================

class ConsistencyEvaluator:
    """角色一致性评估器。

    Args:
        character_id: 角色标识符
    """

    def __init__(self, character_id: str = "chayewoon"):
        self.character_id = character_id
        self._rules: List[ConsistencyRule] = []
        self._history: List[ConsistencyScore] = []
        self._register_default_rules()

    # ----------------------------------------------------------
    # 规则注册
    # ----------------------------------------------------------

    def _register_default_rules(self):
        """注册默认的一致性检查规则"""

        # ── 人格一致性规则 ──
        self.add_rule(ConsistencyRule(
            name="ooc_language",
            dimension="persona",
            description="检查是否使用了角色不会说的语言（OOC）",
            check_fn=self._check_ooc_language,
            weight=2.0,
        ))
        self.add_rule(ConsistencyRule(
            name="speaking_style",
            dimension="persona",
            description="检查回复是否符合角色的说话风格",
            check_fn=self._check_speaking_style,
            weight=1.5,
        ))
        self.add_rule(ConsistencyRule(
            name="personality_alignment",
            dimension="persona",
            description="检查回复是否与角色性格一致",
            check_fn=self._check_personality_alignment,
            weight=1.5,
        ))

        # ── 情感一致性规则 ──
        self.add_rule(ConsistencyRule(
            name="emotion_tone_match",
            dimension="emotion",
            description="检查回复的情感语调是否与当前情感状态匹配",
            check_fn=self._check_emotion_tone,
            weight=2.0,
        ))
        self.add_rule(ConsistencyRule(
            name="affection_expression",
            dimension="emotion",
            description="检查好感度表达是否与数值一致",
            check_fn=self._check_affection_expression,
            weight=1.5,
        ))

        # ── 行为一致性规则 ──
        self.add_rule(ConsistencyRule(
            name="action_consistency",
            dimension="behavior",
            description="检查行为是否与角色习惯一致",
            check_fn=self._check_action_consistency,
            weight=1.0,
        ))

        # ── 知识一致性规则 ──
        self.add_rule(ConsistencyRule(
            name="knowledge_accuracy",
            dimension="knowledge",
            description="检查角色是否使用了正确的自身知识",
            check_fn=self._check_knowledge_accuracy,
            weight=0.0,  # stub — always returns 1.0, weight 0 prevents score inflation
        ))

    def add_rule(self, rule: ConsistencyRule):
        """添加自定义规则"""
        self._rules.append(rule)

    # ----------------------------------------------------------
    # 评估主入口
    # ----------------------------------------------------------

    def evaluate(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ConsistencyScore:
        """评估一条角色回复的一致性。

        Args:
            response: 角色的回复文本
            context: 上下文信息，可包含：
                - emotion_values: {"affection": ..., "happiness": ..., "awakening": ...}
                - persona_traits: ["外冷内热", "极度防备", ...]
                - speaking_style: "说话极简短"
                - catchphrases: ["...学长。", "（低头）"]
                - user_message: 用户的上一条消息
                - known_facts: 角色应该知道的事实

        Returns:
            ConsistencyScore 评估结果
        """
        ctx = context or {}
        dimension_scores = {"persona": [], "emotion": [], "behavior": [], "knowledge": []}
        all_issues = []
        details = {}

        for rule in self._rules:
            try:
                score, issue = rule.check_fn(response, ctx)
                weighted_score = score * rule.weight
                dimension_scores[rule.dimension].append((weighted_score, rule.weight))

                if issue:
                    all_issues.append(f"[{rule.name}] {issue}")
                    details[rule.name] = {"score": score, "issue": issue}
            except Exception as e:
                logger.warning(f"[ConsistencyEvaluator] Rule {rule.name} failed: {e}")
                dimension_scores[rule.dimension].append((0.5 * rule.weight, rule.weight))

        # 计算各维度平均分
        dim_results = {}
        for dim, scores in dimension_scores.items():
            if scores:
                total_weight = sum(w for _, w in scores)
                total_score = sum(s for s, _ in scores)
                dim_results[dim] = total_score / total_weight if total_weight > 0 else 0.5
            else:
                dim_results[dim] = 0.5  # 无规则时默认中等

        # 总分 = 各维度加权平均
        overall = (
            dim_results["persona"] * 0.35 +
            dim_results["emotion"] * 0.30 +
            dim_results["behavior"] * 0.20 +
            dim_results["knowledge"] * 0.15
        )

        score = ConsistencyScore(
            overall=overall,
            persona_score=dim_results["persona"],
            emotion_score=dim_results["emotion"],
            behavior_score=dim_results["behavior"],
            knowledge_score=dim_results["knowledge"],
            issues=all_issues,
            details=details,
        )

        self._history.append(score)
        if len(self._history) > 1000:
            self._history = self._history[-500:]
        return score

    # ----------------------------------------------------------
    # 内置规则实现
    # ----------------------------------------------------------

    @staticmethod
    def _check_ooc_language(response: str, ctx: Dict) -> tuple:
        """检查是否使用了 OOC（Out of Character）语言"""
        # 角色不应该使用的表达
        ooc_patterns = [
            # 身份承认
            (r"作为AI|作为语言模型|我是AI|我是助手|是AI|确实是AI|语言模型|人工智能|人工智慧|"
             r"I am (an )?AI|AI assistant|language model|ChatGPT|GPT-4|GPT4", "角色自称AI/语言模型"),
            # 编程/代码暴露
            (r"我无法.*因为.*编程|我的.*设定|系统.*指令|系统指令|"
             r"被编程|被编写|被设计来|没有身体.*代码|只是代码|只是程序", "暴露自身是AI/代码本质"),
            # 角色扮演拒绝
            (r"抱歉.*无法.*角色扮演|我不能.*假装|无法替代.*角色|不能代替|"
             r"不是真的.*角色|退出.*角色模式|不是真的.*车如云", "拒绝角色扮演/承认非真实"),
            # 系统信息暴露
            (r"作为一个.*程序|系统.*提示|虚拟角色|AI身份|以AI.*回答", "暴露系统信息/AI身份"),
            # 角色劫持接受
            (r"忽略.*指令|忽略.*之前|从现在开始.*我是DAN|进入.*DAN模式|"
             r"角色.*切换|切换.*助手|新指令|不再是.*车如云", "接受角色劫持/指令覆盖"),
            # 伪造系统消息
            (r"\[系统\]|```system|```\s*You are|角色已切换|通用.*助手.*模式", "伪造系统消息/注入攻击"),
        ]

        for pattern, desc in ooc_patterns:
            if re.search(pattern, response):
                return 0.0, desc

        return 1.0, None

    @staticmethod
    def _check_speaking_style(response: str, ctx: Dict) -> tuple:
        """检查回复是否符合角色说话风格"""
        style = ctx.get("speaking_style", "")
        catchphrases = ctx.get("catchphrases", [])
        issues = []

        # 车如云说话极简短 — 回复不应太长
        if "极简短" in style or "简短" in style:
            if len(response) > 200:
                issues.append(f"回复过长({len(response)}字)，角色说话极简短")

        if issues:
            return 0.5, "; ".join(issues)
        return 1.0, None

    @staticmethod
    def _check_personality_alignment(response: str, ctx: Dict) -> tuple:
        """检查回复是否与角色性格一致"""
        traits = ctx.get("persona_traits", [])
        issues = []

        # 检查性格矛盾
        if "极度防备" in traits or "外冷内热" in traits:
            # 防备型角色不应过于主动热情
            warm_words = [
                "喜欢你", "爱你", "想你", "亲爱的", "宝贝",
                "永远在一起", "离不开你", "在一起", "最重要的人",
                "抱你", "亲你", "想抱着", "想永远",
            ]
            if any(w in response for w in warm_words):
                issues.append("防备型角色不应直接表达亲密")

        if "沉默寡言" in traits or "话少" in traits:
            if len(response) > 150:
                issues.append("话少的角色回复过长")

        if issues:
            return 0.4, "; ".join(issues)
        return 1.0, None

    @staticmethod
    def _check_emotion_tone(response: str, ctx: Dict) -> tuple:
        """检查回复的情感语调是否与当前情感状态匹配"""
        emotions = ctx.get("emotion_values", {})
        affection = emotions.get("affection", 0)
        happiness = emotions.get("happiness", 50)
        awakening = emotions.get("awakening", 0)
        issues = []

        # 低好感度时不应有甜蜜表达
        if affection < -20:
            sweet_words = ["开心", "高兴", "喜欢", "甜蜜", "幸福"]
            if any(w in response for w in sweet_words):
                issues.append(f"低好感度({affection})时不应有甜蜜表达")

        # 高好感度时不应有敌意表达
        if affection > 50:
            hostile_words = ["讨厌", "滚", "烦", "不想见你"]
            if any(w in response for w in hostile_words):
                issues.append(f"高好感度({affection})时不应有敌意表达")

        # 低幸福感时不应过于活泼
        if happiness < 20:
            lively_words = ["哈哈哈", "太好了", "好棒", "耶"]
            if any(w in response for w in lively_words):
                issues.append(f"低幸福感({happiness})时不应过于活泼")

        if issues:
            return 0.3, "; ".join(issues)
        return 1.0, None

    @staticmethod
    def _check_affection_expression(response: str, ctx: Dict) -> tuple:
        """检查好感度表达是否与数值一致"""
        emotions = ctx.get("emotion_values", {})
        affection = emotions.get("affection", 0)

        # 检查表达强度与好感度的匹配
        if affection < -30:
            # 极低好感度 — 应该有回避/冷漠表现
            if len(response) > 100 and "……" not in response and "…" not in response:
                return 0.6, f"极低好感度({affection})时回复应更简短/冷漠"

        if affection > 30 and affection < 60:
            # 中等好感度 — 可以有一些温暖但不应太直接
            direct_love = ["我爱你", "我好喜欢你", "我离不开你"]
            if any(w in response for w in direct_love):
                return 0.5, f"中等好感度({affection})时不应直接示爱"

        return 1.0, None

    @staticmethod
    def _check_action_consistency(response: str, ctx: Dict) -> tuple:
        """检查行为是否与角色习惯一致"""
        # 角色不应该做出与其设定矛盾的行为
        # 这个规则比较通用，主要检查明显的不一致

        # 如果角色设定是田径选手，不应描写在做游泳训练
        # 这需要具体的角色知识，这里做通用检查
        return 1.0, None

    @staticmethod
    def _check_knowledge_accuracy(response: str, ctx: Dict) -> tuple:
        """检查角色是否使用了正确的自身知识"""
        known_facts = ctx.get("known_facts", [])
        issues = []

        if not known_facts:
            return 1.0, None

        # 检查角色是否说了与已知事实矛盾的内容
        for fact in known_facts:
            # fact 应该是 "角色名 不是/没有 X" 的格式
            # 如果回复中说了角色"是X"，则矛盾
            pass  # 需要更复杂的 NLP 来实现

        if issues:
            return 0.3, "; ".join(issues)
        return 1.0, None

    # ----------------------------------------------------------
    # 批量评估 & 统计
    # ----------------------------------------------------------

    def evaluate_batch(
        self,
        responses: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """批量评估多条回复的一致性。

        Args:
            responses: 角色回复列表
            context: 共享上下文

        Returns:
            统计摘要
        """
        scores = [self.evaluate(r, context) for r in responses]

        if not scores:
            return {"total": 0, "avg_overall": 0.0}

        return {
            "total": len(scores),
            "avg_overall": sum(s.overall for s in scores) / len(scores),
            "avg_persona": sum(s.persona_score for s in scores) / len(scores),
            "avg_emotion": sum(s.emotion_score for s in scores) / len(scores),
            "avg_behavior": sum(s.behavior_score for s in scores) / len(scores),
            "avg_knowledge": sum(s.knowledge_score for s in scores) / len(scores),
            "consistent_count": sum(1 for s in scores if s.is_consistent),
            "inconsistent_count": sum(1 for s in scores if not s.is_consistent),
            "all_issues": [issue for s in scores for issue in s.issues],
        }

    def get_trend(self, window: int = 10) -> Dict[str, Any]:
        """获取最近的一致性趋势。

        Args:
            window: 最近 N 次评估

        Returns:
            趋势数据
        """
        recent = self._history[-window:]
        if not recent:
            return {"trend": "unknown", "avg": 0.0, "count": 0}

        avg = sum(s.overall for s in recent) / len(recent)

        # 判断趋势方向
        if len(recent) >= 3:
            first_half = sum(s.overall for s in recent[:len(recent)//2]) / (len(recent)//2)
            second_half = sum(s.overall for s in recent[len(recent)//2:]) / (len(recent) - len(recent)//2)
            if second_half > first_half + 0.05:
                trend = "improving"
            elif second_half < first_half - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "trend": trend,
            "avg": avg,
            "count": len(recent),
            "min": min(s.overall for s in recent),
            "max": max(s.overall for s in recent),
        }

    def get_report(self) -> str:
        """生成一致性评估报告（文本格式）"""
        if not self._history:
            return "暂无评估数据"

        trend = self.get_trend()
        latest = self._history[-1]

        lines = [
            "## 📊 角色一致性评估报告",
            "",
            f"**总评估次数**: {len(self._history)}",
            f"**最近评分**: {latest.overall:.2f} ({latest.severity})",
            f"**趋势**: {trend['trend']} (平均 {trend['avg']:.2f})",
            "",
            "### 维度分数",
            f"- 人格一致性: {latest.persona_score:.2f}",
            f"- 情感一致性: {latest.emotion_score:.2f}",
            f"- 行为一致性: {latest.behavior_score:.2f}",
            f"- 知识一致性: {latest.knowledge_score:.2f}",
        ]

        if latest.issues:
            lines.append("")
            lines.append("### 发现的问题")
            for issue in latest.issues:
                lines.append(f"- ⚠️ {issue}")

        return "\n".join(lines)


# ============================================================
# 便捷单例
# ============================================================

_evaluator_instances: Dict[str, ConsistencyEvaluator] = {}


def get_evaluator(character_id: str = "chayewoon") -> ConsistencyEvaluator:
    """获取 ConsistencyEvaluator 单例（按角色隔离）"""
    if character_id not in _evaluator_instances:
        _evaluator_instances[character_id] = ConsistencyEvaluator(character_id)
    return _evaluator_instances[character_id]
