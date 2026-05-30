"""
Tests for RelationshipMixin (database/relationship.py)

Covers:
- get_relationship
- update_hearts (clamping 0-10)
- update_relationship_status
- record_conversation
- reset_daily_flags
- update_emotion_values (3D emotion system)
- Emotion value clamping

Note: RelationshipMixin requires self.get_connection() which returns
a SQLite context manager. We mock this with in-memory SQLite.
"""

import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from database.relationship import RelationshipMixin


# ══════════════════════════════════════════════════════════════
# Test Helper — In-Memory DB with Mixin
# ══════════════════════════════════════════════════════════════

class FakeDB(RelationshipMixin):
    """Minimal DB class that provides get_connection() for testing."""

    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS relationships (
                user_id INTEGER,
                character_id TEXT DEFAULT 'chayewoon',
                hearts INTEGER DEFAULT 0,
                relationship_status TEXT DEFAULT 'stranger',
                total_conversations INTEGER DEFAULT 0,
                talked_today INTEGER DEFAULT 0,
                gifted_today INTEGER DEFAULT 0,
                affection INTEGER DEFAULT 0,
                happiness INTEGER DEFAULT 50,
                awakening INTEGER DEFAULT 0,
                updated_at TEXT,
                PRIMARY KEY (user_id, character_id)
            );
        """)

    @contextmanager
    def get_connection(self):
        yield self._conn

    def close(self):
        self._conn.close()


@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    d = FakeDB()
    yield d
    d.close()


@pytest.fixture
def db_with_user(db):
    """Database with one relationship row pre-inserted."""
    db._conn.execute(
        "INSERT INTO relationships (user_id, character_id, hearts, relationship_status, "
        "total_conversations, affection, happiness, awakening) "
        "VALUES (1, 'chayewoon', 3, 'acquaintance', 5, 10, 20, 0)"
    )
    db._conn.commit()
    return db


# ══════════════════════════════════════════════════════════════
# get_relationship
# ══════════════════════════════════════════════════════════════

class TestGetRelationship:
    """Verify get_relationship returns correct data."""

    def test_returns_none_for_missing(self, db):
        result = db.get_relationship(999)
        assert result is None

    def test_returns_existing_relationship(self, db_with_user):
        result = db_with_user.get_relationship(1)
        assert result is not None
        assert result["user_id"] == 1
        assert result["character_id"] == "chayewoon"
        assert result["hearts"] == 3

    def test_default_character_id(self, db_with_user):
        result = db_with_user.get_relationship(1, "chayewoon")
        assert result is not None

    def test_different_character_returns_none(self, db_with_user):
        result = db_with_user.get_relationship(1, "other_char")
        assert result is None

    def test_returns_dict(self, db_with_user):
        result = db_with_user.get_relationship(1)
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════
# update_hearts
# ══════════════════════════════════════════════════════════════

class TestUpdateHearts:
    """Verify update_hearts with clamping 0-10."""

    def test_positive_delta(self, db_with_user):
        new = db_with_user.update_hearts(1, "chayewoon", 2)
        assert new == 5  # 3 + 2

    def test_negative_delta(self, db_with_user):
        new = db_with_user.update_hearts(1, "chayewoon", -1)
        assert new == 2  # 3 - 1

    def test_clamp_at_10(self, db_with_user):
        new = db_with_user.update_hearts(1, "chayewoon", 100)
        assert new == 10

    def test_clamp_at_0(self, db_with_user):
        new = db_with_user.update_hearts(1, "chayewoon", -100)
        assert new == 0

    def test_no_relationship_returns_clamped(self, db):
        # No row for user 999 — current_hearts defaults to 0
        new = db.update_hearts(999, "chayewoon", 5)
        # UPDATE won't match any row, but function still returns clamped value
        assert new == 5  # max(0, min(10, 0 + 5))


# ══════════════════════════════════════════════════════════════
# update_relationship_status
# ══════════════════════════════════════════════════════════════

class TestUpdateRelationshipStatus:
    """Verify relationship status updates."""

    def test_updates_status(self, db_with_user):
        db_with_user.update_relationship_status(1, "chayewoon", "friend")
        result = db_with_user.get_relationship(1)
        assert result["relationship_status"] == "friend"

    def test_overwrites_status(self, db_with_user):
        db_with_user.update_relationship_status(1, "chayewoon", "close_friend")
        db_with_user.update_relationship_status(1, "chayewoon", "lover")
        result = db_with_user.get_relationship(1)
        assert result["relationship_status"] == "lover"


# ══════════════════════════════════════════════════════════════
# record_conversation
# ══════════════════════════════════════════════════════════════

class TestRecordConversation:
    """Verify conversation counting."""

    def test_increments_count(self, db_with_user):
        db_with_user.record_conversation(1, "chayewoon")
        result = db_with_user.get_relationship(1)
        assert result["total_conversations"] == 6  # 5 + 1

    def test_sets_talked_today(self, db_with_user):
        db_with_user.record_conversation(1, "chayewoon")
        result = db_with_user.get_relationship(1)
        assert result["talked_today"] == 1


# ══════════════════════════════════════════════════════════════
# reset_daily_flags
# ══════════════════════════════════════════════════════════════

class TestResetDailyFlags:
    """Verify daily flag reset."""

    def test_resets_talked_today(self, db_with_user):
        db_with_user.record_conversation(1, "chayewoon")
        db_with_user.reset_daily_flags()
        result = db_with_user.get_relationship(1)
        assert result["talked_today"] == 0

    def test_resets_gifted_today(self, db_with_user):
        db_with_user._conn.execute(
            "UPDATE relationships SET gifted_today = 1 WHERE user_id = 1"
        )
        db_with_user._conn.commit()
        db_with_user.reset_daily_flags()
        result = db_with_user.get_relationship(1)
        assert result["gifted_today"] == 0


# ══════════════════════════════════════════════════════════════
# update_emotion_values (3D Emotion System)
# ══════════════════════════════════════════════════════════════

class TestUpdateEmotionValues:
    """Verify 3D emotion value updates."""

    def test_positive_affection_delta(self, db_with_user):
        result = db_with_user.update_emotion_values(
            1, "chayewoon", affection_delta=5
        )
        assert result["affection"] == 15  # 10 + 5

    def test_negative_happiness_delta(self, db_with_user):
        result = db_with_user.update_emotion_values(
            1, "chayewoon", happiness_delta=-10
        )
        assert result["happiness"] == 10  # 20 - 10

    def test_awakening_delta(self, db_with_user):
        result = db_with_user.update_emotion_values(
            1, "chayewoon", awakening_delta=3
        )
        assert result["awakening"] == 3  # 0 + 3

    def test_multiple_deltas(self, db_with_user):
        result = db_with_user.update_emotion_values(
            1, "chayewoon",
            affection_delta=5, happiness_delta=-3, awakening_delta=1
        )
        assert result["affection"] == 15
        assert result["happiness"] == 17
        assert result["awakening"] == 1

    def test_zero_deltas_no_change(self, db_with_user):
        result = db_with_user.update_emotion_values(1, "chayewoon")
        assert result["affection"] == 10
        assert result["happiness"] == 20
        assert result["awakening"] == 0

    def test_returns_dict(self, db_with_user):
        result = db_with_user.update_emotion_values(1, "chayewoon")
        assert isinstance(result, dict)
        assert "affection" in result
        assert "happiness" in result
        assert "awakening" in result
