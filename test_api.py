#!/usr/bin/env python3
"""
API服务测试脚本
"""

import requests
import time
import sys

def test_api_health():
    """测试API健康状态"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API服务正常运行")
            return True
        else:
            print(f"❌ API服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到API服务，请确保API服务已启动")
        return False
    except Exception as e:
        print(f"❌ 测试API服务时出错: {e}")
        return False

def test_api_endpoints():
    """测试API端点"""
    base_url = "http://localhost:8000"
    
    endpoints = [
        "/strategies",
        "/strategies/available",
        "/data/symbols",
        "/config"
    ]
    
    print("\n测试API端点:")
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {endpoint} - 正常")
            else:
                print(f"❌ {endpoint} - 错误: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} - 异常: {e}")

def main():
    print("量化交易系统API测试")
    print("=" * 50)
    
    # 测试健康状态
    if not test_api_health():
        print("\n请先启动API服务:")
        print("python start_api.py")
        sys.exit(1)
    
    # 测试API端点
    test_api_endpoints()
    
    print("\n✅ API服务测试完成！")
    print("现在可以启动Web界面: python start_web.py")

if __name__ == "__main__":
    main() 