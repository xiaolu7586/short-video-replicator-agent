#!/usr/bin/env python3
"""
视频文案分析工具 - 主入口
用法: python main.py <视频URL或分享文本或文件路径> [输出目录]

凭证（可选，用于 Bilibili/YouTube 直接转录，无需下载视频）:
  VIDEO_TRANSCRIPT_API_KEY — 视频转录服务 API Key（支持 BibiGPT 或兼容服务）
  VIDEO_TRANSCRIPT_BASE_URL — 自定义 API 地址（留空默认使用 BibiGPT）
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "core"))

from core.downloader import download_video, extract_video_id
from core.transcriber import transcribe_video
from core.guidance import generate_transcript

try:
    from scripts.extract_video_url import extract_video_url_from_text
except ImportError:
    extract_video_url_from_text = None

try:
    from scripts.bibigpt_api import has_api_token as _has_bibi_token
except ImportError:
    _has_bibi_token = lambda: False


def is_url(path: str) -> bool:
    return path.startswith(("http://", "https://", "BV"))


def is_bilibili_or_youtube(url: str) -> bool:
    return any(x in url for x in ("bilibili.com", "youtube.com", "youtu.be")) or url.startswith("BV")


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
        print("Default output dir: <sub-agent>/canvas (auto-detected)")
        print("")
        print("Examples:")
        print("  python main.py 'https://www.bilibili.com/video/BVxxxx'")
        print("  python main.py BV1234567890")
        print("  python main.py ./my_video.mp4 ./output")
        sys.exit(0)

    input_text = sys.argv[1]
    # 默认使用 sub-agent 的 canvas 目录，可通过参数指定其他目录
    # 自动检测：从脚本位置向上查找 workspace-* 目录
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

    use_bibigpt = is_url(url) and is_bilibili_or_youtube(url) and _has_bibi_token()

    if use_bibigpt:
        # BibiGPT 路径: 直接 API 获取转录，跳过视频下载和本地音频转录
        from scripts.bibigpt_api import fetch_transcript, write_srt_from_text

        video_id = extract_video_id(url)
        srt_path = output_dir / f"{video_id}.srt"

        print("🌐 检测到 Bilibili/YouTube 链接，通过 BibiGPT API 获取转录...")
        text = fetch_transcript(url)
        write_srt_from_text(text, srt_path)
        report_stage(1, "BibiGPT 转录", srt_path, f"{len(text)} 字符")

        video_stem = video_id
        video_source = url

    elif is_url(url):
        # 原有路径: 下载视频 → 本地音频转录
        if is_bilibili_or_youtube(url) and not _has_bibi_token():
            print("⚠️  Bilibili/YouTube 链接建议配置 Video Transcript API Key 以避免平台限制")
            print("   请在 Agent 设置 → 凭证 中填入（支持 BibiGPT 或兼容服务）")
            print("   将尝试直接下载（可能因平台风控失败）...\n")

        video_path = download_video(url, output_dir)
        video_source = url
        size_mb = video_path.stat().st_size / 1024 / 1024
        report_stage(1, "下载视频", video_path, f"{size_mb:.1f}MB")

        srt_path = output_dir / f"{video_path.stem}.srt"
        transcribe_video(video_path, srt_path)
        segment_count = sum(1 for line in open(srt_path, "r", encoding="utf-8") if line.strip().isdigit())
        report_stage(2, "语音转录", srt_path, f"{segment_count} 片段")

        video_stem = video_path.stem

    else:
        # 本地文件路径
        video_path = Path(url)
        if not video_path.exists():
            print(f"❌ 文件不存在: {video_path}")
            sys.exit(1)
        video_source = str(video_path)
        size_mb = video_path.stat().st_size / 1024 / 1024
        report_stage(1, "本地文件", video_path, f"{size_mb:.1f}MB")

        srt_path = output_dir / f"{video_path.stem}.srt"
        transcribe_video(video_path, srt_path)
        segment_count = sum(1 for line in open(srt_path, "r", encoding="utf-8") if line.strip().isdigit())
        report_stage(2, "语音转录", srt_path, f"{segment_count} 片段")

        video_stem = video_path.stem

    # 阶段3: 生成文字稿
    transcript_path = generate_transcript(srt_path, output_dir, video_source)

    with open(transcript_path, "r", encoding="utf-8") as f:
        content = f.read()
        if "## Full Transcript" in content:
            content = content.split("## Full Transcript")[1].strip()
    report_stage(3, "生成文字稿", transcript_path, f"{len(content)} 字符")

    # 完成
    duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 50)
    print("✅ 完成!")
    print("=" * 50)
    print(f"⏱️  耗时: {duration:.1f}秒")
    print(f"📁 目录: {output_dir}\n")

    print("📄 生成文件:")
    if not use_bibigpt:
        print(f"   • {video_stem}.mp4")
    print(f"   • {srt_path.name}")
    print(f"   • {transcript_path.name}")

    print("\n🤖 Agent Next Step:")
    print("   Read analysis framework from prompt/")
    print("   Call LLM to generate de-ai-fied analysis report")
    print(f"   Output: {output_dir}/{video_stem}_analysis.md")


if __name__ == "__main__":
    main()
