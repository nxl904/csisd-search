# CSISD RAG Search

A small retrieval-augmented-generation (RAG) app for making College Station ISD
public documents (board agendas/minutes, budgets, policies, news coverage)
searchable with an LLM.

## Pipeline

1. `src/scrape.py`      — pull PDFs/links from csisd.org, boardbook.org, TEA
2. `src/parse.py`       — extract text from PDFs into chunked, metadata-tagged JSON
3. `src/build_index.py` — embed chunks and load them into a local Chroma vector store
4. `src/query.py`       — CLI: ask a question, get a cited answer
5. `src/app.py`         — Streamlit chat UI on top of the same retrieval logic

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Anthropic key for generation, OpenAI (or local) key for embeddings
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...        # only if using OpenAI embeddings
```

## Usage

```bash
# 1. Drop PDFs into data/raw/ (or run the scraper)
python src/scrape.py --out data/raw

# 2. Parse + chunk
python src/parse.py --in data/raw --out data/processed/chunks.jsonl

# 3. Build the vector index
python src/build_index.py --chunks data/processed/chunks.jsonl --db data/chroma

# 4. Ask questions
python src/query.py --db data/chroma --q "What was the CFO's salary in 2023?"

# or launch the chat UI
streamlit run src/app.py
```

## Notes on sourcing CSISD data specifically

- Board agenda packets: boardbook.org (best structured source — has line-item
  budget backup, contracts, HR actions)
- Budgets: csisd.org/Userfiles/DBFiles/... (adopted + proposed budget PDFs)
- Financial/staff detail: TEA PEIMS financial and staff reports — much better
  than scraping budget PDFs for line items like salaries
- News coverage for context/cross-checking: KBTX, WTAW
- Always store the source URL + date + doc type as metadata on every chunk so
  the LLM can cite it, and so you can filter by recency at query time.

## Extending

- Swap Chroma for LanceDB/Pinecone/Weaviate if you outgrow local storage.
- Add a re-ranker (e.g. Cohere rerank) before generation if precision on
  numeric/financial questions matters — vector similarity alone is weak for
  "find the exact salary number" style queries; consider also indexing
  structured tables (budget line items) separately as JSON/CSV rows rather
  than prose chunks.
- Add a `doc_type` filter (agenda / minutes / budget / policy / news) so
  the UI can let users scope a search.
