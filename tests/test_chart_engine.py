"""
tests/test_chart_engine.py
===========================
Unit tests for the Astryx chart computation engine.
Tests: geocoding, chart computation, dosha detection, dasha calculation.
"""

import pytest
from datetime import datetime

from astryx.chart_engine import (
    compute_chart,
    compute_current_dasha,
    detect_doshas,
    get_coordinates,
    SIGNS,
    NAKSHATRAS,
)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

class TestGeocoding:
    def test_known_city(self):
        coords = get_coordinates("Mumbai, India")
        assert coords is not None
        lat, lon = coords
        # Mumbai is roughly at 19°N, 72°E
        assert 18.5 < lat < 20.0
        assert 72.0 < lon < 73.5

    def test_unknown_city_returns_none(self):
        result = get_coordinates("Zzzyyyxxx NonexistentPlace 12345")
        assert result is None


# ---------------------------------------------------------------------------
# Chart computation
# ---------------------------------------------------------------------------

class TestComputeChart:
    """Compute a chart for a known date and verify structure."""

    @pytest.fixture
    def sample_chart(self):
        return compute_chart(
            name="TestUser",
            gender="Male",
            dob="1990-03-21",
            tob="10:30",
            lat=19.076,  # Mumbai
            lon=72.877,
            tz_offset=5.5,
        )

    def test_chart_has_required_keys(self, sample_chart):
        for key in ["name", "gender", "dob", "tob", "ascendant", "planets", "dasha", "doshas"]:
            assert key in sample_chart, f"Missing key: {key}"

    def test_ascendant_has_sign_and_degree(self, sample_chart):
        asc = sample_chart["ascendant"]
        assert asc["sign"] in SIGNS
        assert 0 <= asc["degree"] < 30

    def test_all_nine_planets_plus_ketu(self, sample_chart):
        expected_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
        for planet in expected_planets:
            assert planet in sample_chart["planets"], f"Missing planet: {planet}"

    def test_planet_info_structure(self, sample_chart):
        for planet, info in sample_chart["planets"].items():
            assert info["sign"] in SIGNS, f"{planet}: invalid sign '{info['sign']}'"
            assert 1 <= info["house"] <= 12, f"{planet}: house {info['house']} out of range"
            assert info["nakshatra"] in NAKSHATRAS, f"{planet}: invalid nakshatra '{info['nakshatra']}'"
            assert 0 <= info["longitude"] < 360
            assert 0 <= info["degrees_in_sign"] < 30

    def test_ketu_is_180_from_rahu(self, sample_chart):
        rahu_lon = sample_chart["planets"]["Rahu"]["longitude"]
        ketu_lon = sample_chart["planets"]["Ketu"]["longitude"]
        diff = abs(rahu_lon - ketu_lon)
        assert abs(diff - 180) < 0.01 or abs(diff - (360 - 180)) < 0.01

    def test_dasha_structure(self, sample_chart):
        dasha = sample_chart["dasha"]
        assert "mahadasha" in dasha
        assert "antardasha" in dasha
        assert "planet" in dasha["mahadasha"]
        assert "start" in dasha["mahadasha"]
        assert "end" in dasha["mahadasha"]

    def test_doshas_is_list(self, sample_chart):
        assert isinstance(sample_chart["doshas"], list)


# ---------------------------------------------------------------------------
# Dosha detection
# ---------------------------------------------------------------------------

class TestDoshaDetection:
    def test_mangal_dosha_mars_in_7(self):
        planets = {
            "Mars": {"sign": "Aries", "house": 7, "nakshatra": "Ashwini", "longitude": 10.0},
            "Saturn": {"sign": "Capricorn", "house": 4, "nakshatra": "Shravana", "longitude": 280.0},
            "Moon": {"sign": "Cancer", "house": 10, "nakshatra": "Pushya", "longitude": 100.0},
            "Rahu": {"sign": "Gemini", "house": 9, "nakshatra": "Ardra", "longitude": 70.0},
            "Ketu": {"sign": "Sagittarius", "house": 3, "nakshatra": "Mula", "longitude": 250.0},
            "Sun": {"sign": "Leo", "house": 11, "nakshatra": "Magha", "longitude": 130.0},
            "Mercury": {"sign": "Virgo", "house": 12, "nakshatra": "Hasta", "longitude": 160.0},
            "Jupiter": {"sign": "Pisces", "house": 6, "nakshatra": "Revati", "longitude": 350.0},
            "Venus": {"sign": "Taurus", "house": 8, "nakshatra": "Rohini", "longitude": 40.0},
        }
        doshas = detect_doshas(planets, "Aries")
        assert "Mangal Dosha" in doshas

    def test_no_mangal_dosha_mars_in_3(self):
        planets = {
            "Mars": {"sign": "Aries", "house": 3, "nakshatra": "Ashwini", "longitude": 10.0},
            "Saturn": {"sign": "Capricorn", "house": 4, "nakshatra": "Shravana", "longitude": 280.0},
            "Moon": {"sign": "Leo", "house": 10, "nakshatra": "Magha", "longitude": 130.0},
        }
        doshas = detect_doshas(planets, "Aries")
        assert "Mangal Dosha" not in doshas

    def test_sade_sati_saturn_same_sign_as_moon(self):
        planets = {
            "Saturn": {"sign": "Cancer", "house": 10, "nakshatra": "Pushya", "longitude": 100.0},
            "Moon": {"sign": "Cancer", "house": 10, "nakshatra": "Ashlesha", "longitude": 108.0},
        }
        doshas = detect_doshas(planets, "Libra")
        assert "Shani Sade Sati" in doshas

    def test_no_sade_sati_when_saturn_far_from_moon(self):
        planets = {
            "Saturn": {"sign": "Capricorn", "house": 4, "nakshatra": "Shravana", "longitude": 280.0},
            "Moon": {"sign": "Leo", "house": 11, "nakshatra": "Magha", "longitude": 130.0},
        }
        doshas = detect_doshas(planets, "Libra")
        assert "Shani Sade Sati" not in doshas


# ---------------------------------------------------------------------------
# Dasha calculation
# ---------------------------------------------------------------------------

class TestDashaCalculation:
    def test_dasha_returns_correct_structure(self):
        moon_lon = 100.0  # Cancer area
        birth_dt = datetime(1990, 3, 21, 10, 30)
        result = compute_current_dasha(moon_lon, birth_dt)

        assert "mahadasha" in result
        assert "antardasha" in result
        assert "all_mahadasha_periods" in result
        assert result["mahadasha"]["planet"] in [d[0] for d in [
            ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10),
            ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)
        ]]

    def test_all_mahadasha_periods_cover_expected_total(self):
        """The total should be <= 120 years (first period is shortened by birth offset)."""
        moon_lon = 50.0
        birth_dt = datetime(2000, 1, 1, 0, 0)
        result = compute_current_dasha(moon_lon, birth_dt)
        periods = result["all_mahadasha_periods"]
        total_years = sum(p["duration_years"] for p in periods)
        # Full cycle is 120 years, but first period is shortened by the
        # fraction of the nakshatra already traversed at birth
        assert 100 <= total_years <= 120
