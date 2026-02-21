"""
scraper/ingest.py

Reads raw JSON files from data/raw/, chunks text, generates embeddings
via nomic-embed-text (Ollama), and upserts into the Qdrant collection.

Usage:
    python scraper/ingest.py
    python scraper/ingest.py --raw-dir data/raw --collection fcup_docs
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

load_dotenv()

import os

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "fcup_docs")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
RAW_DATA_DIR = Path("data/raw")

# Chunk settings
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
# nomic-embed-text dimension
EMBED_DIM = 768


def load_raw_docs(raw_dir: Path) -> list[Document]:
    docs = []
    files = list(raw_dir.glob("*.json"))
    if not files:
        print(f"[ingest] ⚠️  No files found in {raw_dir}")
        return docs

    for f in files:
        data = json.loads(f.read_text())
        doc = Document(
            text=data["text"],
            metadata={
                "url": data["url"],
                "title": data["title"],
                "crawled_at": data["crawled_at"],
                "source": data["url"],  # duplicate for retrieval convenience
            },
            excluded_llm_metadata_keys=["crawled_at"],
            excluded_embed_metadata_keys=["crawled_at"],
        )
        docs.append(doc)
        print(f"[ingest] Loaded: {data['title']!r} ({len(data['text'])} chars)")

    return docs


def ensure_collection(client: QdrantClient, collection: str) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if collection not in existing:
        print(f"[ingest] Creating Qdrant collection '{collection}'...")
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
    else:
        print(f"[ingest] Collection '{collection}' already exists, upserting...")


def run_ingest(raw_dir: Path, collection: str) -> None:
    # 1. Load documents
    docs = load_raw_docs(raw_dir)
    if not docs:
        return

    # 2. Configure LlamaIndex settings
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    # No LLM needed for ingestion
    Settings.llm = None

    # 3. Connect to Qdrant
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, collection)
    vector_store = QdrantVectorStore(client=client, collection_name=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 4. Chunk + embed + index
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    print(f"\n[ingest] Indexing {len(docs)} documents into '{collection}'...")
    VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        transformations=[splitter],
        show_progress=True,
    )

    print(f"\n[ingest] ✅ Done. Documents indexed in Qdrant collection '{collection}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FCUP RAG Ingestion Pipeline")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--collection", type=str, default=COLLECTION)
    args = parser.parse_args()

    run_ingest(args.raw_dir, args.collection)
