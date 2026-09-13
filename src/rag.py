"""
Shared retrieval + generation logic. Both query.py (CLI) and app.py
(Streamlit) import from here so the two stay in sync.
"""
import os

import chromadb
from anthropic import Anthropic
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"
CLAUDE_MODEL = "claude-sonnet-4-6"
TOP_K = 8

SYSTEM_PROMPT = """You are a research assistant answering questions about \
College Station ISD using ONLY the provided document excerpts. Rules:

- Cite the source file for every claim, e.g. (source: 2023_2024_proposed_budget.pdf)
- If the excerpts don't contain the answer, say so plainly — don't guess or \
fill in from general knowledge.
- Quote sparingly; prefer paraphrasing, except for exact figures/dates which \
should be stated precisely.
- If multiple excerpts give conflicting figures (e.g. different budget years), \
surface the conflict rather than picking one silently.
"""


def get_clients():
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return openai_client, anthropic_client


def get_collection(db_path: str, collection_name: str = "csisd_docs"):
    chroma_client = chromadb.PersistentClient(path=db_path)
    return chroma_client.get_collection(collection_name)


def retrieve(openai_client, collection, question: str, top_k: int = TOP_K, doc_type: str | None = None):
    embedding = openai_client.embeddings.create(
        model=EMBED_MODEL, input=[question]
    ).data[0].embedding

    where = {"doc_type": doc_type} if doc_type else None
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where,
    )
    hits = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({"text": doc, "metadata": meta, "distance": dist})
    return hits


def build_context_block(hits: list[dict]) -> str:
    blocks = []
    for h in hits:
        src = h["metadata"].get("source_file", "unknown")
        year = h["metadata"].get("year", "")
        blocks.append(f"[source: {src}{' (' + year + ')' if year else ''}]\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


def answer_question(openai_client, anthropic_client, collection, question: str, doc_type: str | None = None) -> tuple[str, list[dict]]:
    hits = retrieve(openai_client, collection, question, doc_type=doc_type)
    context = build_context_block(hits)

    message = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Document excerpts:\n\n{context}\n\nQuestion: {question}",
            }
        ],
    )
    answer_text = "".join(
        block.text for block in message.content if block.type == "text"
    )
    return answer_text, hits
