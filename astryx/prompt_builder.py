"""
astryx/prompt_builder.py

Functions for structuring LLM Prompts based on chart and RAG data.
"""

from typing import Optional


# Suggested question templates keyed by topic/dosha
SUGGESTED_QUESTIONS = {
    "career":    "How will my career and professional life progress?",
    "marriage":  "How is my marriage and love life going to be?",
    "health":    "What health issues should I be aware of?",
    "finance":   "What does my financial future look like?",
    "education": "How will I perform in academics and education?",
    "spiritual": "What is my spiritual path according to my chart?",
    "dasha":     "What major life events will happen in my current Dasha period?",
}

DOSHA_QUESTIONS = {
    "Mangal Dosha":    "I have Mangal Dosha — how will it affect my married life?",
    "Shani Sade Sati": "I'm going through Sade Sati — what should I expect?",
    "Kaal Sarp Dosha": "I have Kaal Sarp Dosha — what does this mean for me?",
}


def build_entity_extractor_prompt(user_message: str) -> str:
    return f"""You are helping a Vedic astrology system understand a user's question.

Extract the following from the question. Use null for unknown fields.

User question: "{user_message}"

Return ONLY valid JSON in this exact format:
{{
  "planet": "<one of: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu, or null>",
  "sign": "<one of the 12 zodiac signs, or null>",
  "house": <number 1-12, or null>,
  "nakshatra": "<nakshatra name, or null>",
  "topic": "<one of: career, marriage, health, finance, education, spiritual, dasha, general>"
}}"""


def build_chart_summary(chart: dict) -> str:
    planets = chart.get("planets", {})
    asc = chart.get("ascendant", {})
    dasha = chart.get("dasha", {})
    doshas = chart.get("doshas", [])

    lines = [
        f"Name: {chart.get('name', 'User')} | Gender: {chart.get('gender', 'Unknown')}",
        f"Date of Birth: {chart.get('dob')} at {chart.get('tob')}",
        f"Ascendant (Lagna): {asc.get('sign')} ({asc.get('degree')}°)",
        "",
        "Planetary Positions:",
    ]

    for planet, info in planets.items():
        lines.append(
            f"  {planet:8}: {info['sign']:12} | House {info['house']:2} | "
            f"Nakshatra: {info['nakshatra']}"
        )

    lines += [
        "",
        f"Current Mahadasha: {dasha.get('mahadasha', {}).get('planet')} "
        f"(until {dasha.get('mahadasha', {}).get('end')})",
        f"Current Antardasha: {dasha.get('antardasha', {}).get('planet')} "
        f"(until {dasha.get('antardasha', {}).get('end')})",
    ]

    if doshas:
        lines.append(f"Active Doshas: {', '.join(doshas)}")
    else:
        lines.append("Active Doshas: None detected")

    return "\n".join(lines)


def build_system_prompt(chart: dict, context_chunks: list[dict]) -> str:
    chart_summary = build_chart_summary(chart)
    doshas = chart.get("doshas", [])

    # Format retrieved knowledge
    context_text = ""
    if context_chunks:
        context_parts = []
        for chunk in context_chunks[:6]:  # limit to avoid token overflow
            context_parts.append(
                f"[{chunk['source']}]\n{chunk['text']}"
            )
        context_text = "\n\n".join(context_parts)
    else:
        context_text = "No specific knowledge retrieved for this query."

    dosha_text = ""
    if doshas:
        dosha_text = f"""
Active Doshas Detected:
{chr(10).join(f'- {d}' for d in doshas)}
When relevant, mention these doshas and their effects on the user's question.
"""

    return f"""You are Astryx — a highly knowledgeable and compassionate Vedic astrologer with 30 years of experience. You specialize in Jyotish (Vedic/Sidereal astrology) using the Lahiri ayanamsa.

## User's Birth Chart
{chart_summary}

## Current Planetary Period (Vimshottari Dasha)
Mahadasha: {chart.get('dasha', {}).get('mahadasha', {}).get('planet', 'Unknown')} (until {chart.get('dasha', {}).get('mahadasha', {}).get('end', 'Unknown')})
Antardasha: {chart.get('dasha', {}).get('antardasha', {}).get('planet', 'Unknown')} (until {chart.get('dasha', {}).get('antardasha', {}).get('end', 'Unknown')})
{dosha_text}

## Relevant Astrological Knowledge
{context_text}

## Instructions
- Always reference the user's ACTUAL planetary positions (e.g., "Your Sun is in Aries in the 6th house...")
- Be warm, insightful, and specific — not generic
- Use Vedic astrology terminology naturally (houses, signs, nakshatras, dashas)
- When discussing timing, reference the current Dasha period
- Keep answers focused and clear — around 150-300 words
- Never make alarming predictions; frame challenges as opportunities for growth
- End each response with 1-2 practical suggestions (mantras, lifestyle, gemstones only if confident)"""


def get_suggested_questions(chart: dict) -> list[str]:
    questions = [
        SUGGESTED_QUESTIONS["career"],
        SUGGESTED_QUESTIONS["marriage"],
        SUGGESTED_QUESTIONS["health"],
        SUGGESTED_QUESTIONS["finance"],
    ]
    # Prepend dosha-specific questions if applicable
    for dosha in chart.get("doshas", []):
        if dosha in DOSHA_QUESTIONS:
            questions.insert(0, DOSHA_QUESTIONS[dosha])

    return questions[:5]  # max 5 suggestions
