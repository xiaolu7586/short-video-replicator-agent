#!/usr/bin/env python3
"""
视频文案分析工具 - 主入口
用法: python main.py <视频URL或分享文本或文件路径> [输出目录]

凭证配置（Agent 设置 → Credentials）:
  youtube_transcript_api_key — TranscriptAPI.com key，用于 YouTube 字幕获取
                                获取: https://transcriptapi.com（免费 100 次/月）
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "core"))

from core.downloader import download_video, extract_video_id
from core.transcriber import transcribe_video
from core.guidance import generate_transcript

try:
    from scripts.extract_video_url import extract_video_url_from_text
except ImportError:
    extract_video_url_from_text = None

try:
    from scripts.youtube_transcript import has_api_key as _has_youtube_key
except ImportError:
    _has_youtube_key = lambda: False


def is_url(path: str) -> bool:
    return path.startswith(("http://", "https://", "BV"))


def is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def is_bilibili(url: str) -> bool:
    return "bilibili.com" in url or url.startswith("BV")


def report_stage(stage: int, name: str, file: Path = None, status: str = None):
    print(f"\n✅ 阶段 {stage}/3: {name}")
    if file:
        print(f"   📄 {file.name}")
    if status:
        print(f"   📊 {status}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python main.py <video_url/share_text/file_path> [output_dir]")
        print("")
        print("Supported platforms:")
        print("  YouTube  — requires youtube_transcript_api_key (transcriptapi.com)")
        print("  Bilibili — browser login support coming soon")
        print("  Douyin   — direct download")
        print("  Local    — local video/audio file")
        sys.exit(0)

    input_text = sys.argv[1]
    script_dir = Path(__file__).parent.resolve()
    subagent_dir = script_dir
    while subagent_dir.name and not subagent_dir.name.startswith("workspace-"):
        subagent_dir = subagent_dir.parent
    default_dir = subagent_dir / "canvas" if subagent_dir.name.startswith("workspace-") else Path.home()
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else default_dir)

    # 提取链接
    url = input_text
    if extract_video_url_from_text and not os.path.exists(input_text):
        extracted, platform = extract_video_url_from_text(input_text)
        if extracted:
            print(f"📋 提取到{platform}链接: {extracted}")
            url = extracted

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("🎬 视频文案分析工具")
    print("=" * 50)
    print(f"📁 输出: {output_dir}\n")

    start_time = datetime.now()
    video_stem = None
    video_source = url if is_url(url) else str(Path(url))

    # ──────────────────────────────────────────
    # YouTube → TranscriptAPI.com
    # ──────────────────────────────────────────
    if is_url(url) and is_youtube(url):
        if not _has_youtube_key():
            print("❌ YouTube 视频需要配置 TranscriptAPI key")
            print("   请在 Agent 设置 → Credentials 中填入 youtube_transcript_api_key")
            print("   免费获取: https://transcriptapi.com")
            sys.exit(1)

        from scripts.youtube_transcript import fetch_transcript, write_srt

        video_id = extract_video_id(url)
        srt_path = output_dir / f"{video_id}.srt"

        print("🎬 通过 TranscriptAPI 获取 YouTube 字幕...")
        segments = fetch_transcript(url)
        write_srt(segments, srt_path)
        report_stage(1, "YouTube 字幕", srt_path, f"{len(segments)} 片段")

        video_stem = video_id

    # ──────────────────────────────────────────
    # Bilibili → browser cookie 方案（即将上线）
    # ──────────────────────────────────────────
    elif is_url(url) and is_bilibili(url):
        print("⚠️  Bilibili 支持：请确保 Chrome 已登录 bilibili.com")
        print("   正在尝试通过浏览器 cookie 获取字幕...\n")

        from scripts.fetch_bilibili_subtitle import get_bilibili_cookies, fetch_subtitle, extract_bvid

        bvid = extract_bvid(url) or extract_video_id(url)
        srt_path = output_dir / f"{bvid}.srt"

        cookies = get_bilibili_cookies()
        if not cookies.get("SESSDATA"):
            print("❌ 未能获取 B站 cookie，请确认：")
            print("   1. 已在 Chrome 中登录 bilibili.com")
            print("   2. ClawDI 运行在 Chrome 中")
            sys.exit(1)

        success = fetch_subtitle(bvid, cookies, str(srt_path))
        if not success:
            print("❌ 字幕获取失败（该视频可能未开启 AI 字幕）")
            sys.exit(1)

        report_stage(1, "B站字幕", srt_path)
        video_stem = bvid

    # ──────────────────────────────────────────
    # Douyin / 其他平台 URL → 下载 + 转录
    # ──────────────────────────────────────────
    elif is_url(url):
        video_path = download_video(url, output_dir)
        size_mb = video_path.stat().st_size / 1024 / 1024
        report_stage(1, "下载视频", video_path, f"{size_mb:.1f}MB")

        srt_path = output_dir / f"{video_path.stem}.srt"
        transcribe_video(video_path, srt_path)
        segment_count = sum(1 for line in open(srt_path, "r", encoding="utf-8") if line.strip().isdigit())
        report_stage(2, "语音转录", srt_path, f"{segment_count} 片段")

        video_stem = video_path.stem

    # ──────────────────────────────────────────
    # 本地文件 → 转录
    # ──────────────────────────────────────────
    else:
        video_path = Path(url)
        if not video_path.exists():
            print(f"❌ 文件不存在: {video_path}")
            sys.exit(1)
        size_mb = video_path.stat().st_size / 1024 / 1024
        report_stage(1, "本地文件", video_path, f"{size_mb:.1f}MB")

        srt_path = output_dir / f"{video_path.stem}.srt"
        transcribe_video(video_path, srt_path)
        segment_count = sum(1 for line in open(srt_path, "r", encoding="utf-8") if line.strip().isdigit())
        report_stage(2, "语音转录", srt_path, f"{segment_count} 片段")

        video_stem = video_path.stem

    # ──────────────────────────────────────────
    # 阶段3: 生成文字稿（所有路径共用）
    # ──────────────────────────────────────────
    transcript_path = generate_transcript(srt_path, output_dir, video_source)

    with open(transcript_path, "r", encoding="utf-8") as f:
        content = f.read()
        body = content.split("## Full Transcript")[1].strip() if "## Full Transcript" in content else content
    report_stage(3, "生成文字稿", transcript_path, f"{len(body)} 字符")

    duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 50)
    print("✅ 完成!")
    print("=" * 50)
    print(f"⏱️  耗时: {duration:.1f}秒")
    print(f"📁 目录: {output_dir}\n")
    print("📄 生成文件:")
    print(f"   • {srt_path.name}")
    print(f"   • {transcript_path.name}")
    print("\n🤖 Agent Next Step:")
    print("   Read analysis framework from prompt/")
    print("   Call LLM to generate de-ai-fied analysis report")
    print(f"   Output: {output_dir}/{video_stem}_analysis.md")


if __name__ == "__main__":
    main()
