"""
Tests for MemoryRouter (characters/memory_router.py)

Covers:
- MemoryCategory enum
- MemoryResult dataclass
- _resolve_category()
- Router initialization (lazy loading)
- add_memory routing logic
- search_memories (short/long query)
- get_recent_memories
- get_context_for_prompt
- get_stats
- get_router singleton
- Error handling when stores unavailable
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from characters.memory_router import (
    MemoryCategory,
    MemoryResult,
    MemoryRouter,
    SHORT_QUERY_THRESHOLD,
    _CATEGORY_ROUTES,
    get_router,
)


# ══════════════════════════════════════════════════════════════
# MemoryCategory Enum
# ══════════════════════════════════════════════════════════════

class TestMemoryCategory:
    """Verify MemoryCategory enum values."""

    def test_has_dialogue(self):
        assert MemoryCategory.DIALOGUE == "dialogue"

    def test_has_preference(self):
        assert MemoryCategory.PREFERENCE == "preference"

    def test_has_event(self):
        assert MemoryCategory.EVENT == "event"

    def test_has_emotion(self):
        assert MemoryCategory.EMOTION == "emotion"

    def test_has_fact(self):
        assert MemoryCategory.FACT == "fact"

    def test_has_other(self):
        assert MemoryCategory.OTHER == "other"

    def test_is_string_enum(self):
        assert isinstance(MemoryCategory.DIALOGUE, str)

    def test_all_categories_have_routes(self):
        for cat in MemoryCategory:
            assert cat in _CATEGORY_ROUTES, f"{cat} missing from routes"
            assert "write" in _CATEGORY_ROUTES[cat]
            assert "query" in _CATEGORY_ROUTES[cat]


# ══════════════════════════════════════════════════════════════
# MemoryResult Dataclass
# ══════════════════════════════════════════════════════════════

class TestMemoryResult:
    """Verify MemoryResult dataclass."""

    def test_basic_creation(self):
        r = MemoryResult(content="hello", source="legacy")
        assert r.content == "hello"
        assert r.source == "legacy"
        assert r.score == 0.0
        assert r.metadata == {}

    def test_with_score(self):
        r = MemoryResult(content="test", source="db", score=0.95)
        assert r.score == 0.95

    def test_with_metadata(self):
        r = MemoryResult(content="x", source="lightrag", metadata={"k": "v"})
        assert r.metadata["k"] == "v"

    def test_repr_truncates(self):
        r = MemoryResult(content="a" * 100, source="legacy")
        rep = repr(r)
        assert "legacy" in rep
        assert len(rep) < 100

    def test_repr_handles_newlines(self):
        r = MemoryResult(content="line1\nline2", source="db")
        assert "\n" not in repr(r)


# ══════════════════════════════════════════════════════════════
# _resolve_category
# ══════════════════════════════════════════════════════════════

class TestResolveCategory:
    """Verify _resolve_category static method."""

    def test_valid_category(self):
        assert MemoryRouter._resolve_category("dialogue") == MemoryCategory.DIALOGUE

    def test_case_insensitive(self):
        assert MemoryRouter._resolve_category("PREFERENCE") == MemoryCategory.PREFERENCE

    def test_invalid_returns_other(self):
        assert MemoryRouter._resolve_category("nonsense") == MemoryCategory.OTHER

    def test_empty_string_returns_other(self):
        assert MemoryRouter._resolve_category("") == MemoryCategory.OTHER

    def test_none_returns_other(self):
        assert MemoryRouter._resolve_category(None) == MemoryCategory.OTHER

    def test_all_enum_values_resolve(self):
        for cat in MemoryCategory:
            assert MemoryRouter._resolve_category(cat.value) == cat


# ══════════════════════════════════════════════════════════════
# Router Initialization
# ══════════════════════════════════════════════════════════════

class TestRouterInit:
    """Verify router initialization and lazy loading."""

    def test_default_character_id(self):
        r = MemoryRouter()
        assert r.character_id == "chayewoon"

    def test_custom_character_id(self):
        r = MemoryRouter("custom_char")
        assert r.character_id == "custom_char"

    def test_stores_initially_none(self):
        r = MemoryRouter()
        assert r._legacy is None
        assert r._lightrag is None
        assert r._evolution is None
        assert r._db is None
        assert r._initialized is False

    def test_init_stores_idempotent(self):
        r = MemoryRouter()
        r._init_stores()
        assert r._initialized is True
        # Call again — should not raise
        r._init_stores()
        assert r._initialized is True


# ══════════════════════════════════════════════════════════════
# Category Routes Configuration
# ══════════════════════════════════════════════════════════════

class TestCategoryRoutes:
    """Verify route configuration for each category."""

    def test_dialogue_routes_to_lightrag_and_legacy(self):
        routes = _CATEGORY_ROUTES[MemoryCategory.DIALOGUE]
        assert "lightrag" in routes["write"]
        assert "legacy" in routes["write"]

    def test_preference_routes_to_evolution_and_database(self):
        routes = _CATEGORY_ROUTES[MemoryCategory.PREFERENCE]
        assert "evolution" in routes["write"]
        assert "database" in routes["write"]

    def test_fact_routes_only_to_lightrag(self):
        routes = _CATEGORY_ROUTES[MemoryCategory.FACT]
        assert routes["write"] == ["lightrag"]

    def test_other_routes_only_to_legacy(self):
        routes = _CATEGORY_ROUTES[MemoryCategory.OTHER]
        assert routes["write"] == ["legacy"]

    def test_short_query_threshold(self):
        assert SHORT_QUERY_THRESHOLD == 50


# ══════════════════════════════════════════════════════════════
# add_memory (mocked stores)
# ══════════════════════════════════════════════════════════════

class TestAddMemory:
    """Test add_memory with mocked stores."""

    @pytest.mark.asyncio
    async def test_add_to_legacy_when_other_category(self):
        r = MemoryRouter()
        r._legacy = {"save": MagicMock(), "save_entry": MagicMock()}
        r._initialized = True

        results = await r.add_memory("test content", category="other", user_id=1)
        assert results.get("legacy") is True
        r._legacy["save"].assert_called_once()
        r._legacy["save_entry"].assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_lightrag_when_fact(self):
        r = MemoryRouter()
        mock_lr = AsyncMock()
        mock_lr.add_memory = AsyncMock(return_value=True)
        r._lightrag = mock_lr
        r._initialized = True

        results = await r.add_memory("fact content", category="fact", user_id=1)
        assert results.get("lightrag") is True

    @pytest.mark.asyncio
    async def test_add_to_evolution_when_preference(self):
        r = MemoryRouter()
        r._evolution = MagicMock()
        r._evolution.char_dir = "/tmp/test"
        r._db = MagicMock()
        r._db.save_memory = MagicMock()
        r._initialized = True

        import os
        os.makedirs("/tmp/test", exist_ok=True)
        mem_path = os.path.join("/tmp/test", "memories.md")
        # Create empty file
        with open(mem_path, "w") as f:
            f.write("")

        try:
            results = await r.add_memory("user likes cats", category="preference", user_id=1)
            assert results.get("database") is True
            r._db.save_memory.assert_called_once()
        finally:
            if os.path.exists(mem_path):
                os.remove(mem_path)

    @pytest.mark.asyncio
    async def test_add_with_all_stores_unavailable(self):
        r = MemoryRouter()
        r._initialized = True
        # All stores are None

        results = await r.add_memory("orphan memory", category="dialogue", user_id=1)
        # Should return empty or all False — no crash
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_add_dialogue_routes_to_both(self):
        r = MemoryRouter()
        r._legacy = {"save": MagicMock(), "save_entry": MagicMock()}
        mock_lr = AsyncMock()
        mock_lr.add_memory = AsyncMock(return_value=True)
        r._lightrag = mock_lr
        r._initialized = True

        results = await r.add_memory("dialogue content", category="dialogue", user_id=1)
        assert results.get("legacy") is True
        assert results.get("lightrag") is True


# ══════════════════════════════════════════════════════════════
# search_memories
# ══════════════════════════════════════════════════════════════

class TestSearchMemories:
    """Test search_memories with mocked stores."""

    @pytest.mark.asyncio
    async def test_short_query_prefers_legacy(self):
        r = MemoryRouter()
        r._legacy = {
            "search": MagicMock(return_value=[
                {"key": "test", "value": "result", "access_count": 5, "category": "other"}
            ])
        }
        r._initialized = True

        results = await r.search_memories("short query", user_id=1, limit=5)
        # Should have legacy results
        assert any(m.source == "legacy" for m in results)

    @pytest.mark.asyncio
    async def test_long_query_prefers_lightrag(self):
        r = MemoryRouter()
        mock_lr = AsyncMock()
        mock_lr.search_memories = AsyncMock(return_value=[
            {"content": "semantic result", "distance": 0.1, "metadata": {}}
        ])
        r._lightrag = mock_lr
        r._initialized = True

        long_query = "x" * (SHORT_QUERY_THRESHOLD + 10)
        results = await r.search_memories(long_query, user_id=1, limit=5)
        assert any(m.source == "lightrag" for m in results)

    @pytest.mark.asyncio
    async def test_deduplication(self):
        r = MemoryRouter()
        r._legacy = {
            "search": MagicMock(return_value=[
                {"key": "dup", "value": "content", "access_count": 1, "category": "other"},
                {"key": "dup", "value": "content", "access_count": 2, "category": "other"},
            ])
        }
        r._initialized = True

        results = await r.search_memories("dup test", user_id=1, limit=10)
        # Should be deduplicated by content prefix
        contents = [m.content[:100] for m in results]
        assert len(contents) == len(set(contents))

    @pytest.mark.asyncio
    async def test_empty_results_when_no_stores(self):
        r = MemoryRouter()
        r._initialized = True

        results = await r.search_memories("anything", user_id=1)
        assert results == []

    @pytest.mark.asyncio
    async def test_results_sorted_by_score(self):
        r = MemoryRouter()
        r._legacy = {
            "search": MagicMock(return_value=[
                {"key": "low", "value": "low score", "access_count": 1, "category": "other"},
                {"key": "high", "value": "high score", "access_count": 10, "category": "other"},
            ])
        }
        r._initialized = True

        results = await r.search_memories("test", user_id=1, limit=10)
        scores = [m.score for m in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        r = MemoryRouter()
        r._legacy = {
            "search": MagicMock(return_value=[
                {"key": f"item{i}", "value": f"val{i}", "access_count": i, "category": "other"}
                for i in range(20)
            ])
        }
        r._initialized = True

        results = await r.search_memories("test", user_id=1, limit=3)
        assert len(results) <= 3


# ══════════════════════════════════════════════════════════════
# get_recent_memories
# ══════════════════════════════════════════════════════════════

class TestGetRecentMemories:
    """Test get_recent_memories with mocked stores."""

    @pytest.mark.asyncio
    async def test_from_legacy(self):
        r = MemoryRouter()
        r._legacy = {"get_long_term": MagicMock(return_value="line1\nline2\nline3")}
        r._initialized = True

        results = await r.get_recent_memories(user_id=1, limit=5)
        assert len(results) == 3
        assert all(m.source == "legacy" for m in results)

    @pytest.mark.asyncio
    async def test_from_database(self):
        r = MemoryRouter()
        r._db = MagicMock()
        r._db.get_memories = MagicMock(return_value=[
            {"memory_key": "k1", "memory_value": "v1", "category": "event"},
            {"memory_key": "k2", "memory_value": "v2", "category": "fact"},
        ])
        r._initialized = True

        results = await r.get_recent_memories(user_id=1, limit=5)
        assert any(m.source == "database" for m in results)

    @pytest.mark.asyncio
    async def test_empty_when_no_stores(self):
        r = MemoryRouter()
        r._initialized = True

        results = await r.get_recent_memories(user_id=1)
        assert results == []

    @pytest.mark.asyncio
    async def test_combined_from_multiple_stores(self):
        r = MemoryRouter()
        r._legacy = {"get_long_term": MagicMock(return_value="legacy line")}
        r._db = MagicMock()
        r._db.get_memories = MagicMock(return_value=[
            {"memory_key": "k", "memory_value": "db line", "category": "other"}
        ])
        r._initialized = True

        results = await r.get_recent_memories(user_id=1, limit=5)
        sources = {m.source for m in results}
        assert "legacy" in sources
        assert "database" in sources


# ══════════════════════════════════════════════════════════════
# get_stats
# ══════════════════════════════════════════════════════════════

class TestGetStats:
    """Test get_stats method."""

    def test_all_unavailable(self):
        r = MemoryRouter()
        r._initialized = True
        stats = r.get_stats()
        assert stats["legacy"] == "unavailable"
        assert stats["lightrag"] == "unavailable"
        assert stats["evolution"] == "unavailable"
        assert stats["database"] == "unavailable"

    def test_legacy_available(self):
        r = MemoryRouter()
        r._legacy = {"some": "data"}
        r._initialized = True
        stats = r.get_stats()
        assert stats["legacy"] == "available"

    def test_character_id_in_stats(self):
        r = MemoryRouter("test_char")
        r._initialized = True
        stats = r.get_stats()
        assert stats["character_id"] == "test_char"


# ══════════════════════════════════════════════════════════════
# get_router Singleton
# ══════════════════════════════════════════════════════════════

class TestGetRouter:
    """Test get_router singleton."""

    def test_returns_same_instance(self):
        from characters.memory_router import _router_instances
        _router_instances.clear()

        r1 = get_router("test_singleton")
        r2 = get_router("test_singleton")
        assert r1 is r2
        _router_instances.clear()

    def test_different_ids_different_instances(self):
        from characters.memory_router import _router_instances
        _router_instances.clear()

        r1 = get_router("char_a")
        r2 = get_router("char_b")
        assert r1 is not r2
        _router_instances.clear()

    def test_default_character_id(self):
        from characters.memory_router import _router_instances
        _router_instances.clear()

        r = get_router()
        assert r.character_id == "chayewoon"
        _router_instances.clear()


# ══════════════════════════════════════════════════════════════
# Error Handling
# ══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Verify fault tolerance when stores fail."""

    @pytest.mark.asyncio
    async def test_legacy_search_exception_returns_empty(self):
        r = MemoryRouter()
        r._legacy = {"search": MagicMock(side_effect=Exception("db error"))}
        r._initialized = True

        results = await r.search_memories("test", user_id=1)
        # Should not crash, just return empty
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_lightrag_add_failure_doesnt_crash(self):
        r = MemoryRouter()
        mock_lr = AsyncMock()
        mock_lr.add_memory = AsyncMock(side_effect=Exception("connection lost"))
        r._lightrag = mock_lr
        r._initialized = True

        # Should not raise
        results = await r.add_memory("test", category="fact", user_id=1)
        assert isinstance(results, dict)
        assert results.get("lightrag") is False

    @pytest.mark.asyncio
    async def test_database_unavailable_graceful(self):
        r = MemoryRouter()
        r._db = MagicMock()
        r._db.get_memories = MagicMock(side_effect=Exception("no table"))
        r._initialized = True

        results = await r.get_recent_memories(user_id=1)
        assert isinstance(results, list)
