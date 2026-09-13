"""
Parse YouTube auto-generated caption files (.vtt or .srt) into the same
chunked JSONL schema that parse.py produces for PDFs, so both sources can
be embedded into the same Chroma index.

Getting the caption files:
    pip install yt-dlp
    yt-dlp --write-auto-sub --skip-download --sub-lang en -o "data/transcripts_raw/%(upload_date)s_%(title)s.%(ext)s" <video-url>

    Repeat per video, or pass a channel/playlist URL to yt-dlp to pull many
    at once — see yt-dlp docs for batch options.

Usage:
    python src/parse_transcripts.py --in data/transcripts_raw --out data/processed/transcript_chunks.jsonl

Then combine with your existing PDF chunks before indexing:
    Get-Content data\\processed\\chunks.jsonl, data\\processed\\transcript_chunks.jsonl | Set-Content data\\processed\\all_chunks.jsonl
    (Mac/Linux: cat data/processed/chunks.jsonl data/processed/transcript_chunks.jsonl > data/processed/all_chunks.jsonl)

    python src/build_index.py --chunks data/processed/all_chunks.jsonl --db data/chroma
"""
import argparse
import json
import re
from pathlib import Path

CHUNK_SIZE_CHARS = 2800
CHUNK_OVERLAP_CHARS = 300

# Matches VTT/SRT timestamp lines, e.g.
#   00:00:01.000 --> 00:00:04.000
#   00:00:01,000 --> 00:00:04,000
TIMESTAMP_LINE = re.compile(
    r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}"
)
# Inline VTT timestamp tags like <00:00:01.440>
INLINE_TIMESTAMP = re.compile(r"<\d{2}:\d{2}:\d{2}[.,]\d{3}>")
# VTT position/style cues like <c> </c>
TAG = re.compile(r"</?c[^>]*>")
SRT_INDEX_LINE = re.compile(r"^\d+$")


def clean_caption_file(path: Path) -> str:
    """
    Extract plain spoken text from a .vtt or .srt file, stripping headers,
    timestamps, cue tags, and index numbers. Auto-captions frequently repeat
    the same line across consecutive cues (rolling captions) — collapse
    consecutive duplicate lines to avoid tripling the text.
    """
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    text_lines = []
    prev_line = None

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if line.upper().startswith("KIND:") or line.upper().startswith("LANGUAGE:"):
            continue
        if TIMESTAMP_LINE.match(line):
            continue
        if SRT_INDEX_LINE.match(line):
            continue

        line = INLINE_TIMESTAMP.sub("", line)
        line = TAG.sub("", line)
        line = line.strip()

        if not line:
            continue
        if line == prev_line:
            continue  # collapse rolling-caption duplicates

        text_lines.append(line)
        prev_line = line

    return " ".join(text_lines)


def guess_year(filename: str) -> str | None:
    # yt-dlp's %(upload_date)s gives YYYYMMDD — grab the YYYY
    match = re.search(r"(20\d{2})\d{4}", filename)
    if match:
        return match.group(1)
    match = re.search(r"(20\d{2})", filename)
    return match.group(1) if match else None


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

    caption_files = sorted(list(in_dir.glob("*.vtt")) + list(in_dir.glob("*.srt")))
    print(f"Found {len(caption_files)} caption file(s) in {in_dir}")

    chunk_count = 0
    with out_path.open("w", encoding="utf-8") as out_f:
        for cap_path in caption_files:
            text = clean_caption_file(cap_path)
            chunks = chunk_text(text, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
            year = guess_year(cap_path.name)

            if not chunks:
                print(f"  [warn] no text extracted from {cap_path.name}")
                continue

            for i, chunk in enumerate(chunks):
                record = {
                    "id": f"{cap_path.stem}_{i}",
                    "text": chunk,
                    "source_file": cap_path.name,
                    "doc_type": "transcript",
                    "year": year,
                    "chunk_index": i,
                }
                out_f.write(json.dumps(record) + "\n")
                chunk_count += 1
            print(f"  [ok] {cap_path.name} -> {len(chunks)} chunk(s)")

    print(f"\nWrote {chunk_count} chunks to {out_path}")


if __name__ == "__main__":
    main()
