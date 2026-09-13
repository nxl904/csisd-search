"""
Extract text from PDFs in a directory, chunk it, and write out a JSONL file
of chunks with metadata — one line per chunk, ready for embedding.

Usage:
    python src/parse.py --in data/raw --out data/processed/chunks.jsonl
"""
import argparse
import json
import re
from pathlib import Path

import pdfplumber
from tqdm import tqdm

CHUNK_SIZE_CHARS = 2800   # ~600-800 tokens
CHUNK_OVERLAP_CHARS = 300


def guess_doc_type(filename: str) -> str:
    name = filename.lower()
    if "budget" in name:
        return "budget"
    elif "agenda" in name:
        return "agenda"
    elif "minutes" in name:
        return "minutes"
    elif "policy" in name or "policies" in name:
        return "policy"
    elif "contract" in name:
        return "contract"
    return "other"


def guess_year(filename: str) -> str | None:
    match = re.search(r"(20\d{2})", filename)
    return match.group(1) if match else None


def extract_text(pdf_path: Path) -> str:
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
    except Exception as e:
        print(f"  [error] {pdf_path.name}: {e}")
    return "\n".join(text_parts)


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", required=True)
    parser.add_argument("--out", dest="out_path", required=True)
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(in_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF(s) in {in_dir}")

    chunk_count = 0
    with out_path.open("w", encoding="utf-8") as out_f:
        for pdf_path in tqdm(pdf_files, desc="Parsing"):
            text = extract_text(pdf_path)
            chunks = chunk_text(text, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
            doc_type = guess_doc_type(pdf_path.name)
            year = guess_year(pdf_path.name)
            for i, chunk in enumerate(chunks):
                record = {
                    "id": f"{pdf_path.stem}_{i}",
                    "text": chunk,
                    "source_file": pdf_path.name,
                    "doc_type": doc_type,
                    "year": year,
                    "chunk_index": i,
                }
                out_f.write(json.dumps(record) + "\n")
                chunk_count += 1

    print(f"Wrote {chunk_count} chunks to {out_path}")


if __name__ == "__main__":
    main()
