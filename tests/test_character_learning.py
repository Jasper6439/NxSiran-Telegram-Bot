"""
Tests for CharacterLearning (characters/character_learning.py)

Covers:
- IMMUTABLE_FILES protection
- _write_file refuses immutable targets
- _read_file returns empty for missing files
- File I/O with tmp_path
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from characters.character_learning import CharacterLearning


# ══════════════════════════════════════════════════════════════
# IMMUTABLE_FILES
# ══════════════════════════════════════════════════════════════

class TestImmutableFiles:
    """Verify IMMUTABLE_FILES contains the expected entries."""

    def test_is_frozenset(self):
        assert isinstance(CharacterLearning.IMMUTABLE_FILES, frozenset)

    def test_contains_persona_md(self):
        assert "persona.md" in CharacterLearning.IMMUTABLE_FILES

    def test_contains_exemplars_md(self):
        assert "exemplars.md" in CharacterLearning.IMMUTABLE_FILES

    def test_contains_config_json(self):
        assert "config.json" in CharacterLearning.IMMUTABLE_FILES

    def test_does_not_contain_mutable(self):
        assert "persona_mutable.md" not in CharacterLearning.IMMUTABLE_FILES
        assert "memories.md" not in CharacterLearning.IMMUTABLE_FILES

    def test_cannot_modify(self):
        with pytest.raises(AttributeError):
            CharacterLearning.IMMUTABLE_FILES.add("new_file.md")


# ══════════════════════════════════════════════════════════════
# _write_file Protection
# ══════════════════════════════════════════════════════════════

class TestWriteFileProtection:
    """Verify _write_file refuses to write to immutable files."""

    def test_writes_to_mutable_file(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        test_file = "test_output.md"
        learner._write_file(test_file, "hello world")

        path = os.path.join(str(tmp_path), test_file)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            assert f.read() == "hello world"

    def test_refuses_persona_md(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        path = os.path.join(str(tmp_path), "persona.md")
        learner._write_file("persona.md", "SHOULD NOT WRITE")

        # File should not exist (write was refused)
        assert not os.path.exists(path)

    def test_refuses_exemplars_md(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        path = os.path.join(str(tmp_path), "exemplars.md")
        learner._write_file("exemplars.md", "SHOULD NOT WRITE")

        assert not os.path.exists(path)

    def test_refuses_config_json(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        path = os.path.join(str(tmp_path), "config.json")
        learner._write_file("config.json", '{"blocked": true}')

        assert not os.path.exists(path)

    def test_writes_memories_md(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        learner._write_file("memories.md", "- learned something")

        path = os.path.join(str(tmp_path), "memories.md")
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            assert "- learned something" in f.read()


# ══════════════════════════════════════════════════════════════
# _read_file
# ══════════════════════════════════════════════════════════════

class TestReadFile:
    """Verify _read_file behavior."""

    def test_reads_existing_file(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        path = os.path.join(str(tmp_path), "test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("test content")

        result = learner._read_file("test.md")
        assert result == "test content"

    def test_returns_empty_for_missing(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        result = learner._read_file("nonexistent.md")
        assert result == ""

    def test_reads_unicode(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        path = os.path.join(str(tmp_path), "unicode.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 角色设定\n\n车如云，18岁。")

        result = learner._read_file("unicode.md")
        assert "车如云" in result


# ══════════════════════════════════════════════════════════════
# Initialization
# ══════════════════════════════════════════════════════════════

class TestInit:
    """Verify CharacterLearning initialization."""

    def test_creates_char_dir(self, tmp_path):
        char_dir = os.path.join(str(tmp_path), "new_char")
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.character_id = "new_char"
        learner.char_dir = char_dir
        learner._ensure_dir()

        assert os.path.isdir(char_dir)

    def test_existing_dir_no_error(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.character_id = "existing"
        learner.char_dir = str(tmp_path)
        # Should not raise
        learner._ensure_dir()
        assert os.path.isdir(str(tmp_path))


# ══════════════════════════════════════════════════════════════
# File Operations Integration
# ══════════════════════════════════════════════════════════════

class TestFileOperations:
    """Integration test: read after write."""

    def test_write_then_read(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        learner._write_file("notes.md", "## Notes\n\nItem 1\nItem 2")
        content = learner._read_file("notes.md")
        assert "Item 1" in content
        assert "Item 2" in content

    def test_overwrite_mutable_file(self, tmp_path):
        learner = CharacterLearning.__new__(CharacterLearning)
        learner.char_dir = str(tmp_path)

        learner._write_file("notes.md", "version 1")
        learner._write_file("notes.md", "version 2")
        assert learner._read_file("notes.md") == "version 2"
