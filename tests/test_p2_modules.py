"""
Tests for P2 modules:
- tools/context_instruct.py
- tools/chat_format_parser.py
- tools/local_model_adapter.py
- tools/multilingual_builder.py
"""

import json
import os
import pytest
import tempfile
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# Context-Instruct Tests
# ══════════════════════════════════════════════════════════════

from tools.context_instruct import NovelParser, QAPair, DialogueTurn


class TestNovelParser:
    """Test novel text parsing and Q&A generation."""

    def test_infer_speaker_user(self):
        parser = NovelParser()
        lines = ["学长：你好啊", '"……随便。"']
        speaker = parser._infer_speaker(lines, 1, "……随便。")
        assert speaker == "车如云" or speaker == "user"

    def test_parse_dialogue_extracts_quotes(self):
        parser = NovelParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write('第01章\n"学长为什么对我这么好。"\n\n那张脸皱巴巴了。\n"……随便。"\n')
            f.flush()
            path = f.name

        try:
            turns = parser.parse_file(path)
            assert len(turns) >= 1
            assert any(t.text == "学长为什么对我这么好。" or t.text == "……随便。" for t in turns)
        finally:
            os.unlink(path)

    def test_infer_emotion_cold(self):
        assert "冷淡" in NovelParser._infer_emotion("……随便。")

    def test_infer_emotion_confused(self):
        assert "困惑" in NovelParser._infer_emotion("学长为什么这样？")

    def test_infer_emotion_resistant(self):
        assert "抗拒" in NovelParser._infer_emotion("讨厌，烦死了")

    def test_infer_emotion_neutral(self):
        assert NovelParser._infer_emotion("今天天气不错") == "中性"

    def test_export_jsonl(self):
        parser = NovelParser()
        pairs = [QAPair(context="场景", question="你好", answer="……嗯", emotion="冷淡")]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            path = f.name

        try:
            parser.export_jsonl(pairs, path)
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["answer"] == "……嗯"
        finally:
            os.unlink(path)

    def test_get_stats(self):
        parser = NovelParser()
        pairs = [
            QAPair(context="", question="a", answer="b", emotion="冷淡/回避"),
            QAPair(context="", question="c", answer="d", emotion="困惑/依存"),
        ]
        stats = parser.get_stats(pairs)
        assert stats["total_pairs"] == 2
        assert "冷淡/回避" in stats["emotion_distribution"]


# ══════════════════════════════════════════════════════════════
# Chat Format Parser Tests
# ══════════════════════════════════════════════════════════════

from tools.chat_format_parser import (
    QQParser, LINEParser, KakaoTalkParser, WeChatParser,
    parse_chat_export, detect_platform,
)


class TestQQParser:
    def test_parse_basic(self):
        parser = QQParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024-01-15 14:30:25 张三(123456)\n你好啊\n\n2024-01-15 14:31:02 李四(789012)\n回复消息\n")
            f.flush()
            path = f.name

        try:
            messages = parser.parse(path, user_name="张三")
            assert len(messages) == 2
            assert messages[0].sender == "user"
            assert messages[1].sender == "other"
            assert messages[0].content == "你好啊"
        finally:
            os.unlink(path)


class TestLINEParser:
    def test_parse_tab_separated(self):
        parser = LINEParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024/01/15 14:30\t太郎\tメッセージ\n2024/01/15 14:31\t花子\t返事\n")
            f.flush()
            path = f.name

        try:
            messages = parser.parse(path, user_name="太郎")
            assert len(messages) == 2
            assert messages[0].sender == "user"
            assert messages[1].sender == "other"
        finally:
            os.unlink(path)


class TestKakaoTalkParser:
    def test_parse_korean_format(self):
        parser = KakaoTalkParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024년 1월 15일 월요일 오후 2시 30분, 김철수 : 안녕하세요\n")
            f.write("2024년 1월 15일 월요일 오후 2시 31분, 이영희 : 네, 안녕하세요\n")
            f.flush()
            path = f.name

        try:
            messages = parser.parse(path, user_name="김철수")
            assert len(messages) == 2
            assert messages[0].sender == "user"
            assert messages[1].sender == "other"
        finally:
            os.unlink(path)

    def test_korean_time_parsing(self):
        assert KakaoTalkParser._parse_korean_time("2024년 1월 15일 월요일 오후 2시 30분") == "2024-01-15 14:30"
        assert KakaoTalkParser._parse_korean_time("2024년 12월 25일 수요일 오전 9시 00분") == "2024-12-25 09:00"


class TestPlatformDetection:
    def test_detect_qq(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024-01-15 14:30:25 张三(123456)\n你好\n")
            f.flush()
            path = f.name

        try:
            result = detect_platform(path)
            assert result == "qq"
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════
# Local Model Adapter Tests
# ══════════════════════════════════════════════════════════════

from tools.local_model_adapter import OllamaClient, VLLMClient, get_local_client


class TestLocalModelAdapter:
    def test_get_local_client_ollama(self):
        client = get_local_client("ollama")
        assert isinstance(client, OllamaClient)
        assert client.base_url == "http://localhost:11434"

    def test_get_local_client_vllm(self):
        client = get_local_client("vllm")
        assert isinstance(client, VLLMClient)
        assert client.base_url == "http://localhost:8000"

    def test_get_local_client_custom_url(self):
        client = get_local_client("ollama", base_url="http://192.168.1.100:11434")
        assert client.base_url == "http://192.168.1.100:11434"

    def test_get_local_client_invalid_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_local_client("invalid")

    def test_ollama_client_init(self):
        client = OllamaClient(base_url="http://localhost:11434", model="llama3")
        assert client.model == "llama3"

    def test_vllm_client_init(self):
        client = VLLMClient(base_url="http://localhost:8000", model="default")
        assert client.model == "default"


# ══════════════════════════════════════════════════════════════
# Multilingual Builder Tests
# ══════════════════════════════════════════════════════════════

from tools.multilingual_builder import (
    MultilingualBuilder, LANGUAGE_CONFIGS,
    build_multilingual_persona, get_supported_languages,
)


class TestMultilingualBuilder:
    def test_supported_languages(self):
        langs = get_supported_languages()
        codes = [l["code"] for l in langs]
        assert "ja" in codes
        assert "en" in codes
        assert "ko" in codes

    def test_japanese_persona_generation(self):
        builder = MultilingualBuilder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# 车如云 角色设定\n\nLayer 0: 基本信息\n")
            f.flush()
            source = f.name

        try:
            result = builder.build_persona(source, "ja")
            assert "先輩" in result or "日本語" in result
            assert "警戒心" in result or "冷たい" in result
        finally:
            os.unlink(source)

    def test_english_persona_generation(self):
        builder = MultilingualBuilder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# 车如云 角色设定\n")
            f.flush()
            source = f.name

        try:
            result = builder.build_persona(source, "en")
            assert "English" in result
            assert "senior" in result or "Guarded" in result or "guarded" in result
        finally:
            os.unlink(source)

    def test_korean_persona_generation(self):
        builder = MultilingualBuilder()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# 车如云 角色设定\n")
            f.flush()
            source = f.name

        try:
            result = builder.build_persona(source, "ko")
            assert "한국어" in result
            assert "선배" in result or "경계심" in result
        finally:
            os.unlink(source)

    def test_unsupported_language_raises(self):
        builder = MultilingualBuilder()
        with pytest.raises(ValueError, match="Unsupported"):
            builder.build_persona("fake.md", "xx")

    def test_config_override_ja(self):
        builder = MultilingualBuilder()
        override = builder.build_config_override("ja")
        assert override["language"] == "ja"
        assert override["user_nickname"] == "先輩"
        assert override["honorific_system"] is True

    def test_config_override_en(self):
        builder = MultilingualBuilder()
        override = builder.build_config_override("en")
        assert override["language"] == "en"
        assert override["honorific_system"] is False

    def test_ja_language_config(self):
        config = LANGUAGE_CONFIGS["ja"]
        assert config.honorific_system is True
        assert config.self_reference == "私"

    def test_ko_language_config(self):
        config = LANGUAGE_CONFIGS["ko"]
        assert config.honorific_system is True
        assert config.self_reference == "나"


# ══════════════════════════════════════════════════════════════
# P3: WeChat Parser Tests
# ══════════════════════════════════════════════════════════════

class TestWeChatParser:
    """Tests for WeChat chat export parsing (both formats)."""

    def test_parse_format1_three_line(self):
        """Format 1: timestamp line, name line, content line(s)."""
        parser = WeChatParser()
        content = (
            "2024-01-15 14:30:25\n"
            "张三\n"
            "你好啊\n"
            "\n"
            "2024-01-15 14:31:02\n"
            "李四\n"
            "回复消息\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            f.flush()
            path = f.name

        try:
            messages = parser.parse(path, user_name="张三")
            assert len(messages) == 2
            assert messages[0].sender == "user"
            assert messages[0].content == "你好啊"
            assert messages[0].timestamp == "2024-01-15 14:30:25"
            assert messages[1].sender == "other"
            assert messages[1].content == "回复消息"
            assert messages[1].platform == "wechat"
        finally:
            os.unlink(path)

    def test_parse_format2_wechat_exporter(self):
        """Format 2: WechatExporter format (name + date on one line)."""
        parser = WeChatParser()
        content = (
            "张三 2024/1/15 14:30\n"
            "你好啊\n"
            "李四 2024/1/15 14:31\n"
            "回复消息\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            f.flush()
            path = f.name

        try:
            messages = parser.parse(path, user_name="张三")
            assert len(messages) == 2
            assert messages[0].sender == "user"
            assert messages[0].content == "你好啊"
            assert messages[1].sender == "other"
            assert messages[1].content == "回复消息"
        finally:
            os.unlink(path)

    def test_parse_format1_multiline_content(self):
        """Format 1 with multi-line content between timestamps."""
        parser = WeChatParser()
        content = (
            "2024-01-15 14:30:00\n"
            "张三\n"
            "第一行\n"
            "第二行\n"
            "\n"
            "2024-01-15 14:31:00\n"
            "李四\n"
            "收到\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            f.flush()
            path = f.name

        try:
            messages = parser.parse(path)
            assert len(messages) == 2
            assert "第一行" in messages[0].content
            assert "第二行" in messages[0].content
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════
# P3: Platform Detection Tests
# ══════════════════════════════════════════════════════════════

class TestParseChatExport:
    """Tests for the unified parse_chat_export() entry point."""

    def test_parse_chat_export_qq(self):
        """parse_chat_export works through the unified entry point."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024-01-15 14:30:25 张三(123456)\n你好\n")
            f.flush()
            path = f.name

        try:
            messages = parse_chat_export(path, "qq", user_name="张三")
            assert len(messages) == 1
            assert messages[0].sender == "user"
        finally:
            os.unlink(path)

    def test_parse_chat_export_file_not_found(self):
        """parse_chat_export raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            parse_chat_export("/nonexistent/path.txt", "qq")

    def test_parse_chat_export_unsupported_platform(self):
        """parse_chat_export raises ValueError for unknown platform."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("test\n")
            f.flush()
            path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported platform"):
                parse_chat_export(path, "telegram")
        finally:
            os.unlink(path)


class TestPlatformDetectionExtended:
    """Tests for auto-detecting LINE, KakaoTalk, and WeChat formats."""

    def test_detect_line(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024/01/15 14:30\t太郎\tメッセージ\n2024/01/15 14:31\t花子\t返事\n")
            f.flush()
            path = f.name

        try:
            result = detect_platform(path)
            assert result == "line"
        finally:
            os.unlink(path)

    def test_detect_kakaotalk(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024년 1월 15일 월요일 오후 2시 30분, 김철수 : 안녕하세요\n")
            f.write("2024년 1월 15일 월요일 오후 2시 31분, 이영희 : 네\n")
            f.flush()
            path = f.name

        try:
            result = detect_platform(path)
            assert result == "kakaotalk"
        finally:
            os.unlink(path)

    def test_detect_wechat_format1(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("2024-01-15 14:30:25\n张三\n你好\n")
            f.flush()
            path = f.name

        try:
            result = detect_platform(path)
            assert result == "wechat"
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════
# P3: Async Mock Tests for Local Model Adapter
# ══════════════════════════════════════════════════════════════

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class _FakeResponse:
    """Minimal fake httpx response for mocking."""
    def __init__(self, json_data=None, lines=None, status_code=200):
        self._json = json_data or {}
        self._lines = lines or []
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestOllamaClientAsync:
    """P3: Async tests for OllamaClient with mocked httpx."""

    def test_chat_calls_api(self):
        """OllamaClient.chat() sends correct payload and returns content."""
        client = OllamaClient(base_url="http://test:11434", model="llama3")
        fake_resp = _FakeResponse(json_data={"message": {"content": "안녕하세요, 선배."}})

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=fake_resp)
        mock_client.is_closed = False
        client._client = mock_client

        result = _run(client.chat([{"role": "user", "content": "你好"}]))
        assert result == "안녕하세요, 선배."
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/api/chat" in call_args[0][0]
        assert call_args[1]["json"]["model"] == "llama3"

    def test_chat_stream_yields_chunks(self):
        """OllamaClient.chat_stream() yields content from streaming response."""
        client = OllamaClient(base_url="http://test:11434", model="llama3")

        stream_lines = [
            json.dumps({"message": {"content": "안녕"}}),
            json.dumps({"message": {"content": "하세요"}}),
            json.dumps({"message": {"content": ""}}),  # empty → skip
        ]
        fake_resp = _FakeResponse(lines=stream_lines)

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=fake_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.is_closed = False
        client._client = mock_client

        async def collect():
            chunks = []
            async for chunk in client.chat_stream([{"role": "user", "content": "你好"}]):
                chunks.append(chunk)
            return chunks

        chunks = _run(collect())
        assert chunks == ["안녕", "하세요"]
        mock_client.stream.assert_called_once()
        # Verify stream call arguments
        call_args = mock_client.stream.call_args
        assert call_args[0][0] == "POST"
        assert "/api/chat" in call_args[0][1]
        assert call_args[1]["json"]["stream"] is True
        assert call_args[1]["json"]["model"] == "llama3"


class TestVLLMClientAsync:
    """P3: Async tests for VLLMClient with mocked httpx."""

    def test_chat_calls_openai_api(self):
        """VLLMClient.chat() sends OpenAI-compatible payload."""
        client = VLLMClient(base_url="http://test:8000", model="default")
        fake_resp = _FakeResponse(json_data={
            "choices": [{"message": {"content": "Hello, senior."}}]
        })

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=fake_resp)
        mock_client.is_closed = False
        client._client = mock_client

        result = _run(client.chat([{"role": "user", "content": "hi"}]))
        assert result == "Hello, senior."
        call_args = mock_client.post.call_args
        assert "/v1/chat/completions" in call_args[0][0]
        assert call_args[1]["json"]["stream"] is False

    def test_chat_stream_yields_deltas(self):
        """VLLMClient.chat_stream() parses SSE data lines."""
        client = VLLMClient(base_url="http://test:8000")

        stream_lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]',
        ]
        fake_resp = _FakeResponse(lines=stream_lines)

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=fake_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.is_closed = False
        client._client = mock_client

        async def collect():
            chunks = []
            async for chunk in client.chat_stream([{"role": "user", "content": "hi"}]):
                chunks.append(chunk)
            return chunks

        chunks = _run(collect())
        assert chunks == ["Hello", " world"]
        # Verify stream call arguments
        call_args = mock_client.stream.call_args
        assert call_args[0][0] == "POST"
        assert "/v1/chat/completions" in call_args[0][1]
        assert call_args[1]["json"]["stream"] is True
        assert call_args[1]["json"]["model"] == "default"
