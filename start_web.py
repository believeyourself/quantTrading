#!/usr/bin/env python3
"""
Web界面启动脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web.interface import app

if __name__ == "__main__":
    print("启动量化交易系统Web界面...")
    print("访问地址: http://localhost:8050")
    print("按 Ctrl+C 停止服务")
    
    app.run(
        debug=True,
        host="0.0.0.0",
        port=8050
    ) 