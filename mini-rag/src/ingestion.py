"""
Step 2 — Document ingestion.

Responsibility of this module:
  Load raw files from disk and turn them into LangChain Document objects.

We intentionally stop here. Chunking, embeddings, and retrieval come later.
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from src.config import DOCUMENTS_DIR


SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def load_documents(documents_dir: Path | None = None) -> list[Document]:
    """
    Load every supported file in the documents folder.

    Returns a list of LangChain Document objects.
    Each Document has:
      - page_content: the text string
      - metadata: a dict (source path, page number for PDFs, etc.)
    """
    directory = documents_dir or DOCUMENTS_DIR

    if not directory.exists():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    files = sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )

    if not files:
        raise FileNotFoundError(
            f"No supported documents found in {directory}. "
            f"Add .txt, .md, or .pdf files."
        )

    documents: list[Document] = []

    for path in files:
        suffix = path.suffix.lower()

        if suffix in {".txt", ".md"}:
            # TextLoader reads the whole file as one Document by default.
            loader = TextLoader(str(path), encoding="utf-8")
        elif suffix == ".pdf":
            # PyPDFLoader creates one Document per PDF page.
            loader = PyPDFLoader(str(path))
        else:
            continue

        loaded = loader.load()
        documents.extend(loaded)

    return documents


def preview_documents(documents: list[Document], max_chars: int = 400) -> None:
    """Print a small inspection report — useful for debugging ingestion."""
    print(f"Number of documents: {len(documents)}")
    print("-" * 60)

    for i, doc in enumerate(documents):
        print(f"\n=== Document index {i} ===")
        print(f"metadata: {doc.metadata}")
        content = doc.page_content
        preview = content if len(content) <= max_chars else content[:max_chars] + "..."
        print(f"page_content preview:\n{preview}")


if __name__ == "__main__":
    docs = load_documents()
    preview_documents(docs)

    # Extra interview-friendly checks:
    first = docs[0]
    print("\n" + "=" * 60)
    print("FIRST DOCUMENT — focused inspection")
    print("=" * 60)
    print(f"type(first): {type(first)}")
    print(f"metadata keys: {list(first.metadata.keys())}")
    print(f"source: {first.metadata.get('source')}")
    print(f"page_content length (chars): {len(first.page_content)}")
    print(f"first 200 chars of page_content:\n{first.page_content[:200]}")
