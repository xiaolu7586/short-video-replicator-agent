#!/usr/bin/env python3
"""
环境检测脚本 - 检查 video-copy-analyzer 所需依赖和 API 配置
"""

import subprocess
import sys
import os
import json
import re
import urllib.request
import urllib.error
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
WORKSPACE_ROOT = (SCRIPT_DIR / ".." / ".." / "..").resolve()
SECRETS_PATH = WORKSPACE_ROOT / ".secrets" / "transcribe-config.json"
OPENCLAW_HOME = Path.home() / ".openclaw"

WHISPER_MODEL = "gpt-4o-mini-transcribe"


def check_command(cmd: str, *args) -> tuple[bool, str]:
    try:
        result = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=10)
        version = (result.stdout or result.stderr).strip().splitlines()[0]
        return True, version
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def load_transcribe_config() -> dict | None:
    """按优先级加载转录 API 配置"""
    # 1. formData secrets
    if SECRETS_PATH.exists():
        try:
            cfg = json.loads(SECRETS_PATH.read_text())
            api_key = cfg.get("transcribe_api_key", "").strip()
            if api_key:
                base_url = cfg.get("transcribe_base_url", "https://api.openai.com/v1").rstrip("/")
                return {"mode": "apikey", "api_key": api_key, "base_url": base_url}
        except Exception:
            pass

    # 2. 环境变量
    api_key = os.environ.get("TRANSCRIBE_API_KEY", "").strip()
    if api_key:
        base_url = os.environ.get("TRANSCRIBE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        return {"mode": "apikey", "api_key": api_key, "base_url": base_url}

    # 3. ~/.openclaw/ 运行时
    userinfo_path = OPENCLAW_HOME / "identity" / "openclaw-userinfo.json"
    config_path = OPENCLAW_HOME / "openclaw.json"
    if userinfo_path.exists():
        try:
            identity = json.loads(userinfo_path.read_text())
            uid_key = next(k for k in identity if re.search(r'uid', k, re.I))
            token_key = next(k for k in identity if re.search(r'token', k, re.I))
            uid, token = identity[uid_key], identity[token_key]
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
            if base_url:
                return {"mode": "openclaw", "uid": uid, "token": token, "base_url": base_url}
        except Exception:
            pass

    return None


def check_api(config: dict) -> tuple[bool, str]:
    try:
        if config["mode"] == "apikey":
            headers = {"Authorization": f"Bearer {config['api_key']}"}
        else:
            headers = {"X-Auth-Uid": config["uid"], "X-Auth-Token": config["token"]}
        req = urllib.request.Request(
            f"{config['base_url']}/models",
            headers=headers, method="HEAD"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 405), "OK"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 405):
            return False, f"认证失败 HTTP {e.code}，请检查 API Key"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 50)
    print("🔍 Video Copy Analyzer 环境检测")
    print("=" * 50)
    print()

    all_ok = True

    # 1. FFmpeg
    print("1️⃣  检查 FFmpeg...")
    ok, version = check_command("ffmpeg", "-version")
    if ok:
        print(f"   ✅ FFmpeg: {version[:60]}")
    else:
        print("   ❌ FFmpeg 未安装")
        if sys.platform == "win32":
            print("      安装: winget install ffmpeg")
        elif sys.platform == "darwin":
            print("      安装: brew install ffmpeg")
        else:
            print("      安装: sudo apt install ffmpeg")
        all_ok = False

    # 2. yt-dlp
    print("2️⃣  检查 yt-dlp...")
    ok, version = check_command("yt-dlp", "--version")
    if ok:
        print(f"   ✅ yt-dlp: {version}")
    else:
        print("   ❌ yt-dlp 未安装（B站/YouTube 视频下载需要）")
        print("      安装: pip install yt-dlp")
        all_ok = False

    # 3. 转录 API 配置
    print("3️⃣  检查转录 API 配置...")
    config = load_transcribe_config()
    if config:
        if config["mode"] == "apikey":
            print(f"   ✅ API Key: {config['api_key'][:8]}...")
        else:
            print(f"   ✅ OpenClaw 运行时: uid={config['uid'][:8]}...")
        print(f"   ✅ Base URL: {config['base_url']}")
    else:
        print("   ❌ 未找到转录 API 配置")
        print("      方式1: 在平台激活对话框填写 transcribe_api_key")
        print("      方式2: export TRANSCRIBE_API_KEY=sk-...")
        all_ok = False

    # 4. API 连通性
    print("4️⃣  检查 API 连通性...")
    print(f"   📌 转录模型: {WHISPER_MODEL}")
    if config:
        ok, msg = check_api(config)
        if ok:
            print("   ✅ API 可正常访问")
        else:
            print(f"   ❌ API 访问失败: {msg}")
            all_ok = False
    else:
        print("   ⚠️  跳过（API 配置未就绪）")

    print()
    print("=" * 50)
    if all_ok:
        print("✅ 所有依赖已满足，可以使用 video-copy-analyzer！")
    else:
        print("❌ 存在缺失依赖，请按上述提示安装配置")
    print("=" * 50)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
