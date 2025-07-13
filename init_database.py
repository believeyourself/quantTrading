#!/usr/bin/env python3
"""
数据库初始化脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.models import init_db

if __name__ == "__main__":
    print("正在初始化数据库...")
    try:
        init_db()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}") 