"""
Steps 2–3 — Document ingestion and chunking.

Step 2: Load raw files → LangChain Document objects
Step 3: Split Documents into smaller overlapping chunks

Embeddings / vector store come later.
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, DOCUMENTS_DIR


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


def split_documents(
    documents: list[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    """
    Split Documents into smaller chunks for embedding + retrieval.

    RecursiveCharacterTextSplitter tries to split on natural boundaries:
      paragraphs → newlines → spaces → characters
    so chunks stay more readable than a naive fixed-width cut.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be smaller than chunk_size ({chunk_size})."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Prefer these separators, in order, when cutting text.
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )
    return splitter.split_documents(documents)


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


def preview_chunks(chunks: list[Document], max_chunks: int = 5, max_chars: int = 300) -> None:
    """Inspect several chunks before moving on to embeddings."""
    print(f"Total chunks: {len(chunks)}")
    print(f"Showing first {min(max_chunks, len(chunks))} chunks")
    print("-" * 60)

    for i, chunk in enumerate(chunks[:max_chunks]):
        print(f"\n=== Chunk {i} ===")
        print(f"chars: {len(chunk.page_content)}")
        print(f"metadata: {chunk.metadata}")
        content = chunk.page_content
        preview = content if len(content) <= max_chars else content[:max_chars] + "..."
        print(f"page_content:\n{preview}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect document loading and chunking.")
    parser.add_argument(
        "--mode",
        choices=["load", "chunk"],
        default="chunk",
        help="load = Step 2 only; chunk = Step 2 + Step 3 (default)",
    )
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    parser.add_argument("--max-chunks", type=int, default=5)
    args = parser.parse_args()

    docs = load_documents()

    if args.mode == "load":
        preview_documents(docs)
        first = docs[0]
        print("\n" + "=" * 60)
        print("FIRST DOCUMENT — focused inspection")
        print("=" * 60)
        print(f"type(first): {type(first)}")
        print(f"metadata keys: {list(first.metadata.keys())}")
        print(f"source: {first.metadata.get('source')}")
        print(f"page_content length (chars): {len(first.page_content)}")
        print(f"first 200 chars of page_content:\n{first.page_content[:200]}")
    else:
        print(f"Loaded documents: {len(docs)}")
        print(f"chunk_size={args.chunk_size}, chunk_overlap={args.chunk_overlap}")
        chunks = split_documents(
            docs,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        preview_chunks(chunks, max_chunks=args.max_chunks)

        # Help you see overlap between consecutive chunks
        if len(chunks) >= 2:
            a, b = chunks[0].page_content, chunks[1].page_content
            # Find longest suffix of a that is a prefix of b (simple overlap check)
            overlap_hint = ""
            max_check = min(len(a), len(b), args.chunk_overlap + 50)
            for n in range(max_check, 0, -1):
                if a.endswith(b[:n]):
                    overlap_hint = b[:n]
                    break
            print("\n" + "=" * 60)
            print("OVERLAP HINT (chunk 0 → chunk 1)")
            print("=" * 60)
            if overlap_hint:
                print(f"Shared text length ~{len(overlap_hint)} chars:")
                print(repr(overlap_hint[:200]))
            else:
                print("No exact suffix/prefix overlap found (can happen near separator boundaries).")
