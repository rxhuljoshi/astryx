# Astryx

A Vedic Astrology API and command-line companion powered by FreeAstrologyAPI, Groq (Llama 3), and ChromaDB.

Astryx takes birth data (Date, Time, City), computes a full Jyotish D1 chart, and embeds an astrological knowledge graph (RAG) to allow you to talk to a highly knowledgeable AI astrologer in your terminal.

## Features

- **Birth Chart Computation:** Uses `freeastrologyapi.com` to accurately compute Ascendant, planetary positions, houses, and Nakshatras using the Lahiri ayanamsa.
- **Dasha Calculator:** Generates your active Vimshottari Mahadasha and Antardasha periods.
- **Dosha Detection:** Checks for foundational Vedic alignments like Mangal Dosha, Sade Sati, and Kaal Sarp.
- **RAG Architecture:** Astryx embeds thousands of Vedic astrology interpretations across houses, signs, and planets securely in a local vector database.
- **Interactive CLI:** An easy-to-use command-line interface to generate charts and text with Astryx without leaving your terminal.

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- [PostgreSQL](https://www.postgresql.org/) (Astryx stores active chart sessions and chat history in Postgres)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/rxhuljoshi/astryx.git
   cd astryx
   ```

2. **Setup virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Database Configuration**
   - Create a PostgreSQL database called `astryx`.
   - Start the PostgreSQL server process locally.

4. **Environment Variables**
   Rename `.env.example` to `.env` and fill in the real values:
   ```bash
   DATABASE_URL="postgresql://user:password@localhost:5432/astryx" # Adjust to match your DB
   GROQ_API_KEY="your_groq_api_key"                                # Get from console.groq.com
   ASTROLOGY_API_KEY="your_free_astrology_api_key"                 # Get from json.freeastrologyapi.com
   ```

## Usage

### 1. Run the API Server
Before using the CLI, ensure the FastAPI backend is running via Uvicorn:

```bash
# inside the astryx directory
source venv/bin/activate
uvicorn main:app --reload
```

The server will automatically generate the SQL tables and initialize the ChromaDB vector embeddings the very first time it starts up.

### 2. Enter the CLI
In a second terminal window, run the interactive companion app:

```bash
python cli.py
```

From the Main Menu, select **Option 1** to input your birth details. After Astryx calculates your alignment and saves your session, pick **Option 2** to ask your chart anything!

## Testing

Astryx ships with a full `pytest` suite ensuring reliable retrieval systems and accurate chart payloads. You can run tests inside your virtual environment using:

```bash
python -m pytest tests/ -v
```

## Structure

- `astryx/chart_engine.py`: External API chart computation and calculation logic.
- `astryx/knowledge_retriever.py`: Search and semantic ranking for the included Vedic json texts.
- `astryx/prompt_builder.py`: Combines context into LLM system prompts.
- `main.py`: FastAPI endpoints and PostgreSQL state management.
- `cli.py`: Interactive python CLI utilizing the `rich` UI library.
