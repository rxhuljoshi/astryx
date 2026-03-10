"""
tests/test_knowledge_retriever.py
==================================
Unit tests for the Astryx knowledge retrieval system.
Tests: knowledge base loading, structured lookups, chart-based retrieval, ChromaDB semantic search.
"""

import pytest

from astryx.knowledge_retriever import (
    load_knowledge_base,
    get_kb,
    retrieve_structured,
    retrieve_for_chart,
    init_chromadb,
    retrieve_semantic,
)


# ---------------------------------------------------------------------------
# Knowledge base loading
# ---------------------------------------------------------------------------

class TestKnowledgeBaseLoading:
    def test_load_returns_non_empty_dict(self):
        kb = load_knowledge_base()
        assert isinstance(kb, dict)
        assert len(kb) > 0

    def test_all_nine_planets_present(self):
        kb = get_kb()
        expected = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
        for planet in expected:
            assert planet in kb, f"Missing planet key: {planet}"

    def test_each_planet_has_expected_sections(self):
        kb = get_kb()
        for planet, data in kb.items():
            assert isinstance(data, dict), f"{planet} data should be a dict"
            # At minimum, data.json should have some of these keys
            expected_keys = {"general", "effects_by_sign", "effects_by_house"}
            present = set(data.keys()) & expected_keys
            assert len(present) >= 2, f"{planet} missing expected sections, found: {data.keys()}"


# ---------------------------------------------------------------------------
# Structured retrieval
# ---------------------------------------------------------------------------

class TestStructuredRetrieval:
    def test_planet_only(self):
        results = retrieve_structured(planet="Sun")
        assert len(results) > 0
        # Should at least include the general section
        sources = [r["source"] for r in results]
        assert any("general" in s for s in sources)

    def test_planet_and_sign(self):
        results = retrieve_structured(planet="Sun", sign="Aries")
        assert len(results) > 0
        # Should have sign-specific results
        sources = [r["source"] for r in results]
        assert any("Aries" in s for s in sources)

    def test_planet_sign_and_house(self):
        results = retrieve_structured(planet="Moon", sign="Cancer", house=4)
        assert len(results) > 0

    def test_nonexistent_planet_returns_empty(self):
        results = retrieve_structured(planet="Pluto")
        assert results == []

    def test_none_planet_returns_empty(self):
        results = retrieve_structured(planet=None)
        assert results == []

    def test_results_have_priority(self):
        results = retrieve_structured(planet="Jupiter", sign="Sagittarius", house=9)
        if len(results) > 1:
            # Higher priority = lower number = more specific
            priorities = [r["priority"] for r in results]
            assert priorities == sorted(priorities), "Results should be sorted by priority"


# ---------------------------------------------------------------------------
# Chart-based retrieval
# ---------------------------------------------------------------------------

class TestChartRetrieval:
    @pytest.fixture
    def mock_chart(self):
        return {
            "planets": {
                "Sun": {"sign": "Aries", "house": 6, "nakshatra": "Ashwini"},
                "Moon": {"sign": "Cancer", "house": 9, "nakshatra": "Pushya"},
                "Mars": {"sign": "Leo", "house": 10, "nakshatra": "Magha"},
                "Mercury": {"sign": "Pisces", "house": 5, "nakshatra": "Revati"},
                "Jupiter": {"sign": "Gemini", "house": 8, "nakshatra": "Ardra"},
                "Venus": {"sign": "Aquarius", "house": 4, "nakshatra": "Shatabhisha"},
                "Saturn": {"sign": "Capricorn", "house": 3, "nakshatra": "Shravana"},
                "Rahu": {"sign": "Virgo", "house": 11, "nakshatra": "Hasta"},
                "Ketu": {"sign": "Pisces", "house": 5, "nakshatra": "Uttara Bhadrapada"},
            }
        }

    def test_career_topic(self, mock_chart):
        results = retrieve_for_chart(mock_chart, topic="career")
        assert len(results) > 0

    def test_marriage_topic(self, mock_chart):
        results = retrieve_for_chart(mock_chart, topic="marriage")
        assert len(results) > 0

    def test_general_topic(self, mock_chart):
        results = retrieve_for_chart(mock_chart, topic="general")
        assert len(results) > 0


# ---------------------------------------------------------------------------
# ChromaDB semantic search
# ---------------------------------------------------------------------------

class TestSemanticRetrieval:
    @pytest.fixture(scope="class", autouse=True)
    def setup_chromadb(self, tmp_path_factory):
        """Initialize ChromaDB once for all tests in this class."""
        persist_dir = str(tmp_path_factory.mktemp("chroma_test"))
        load_knowledge_base()
        init_chromadb(persist_dir=persist_dir)

    def test_semantic_search_returns_results(self):
        results = retrieve_semantic("Which planet helps with career?", top_k=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_semantic_results_have_source_and_text(self):
        results = retrieve_semantic("marriage compatibility", top_k=2)
        for r in results:
            assert "source" in r
            assert "text" in r
            assert len(r["text"]) > 0

    def test_semantic_handles_unusual_query(self):
        results = retrieve_semantic("asdfghjkl random nonsense", top_k=2)
        # Should still return something (nearest neighbors)
        assert isinstance(results, list)
