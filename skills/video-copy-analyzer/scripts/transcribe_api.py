#!/usr/bin/env python3
"""
语音转录脚本 — 通过 OpenAI 兼容转录 API 生成 SRT 字幕

鉴权优先级（从高到低）：
  1. .secrets/transcribe-config.json（formData 配置，推荐）
  2. 环境变量 TRANSCRIBE_API_KEY / TRANSCRIBE_BASE_URL
  3. ~/.openclaw/ 运行时（兼容 OpenClaw 协议的平台）
"""

import os
import sys
import json
import re
import tempfile
import urllib.request
import urllib.error
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
WORKSPACE_ROOT = (SCRIPT_DIR / ".." / ".." / "..").resolve()
SECRETS_PATH = WORKSPACE_ROOT / ".secrets" / "transcribe-config.json"
OPENCLAW_HOME = Path.home() / ".openclaw"


def _load_from_secrets() -> dict | None:
    """从 .secrets/transcribe-config.json 读取 API Key（formData 配置）"""
    if not SECRETS_PATH.exists():
        return None
    try:
        cfg = json.loads(SECRETS_PATH.read_text())
        api_key = cfg.get("transcribe_api_key", "").strip()
        if not api_key:
            return None
        base_url = cfg.get("transcribe_base_url", "").strip() or "https://api.openai.com/v1"
        return {"mode": "apikey", "api_key": api_key, "base_url": base_url.rstrip("/")}
    except Exception:
        return None


def _load_from_env() -> dict | None:
    """从环境变量读取 API Key"""
    api_key = os.environ.get("TRANSCRIBE_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.environ.get("TRANSCRIBE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return {"mode": "apikey", "api_key": api_key, "base_url": base_url}


def _load_from_openclaw() -> dict | None:
    """从 ~/.openclaw/ 运行时读取凭据（OpenClaw 兼容平台）"""
    userinfo_path = OPENCLAW_HOME / "identity" / "openclaw-userinfo.json"
    config_path = OPENCLAW_HOME / "openclaw.json"
    if not userinfo_path.exists():
        return None
    try:
        identity = json.loads(userinfo_path.read_text())
        uid_key = next(k for k in identity if re.search(r'uid', k, re.I))
        token_key = next(k for k in identity if re.search(r'token', k, re.I))
        uid, token = identity[uid_key], identity[token_key]
    except Exception:
        return None
    try:
        cfg = json.loads(config_path.read_text())
        providers = cfg.get("models", {}).get("providers", {})
        base_url = None
        for provider in providers.values():
            for k, v in provider.items():
                if re.search(r'base.?url', k, re.I) and isinstance(v, str) and v.startswith("http"):
                    base_url = v.rstrip("/")
                    break
            if base_url:
                break
    except Exception:
        base_url = None
    if not base_url:
        return None
    return {"mode": "openclaw", "uid": uid, "token": token, "base_url": base_url}


def load_config() -> dict:
    """按优先级加载鉴权配置，全部失败则退出并提示"""
    for loader in [_load_from_secrets, _load_from_env, _load_from_openclaw]:
        cfg = loader()
        if cfg:
            return cfg
    print("❌ 未找到转录 API 配置", file=sys.stderr)
    print("", file=sys.stderr)
    print("请通过以下任一方式配置：", file=sys.stderr)
    print("  1. 在平台激活对话框中填写转录 API Key", file=sys.stderr)
    print("  2. 设置环境变量 TRANSCRIBE_API_KEY", file=sys.stderr)
    print("  3. 使用支持 OpenClaw 运行时标准的平台（自动识别）", file=sys.stderr)
    sys.exit(1)


def extract_audio(video_path: Path) -> Path:
    """用 ffmpeg 从视频提取音频，压缩为低码率 mono mp3"""
    import subprocess
    audio_path = Path(tempfile.mktemp(suffix=".mp3"))
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame",
        "-ar", "16000", "-ac", "1", "-q:a", "5",
        str(audio_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"音频提取失败: {result.stderr}")
    size_mb = audio_path.stat().st_size / 1024 / 1024
    print(f"   音频提取完成: {size_mb:.1f}MB")
    return audio_path


def transcribe_audio(audio_path: Path, config: dict) -> dict:
    """上传音频到转录 API"""
    boundary = "----TranscribeBoundary"
    with open(audio_path, "rb") as f:
        file_content = f.read()

    body = b""
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\ngpt-4o-mini-transcribe\r\n'.encode()
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="response_format"\r\n\r\nverbose_json\r\n'.encode()
    body += (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'
        f'Content-Type: audio/mpeg\r\n\r\n'
    ).encode() + file_content + b'\r\n'
    body += f'--{boundary}--\r\n'.encode()

    if config["mode"] == "apikey":
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {config['api_key']}"
        }
    else:  # openclaw
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Auth-Uid": config["uid"],
            "X-Auth-Token": config["token"]
        }

    req = urllib.request.Request(
        f"{config['base_url']}/audio/transcriptions",
        data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 请求失败 {e.code}: {e.read().decode('utf-8')}")


def write_srt(result: dict, output_srt: Path) -> None:
    """将转录结果写为 SRT 文件"""
    segments = result.get("segments", [])
    if not segments:
        segments = [{
            "id": 1, "start": 0.0,
            "end": result.get("duration", 60.0) or 60.0,
            "text": result.get("text", "")
        }]

    def fmt(seconds: float) -> str:
        h, m = int(seconds // 3600), int((seconds % 3600) // 60)
        s, ms = int(seconds % 60), int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(output_srt, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"{seg.get('id', 1)}\n")
            f.write(f"{fmt(seg['start'])} --> {fmt(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")


def main():
    if len(sys.argv) < 2:
        print("用法: python transcribe_api.py <视频/音频路径> [输出SRT路径]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_srt = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".srt")

    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"🎤 开始转录: {input_path.name}")
    config = load_config()
    is_video = input_path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm")
    audio_path = None

    try:
        if is_video:
            print("   从视频提取音频...")
            audio_path = extract_audio(input_path)
        else:
            audio_path = input_path

        print("   上传到转录 API...")
        result = transcribe_audio(audio_path, config)
        write_srt(result, output_srt)
        print(f"✅ 转录完成: {len(result.get('segments', []))} 片段 → {output_srt.name}")
    finally:
        if is_video and audio_path and audio_path.exists():
            audio_path.unlink()


if __name__ == "__main__":
    main()
