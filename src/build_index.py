"""
Embed chunks (from parse.py) and load them into a local Chroma vector store.

Usage:
    python src/build_index.py --chunks data/processed/chunks.jsonl --db data/chroma
"""
import argparse
import json
import os
from pathlib import Path

import chromadb
from tqdm import tqdm

# Uses OpenAI embeddings by default. Swap EMBED_FN for a local
# sentence-transformers model if you'd rather not send text to OpenAI.
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set OPENAI_API_KEY to embed chunks (or edit build_index.py to "
            "use a local embedding model instead)."
        )
    return OpenAI(api_key=api_key)


def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def load_chunks(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--db", required=True, help="Path for persistent Chroma DB")
    parser.add_argument("--collection", default="csisd_docs")
    args = parser.parse_args()

    records = load_chunks(Path(args.chunks))
    print(f"Loaded {len(records)} chunks")

    client = get_openai_client()
    chroma_client = chromadb.PersistentClient(path=args.db)
    collection = chroma_client.get_or_create_collection(args.collection)

    for i in tqdm(range(0, len(records), BATCH_SIZE), desc="Embedding + indexing"):
        batch = records[i : i + BATCH_SIZE]
        texts = [r["text"] for r in batch]
        embeddings = embed_batch(client, texts)
        collection.upsert(
            ids=[r["id"] for r in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "source_file": r["source_file"],
                    "doc_type": r["doc_type"],
                    "year": r["year"] or "",
                }
                for r in batch
            ],
        )

    print(f"Index built at {args.db} (collection: {args.collection})")


if __name__ == "__main__":
    main()
