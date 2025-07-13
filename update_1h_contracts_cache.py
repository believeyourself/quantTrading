#!/usr/bin/env python3
"""
定时更新1小时结算合约缓存脚本
独立进程运行，每小时自动刷新缓存
"""
import sys
import os
import time
import signal
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.binance_funding import BinanceFunding
from utils.notifier import send_telegram_message

class CacheUpdater:
    def __init__(self):
        self.funding = BinanceFunding()
        self.running = True
        self.update_interval = 3600  # 1小时更新一次
        
        # 注册信号处理器，优雅退出
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """信号处理器，优雅退出"""
        print(f"\n📴 收到退出信号 {signum}，正在停止缓存更新进程...")
        self.running = False
    
    def update_cache(self):
        """更新1小时结算合约缓存"""
        try:
            print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始更新1小时结算合约缓存...")
            
            # 强制刷新缓存
            contracts = self.funding.scan_1h_funding_contracts(force_refresh=True)
            
            if contracts:
                msg = f"✅ 缓存更新成功！找到 {len(contracts)} 个1小时结算合约"
                print(msg)
                try:
                    send_telegram_message(msg)
                except Exception as e:
                    print(f"⚠️ 发送成功通知失败: {e}")
            else:
                msg = "⚠️ 缓存更新完成，但未找到1小时结算合约"
                print(msg)
                try:
                    send_telegram_message(msg)
                except Exception as e:
                    print(f"⚠️ 发送警告通知失败: {e}")
                    
        except Exception as e:
            error_msg = f"❌ 缓存更新失败: {e}"
            print(error_msg)
            try:
                send_telegram_message(error_msg)
            except Exception as notify_e:
                print(f"❌ 发送错误通知失败: {notify_e}")
    
    def run(self):
        """主运行循环"""
        print("🚀 1小时结算合约缓存更新进程启动")
        print(f"⏰ 更新间隔: {self.update_interval/3600:.1f}小时")
        print("📱 异常情况将发送Telegram通知")
        print("🛑 按 Ctrl+C 停止进程")
        print("=" * 60)
        
        # 启动时立即更新一次
        self.update_cache()
        
        while self.running:
            try:
                # 等待下次更新
                print(f"⏳ 等待下次更新... ({self.update_interval/3600:.1f}小时后)")
                time.sleep(self.update_interval)
                
                if self.running:
                    self.update_cache()
                    
            except KeyboardInterrupt:
                print("\n🛑 用户中断，正在退出...")
                break
            except Exception as e:
                print(f"❌ 运行异常: {e}")
                try:
                    send_telegram_message(f"❌ 缓存更新进程异常: {e}")
                except:
                    pass
                time.sleep(60)  # 异常后等待1分钟再继续
        
        print("👋 缓存更新进程已停止")

def main():
    """主函数"""
    updater = CacheUpdater()
    updater.run()

if __name__ == "__main__":
    main() 