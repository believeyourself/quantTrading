#!/usr/bin/env python3
"""
启动资金费率策略
"""

import requests
import json

def start_funding_strategy():
    """启动资金费率策略"""
    url = "http://localhost:8000/funding-arbitrage/start"
    
    try:
        response = requests.post(url, json={})
        print(f"启动策略响应: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ 策略启动成功")
        else:
            print("❌ 策略启动失败")
            
    except Exception as e:
        print(f"❌ 启动策略失败: {e}")

if __name__ == "__main__":
    start_funding_strategy() 