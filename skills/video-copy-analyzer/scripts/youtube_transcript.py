#!/usr/bin/env python3
"""
YouTube transcript fetcher via TranscriptAPI.com
No video download needed — fetches captions directly from YouTube.

Credential priority:
  1. .secrets/youtube-transcript-config.json  (formData / user-configured)
  2. YOUTUBE_TRANSCRIPT_API_KEY env var        (local / dev fallback)

Get your API key: https://transcriptapi.com
"""

import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

API_BASE = "https://transcriptapi.com/api/v2"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SECRETS_PATH = os.path.join(WORKSPACE_ROOT, ".secrets", "youtube-transcript-config.json")


def _load_api_key() -> str:
    """
    Load TranscriptAPI key with priority:
    1. .secrets/youtube-transcript-config.json  (formData)
    2. YOUTUBE_TRANSCRIPT_API_KEY env var        (dev fallback)
    """
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = cfg.get("youtube_transcript_api_key", "").strip()
            if key:
                return key
        except Exception:
            pass

    key = os.environ.get("YOUTUBE_TRANSCRIPT_API_KEY", "").strip()
    if key:
        return key

    return ""


def has_api_key() -> bool:
    return bool(_load_api_key())


def fetch_transcript(video_url: str) -> list:
    """
    Fetch YouTube transcript from TranscriptAPI.com.
    Returns list of segments: [{"text": str, "start": float, "duration": float}]
    """
    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError(
            "YouTube Transcript API key not configured.\n"
            "Please add your key in Agent Settings → Credentials (youtube_transcript_api_key).\n"
            "Get a free key at: https://transcriptapi.com"
        )

    params = urllib.parse.urlencode({"video_url": video_url})
    req = urllib.request.Request(
        f"{API_BASE}/youtube/transcript?{params}",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            raise RuntimeError("API key invalid — please check your TranscriptAPI key")
        if e.code == 402:
            raise RuntimeError("TranscriptAPI quota exceeded — check your plan at transcriptapi.com")
        if e.code == 404:
            raise RuntimeError("No transcript found for this video (may have no captions)")
        if e.code == 429:
            raise RuntimeError("Rate limited — please retry in a moment")
        raise RuntimeError(f"TranscriptAPI error {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error reaching TranscriptAPI: {e.reason}")

    segments = data.get("transcript", [])
    if not segments:
        raise RuntimeError(
            "TranscriptAPI returned empty transcript. "
            "Video may have no captions or captions are disabled."
        )

    return segments


def write_srt(segments: list, output_srt: Path) -> None:
    """Write timestamped transcript segments to SRT format."""
    def fmt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(output_srt, "w", encoding="utf-8") as f:
        idx = 1
        for item in segments:
            text = item.get("text", "").strip()
            if not text:
                continue
            start = float(item.get("start", 0))
            duration = float(item.get("duration", 3.0))
            end = start + duration
            f.write(f"{idx}\n{fmt(start)} --> {fmt(end)}\n{text}\n\n")
            idx += 1


def main():
    if len(sys.argv) < 2:
        print("Usage: python youtube_transcript.py <youtube_url> [output_srt]")
        sys.exit(1)

    url = sys.argv[1]
    output_srt = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("transcript.srt")

    print(f"🎬 Fetching YouTube transcript: {url}")
    segments = fetch_transcript(url)
    write_srt(segments, output_srt)
    print(f"✅ Done ({len(segments)} segments) → {output_srt.name}")


if __name__ == "__main__":
    main()
