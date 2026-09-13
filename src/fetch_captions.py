"""
Batch-download auto-generated English captions for a list of YouTube URLs.

Dedupes the URL list, skips videos already downloaded, and logs any video
with no available captions to a separate file so you know which ones need
the Whisper-transcription fallback instead.

Usage:
    1. Put one YouTube URL per line in a text file, e.g. urls.txt
    2. python src/fetch_captions.py --urls urls.txt --out data/transcripts_raw
"""
import argparse
import subprocess
from pathlib import Path


def load_urls(path: Path) -> list[str]:
    urls = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def video_id_from_url(url: str) -> str:
    # crude but sufficient: grab the v= param
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    return url.rstrip("/").split("/")[-1]


def already_downloaded(video_id: str, out_dir: Path) -> bool:
    # Filenames are written as "<id>_<upload_date>_<title>.<ext>" — match on
    # the id prefix specifically to avoid false positives from titles that
    # happen to contain another video's id as a substring.
    return any(f.name.startswith(f"{video_id}_") for f in out_dir.glob("*"))


def has_english_captions(url: str) -> bool:
    result = subprocess.run(
        ["yt-dlp", "--list-subs", url],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    # yt-dlp lists caption tracks with the language code at the start of
    # each line, e.g. "en       English". Check for a line that starts
    # with "en" as a whole token (avoids matching "en-orig" twice, etc.)
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("en ") or stripped.startswith("en\t"):
            return True
    return False


def download_captions(url: str, out_dir: Path) -> bool:
    result = subprocess.run(
        [
            "yt-dlp",
            "--write-auto-sub",
            "--skip-download",
            "--sub-lang", "en",
            "-o", str(out_dir / "%(id)s_%(upload_date)s_%(title)s.%(ext)s"),
            url,
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "no subtitles" not in result.stdout.lower()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", required=True, help="Text file, one YouTube URL per line")
    parser.add_argument("--out", required=True, help="Output directory for caption files")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = load_urls(Path(args.urls))
    print(f"Loaded {len(urls)} unique URL(s)")

    no_captions = []
    downloaded = []
    failed = []

    for i, url in enumerate(urls, 1):
        vid = video_id_from_url(url)
        print(f"[{i}/{len(urls)}] {vid}")

        if already_downloaded(vid, out_dir):
            print("  [skip] already downloaded")
            continue

        if not has_english_captions(url):
            print("  [none] no English captions available")
            no_captions.append(url)
            continue

        ok = download_captions(url, out_dir)
        if ok:
            print("  [ok] downloaded")
            downloaded.append(url)
        else:
            print("  [fail] download command did not succeed")
            failed.append(url)

    print(f"\nDownloaded: {len(downloaded)}")
    print(f"No captions available: {len(no_captions)}")
    print(f"Failed: {len(failed)}")

    if no_captions:
        no_cap_path = out_dir.parent / "no_captions.txt"
        no_cap_path.write_text("\n".join(no_captions), encoding="utf-8")
        print(f"\nVideos with no captions written to {no_cap_path}")
        print("(these are candidates for the Whisper-transcription fallback)")

    if failed:
        failed_path = out_dir.parent / "failed_downloads.txt"
        failed_path.write_text("\n".join(failed), encoding="utf-8")
        print(f"Failed downloads written to {failed_path}")


if __name__ == "__main__":
    main()
