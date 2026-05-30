"""
Shared pytest fixtures for the LoveSupremacy Universe test suite.

Provides:
- Mock character implementation (ConcreteCharacter)
- Temporary data directories with sample files
- Mock database
- Helper factories for CharacterConfig
"""

import os
import json
import pathlib
import pytest
import sys

# ── Ensure project root is on sys.path ──
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prevent system.config from touching real data dirs
os.environ.setdefault("DATA_DIR", str(PROJECT_ROOT / "data"))

from characters.base import CharacterBase, CharacterConfig  # noqa: E402


# ══════════════════════════════════════════════════════════════
# Autouse cleanup — clear singleton dicts between tests
# ══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _clear_singletons():
    """Clear module-level singleton dicts after each test."""
    yield
    from characters.memory_router import _router_instances
    from api.narrative_arc import _arc_instances
    from api.consistency_evaluator import _evaluator_instances
    _router_instances.clear()
    _arc_instances.clear()
    _evaluator_instances.clear()


# ══════════════════════════════════════════════════════════════
# Mock Character — minimal concrete subclass of CharacterBase
# ══════════════════════════════════════════════════════════════

class ConcreteCharacter(CharacterBase):
    """Minimal concrete character for testing — satisfies abstract methods."""

    def format_response(self, text: str) -> str:
        return text.strip() if text else "……"

    def get_random_selfie_caption(self) -> str:
        return "（低头）"


# ══════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def sample_config_data() -> dict:
    """Raw config.json dict matching the chayewoon schema."""
    return {
        "name": "车如云",
        "source": "恋爱至上主义区域 (Love Supremacy Zone)",
        "personality": "外冷内热，极度防备",
        "background": "18岁，田径短跑选手",
        "speaking_style": "说话极简短",
        "catchphrases": ["...学长。", "（低头）", "...随便。"],
        "user_nickname": "学长",
        "world_layer": "stage",
        "emotion_defaults": {
            "affection": -50,
            "happiness": 5,
            "awakening": 0,
        },
        "awakening_conditions": {
            "min_affection": 30,
            "min_happiness": 20,
            "required_events": [],
        },
        "is_novel_character": True,
        "world_role": "trapped_character",
        "timezone": "Asia/Seoul",
        "theme_color": "#660874",
    }


@pytest.fixture
def tmp_data_dir(tmp_path, sample_config_data) -> pathlib.Path:
    """Create a temporary character data directory with sample files.

    Directory structure mirrors ``characters/chayewoon/``:
        tmp_data_dir/
        ├── config.json
        ├── persona.md
        ├── exemplars.md
        ├── world.md
        ├── persona_mutable.md
        └── memories.md
    """
    d = tmp_path / "chayewoon"
    d.mkdir()

    # config.json
    (d / "config.json").write_text(
        json.dumps(sample_config_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # persona.md  (immutable)
    (d / "persona.md").write_text(
        "# 车如云 角色设定\n\n这是不可变的角色设定文件。\n",
        encoding="utf-8",
    )

    # exemplars.md  (immutable)
    (d / "exemplars.md").write_text(
        "学长：今天怎么样？\n车如云：……随便。\n",
        encoding="utf-8",
    )

    # world.md
    (d / "world.md").write_text(
        "# 世界观\n\n角色被困在未完成的游戏世界中。\n",
        encoding="utf-8",
    )

    # persona_mutable.md  (mutable — evolution system can write)
    (d / "persona_mutable.md").write_text(
        "# 可变状态\n\n## Correction 记录\n\n（暂无记录）\n\n"
        "## 学习到的用户偏好\n\n（暂无记录）\n\n"
        "## 行为总原则\n\n1. Correction 层优先级最高\n",
        encoding="utf-8",
    )

    # memories.md
    (d / "memories.md").write_text("", encoding="utf-8")

    return d


@pytest.fixture
def tmp_data_dir_no_files(tmp_path) -> pathlib.Path:
    """Empty data directory (no character files) — tests graceful fallback."""
    d = tmp_path / "empty_character"
    d.mkdir()
    return d


@pytest.fixture
def character_config(tmp_data_dir) -> CharacterConfig:
    """CharacterConfig pointing at the temp data directory."""
    cfg_path = tmp_data_dir / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CharacterConfig.from_dict(data, id="chayewoon", data_dir=str(tmp_data_dir))


@pytest.fixture
def empty_config(tmp_data_dir_no_files) -> CharacterConfig:
    """CharacterConfig with no data files."""
    return CharacterConfig(
        id="test_empty",
        name="空角色",
        source="测试",
        data_dir=str(tmp_data_dir_no_files),
    )


@pytest.fixture
def character(character_config) -> ConcreteCharacter:
    """Fully-loaded ConcreteCharacter instance."""
    return ConcreteCharacter(character_config)


@pytest.fixture
def empty_character(empty_config) -> ConcreteCharacter:
    """ConcreteCharacter with no data files (all fallbacks)."""
    return ConcreteCharacter(empty_config)
