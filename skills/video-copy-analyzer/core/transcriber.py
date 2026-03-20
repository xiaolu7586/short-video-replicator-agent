"""语音转录模块"""

import subprocess
import sys
from pathlib import Path


def transcribe_video(video_path: Path, output_srt: Path) -> None:
    script_path = Path(__file__).parent.parent / "scripts" / "transcribe_api.py"

    cmd = [sys.executable, str(script_path), str(video_path), str(output_srt)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"转录失败: {result.stderr}")

    if not output_srt.exists():
        raise RuntimeError("未找到生成的字幕文件")
