#!/usr/bin/env python3
"""
API服务启动脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.routes import app
from config.settings import settings

if __name__ == "__main__":
    print("启动量化交易系统API服务...")
    print(f"API地址: http://{settings.API_HOST}:{settings.API_PORT}")
    print("按 Ctrl+C 停止服务")
    
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.API_HOST, 
        port=settings.API_PORT,
        reload=True
    ) 