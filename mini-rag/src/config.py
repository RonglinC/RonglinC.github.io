"""
Load configuration from environment variables.

We keep secrets (like OPENAI_API_KEY) out of source code.
They live in a local .env file that is gitignored.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# mini-rag/ root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load variables from mini-rag/.env into the process environment
load_dotenv(PROJECT_ROOT / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Where we keep source PDFs / text files for ingestion
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"

# Where Chroma will persist embeddings on disk (Step 5)
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

# Chunking defaults (Step 3) — measured in characters for RecursiveCharacterTextSplitter
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Embedding model (Step 4)
EMBEDDING_MODEL = "text-embedding-3-small"


def require_openai_api_key() -> str:
    """Fail fast with a clear message if the key is missing."""
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your-key"):
        raise ValueError(
            "OPENAI_API_KEY is missing or still a placeholder. "
            "Copy .env.example to .env and set your real key."
        )
    return OPENAI_API_KEY
