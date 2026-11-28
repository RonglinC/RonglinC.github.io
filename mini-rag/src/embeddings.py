"""
Step 4 — Embeddings.

Convert text into dense numeric vectors so we can compare meaning
(semantic similarity), not just exact keyword overlap.

The vector store (Step 5) will store these vectors; here we only generate them.
"""

from __future__ import annotations

import math

from langchain_openai import OpenAIEmbeddings

from src.config import EMBEDDING_MODEL, require_openai_api_key

# text-embedding-3-small is a good default for learning:
# cheap, fast, strong quality for RAG demos.
DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODEL


def get_embedding_model(model: str = DEFAULT_EMBEDDING_MODEL) -> OpenAIEmbeddings:
    """
    Create the LangChain wrapper around OpenAI's embedding API.

    require_openai_api_key() fails early if .env is missing/placeholder.
    """
    api_key = require_openai_api_key()
    return OpenAIEmbeddings(model=model, api_key=api_key)


def embed_text(text: str, embeddings: OpenAIEmbeddings | None = None) -> list[float]:
    """
    Turn one string into one embedding vector (list of floats).

    Uses embed_query() — intended for search queries / single sentences.
    For many chunks at once, prefer embeddings.embed_documents([...]).
    """
    model = embeddings or get_embedding_model()
    return model.embed_query(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Conceptual similarity score between two vectors.

    1.0  → identical direction (very similar meaning, for normalized embeddings)
    ~0.0 → unrelated
    -1.0 → opposite direction (rare for text embeddings in practice)

    We use this only for intuition in Step 4 — the vector store does this at scale.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cannot compute cosine similarity with a zero vector.")
    return dot / (norm_a * norm_b)


if __name__ == "__main__":
    sample = "What was the company's annual recurring revenue?"
    embeddings = get_embedding_model()

    vector = embed_text(sample, embeddings)

    print("=" * 60)
    print("SINGLE EMBEDDING INSPECTION")
    print("=" * 60)
    print(f"text: {sample!r}")
    print(f"model: {DEFAULT_EMBEDDING_MODEL}")
    print(f"vector length (dimensions): {len(vector)}")
    print(f"first 8 values: {[round(v, 6) for v in vector[:8]]}")
    print("(These numbers alone are not human-readable — similarity is what matters.)")

    # Semantic similarity demo — no vector DB yet
    sentences = [
        "What was Acme's ARR in 2024?",  # similar meaning to sample
        "Where is the company headquartered?",  # related domain, different question
        "How do I bake sourdough bread?",  # unrelated
    ]

    print("\n" + "=" * 60)
    print("COSINE SIMILARITY VS SAMPLE QUESTION")
    print("=" * 60)
    print(f"sample: {sample}\n")

    sample_vec = vector
    for s in sentences:
        sim = cosine_similarity(sample_vec, embed_text(s, embeddings))
        print(f"similarity={sim:.4f} | {s}")

    print(
        "\nExpect: revenue/ARR question ≈ highest score; "
        "bread question ≈ lowest score."
    )
