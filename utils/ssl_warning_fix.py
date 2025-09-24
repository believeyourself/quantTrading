#!/usr/bin/env python3
"""
SSL警告修复工具
用于禁用urllib3的SSL证书验证警告
"""
import urllib3

# 禁用urllib3的SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("✅ SSL警告已禁用")
