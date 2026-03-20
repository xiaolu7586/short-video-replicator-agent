# 短视频复刻助手

> OpenClaw Agent 配置 — 可用于任何兼容 OpenClaw 协议的 AI 产品

## 简介

输入一个短视频链接，自动完成下载、转录、三维度文案拆解，并生成去 AI 味的二创文案。支持抖音、B 站、YouTube 等主流平台。

## 核心功能

- 🎬 **多平台视频下载** — 抖音（内置）/ B 站 / YouTube（需 yt-dlp）
- 🎤 **语音自动转录** — 生成带时间轴的 SRT 字幕 + 结构化文字稿
- 📊 **三维度文案拆解** — 叙事结构 / Viral-5D 诊断 / 创意头脑风暴
- ✍️ **去 AI 味二创** — 基于分析结论，生成可直接拍摄的新文案

---

## 🚀 零配置启动

以下功能**无需任何配置**即可使用：

> 三维度文案分析 · 文案二创 · 抖音视频内置下载

向 Agent 发送视频链接或分享文本即可开始。

---

## ✨ 可选增强能力

### 增强 1：语音转录（音视频 → 文字稿）

配置后可解锁：自动将视频音频转为文字稿，完成完整的「下载 → 转录 → 分析 → 二创」流程。

Agent 内置以下可选配置项：

| 配置项 | 说明 |
|--------|------|
| 转录 API Key | OpenAI Whisper 或兼容服务的 API Key |
| 转录 API Base URL | 留空默认使用 OpenAI 官方接口 |

在 `.secrets/transcribe-config.json` 中填写：

```json
{
  "transcribe_api_key": "sk-...",
  "transcribe_base_url": "https://api.openai.com/v1"
}
```

### 增强 2：B 站 / YouTube 视频下载

**需要：** yt-dlp

```bash
pip install yt-dlp
# 或
brew install yt-dlp
```

安装后即可直接粘贴 B 站 / YouTube 链接，Agent 自动处理。

### 增强 3：视频音频提取（大文件处理）

**需要：** ffmpeg

```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Linux
winget install ffmpeg      # Windows
```

---

## 工作流

```
视频链接
  ↓
阶段 1-3（main.py）: 下载 → 转录 → 生成文字稿
  ↓
阶段 4（Agent LLM）: 校正 + 结构化 → _structured.md
  ↓
阶段 5（Agent LLM）: 三维度分析 → 会话输出
  ↓
阶段 6（Agent LLM）: 文案二创 → 会话输出
```

输出文件保存在 `canvas/` 目录下。

---

## Skills

| Skill | 功能 |
|-------|------|
| `video-copy-analyzer` | 视频下载 + 转录 + 文字稿生成 |

---

## 快速开始

```
# 抖音（无需额外工具）
发送：https://v.douyin.com/xxxxx

# 分享文本（自动提取链接）
发送：3.00 复制此链接 https://v.douyin.com/xxxxx 打开抖音

# B 站（需要 yt-dlp）
发送：https://www.bilibili.com/video/BVxxxxxx

# 本地文件
发送：/path/to/video.mp4
```

## 环境检测

```bash
python skills/video-copy-analyzer/scripts/check_environment.py
```
