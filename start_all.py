#!/usr/bin/env python3
"""
同时启动API服务和Web界面的脚本
"""

import subprocess
import sys
import os
import time
import threading

def start_api_server():
    """启动API服务"""
    print("启动API服务...")
    subprocess.run([sys.executable, "start_api.py"])

def start_web_server():
    """启动Web界面"""
    print("启动Web界面...")
    subprocess.run([sys.executable, "start_web.py"])

if __name__ == "__main__":
    print("启动量化交易系统...")
    print("API服务: http://localhost:8000 (包含资金费率套利)")
    print("Web界面: http://localhost:8050")
    print("按 Ctrl+C 停止所有服务")
    
    # 创建两个线程分别启动服务
    api_thread = threading.Thread(target=start_api_server)
    web_thread = threading.Thread(target=start_web_server)
    
    try:
        # 启动API服务
        api_thread.start()
        time.sleep(2)  # 等待API服务启动
        
        # 启动Web界面
        web_thread.start()
        
        # 等待两个服务
        api_thread.join()
        web_thread.join()
        
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        sys.exit(0) 