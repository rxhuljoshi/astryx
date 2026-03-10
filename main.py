"""
main.py — Astryx FastAPI Application
=====================================
Endpoints:
  POST /api/chart   — Submit birth details, compute and store chart
  POST /api/chat    — Send a message, get chart-aware astrological response
  GET  /api/chart/{session_id} — Retrieve stored chart
  GET  /health      — Health check

Environment variables (see .env.example):
  DATABASE_URL  — PostgreSQL connection string
  GROQ_API_KEY  — Groq API key (free tier at console.groq.com)
"""

import json
import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import AsyncGroq
from pydantic import BaseModel

from astryx.chart_engine import compute_chart, get_coordinates
from astryx.knowledge_retriever import (
    init_chromadb,
    load_knowledge_base,
    retrieve_for_chart,
    retrieve_semantic,
    retrieve_structured,
)
from astryx.prompt_builder import (
    build_entity_extractor_prompt,
    build_system_prompt,
    get_suggested_questions,
)

load_dotenv()

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

db_pool: Optional[asyncpg.Pool] = None
groq_client: Optional[AsyncGroq] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, groq_client

    # Database
    db_pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=2, max_size=10)
    await _init_db(db_pool)

    # LLM
    groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    # Knowledge base
    load_knowledge_base()
    init_chromadb()

    print("Astryx is ready")
    yield

    await db_pool.close()


app = FastAPI(title="Astryx", description="Vedic Astrology Chatbot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# DB Setup
# ---------------------------------------------------------------------------

async def _init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS charts (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id  UUID UNIQUE NOT NULL,
                name        TEXT,
                gender      TEXT,
                dob         DATE,
                tob         TIME,
                city        TEXT,
                lat         FLOAT,
                lon         FLOAT,
                tz_offset   FLOAT DEFAULT 5.5,
                chart_json  JSONB,
                created_at  TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id  UUID NOT NULL,
                role        TEXT NOT NULL,  -- 'user' | 'assistant'
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, created_at);
        """)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ChartRequest(BaseModel):
    name: str
    gender: str               # "Male" | "Female" | "Other"
    dob: str                  # "YYYY-MM-DD"
    tob: str                  # "HH:MM"
    city: str                 # e.g. "Mumbai, India"
    tz_offset: float = 5.5    # IST default; pass explicitly for other zones


class ChartResponse(BaseModel):
    session_id: str
    chart: dict
    suggested_questions: list[str]
    message: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    suggested_questions: list[str]
    dosha_alerts: list[str]
    entities: dict            # what the LLM extracted from the question


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "app": "Astryx"}


@app.get("/api/coordinates")
async def get_city_coordinates(city: str):
    """Get latitude and longitude for a city."""
    coords = get_coordinates(city)
    if not coords:
        raise HTTPException(status_code=404, detail=f"Could not geocode city: '{city}'")
    return {"city": city, "latitude": coords[0], "longitude": coords[1]}


@app.post("/api/chart/compute")
async def compute_chart_stateless(req: ChartRequest):
    """
    Compute a chart statelessly without saving to the database.
    Useful for just fetching the chart data API style.
    """
    coords = get_coordinates(req.city)
    if not coords:
        raise HTTPException(status_code=422, detail=f"Could not geocode city: '{req.city}'")
    lat, lon = coords

    chart = compute_chart(
        name=req.name,
        gender=req.gender,
        dob=req.dob,
        tob=req.tob,
        lat=lat,
        lon=lon,
        tz_offset=req.tz_offset,
    )
    
    return {"chart": chart}


@app.post("/api/chart", response_model=ChartResponse)
async def create_chart(req: ChartRequest):
    """
    Submit birth details, compute chart, and store in DB.
    Returns session_id for subsequent /api/chat calls.
    """
    # Geocode
    coords = get_coordinates(req.city)
    if not coords:
        raise HTTPException(status_code=422, detail=f"Could not geocode city: '{req.city}'. Try a more specific name.")
    lat, lon = coords

    # Compute chart
    chart = compute_chart(
        name=req.name,
        gender=req.gender,
        dob=req.dob,
        tob=req.tob,
        lat=lat,
        lon=lon,
        tz_offset=req.tz_offset,
    )

    # Store in DB
    session_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO charts (session_id, name, gender, dob, tob, city, lat, lon, tz_offset, chart_json)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (session_id) DO UPDATE SET chart_json = $10
            """,
            uuid.UUID(session_id), req.name, req.gender,
            datetime.strptime(req.dob, "%Y-%m-%d").date(),
            datetime.strptime(req.tob, "%H:%M").time(),
            req.city, lat, lon, req.tz_offset,
            json.dumps(chart)
        )

    suggestions = get_suggested_questions(chart)
    return ChartResponse(
        session_id=session_id,
        chart=chart,
        suggested_questions=suggestions,
        message=f"Chart computed for {req.name}. You can now ask any Vedic astrology question!"
    )


@app.get("/api/chart/{session_id}")
async def get_chart(session_id: str):
    """Retrieve a previously computed chart by session_id."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT chart_json FROM charts WHERE session_id = $1",
            uuid.UUID(session_id)
        )
    if not row:
        raise HTTPException(status_code=404, detail="Chart not found. Please submit birth details first.")
    return json.loads(row["chart_json"])


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Process question against a session's chart data, extracting entities 
    for context generation before querying the LLM.
    """
    # Load chart
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT chart_json FROM charts WHERE session_id = $1",
            uuid.UUID(req.session_id)
        )
    if not row:
        raise HTTPException(status_code=404, detail="No chart found for this session. Please POST to /api/chart first.")

    chart = json.loads(row["chart_json"])

    # Load conversation history (last 6 turns for context)
    async with db_pool.acquire() as conn:
        history_rows = await conn.fetch(
            """
            SELECT role, content FROM conversations
            WHERE session_id = $1
            ORDER BY created_at DESC LIMIT 12
            """,
            uuid.UUID(req.session_id)
        )
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]

    # Entity extraction
    extractor_prompt = build_entity_extractor_prompt(req.message)
    entity_resp = await groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": extractor_prompt}],
        temperature=0.0,
        max_tokens=150,
    )
    entities = {}
    try:
        entities = json.loads(entity_resp.choices[0].message.content.strip())
    except json.JSONDecodeError:
        entities = {"topic": "general"}

    # Retrieval
    context_chunks = []
    planet = entities.get("planet")
    if planet:
        # The question explicitly mentions a planet — chart-aware structured lookup
        p_info = chart.get("planets", {}).get(planet, {})
        context_chunks = retrieve_structured(
            planet=planet,
            sign=entities.get("sign") or p_info.get("sign"),
            house=entities.get("house") or p_info.get("house"),
            nakshatra=p_info.get("nakshatra"),
        )
    else:
        # Topic-based: use chart positions for the relevant planets
        topic = entities.get("topic", "general")
        context_chunks = retrieve_for_chart(chart, topic=topic)

    # Semantic fallback if structured retrieval returned nothing
    if not context_chunks:
        context_chunks = retrieve_semantic(req.message, top_k=4)

    # Build prompt
    system_prompt = build_system_prompt(chart, context_chunks)

    # Generate answer
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": req.message})

    answer_resp = await groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.7,
        max_tokens=600,
    )
    answer = answer_resp.choices[0].message.content.strip()

    # Persist conversation
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES ($1, $2, $3)",
            uuid.UUID(req.session_id), "user", req.message
        )
        await conn.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES ($1, $2, $3)",
            uuid.UUID(req.session_id), "assistant", answer
        )

    return ChatResponse(
        answer=answer,
        suggested_questions=get_suggested_questions(chart),
        dosha_alerts=chart.get("doshas", []),
        entities=entities,
    )
