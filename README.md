# AI-Powered Chatbot for Surfaces Tiles UK 🏛️

A production-ready, RAG-based AI customer-support and product-recommendation chatbot for **[Surfaces Tiles UK](https://surfacestiles.co.uk)**. Built with **Google Gemini API**, **`gemini-embedding-001`**, **ChromaDB**, and a headless **FastAPI REST API**, managed completely via a dedicated **Conda** environment.

---

## 🏗️ Architecture

```
                       SURFACES TILES UK
                    https://surfacestiles.co.uk
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   Shopify Products JSON                HTML Pages, FAQs, Blogs,
  (85+ Tiles, Prices, Specs)             Policies (Sitemaps)
            │                                     │
            └──────────────────┬──────────────────┘
                               ▼
                      Python Web Scraper
                    (scraper/scraper.py)
                               │
                               ▼
                        Clean Raw Data
                   (data/raw/*.json datasets)
                               │
                               ▼
                      Text & RAG Chunking
                    (rag/chunker.py)
                               │
                               ▼
                   Gemini Embeddings Model
                    (gemini-embedding-001)
                               │
                               ▼
                   ChromaDB Vector Database
                 (data/embeddings/chroma)
                               ▲
                               │ Vector Similarity Search (Top-K)
                               ▼
   User Question ──► FastAPI REST API ──► Context Retrieval
   (POST /chat)       (api/routes.py)            │
                            ▲                    ▼
                            │             Gemini Prompt & LLM
                            │            (gemini-3.5-flash-lite)
                            │                    │
                            └────────────────────┘
                               Grounded Response + Links
```

---

## 📂 Project Structure

```
surfaces-tiles-chatbot/
│
├── scraper/
│   ├── __init__.py
│   ├── cleaners.py          # HTML stripping, spec table parsing, dimension & finish extractors
│   ├── crawler.py           # Sitemap discovery, Shopify JSON crawler, and HTML page scraper
│   └── scraper.py           # High-level scraping orchestrator saving datasets to data/raw/
│
├── data/
│   ├── raw/                 # Raw scraped products.json, pages.json, blogs.json, collections.json
│   ├── processed/           # Processed chunks.json enriched with RAG metadata
│   └── embeddings/
│       └── chroma/          # Persistent ChromaDB vector database files
│
├── rag/
│   ├── __init__.py
│   ├── chunker.py           # Domain-specific chunking for products, policies, and FAQs
│   ├── embeddings.py        # Gemini API embedding client (gemini-embedding-001) with retry & batching
│   ├── vector_store.py      # ChromaDB client supporting cosine similarity & metadata filtering
│   ├── retriever.py         # Query embedder, vector searcher, and context builder
│   ├── prompt.py            # Customer support system prompt, guardrails & instructions
│   └── chatbot.py           # End-to-end RAG generation engine
│
├── api/
│   ├── __init__.py
│   ├── schemas.py           # Pydantic models for requests, responses, and citations
│   ├── routes.py            # Endpoints: /chat, /health
│   └── app.py               # FastAPI app lifecycle, CORS, and endpoint definitions
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Pydantic Settings reading configuration from .env
│
├── scripts/
│   ├── scrape.py            # CLI script to execute full website scrape
│   └── ingest.py            # CLI script to process chunks, embed, and index in ChromaDB
│
├── main.py                  # Single application entrypoint (run with python main.py)
├── .env                     # Environment variables (API keys, models, ports)
├── .env.example             # Example environment configuration template
├── .gitignore
├── requirements.txt         # Pip dependency specifications
├── environment.yml          # Conda environment specifications
└── README.md
```

---

## ⚡ Quick Start Guide

### 1. Prerequisites
- **Conda** (Miniconda or Anaconda installed).

### 2. Create & Activate Conda Environment

```bash
# Create dedicated environment with Python 3.11
conda create -y -n surfaces-chatbot python=3.11

# Activate the environment
conda activate surfaces-chatbot
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Alternatively, you can recreate using conda:
```bash
conda env create -f environment.yml
conda activate surfaces-chatbot
```

### 4. Configure Environment Variables

Edit `.env` (or copy `.env.example` to `.env`):

```bash
cp .env.example .env
```

Set your Google Gemini API key:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
PORT=8060
HOST=0.0.0.0
```

> **Note**: If `GEMINI_API_KEY` is not provided, the system gracefully falls back to deterministic mock embedding and grounded offline responses so all tests, ingestion, and endpoints can still be verified without failure.

---

## 🚀 Running the Pipeline

### Step 1: Scrape Website Data

Scrape the entire product catalog (85+ products, variants, prices, dimensions, specs) along with delivery, returns, FAQs, and blogs:

```bash
python scripts/scrape.py
```

Raw JSON files will be generated in `data/raw/`:
- `data/raw/products.json`
- `data/raw/pages.json`
- `data/raw/blogs.json`
- `data/raw/collections.json`

### Step 2: Ingest & Embed into Vector Database

Chunk the raw datasets and generate `gemini-embedding-001` vectors into ChromaDB:

```bash
python scripts/ingest.py
```

Processed chunks are saved to `data/processed/chunks.json`, and vectors are indexed in `data/embeddings/chroma/`.

### Step 3: Start FastAPI REST Server

```bash
# Directly with Python:
python main.py

# Or with uvicorn:
uvicorn main:app --host 0.0.0.0 --port 8060 --reload
```

Interactive Swagger API docs will be accessible at:
👉 **`http://localhost:8060/docs`**

---

## 📡 API Reference & Examples

### 1. `POST /chat`
Ask questions about tiles, pricing, delivery, samples, and policies with automatic conversation memory via `session_id`. **The `session_id` is always a UUID**: if omitted from the request, a new UUIDv4 is automatically generated and returned in the response payload. If provided, it must be a valid UUID.

**Request Body:**
```bash
curl -X POST "http://localhost:8060/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "What sizes are available in those?",
       "session_id": "123e4567-e89b-12d3-a456-426614174000"
     }'
```


**Response:**
```json
{
  "meta": {
    "status": 1,
    "message": "Successfully processed user measurements and preferences"
  },
  "data": {
    "Response": "Based on our Surfaces Tiles UK collection, we recommend the following options for your bathroom floor:\n\n- **[Snow Sheen 30x60 CM Polished Porcelain](https://surfacestiles.co.uk/products/starlit-white-30x60-cm-polished)**: £19.99 (Size: 30x60 CM, Finish: Polished Porcelain). Featuring an elegant marble look that is durable and moisture resistant.\n\nWe offer **100% free tile samples** on all our products so you can evaluate the colour and finish in your home before ordering. Fast UK warehouse delivery is available.",
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "history": [
      {
        "role": "user",
        "content": "I need grey floor tiles for my bathroom."
      },
      {
        "role": "assistant",
        "content": "Based on our Surfaces Tiles UK collection..."
      }
    ]
  },
  "statusCode": 200
}
```

---


### 2. `GET /health`
Verify system status and knowledge base size.

```bash
curl -X GET "http://localhost:8060/health"
```

**Response:**
```json
{
  "status": "healthy",
  "document_count": 136,
  "gemini_configured": true,
  "embedding_model": "gemini-embedding-001",
  "llm_model": "gemini-3.5-flash-lite",
  "version": "1.0.0"
}
```


