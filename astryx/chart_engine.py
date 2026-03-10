"""
astryx/chart_engine.py

Compute Vedic birth charts via freeastrologyapi.com.
Calculates placements, dashas, and doshas.
"""

import os
import requests
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from typing import Optional



SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

# Vimshottari Dasha sequence and durations (years)
DASHA_SEQUENCE = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10),
    ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)
]

# Starting nakshatra lord for each nakshatra index (0-26)
NAKSHATRA_LORD = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu",
    "Jupiter", "Saturn", "Mercury", "Ketu", "Venus", "Sun",
    "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu",
    "Jupiter", "Saturn", "Mercury"
]



def get_coordinates(city: str) -> Optional[tuple[float, float]]:
    try:
        geolocator = Nominatim(user_agent="astryx_v1")
        location = geolocator.geocode(city, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None
    except GeocoderTimedOut:
        return None



def compute_current_dasha(moon_lon: float, birth_dt: datetime) -> dict:
    nak_index = int(moon_lon / (360 / 27)) % 27
    lord = NAKSHATRA_LORD[nak_index]

    # Fraction elapsed in the starting nakshatra
    nak_span = 360 / 27
    nak_start = nak_index * nak_span
    fraction_elapsed = (moon_lon - nak_start) / nak_span

    # Find dasha sequence starting from the birth nakshatra lord
    lord_index = next(i for i, (p, _) in enumerate(DASHA_SEQUENCE) if p == lord)
    ordered_dashas = DASHA_SEQUENCE[lord_index:] + DASHA_SEQUENCE[:lord_index]

    # First dasha: subtract elapsed fraction
    first_duration_years = ordered_dashas[0][1]
    elapsed_years = fraction_elapsed * first_duration_years
    remaining_first = first_duration_years - elapsed_years

    # Build timeline from birth_dt
    current_dt = birth_dt
    dasha_periods = []
    for i, (planet, duration) in enumerate(ordered_dashas):
        actual_duration = remaining_first if i == 0 else duration
        end_dt = current_dt + timedelta(days=actual_duration * 365.25)
        dasha_periods.append({
            "planet": planet,
            "start": current_dt.strftime("%Y-%m-%d"),
            "end": end_dt.strftime("%Y-%m-%d"),
            "duration_years": round(actual_duration, 2)
        })
        current_dt = end_dt

    # Find current period
    today = datetime.now()
    current_maha = next(
        (d for d in dasha_periods if datetime.strptime(d["start"], "%Y-%m-%d") <= today <= datetime.strptime(d["end"], "%Y-%m-%d")),
        dasha_periods[0]
    )

    # Compute Antardasha within current Mahadasha
    maha_planet = current_maha["planet"]
    maha_start = datetime.strptime(current_maha["start"], "%Y-%m-%d")
    maha_end = datetime.strptime(current_maha["end"], "%Y-%m-%d")
    total_maha_days = (maha_end - maha_start).days

    maha_lord_index = next(i for i, (p, _) in enumerate(DASHA_SEQUENCE) if p == maha_planet)
    antar_order = DASHA_SEQUENCE[maha_lord_index:] + DASHA_SEQUENCE[:maha_lord_index]

    antar_periods = []
    current_antar_dt = maha_start
    for planet, base_years in antar_order:
        antar_duration_days = (base_years / 120) * total_maha_days
        antar_end = current_antar_dt + timedelta(days=antar_duration_days)
        antar_periods.append({
            "planet": planet,
            "start": current_antar_dt.strftime("%Y-%m-%d"),
            "end": antar_end.strftime("%Y-%m-%d"),
        })
        current_antar_dt = antar_end

    current_antar = next(
        (a for a in antar_periods if datetime.strptime(a["start"], "%Y-%m-%d") <= today <= datetime.strptime(a["end"], "%Y-%m-%d")),
        antar_periods[0]
    )

    return {
        "mahadasha": {
            "planet": current_maha["planet"],
            "start": current_maha["start"],
            "end": current_maha["end"],
        },
        "antardasha": {
            "planet": current_antar["planet"],
            "start": current_antar["start"],
            "end": current_antar["end"],
        },
        "all_mahadasha_periods": dasha_periods
    }




def detect_doshas(planets: dict, ascendant_sign: str) -> list[str]:
    doshas = []

    # Mangal Dosha: Mars in houses 1, 4, 7, 8, or 12
    if "Mars" in planets:
        mars_house = planets["Mars"].get("house")
        if mars_house in [1, 4, 7, 8, 12]:
            doshas.append("Mangal Dosha")

    # Shani Sade Sati: Saturn within 1 sign of Moon
    if "Saturn" in planets and "Moon" in planets:
        try:
            sat_sign_idx = SIGNS.index(planets["Saturn"]["sign"])
            moon_sign_idx = SIGNS.index(planets["Moon"]["sign"])
            diff = abs(sat_sign_idx - moon_sign_idx) % 12
            if diff <= 1 or diff >= 11:
                doshas.append("Shani Sade Sati")
        except (ValueError, KeyError):
            pass

    # Kaal Sarp Dosha: all 7 main planets between Rahu and Ketu
    if "Rahu" in planets and "Ketu" in planets:
        rahu_lon = planets["Rahu"].get("longitude", 0.0)
        ketu_lon = planets["Ketu"].get("longitude", 0.0)
        planet_lons = [
            planets[p]["longitude"] for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
            if p in planets and "longitude" in planets[p]
        ]

        def between_rahu_ketu(lon, r, k):
            if r > k:
                return k <= lon <= r
            else:
                return lon >= r or lon <= k

        if planet_lons and all(between_rahu_ketu(lon, rahu_lon, ketu_lon) for lon in planet_lons):
            doshas.append("Kaal Sarp Dosha")

    return doshas




def compute_chart(
    name: str,
    gender: str,
    dob: str,        # "YYYY-MM-DD"
    tob: str,        # "HH:MM"
    lat: float,
    lon: float,
    tz_offset: float = 5.5  # IST default
) -> dict:
    api_key = os.getenv("ASTROLOGY_API_KEY")
    if not api_key:
        raise ValueError("ASTROLOGY_API_KEY environment variable is not set. Please set it in your .env file.")

    dob_parts = dob.split("-")
    tob_parts = tob.split(":")
    
    birth_local = datetime(
        int(dob_parts[0]), int(dob_parts[1]), int(dob_parts[2]),
        int(tob_parts[0]), int(tob_parts[1])
    )

    url = "https://json.freeastrologyapi.com/planets/extended"
    payload = {
        "year": birth_local.year,
        "month": birth_local.month,
        "date": birth_local.day,
        "hours": birth_local.hour,
        "minutes": birth_local.minute,
        "seconds": 0,
        "latitude": lat,
        "longitude": lon,
        "timezone": tz_offset,
        "settings": {
            "observation_point": "topocentric",
            "ayanamsha": "lahiri",
            "language": "en"
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key
    }

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    api_data = response.json()

    # The API returns a dictionary of planets inside 'output'
    output_data = api_data.get("output", api_data)

    chart_planets = {}
    asc_sign = "Aries" # fallback
    asc_degree = 0.0

    valid_planets = {"SUN", "MOON", "MARS", "MERCURY", "JUPITER", "VENUS", "SATURN", "RAHU", "KETU"}

    # Process each planet in the output dictionary or list
    iterable = output_data.values() if isinstance(output_data, dict) else output_data
    
    for p in iterable:
        if not isinstance(p, dict):
            continue

        name_upper = p.get("name", p.get("localized_name", "")).upper()
        
        # FreeAstrologyAPI uses these keys
        p_sign = p.get("zodiac_sign_name", p.get("sign", "Aries"))
        p_house = int(p.get("house_number", p.get("house", 1)))
        p_nakshatra = p.get("nakshatra_name", p.get("nakshatra", "Ashwini"))
        p_full = float(p.get("fullDegree", 0.0))
        p_norm = float(p.get("normDegree", 0.0))

        if name_upper in ["ASCENDANT", "LAGNA"]:
            asc_sign = p_sign
            asc_degree = p_norm
            continue
            
        if name_upper in valid_planets:
            target_name = name_upper.capitalize()
            chart_planets[target_name] = {
                "sign": p_sign,
                "house": p_house,
                "nakshatra": p_nakshatra,
                "longitude": round(p_full, 4),
                "degrees_in_sign": round(p_norm, 2),
            }

    # Fetch Moon's longitude for Vimshottari Dasha calculation
    moon_lon = chart_planets.get("Moon", {}).get("longitude", 0.0)
    dasha = compute_current_dasha(moon_lon, birth_local)

    doshas = detect_doshas(chart_planets, asc_sign)

    return {
        "name": name,
        "gender": gender,
        "dob": dob,
        "tob": tob,
        "ascendant": {
            "sign": asc_sign,
            "degree": round(asc_degree, 2)
        },
        "planets": chart_planets,
        "dasha": dasha,
        "doshas": doshas,
    }
