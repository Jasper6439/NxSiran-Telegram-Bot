"""
Context-Instruct 生成器
=======================

从小说原文自动提取角色对话，生成结构化的 Q&A 训练数据。
用于增强角色的对话能力和一致性。

工作流程：
1. 解析小说文本，识别对话段落
2. 提取用户(学长) → 角色(车如云) 的对话对
3. 生成上下文窗口（前后 N 句作为 context）
4. 输出 JSONL 格式的训练数据

输出格式：
{
    "context": "前文描述...",
    "question": "学长说的话",
    "answer": "车如云的回复",
    "emotion": "推断的情感状态",
    "scene": "场景描述"
}
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class DialogueTurn:
    """一轮对话"""
    speaker: str        # 说话者
    text: str           # 对话内容
    line_num: int       # 原文行号
    context_before: str = ""  # 前文描述
    context_after: str = ""   # 后文描述


@dataclass
class QAPair:
    """一个 Q&A 训练对"""
    context: str        # 上下文（场景 + 前文）
    question: str       # 用户输入（学长的话）
    answer: str         # 角色回复（车如云的话）
    emotion: str = ""   # 推断的情感
    scene: str = ""     # 场景标签
    chapter: int = 0    # 章节号


# ============================================================
# 小说解析器
# ============================================================

class NovelParser:
    """解析小说文本，提取对话段落"""

    # 对话匹配模式（中文引号）
    DIALOGUE_PATTERN = re.compile(r'^["""](.+?)["""]\s*$')
    # 说话者标注
    SPEAKER_PATTERN = re.compile(r'^(.{1,5}?)(?:说|道|问|答|喊|叫|嘟囔|低语|轻声|大声)')
    # 章节标记
    CHAPTER_PATTERN = re.compile(r'^第(\d+)章')

    def __init__(self, character_name: str = "车如云"):
        self.character_name = character_name
        self.user_names = {"学长", "泰明河", "我"}

    def parse_file(self, filepath: str) -> List[DialogueTurn]:
        """解析小说文件，提取所有对话"""
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [l.rstrip('\n') for l in f]

        turns = []
        current_chapter = 0
        buffer = []  # 上下文缓冲区

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # 检测章节
            ch_match = self.CHAPTER_PATTERN.match(line)
            if ch_match:
                current_chapter = int(ch_match.group(1))
                continue

            # 检测对话
            dial_match = self.DIALOGUE_PATTERN.match(line)
            if dial_match:
                dialogue_text = dial_match.group(1)
                # 推断说话者
                speaker = self._infer_speaker(lines, i, dialogue_text)

                turn = DialogueTurn(
                    speaker=speaker,
                    text=dialogue_text,
                    line_num=i + 1,
                    context_before='\n'.join(buffer[-3:]),
                )
                # 回填 context_after
                if turns and not turns[-1].context_after:
                    turns[-1].context_after = dialogue_text

                turns.append(turn)
                buffer = []
            else:
                buffer.append(line)

        return turns

    def _infer_speaker(self, lines: List[str], current_idx: int, dialogue: str) -> str:
        """推断对话说话者"""
        # 检查前一行或同行的说话者标注
        for offset in range(1, 4):  # skip current line to avoid self-mention misattribution
            check_idx = current_idx - offset
            if 0 <= check_idx < len(lines):
                check_line = lines[check_idx].strip()
                for name in self.user_names:
                    if name in check_line and check_line.index(name) < 10:
                        return "user"
                if self.character_name in check_line:
                    return self.character_name

        # 检查对话内容特征
        if any(marker in dialogue for marker in ["学长", "前辈"]):
            return self.character_name

        return "unknown"

    def generate_qa_pairs(
        self,
        filepath: str,
        window: int = 3,
    ) -> List[QAPair]:
        """从小说生成 Q&A 对。

        Args:
            filepath: 小说文件路径
            window: 上下文窗口大小（前后各 N 句）

        Returns:
            QAPair 列表
        """
        turns = self.parse_file(filepath)
        qa_pairs = []

        for i, turn in enumerate(turns):
            # 只要角色的回答（用户提问 → 角色回答）
            if turn.speaker != self.character_name:
                continue

            # 找前一句用户的话作为 question
            question_turn = None
            for j in range(i - 1, max(0, i - window * 2), -1):
                if turns[j].speaker == "user":
                    question_turn = turns[j]
                    break

            if not question_turn:
                continue

            # 构建上下文
            context_parts = []
            # 场景描述
            if turn.context_before:
                context_parts.append(f"[场景] {turn.context_before}")
            # 前几轮对话
            for k in range(max(0, i - window), i):
                if turns[k].speaker != "unknown":
                    context_parts.append(f"{turns[k].speaker}: {turns[k].text}")

            context = '\n'.join(context_parts)

            # 推断情感
            emotion = self._infer_emotion(turn.text)

            qa_pairs.append(QAPair(
                context=context,
                question=question_turn.text,
                answer=turn.text,
                emotion=emotion,
                scene=turn.context_before[:100] if turn.context_before else "",
            ))

        return qa_pairs

    @staticmethod
    def _infer_emotion(text: str) -> str:
        """从对话内容推断情感状态"""
        if any(w in text for w in ["……", "…", "随便", "不知道"]):
            return "冷淡/回避"
        if any(w in text for w in ["学长", "为什么", "怎么"]):
            return "困惑/依赖"
        if any(w in text for w in ["讨厌", "烦", "不想"]):
            return "抗拒"
        if any(w in text for w in ["嗯", "好", "知道了"]):
            return "顺从/接受"
        return "中性"

    def export_jsonl(self, qa_pairs: List[QAPair], output_path: str):
        """导出为 JSONL 格式"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for qa in qa_pairs:
                record = {
                    "context": qa.context,
                    "question": qa.question,
                    "answer": qa.answer,
                    "emotion": qa.emotion,
                    "scene": qa.scene,
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        logger.info(f"[ContextInstruct] Exported {len(qa_pairs)} Q&A pairs to {output_path}")

    def get_stats(self, qa_pairs: List[QAPair]) -> Dict:
        """统计生成的 Q&A 对"""
        emotions = {}
        for qa in qa_pairs:
            emotions[qa.emotion] = emotions.get(qa.emotion, 0) + 1

        return {
            "total_pairs": len(qa_pairs),
            "avg_question_len": sum(len(qa.question) for qa in qa_pairs) / max(len(qa_pairs), 1),
            "avg_answer_len": sum(len(qa.answer) for qa in qa_pairs) / max(len(qa_pairs), 1),
            "emotion_distribution": emotions,
        }


# ============================================================
# 便捷函数
# ============================================================

def generate_training_data(
    novel_path: str,
    character_name: str = "车如云",
    output_path: Optional[str] = None,
) -> List[QAPair]:
    """一键生成训练数据。

    Args:
        novel_path: 小说文件路径
        character_name: 角色名称
        output_path: 输出路径（None 则不写文件）

    Returns:
        QAPair 列表
    """
    parser = NovelParser(character_name)
    qa_pairs = parser.generate_qa_pairs(novel_path)

    if output_path:
        parser.export_jsonl(qa_pairs, output_path)

    stats = parser.get_stats(qa_pairs)
    logger.info(f"[ContextInstruct] Generated {stats['total_pairs']} pairs")
    logger.info(f"  Avg question: {stats['avg_question_len']:.0f} chars")
    logger.info(f"  Avg answer: {stats['avg_answer_len']:.0f} chars")
    logger.info(f"  Emotions: {stats['emotion_distribution']}")

    return qa_pairs
