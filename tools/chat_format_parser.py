"""
多平台聊天记录解析器
====================

支持从以下平台导出的聊天记录中提取用户特征：
- QQ（QQ Messenger 导出）
- LINE（LINE 聊天导出）
- KakaoTalk（카카오톡 聊天导出）
- WeChat（微信导出 — 已有基础支持）
- iMessage（iMessage 导出）

每种格式有不同的时间戳、用户名、消息分隔规则。
本模块统一解析为标准格式，供 soul_manager 使用。

输出标准格式：
[
    {"timestamp": "2024-01-15 14:30", "sender": "user", "content": "消息内容"},
    {"timestamp": "2024-01-15 14:31", "sender": "other", "content": "回复内容"},
    ...
]
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 标准消息格式
# ============================================================

class ChatMessage:
    """标准化的聊天消息"""
    __slots__ = ('timestamp', 'sender', 'content', 'platform')

    def __init__(self, timestamp: str, sender: str, content: str, platform: str = ""):
        self.timestamp = timestamp
        self.sender = sender      # "user" 或 "other"
        self.content = content
        self.platform = platform

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "sender": self.sender,
            "content": self.content,
            "platform": self.platform,
        }


# ============================================================
# 格式解析器基类
# ============================================================

class ChatFormatParser:
    """聊天格式解析器基类"""

    platform_name: str = "unknown"

    def parse(self, filepath: str, user_name: str = "") -> List[ChatMessage]:
        """解析聊天记录文件

        Args:
            filepath: 文件路径
            user_name: 用户名（用于识别谁是"我方"）

        Returns:
            ChatMessage 列表
        """
        raise NotImplementedError

    def _assign_sender(self, detected_name: str, user_name: str) -> str:
        """根据检测到的名字判断 sender 类型"""
        if not user_name:
            return "other"
        return "user" if detected_name == user_name else "other"


# ============================================================
# QQ 格式解析
# ============================================================

class QQParser(ChatFormatParser):
    """QQ 聊天记录解析

    QQ 导出格式（典型）：
    2024-01-15 14:30:25 张三(123456)
    消息内容

    2024-01-15 14:31:02 李四(789012)
    回复内容
    """

    platform_name = "qq"
    # QQ 时间戳 + 用户名格式
    HEADER_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)\s+(.+?)(?:\((\d+)\))?\s*$'
    )

    def parse(self, filepath: str, user_name: str = "") -> List[ChatMessage]:
        messages = []
        current_sender = None
        current_time = None
        content_lines = []

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')

                # 检测消息头
                match = self.HEADER_PATTERN.match(line)
                if match:
                    # 保存前一条消息
                    if current_sender and content_lines:
                        messages.append(ChatMessage(
                            timestamp=current_time,
                            sender=self._assign_sender(current_sender, user_name),
                            content='\n'.join(content_lines).strip(),
                            platform=self.platform_name,
                        ))

                    current_time = match.group(1)
                    current_sender = match.group(2).strip()
                    content_lines = []
                elif line.strip():
                    content_lines.append(line)

        # 最后一条
        if current_sender and content_lines:
            messages.append(ChatMessage(
                timestamp=current_time,
                sender=self._assign_sender(current_sender, user_name),
                content='\n'.join(content_lines).strip(),
                platform=self.platform_name,
            ))

        return messages


# ============================================================
# LINE 格式解析
# ============================================================

class LINEParser(ChatFormatParser):
    """LINE 聊天记录解析

    LINE 导出格式（典型）：
    2024/01/15 14:30	张三	消息内容
    2024/01/15 14:31	李四	回复内容

    或日文格式：
    2024/01/15(月) 14:30	太郎	メッセージ
    """

    platform_name = "line"
    # LINE: 日期/时间 \t 用户名 \t 内容
    LINE_PATTERN = re.compile(
        r'^(\d{4}/\d{2}/\d{2}(?:\([月火水木金土日]\))?\s+\d{2}:\d{2})\t(.+?)\t(.+)$'
    )

    def parse(self, filepath: str, user_name: str = "") -> List[ChatMessage]:
        messages = []

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                match = self.LINE_PATTERN.match(line)
                if match:
                    time_str = match.group(1)
                    # 清理日文星期标记
                    time_str = re.sub(r'\([月火水木金土日]\)', '', time_str).strip()
                    sender_name = match.group(2).strip()
                    content = match.group(3).strip()

                    messages.append(ChatMessage(
                        timestamp=time_str,
                        sender=self._assign_sender(sender_name, user_name),
                        content=content,
                        platform=self.platform_name,
                    ))

        return messages


# ============================================================
# KakaoTalk 格式解析
# ============================================================

class KakaoTalkParser(ChatFormatParser):
    """카카오톡 (KakaoTalk) 聊天记录解析

    KakaoTalk 导出格式（典型）：
    2024년 1월 15일 월요일 오후 2시 30분, 김철수 : 메시지 내용
    2024년 1월 15일 월요일 오후 2시 31분, 이영희 : 응답 내용
    """

    platform_name = "kakaotalk"
    # 韩文日期 + 用户名 + 内容
    HEADER_PATTERN = re.compile(
        r'^(\d{4}년\s+\d{1,2}월\s+\d{1,2}일\s+.+?\s+(?:오전|오후)\s+\d{1,2}시\s+\d{1,2}분)'
        r',\s*(.+?)\s*:\s*(.+)$'
    )

    def parse(self, filepath: str, user_name: str = "") -> List[ChatMessage]:
        messages = []

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                match = self.HEADER_PATTERN.match(line)
                if match:
                    time_str = match.group(1)
                    sender_name = match.group(2).strip()
                    content = match.group(3).strip()

                    # 转换韩文时间为标准格式
                    std_time = self._parse_korean_time(time_str)

                    messages.append(ChatMessage(
                        timestamp=std_time,
                        sender=self._assign_sender(sender_name, user_name),
                        content=content,
                        platform=self.platform_name,
                    ))

        return messages

    @staticmethod
    def _parse_korean_time(korean_time: str) -> str:
        """将韩文时间格式转换为标准格式"""
        # 2024년 1월 15일 월요일 오후 2시 30분 → 2024-01-15 14:30
        try:
            # 提取数字
            nums = re.findall(r'\d+', korean_time)
            if len(nums) >= 5:
                year, month, day, hour, minute = int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3]), int(nums[4])
                # 오전/오후 处理
                if '오후' in korean_time and hour < 12:
                    hour += 12
                elif '오전' in korean_time and hour == 12:
                    hour = 0
                return f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
        except (ValueError, IndexError):
            pass
        return korean_time


# ============================================================
# WeChat 格式解析（增强版）
# ============================================================

class WeChatParser(ChatFormatParser):
    """微信聊天记录解析

    微信导出格式（典型）：
    2024-01-15 14:30:25
    张三
    消息内容

    或 WechatExporter 导出的 txt 格式：
    张三 2024/1/15 14:30
    消息内容
    """

    platform_name = "wechat"
    # 格式1: 时间戳 + 用户名
    PATTERN1 = re.compile(
        r'^(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}(?::\d{2})?)\s*$'
    )
    # 格式2: WechatExporter 格式
    PATTERN2 = re.compile(
        r'^(.+?)\s+(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})\s*$'
    )

    def parse(self, filepath: str, user_name: str = "") -> List[ChatMessage]:
        messages = []
        with open(filepath, 'r', encoding='utf-8') as _f:
            lines = [l.rstrip('\n') for l in _f]

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 尝试格式1: 时间戳行
            match1 = self.PATTERN1.match(line)
            if match1 and i + 2 < len(lines):
                time_str = match1.group(1)
                sender = lines[i + 1].strip()
                content_lines = []
                i += 2
                while i < len(lines) and not self.PATTERN1.match(lines[i].strip()):
                    if lines[i].strip():
                        content_lines.append(lines[i].strip())
                    i += 1
                if content_lines:
                    messages.append(ChatMessage(
                        timestamp=time_str,
                        sender=self._assign_sender(sender, user_name),
                        content='\n'.join(content_lines),
                        platform=self.platform_name,
                    ))
                continue

            # 尝试格式2: WechatExporter
            match2 = self.PATTERN2.match(line)
            if match2:
                sender = match2.group(1).strip()
                time_str = match2.group(2).strip()
                content_lines = []
                i += 1
                while i < len(lines) and not self.PATTERN2.match(lines[i].strip()):
                    if lines[i].strip():
                        content_lines.append(lines[i].strip())
                    i += 1
                if content_lines:
                    messages.append(ChatMessage(
                        timestamp=time_str,
                        sender=self._assign_sender(sender, user_name),
                        content='\n'.join(content_lines),
                        platform=self.platform_name,
                    ))
                continue

            i += 1

        return messages


# ============================================================
# 统一入口
# ============================================================

PARSERS = {
    "qq": QQParser,
    "line": LINEParser,
    "kakaotalk": KakaoTalkParser,
    "wechat": WeChatParser,
}


def parse_chat_export(
    filepath: str,
    platform: str,
    user_name: str = "",
) -> List[ChatMessage]:
    """统一解析入口。

    Args:
        filepath: 聊天记录文件路径
        platform: 平台名称 (qq / line / kakaotalk / wechat)
        user_name: 用户名（用于识别"我方"消息）

    Returns:
        ChatMessage 列表

    Raises:
        ValueError: 不支持的平台
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Chat export file not found: {filepath}")

    parser_cls = PARSERS.get(platform.lower())
    if not parser_cls:
        raise ValueError(f"Unsupported platform: {platform}. Supported: {list(PARSERS.keys())}")

    parser = parser_cls()
    messages = parser.parse(filepath, user_name)
    logger.info(f"[ChatParser] Parsed {len(messages)} messages from {platform}")
    return messages


def detect_platform(filepath: str) -> Optional[str]:
    """自动检测聊天记录平台。

    读取前 20 行，尝试每个解析器，返回匹配度最高的。

    Args:
        filepath: 文件路径

    Returns:
        平台名称或 None
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        sample = [f.readline() for _ in range(20)]

    best_platform = None
    best_count = 0

    for name, parser_cls in PARSERS.items():
        parser = parser_cls()
        count = 0
        for line in sample:
            line = line.strip()
            # Check class-level patterns
            for attr in ('HEADER_PATTERN', 'LINE_PATTERN', 'PATTERN1', 'PATTERN2'):
                pattern = getattr(parser_cls, attr, None) or getattr(parser, attr, None)
                if pattern and hasattr(pattern, 'match') and pattern.match(line):
                    count += 1
                    break

        if count > best_count:
            best_count = count
            best_platform = name

    return best_platform if best_count >= 1 else None
