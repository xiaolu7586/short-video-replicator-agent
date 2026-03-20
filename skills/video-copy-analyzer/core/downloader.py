"""视频下载模块"""

import subprocess
import re
import sys
from pathlib import Path


def get_venv_python():
    script_dir = Path(__file__).parent.parent.resolve()
    venv_python = script_dir / "venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def get_venv_ytdlp():
    script_dir = Path(__file__).parent.parent.resolve()
    venv_ytdlp = script_dir / "venv" / "bin" / "yt-dlp"
    return str(venv_ytdlp) if venv_ytdlp.exists() else "yt-dlp"


def extract_video_id(url: str) -> str:
    bilibili_match = re.search(r'(BV[\w]+|av\d+)', url)
    if bilibili_match:
        return bilibili_match.group(1)

    youtube_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    if youtube_match:
        return youtube_match.group(1)

    douyin_match = re.search(r'video/(\d+)', url)
    if douyin_match:
        return f"douyin_{douyin_match.group(1)}"

    return hex(hash(url) & 0xFFFFFFFF)[2:]


def download_douyin(url: str, output_dir: Path) -> Path:
    video_id = extract_video_id(url)
    output_file = output_dir / f"{video_id}.mp4"
    script_path = Path(__file__).parent.parent / "scripts" / "download_douyin.py"

    cmd = [get_venv_python(), str(script_path), url, str(output_file)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"抖音下载失败: {result.stderr}")

    if not output_file.exists():
        raise RuntimeError("未找到下载的视频文件")

    return output_file


def download_ytdlp(url: str, output_dir: Path) -> Path:
    video_id = extract_video_id(url)
    output_template = str(output_dir / f"{video_id}.%(ext)s")

    cmd = [
        get_venv_ytdlp(),
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败: {result.stderr}")

    for ext in ["mp4", "mkv", "webm"]:
        video_file = output_dir / f"{video_id}.{ext}"
        if video_file.exists():
            return video_file

    raise RuntimeError("未找到下载的视频文件")


def download_video(url: str, output_dir: Path) -> Path:
    is_douyin = "douyin.com" in url or "v.douyin.com" in url

    if is_douyin:
        return download_douyin(url, output_dir)
    else:
        return download_ytdlp(url, output_dir)
