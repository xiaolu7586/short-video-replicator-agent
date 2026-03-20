#!/usr/bin/env python3
"""测试抖音链接提取功能"""

from download_douyin import extract_douyin_url_from_text, is_douyin_url

# 测试用例
test_cases = [
    "https://v.douyin.com/AeAMPZtCygA/",
    "3.00 12/31 以色列是怎样的国家 https://v.douyin.com/AeAMPZtCygA/ 复制此链接",
    "CuF:/ X@Z.zg # 以色列 # 中东  https://v.douyin.com/AeAMPZtCygA/ 打开Dou音搜索",
    "纯文本没有链接",
    "https://www.douyin.com/video/7123456789012345678",
]

print("=" * 60)
print("抖音链接提取测试")
print("=" * 60)

for i, text in enumerate(test_cases, 1):
    print(f"\n测试 {i}:")
    print(f"  输入: {text[:50]}...")

    url = extract_douyin_url_from_text(text)

    if url:
        is_valid = is_douyin_url(url)
        print(f"  提取: {url}")
        print(f"  验证: {'✓ 有效' if is_valid else '✗ 无效'}")
    else:
        print(f"  结果: 未提取到链接")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
