"""
astryx/knowledge_retriever.py
==============================
Hybrid retrieval system:
  1. Structured O(1) lookup from data.json (planet + sign + house + nakshatra)
  2. Semantic ChromaDB fallback for open-ended / topic-only questions

Dependencies: chromadb, sentence-transformers
"""

import json
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

_knowledge_base: dict = {}
_chroma_client = None
_chroma_collection = None

DATA_JSON_PATH = Path(__file__).parent.parent / "data.json"
EMBED_MODEL = "all-MiniLM-L6-v2"  # free, local, fast (~80MB)

PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SIGNS   = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
           "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

def load_knowledge_base() -> dict:
    global _knowledge_base
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        _knowledge_base = json.load(f)
    return _knowledge_base


def get_kb() -> dict:
    if not _knowledge_base:
        load_knowledge_base()
    return _knowledge_base




def retrieve_structured(
    planet: Optional[str] = None,
    sign: Optional[str] = None,
    house: Optional[int] = None,
    nakshatra: Optional[str] = None,
) -> list[dict]:
    kb = get_kb()
    results = []

    if not planet or planet not in kb:
        return results

    p_data = kb[planet]

    # sign + house combination
    if sign and house:
        house_str = str(house)
        val = (
            p_data.get("effects_by_sign_and_house", {})
                  .get(sign, {})
                  .get(house_str)
        )
        if val:
            results.append({
                "source": f"{planet} in {sign} in house {house}",
                "text": val,
                "priority": 1
            })

    # Deep traits
    if sign:
        trait = p_data.get("deep_traits", {}).get(sign)
        if trait:
            combined = (
                f"General: {trait.get('general', '')}\n"
                f"Positive: {trait.get('positive', '')}\n"
                f"Negative: {trait.get('negative', '')}"
            )
            results.append({
                "source": f"{planet} in {sign} (deep traits)",
                "text": combined,
                "priority": 2
            })

    # Effects by sign
    if sign:
        val = p_data.get("effects_by_sign", {}).get(sign)
        if val:
            results.append({"source": f"{planet} in {sign}", "text": val, "priority": 3})

    # Effects by house
    if house:
        val = p_data.get("effects_by_house", {}).get(str(house))
        if val:
            results.append({"source": f"{planet} in house {house}", "text": val, "priority": 4})

    # Nakshatra
    if nakshatra:
        val = p_data.get("nakshatra_effects", {}).get(nakshatra)
        if val:
            results.append({"source": f"{planet} in {nakshatra}", "text": val, "priority": 5})

    # Fallback
    val = p_data.get("general")
    if val:
        results.append({"source": f"{planet} general", "text": val, "priority": 6})

    return results


def retrieve_for_chart(chart: dict, topic: str = "general") -> list[dict]:
    TOPIC_PLANETS = {
        "career":    ["Saturn", "Sun", "Jupiter", "Mars"],
        "marriage":  ["Venus", "Moon", "Jupiter", "Mars"],
        "health":    ["Sun", "Moon", "Mars", "Saturn"],
        "finance":   ["Jupiter", "Venus", "Mercury", "Saturn"],
        "education": ["Mercury", "Jupiter", "Sun"],
        "spiritual": ["Ketu", "Jupiter", "Moon", "Saturn"],
        "general":   ["Sun", "Moon", "Ascendant"],
    }
    relevant_planets = TOPIC_PLANETS.get(topic, ["Sun", "Moon"])
    results = []

    planets = chart.get("planets", {})
    for planet in relevant_planets:
        if planet not in planets:
            continue
        p_info = planets[planet]
        chunks = retrieve_structured(
            planet=planet,
            sign=p_info.get("sign"),
            house=p_info.get("house"),
            nakshatra=p_info.get("nakshatra"),
        )
        results.extend(chunks[:2])  # top 2 per planet to avoid context overflow

    return results




def _build_chunks() -> list[dict]:
    kb = get_kb()
    chunks = []

    for planet, p_data in kb.items():
        # General
        if "general" in p_data:
            chunks.append({
                "id": f"{planet}_general",
                "text": p_data["general"],
                "meta": {"planet": planet, "type": "general"}
            })

        # By sign
        for sign, text in p_data.get("effects_by_sign", {}).items():
            chunks.append({
                "id": f"{planet}_sign_{sign}",
                "text": text,
                "meta": {"planet": planet, "sign": sign, "type": "effects_by_sign"}
            })

        # By house
        for house, text in p_data.get("effects_by_house", {}).items():
            chunks.append({
                "id": f"{planet}_house_{house}",
                "text": text,
                "meta": {"planet": planet, "house": house, "type": "effects_by_house"}
            })

        # Sign + House (most granular)
        for sign, houses in p_data.get("effects_by_sign_and_house", {}).items():
            for house, text in houses.items():
                chunks.append({
                    "id": f"{planet}_{sign}_house{house}",
                    "text": text,
                    "meta": {"planet": planet, "sign": sign, "house": house,
                             "type": "effects_by_sign_and_house"}
                })

        # Nakshatra
        for nak, text in p_data.get("nakshatra_effects", {}).items():
            chunks.append({
                "id": f"{planet}_nak_{nak}",
                "text": text,
                "meta": {"planet": planet, "nakshatra": nak, "type": "nakshatra"}
            })

        # Deep traits
        for sign, traits in p_data.get("deep_traits", {}).items():
            combined = (
                f"General: {traits.get('general', '')} "
                f"Positive: {traits.get('positive', '')} "
                f"Negative: {traits.get('negative', '')}"
            )
            chunks.append({
                "id": f"{planet}_deep_{sign}",
                "text": combined,
                "meta": {"planet": planet, "sign": sign, "type": "deep_traits"}
            })

    return chunks


def init_chromadb(persist_dir: str = "./astryx_chroma_db") -> None:
    global _chroma_client, _chroma_collection

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    _chroma_client = chromadb.PersistentClient(path=persist_dir)

    existing = [c.name for c in _chroma_client.list_collections()]
    if "astryx_knowledge" in existing:
        _chroma_collection = _chroma_client.get_collection(
            name="astryx_knowledge", embedding_function=ef
        )
        print(f"[ChromaDB] Loaded existing collection ({_chroma_collection.count()} chunks)")
        return

    # Create collection
    _chroma_collection = _chroma_client.create_collection(
        name="astryx_knowledge", embedding_function=ef
    )
    chunks = _build_chunks()
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        _chroma_collection.add(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[c["meta"] for c in batch],
        )
    print(f"[ChromaDB] Embedded {len(chunks)} chunks into new collection")


def retrieve_semantic(query: str, top_k: int = 3) -> list[dict]:
    if _chroma_collection is None:
        return []

    results = _chroma_collection.query(query_texts=[query], n_results=top_k)
    output = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        source_parts = [meta.get("planet", ""), meta.get("sign", ""),
                        meta.get("house", ""), meta.get("nakshatra", "")]
        source = " ".join(str(p) for p in source_parts if p)
        output.append({"source": source, "text": doc, "priority": 7})
    return output
