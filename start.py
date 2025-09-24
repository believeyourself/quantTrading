#!/usr/bin/env python3
"""
加密货币资金费率监控系统 - 统一启动脚本
"""

import sys
import os
import subprocess
import multiprocessing
import time
import signal

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入SSL警告修复（必须在其他模块之前导入）
try:
    from utils.ssl_warning_fix import *
except ImportError:
    # 如果导入失败，直接在这里禁用警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def start_web():
    """启动Web界面"""
    print("🌐 启动Web界面...")
    print("访问地址: http://localhost:8050")
    print("按 Ctrl+C 停止服务")
    
    from web.interface import app
    # 在子进程中运行时不使用debug模式，避免信号处理问题
    app.run(debug=False, host="0.0.0.0", port=8050)

def start_api():
    """启动API服务"""
    print("🔌 启动API服务...")
    from config.settings import settings
    print(f"API地址: http://localhost:{settings.API_PORT}")
    print("按 Ctrl+C 停止服务")
    
    import uvicorn
    # 在子进程中运行时不使用reload模式，避免信号处理问题
    uvicorn.run("api.routes:app", host=settings.API_HOST, port=settings.API_PORT, reload=False)

def start_main():
    """启动主程序（监控系统）"""
    print("🚀 启动主程序（监控系统）...")
    print("按 Ctrl+C 停止服务")
    
    subprocess.run([sys.executable, "main.py"])

def start_all():
    """同时启动所有服务"""
    print("🚀 启动所有服务...")
    from config.settings import settings
    print(f"API服务: http://localhost:{settings.API_PORT}")
    print("Web界面: http://localhost:8050")
    print("主程序: 监控系统（包含定时任务）")
    print("Telegram机器人: 轮询模式（日志写入 logs/telegram_bot.log）")
    print("按 Ctrl+C 停止所有服务")
    
    # 使用multiprocessing而不是threading来避免信号处理问题
    processes = []
    bot_subprocs = []
    
    def signal_handler(signum, frame):
        """信号处理器"""
        print(f"\n收到信号 {signum}，正在停止所有服务...")
        # 终止机器人子进程
        for p in bot_subprocs:
            try:
                if p.poll() is None:
                    print(f"正在停止Telegram机器人进程 {p.pid}...")
                    p.terminate()
                    p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        # 终止所有子进程
        for process in processes:
            if process.is_alive():
                print(f"正在停止进程 {process.pid}...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    print(f"强制终止进程 {process.pid}...")
                    process.kill()
        print("所有服务已停止")
        sys.exit(0)
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动API服务
        api_process = multiprocessing.Process(target=start_api)
        api_process.start()
        processes.append(api_process)
        print("✅ API服务已启动")
        time.sleep(3)  # 等待API服务启动
        
        # 启动主程序（监控系统，包含定时任务）
        main_process = multiprocessing.Process(target=start_main)
        main_process.start()
        processes.append(main_process)
        print("✅ 主程序已启动（包含定时任务）")
        time.sleep(2)  # 等待主程序启动
        
        # 启动Telegram机器人（子进程，日志重定向）
        try:
            os.makedirs("logs", exist_ok=True)
            bot_log_path = os.path.join("logs", "telegram_bot.log")
            bot_log = open(bot_log_path, "a", encoding="utf-8", buffering=1)
            print(f"🧩 启动Telegram机器人，日志：{bot_log_path}")
            bot_proc = subprocess.Popen(
                [sys.executable, "-m", "utils.telegram_polling_bot"],
                stdout=bot_log,
                stderr=bot_log,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                shell=False,
            )
            bot_subprocs.append(bot_proc)
            print(f"✅ Telegram机器人已启动 (PID={bot_proc.pid})")
        except Exception as e:
            print(f"⚠️ 启动Telegram机器人失败: {e}")

        # 启动Web界面
        web_process = multiprocessing.Process(target=start_web)
        web_process.start()
        processes.append(web_process)
        print("✅ Web界面已启动")
        
        # 等待所有进程
        for process in processes:
            process.join()
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        # 清理机器人子进程
        for p in bot_subprocs:
            try:
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        # 清理进程
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
        sys.exit(1)

def show_menu():
    """显示启动菜单"""
    print("=" * 60)
    print("🚀 加密货币资金费率监控系统")
    print("=" * 60)
    print("请选择启动模式:")
    print("1. 🌐 Web界面 (端口8050)")
    print("2. 🔌 API服务 (端口8000)")
    print("3. 🚀 主程序 (监控系统)")
    print("4. 🎯 全部启动 (Web + API + 主程序)")
    print("5. ❌ 退出")
    print("=" * 60)

def main():
    """主函数"""
    # 设置multiprocessing启动方法
    multiprocessing.set_start_method('spawn', force=True)
    
    if len(sys.argv) > 1:
        # 命令行参数模式
        mode = sys.argv[1].lower()
        if mode in ['web', 'w']:
            start_web()
        elif mode in ['api', 'a']:
            start_api()
        elif mode in ['main', 'm']:
            start_main()
        elif mode in ['all', 'all']:
            start_all()
        else:
            print(f"未知模式: {mode}")
            print("支持的模式:")
            print("  web, w  - Web界面")
            print("  api, a  - API服务")
            print("  main, m - 主程序（监控系统）")
            print("  all     - 全部启动（Web + API + 主程序）")
            sys.exit(1)
    else:
        # 默认启动所有服务
        print("🚀 默认启动所有服务...")
        print("启动模式: 全部启动 (Web + API + 主程序)")
        start_all()

if __name__ == "__main__":
    main()
