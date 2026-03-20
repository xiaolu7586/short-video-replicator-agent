#!/usr/bin/env python3
"""
抖音视频下载脚本
支持从抖音分享链接或分享文本中提取并下载视频（无水印版本）

✨ 增强功能: 自动从分享文本中提取链接

使用方法:
    python download_douyin.py <抖音链接或分享文本> <输出路径>

示例:
    # 方式1: 纯链接
    python download_douyin.py "https://v.douyin.com/xxxxx" ./video.mp4

    # 方式2: 完整分享文本（自动提取链接）
    python download_douyin.py "3.00 12/31 以色列 https://v.douyin.com/xxxxx 打开抖音" ./video.mp4
"""

import requests
import re
import json
import sys
import os
from urllib.parse import unquote, urlparse

# Windows CMD 编码修复：设置 UTF-8 输出
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python 3.6 及以下版本
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def extract_douyin_url_from_text(text: str) -> str:
    """
    从分享文本中提取抖音链接

    支持格式:
    - 纯链接: https://v.douyin.com/xxxxx
    - 分享文本: "3.00 12/31 复制此链接 https://v.douyin.com/xxxxx 打开抖音"
    - 混合文本: 包含标题、标签、链接的完整分享文本

    返回提取到的第一个有效抖音链接，如果没有则返回None
    """
    # 抖音链接的正则模式（匹配完整URL）
    url_pattern = r'https?://(?:v\.douyin\.com|www\.douyin\.com|m\.douyin\.com)/[A-Za-z0-9]+/?'

    match = re.search(url_pattern, text)
    if match:
        url = match.group(0)
        print(f"ℹ️  从分享文本中提取到链接: {url}")
        return url

    # 如果没找到完整URL，尝试查找 douyin.com/video/ 格式
    video_pattern = r'https?://(?:www\.)?douyin\.com/video/\d+'
    match = re.search(video_pattern, text)
    if match:
        url = match.group(0)
        print(f"ℹ️  从分享文本中提取到链接: {url}")
        return url

    return None


def is_douyin_url(url: str) -> bool:
    """检查是否为抖音链接"""
    douyin_patterns = [
        r'v\.douyin\.com',
        r'www\.douyin\.com',
        r'm\.douyin\.com',
        r'douyin\.com/video/',
        r'douyin\.com/jingxuan',
    ]
    return any(re.search(pattern, url) for pattern in douyin_patterns)


def extract_video_id(url: str) -> str:
    """从抖音链接中提取视频ID"""
    # 尝试从各种格式的链接中提取ID
    patterns = [
        r'/video/(\d+)',
        r'modal_id=(\d+)',
        r'share/video/(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # 如果是短链接，返回None，需要获取重定向后的URL
    return None


def get_redirect_url(short_url: str) -> tuple:
    """获取重定向后的完整URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    try:
        response = requests.get(short_url, headers=headers, allow_redirects=True, timeout=10)
        return response.url, headers['User-Agent'], response.text
    except Exception as e:
        print(f"✗ 获取重定向URL失败: {e}")
        return None, None, None


def extract_render_data(html: str) -> dict:
    """从HTML中提取RENDER_DATA"""
    # 尝试多种可能的模式
    patterns = [
        r'<script id="RENDER_DATA" type="application/json">([^<]+)</script>',
        r'window\._ROUTER_DATA\s*=\s*(\{.+?\});?\s*</script>',
        r'window\._SSR_DATA\s*=\s*(\{.+?\});?\s*</script>',
        r'window\._SSR_HYDRATED_DATA\s*=\s*(\{.+?\});?\s*</script>',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            data_str = matches[0]
            # URL解码
            if '%' in data_str:
                data_str = unquote(data_str)
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                continue

    return None


def extract_video_url(data: dict) -> str:
    """从RENDER_DATA中提取视频URL"""

    def get_nested(obj, path):
        """安全地获取嵌套字典/列表值"""
        current = obj
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(key, int) and key < len(current):
                current = current[key]
            else:
                return None
        return current

    # 尝试多种可能的路径
    possible_paths = [
        ['loaderData', 'video_(id)/page', 'videoInfoRes', 'item_list', 0, 'video', 'play_addr', 'url_list'],
        ['loaderData', 'video_(id)/page', 'aweme_detail', 'video', 'play_addr', 'url_list'],
        ['videoInfoRes', 'item_list', 0, 'video', 'play_addr', 'url_list'],
        ['app', 'videoInfoRes', 'item_list', 0, 'video', 'play_addr', 'url_list'],
        ['app', 'videoDetail', 'video', 'play_addr', 'url_list'],
        ['video', 'play_addr', 'url_list'],
        ['aweme_detail', 'video', 'play_addr', 'url_list'],
    ]

    for path in possible_paths:
        url_list = get_nested(data, path)
        if url_list and isinstance(url_list, list) and len(url_list) > 0:
            video_url = url_list[0]
            # 替换playwm为play获取无水印版本
            video_url = video_url.replace('playwm', 'play')
            return video_url

    # 如果路径查找失败，尝试正则搜索
    json_str = json.dumps(data)
    play_patterns = [
        r'"play_addr":\s*\{[^}]*"url_list":\s*\["([^"]+)"',
        r'"playAddr":\s*\["([^"]+)"',
        r'"download_addr":\s*\{[^}]*"url_list":\s*\["([^"]+)"',
    ]

    for pattern in play_patterns:
        matches = re.findall(pattern, json_str)
        if matches:
            video_url = matches[0].replace('playwm', 'play')
            return video_url

    return None


def download_video(video_url: str, output_path: str, user_agent: str) -> bool:
    """下载视频"""
    headers = {
        'User-Agent': user_agent,
        'Referer': 'https://www.douyin.com/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    try:
        response = requests.get(video_url, headers=headers, stream=True, timeout=60)

        if response.status_code not in [200, 206]:
            print(f"✗ 下载失败，状态码: {response.status_code}")
            return False

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r进度: {percent:.1f}% ({downloaded:,}/{total_size:,} bytes)", end='', flush=True)

        print()  # 换行
        return True

    except Exception as e:
        print(f"✗ 下载视频时出错: {e}")
        return False


def download_douyin_video(url: str, output_path: str) -> bool:
    """
    下载抖音视频的主函数

    Args:
        url: 抖音视频链接（支持短链接和长链接）
        output_path: 输出文件路径

    Returns:
        bool: 下载是否成功
    """
    print(f"🎬 开始下载抖音视频")
    print(f"   链接: {url}")
    print(f"   输出: {output_path}")
    print()

    # 步骤1: 获取重定向URL和页面内容
    print("步骤 1/4: 获取页面信息...")
    full_url, user_agent, html = get_redirect_url(url)
    if not full_url:
        return False
    print(f"✓ 获取到页面 ({len(html):,} 字符)")

    # 步骤2: 提取RENDER_DATA
    print("\n步骤 2/4: 提取视频数据...")
    render_data = extract_render_data(html)
    if not render_data:
        print("✗ 无法提取视频数据")
        return False
    print("✓ 提取到视频数据")

    # 步骤3: 提取视频URL
    print("\n步骤 3/4: 解析视频地址...")
    video_url = extract_video_url(render_data)
    if not video_url:
        print("✗ 无法获取视频下载地址")
        return False
    print(f"✓ 获取到视频地址")

    # 步骤4: 下载视频
    print("\n步骤 4/4: 下载视频...")
    success = download_video(video_url, output_path, user_agent)

    if success:
        file_size = os.path.getsize(output_path)
        print(f"✓ 下载完成: {file_size:,} bytes")
        return True
    else:
        return False


def main():
    if len(sys.argv) < 3:
        print("用法: python download_douyin.py <抖音链接或分享文本> <输出路径>")
        print()
        print("支持格式:")
        print("  1. 纯链接:   https://v.douyin.com/xxxxx")
        print("  2. 分享文本: '3.00 12/31 复制此链接 https://v.douyin.com/xxxxx 打开抖音'")
        print()
        print("示例:")
        print("  python download_douyin.py 'https://v.douyin.com/xxxxx' ./video.mp4")
        print("  python download_douyin.py '复制链接 https://v.douyin.com/xxxxx' ./video.mp4")
        sys.exit(1)

    input_text = sys.argv[1]
    output_path = sys.argv[2]

    # 尝试从输入文本中提取抖音链接
    url = extract_douyin_url_from_text(input_text)

    # 如果提取失败，尝试将输入文本本身作为URL
    if not url:
        url = input_text

    # 检查是否为抖音链接
    if not is_douyin_url(url):
        print(f"✗ 未找到有效的抖音链接")
        print(f"   输入: {input_text[:100]}...")
        sys.exit(1)

    success = download_douyin_video(url, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
