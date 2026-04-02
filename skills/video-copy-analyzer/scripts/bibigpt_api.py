#!/usr/bin/env python3
"""
Video transcript API client for Bilibili/YouTube
Fetches transcripts directly via URL — no video download required.

Supported providers (BibiGPT-compatible REST API):
  - BibiGPT (default): https://bibigpt.co/user/integration
  - Any compatible service: set video_transcript_base_url in agent settings

Credential priority:
  1. .secrets/video-transcript-config.json  (formData / user-configured)
  2. VIDEO_TRANSCRIPT_API_KEY env var        (local / dev fallback)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_BASE_URL = "https://api.bibigpt.co/api/v1"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SECRETS_PATH = os.path.join(WORKSPACE_ROOT, ".secrets", "video-transcript-config.json")


def _load_config() -> tuple[str, str]:
    """
    Load API key and base URL with priority:
    1. .secrets/video-transcript-config.json  (formData / user-configured)
    2. VIDEO_TRANSCRIPT_API_KEY / VIDEO_TRANSCRIPT_BASE_URL env vars (dev fallback)

    Returns: (api_key, base_url)
    """
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            api_key = cfg.get("video_transcript_api_key", "").strip()
            base_url = cfg.get("video_transcript_base_url", "").strip() or DEFAULT_BASE_URL
            if api_key:
                return api_key, base_url
        except Exception:
            pass

    api_key = os.environ.get("VIDEO_TRANSCRIPT_API_KEY", "").strip()
    base_url = os.environ.get("VIDEO_TRANSCRIPT_BASE_URL", "").strip() or DEFAULT_BASE_URL
    return api_key, base_url


def has_api_token() -> bool:
    """Return True if a video transcript API key is configured."""
    api_key, _ = _load_config()
    return bool(api_key)


def fetch_transcript(url: str) -> str:
    """Fetch video transcript text via URL — no video download needed."""
    api_key, base_url = _load_config()
    if not api_key:
        raise RuntimeError(
            "Video Transcript API Key not configured.\n"
            "Please add your API key in Agent Settings → Credentials.\n"
            "Default provider (BibiGPT): https://bibigpt.co/user/integration"
        )

    endpoint = base_url.rstrip("/") + "/getPolishedText"
    payload = json.dumps({"url": url}).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api_token": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            raise RuntimeError("API key invalid — please check your credentials")
        if e.code == 402:
            raise RuntimeError("API quota exceeded — please top up your account")
        if e.code == 429:
            raise RuntimeError("Rate limited — please retry in a moment")
        raise RuntimeError(f"Transcript API error {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error reaching transcript API: {e.reason}")

    # Compatible with multiple response field names across providers
    text = (
        data.get("polishedText")
        or data.get("subtitle")
        or data.get("text")
        or data.get("content")
        or data.get("transcript")
        or ""
    )
    if not text:
        raise RuntimeError(
            f"Transcript API returned empty content. "
            f"Video may have no subtitles or is unsupported.\n"
            f"Raw response: {json.dumps(data, ensure_ascii=False)[:300]}"
        )

    return text.strip()


def write_srt_from_text(text: str, output_srt: Path) -> None:
    """Write plain-text transcript as a single-segment SRT for pipeline compatibility."""
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write("1\n")
        f.write("00:00:00,000 --> 99:59:59,000\n")
        f.write(text + "\n\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python bibigpt_api.py <video_url> [output_srt_path]")
        sys.exit(1)

    url = sys.argv[1]
    output_srt = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("transcript.srt")

    print(f"🌐 Fetching transcript via API: {url}")
    text = fetch_transcript(url)
    write_srt_from_text(text, output_srt)
    print(f"✅ Done ({len(text)} chars) → {output_srt.name}")


if __name__ == "__main__":
    main()
