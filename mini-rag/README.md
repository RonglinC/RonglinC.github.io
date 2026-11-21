# Mini RAG — Local Learning Project

A small Retrieval-Augmented Generation (RAG) app built step-by-step for interview prep.

**Stack:** Python · LangChain · OpenAI · Chroma · Streamlit

## Architecture

```
Documents → Loader → Splitter → Embeddings → Vector Store
                                              ↓
                         Answer ← LLM ← Prompt ← Retriever
```

## Step 1 — Environment setup

### 1. Create a virtual environment

```bash
cd mini-rag
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your OpenAI API key

```bash
cp .env.example .env
# Edit .env and replace sk-your-key-here with your real key
```

### 4. Verify the setup

```bash
python -c "from src.config import require_openai_api_key; print('Key loaded:', require_openai_api_key()[:7] + '...')"
```

If you see `Key loaded: sk-proj...` (or similar), the environment works.

**Do not commit `.env`.** It is listed in `.gitignore`.

## Why API keys must not be hardcoded

- Keys in source code end up in git history forever.
- Anyone with repo access (or a leaked public repo) can burn your quota / steal access.
- `.env` + `python-dotenv` keeps secrets local; production later uses a secret manager.

## Step 2 — Document ingestion

Sample file: `data/documents/acme_overview_2024.txt`

```bash
cd mini-rag
source .venv/bin/activate
python -m src.ingestion --mode load
```

You should see:
- number of documents
- `metadata` (includes `source` path)
- a preview of `page_content`

## Step 3 — Chunking

```bash
python -m src.ingestion --mode chunk
python -m src.ingestion --mode chunk --chunk-size 200 --chunk-overlap 50 --max-chunks 8
```

Inspect total chunk count, each chunk's length, metadata, and overlap between consecutive chunks.

## Step 4 — Embeddings (current)

Requires a valid `OPENAI_API_KEY` in `.env`.

```bash
python -m src.embeddings
```

You should see vector dimensions, a few float values, and cosine similarity scores
(ARR question high, unrelated bread question low).

## Project layout

```
mini-rag/
├── data/documents/
├── src/
│   ├── config.py
│   ├── ingestion.py    # Load + split
│   └── embeddings.py   # Embedding model demo (Step 4)
├── requirements.txt
├── .env.example
└── README.md
```

Later steps add vector store, retrieval, `rag.py`, and Streamlit `app.py`.
