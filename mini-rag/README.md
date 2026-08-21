# Mini RAG — Local Learning Project

A small Retrieval-Augmented Generation (RAG) app built step-by-step for interview prep.

**Stack:** Python · LangChain · OpenAI · Chroma · Streamlit

## Architecture

```
Documents → Loader → Splitter → Embeddings → Vector Store
                                              ↓
                         Answer ← LLM ← Prompt ← Retriever
```

## Step 1 — Environment setup (current)

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

## Project layout

```
mini-rag/
├── data/documents/   # Put PDFs / .txt files here (Step 2)
├── src/
│   └── config.py     # Env loading (Step 1)
├── app.py            # Streamlit UI (Step 11)
├── requirements.txt
├── .env.example
└── README.md
```

Later steps add `ingestion.py`, `retrieval.py`, and `rag.py`.
