"""
tests/test_prompt_builder.py
==============================
Unit tests for the Astryx prompt builder.
Tests: entity extractor prompt, system prompt assembly, chart summary, suggested questions.
"""

import pytest

from astryx.prompt_builder import (
    build_entity_extractor_prompt,
    build_chart_summary,
    build_system_prompt,
    get_suggested_questions,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chart():
    return {
        "name": "TestUser",
        "gender": "Male",
        "dob": "1990-03-21",
        "tob": "10:30",
        "ascendant": {"sign": "Taurus", "degree": 12.5},
        "planets": {
            "Sun": {"sign": "Pisces", "house": 11, "nakshatra": "Revati", "longitude": 350.5, "degrees_in_sign": 20.5},
            "Moon": {"sign": "Cancer", "house": 3, "nakshatra": "Pushya", "longitude": 100.0, "degrees_in_sign": 10.0},
            "Mars": {"sign": "Capricorn", "house": 9, "nakshatra": "Shravana", "longitude": 280.0, "degrees_in_sign": 10.0},
        },
        "dasha": {
            "mahadasha": {"planet": "Jupiter", "start": "2022-01-01", "end": "2038-01-01"},
            "antardasha": {"planet": "Saturn", "start": "2025-06-01", "end": "2027-12-01"},
        },
        "doshas": ["Mangal Dosha"],
    }


@pytest.fixture
def sample_chart_no_doshas(sample_chart):
    chart = dict(sample_chart)
    chart["doshas"] = []
    return chart


@pytest.fixture
def sample_chunks():
    return [
        {"source": "Sun in Pisces", "text": "Sun in Pisces gives intuitive nature.", "priority": 3},
        {"source": "Moon in Cancer", "text": "Moon in Cancer is exalted, emotional depth.", "priority": 2},
    ]


# ---------------------------------------------------------------------------
# Entity extractor prompt
# ---------------------------------------------------------------------------

class TestEntityExtractorPrompt:
    def test_contains_user_message(self):
        prompt = build_entity_extractor_prompt("How is my career?")
        assert "How is my career?" in prompt

    def test_asks_for_json_output(self):
        prompt = build_entity_extractor_prompt("Tell me about Saturn")
        assert "JSON" in prompt

    def test_includes_planet_options(self):
        prompt = build_entity_extractor_prompt("anything")
        assert "Sun" in prompt
        assert "Rahu" in prompt
        assert "Ketu" in prompt


# ---------------------------------------------------------------------------
# Chart summary
# ---------------------------------------------------------------------------

class TestChartSummary:
    def test_includes_name(self, sample_chart):
        summary = build_chart_summary(sample_chart)
        assert "TestUser" in summary

    def test_includes_ascendant(self, sample_chart):
        summary = build_chart_summary(sample_chart)
        assert "Taurus" in summary

    def test_includes_planets(self, sample_chart):
        summary = build_chart_summary(sample_chart)
        assert "Sun" in summary
        assert "Moon" in summary

    def test_includes_dasha(self, sample_chart):
        summary = build_chart_summary(sample_chart)
        assert "Jupiter" in summary

    def test_includes_doshas_when_present(self, sample_chart):
        summary = build_chart_summary(sample_chart)
        assert "Mangal Dosha" in summary

    def test_no_doshas_message(self, sample_chart_no_doshas):
        summary = build_chart_summary(sample_chart_no_doshas)
        assert "None detected" in summary


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_includes_persona(self, sample_chart, sample_chunks):
        prompt = build_system_prompt(sample_chart, sample_chunks)
        assert "Astryx" in prompt
        assert "Vedic" in prompt

    def test_includes_chart_summary(self, sample_chart, sample_chunks):
        prompt = build_system_prompt(sample_chart, sample_chunks)
        assert "TestUser" in prompt
        assert "Taurus" in prompt

    def test_includes_retrieved_context(self, sample_chart, sample_chunks):
        prompt = build_system_prompt(sample_chart, sample_chunks)
        assert "Sun in Pisces gives intuitive nature" in prompt

    def test_includes_dosha_info(self, sample_chart, sample_chunks):
        prompt = build_system_prompt(sample_chart, sample_chunks)
        assert "Mangal Dosha" in prompt

    def test_no_context_message(self, sample_chart):
        prompt = build_system_prompt(sample_chart, [])
        assert "No specific knowledge retrieved" in prompt


# ---------------------------------------------------------------------------
# Suggested questions
# ---------------------------------------------------------------------------

class TestSuggestedQuestions:
    def test_returns_list(self, sample_chart):
        questions = get_suggested_questions(sample_chart)
        assert isinstance(questions, list)

    def test_max_five_questions(self, sample_chart):
        questions = get_suggested_questions(sample_chart)
        assert len(questions) <= 5

    def test_dosha_question_when_dosha_present(self, sample_chart):
        questions = get_suggested_questions(sample_chart)
        assert any("Mangal Dosha" in q for q in questions)

    def test_career_question_always_present(self, sample_chart):
        questions = get_suggested_questions(sample_chart)
        assert any("career" in q.lower() for q in questions)

    def test_no_dosha_question_when_no_doshas(self, sample_chart_no_doshas):
        questions = get_suggested_questions(sample_chart_no_doshas)
        assert not any("Mangal Dosha" in q for q in questions)
