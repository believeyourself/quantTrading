#!/usr/bin/env python3
"""
资金费率合约池监控脚本
功能：
1. 缓存1小时结算周期合约
2. 监控资金费率 >= 0.5% 或 <= -0.5% 的合约
3. 合约池变化时发送TG消息
4. 定时更新缓存和检测
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
import threading
from datetime import datetime
from utils.binance_funding import BinanceFunding
from utils.notifier import send_telegram_message

class FundingPoolMonitor:
    """资金费率合约池监控器"""
    
    def __init__(self, threshold=0.005):  # 0.5%
        self.threshold = threshold
        self.contract_pool = set()  # 当前合约池
        self.funding = BinanceFunding()
        self.running = False
        
        # 缓存文件
        self.cache_file = "cache/funding_pool_cache.json"
        self.h1_cache_file = "cache/1h_funding_contracts_full.json"
        
        # 创建缓存目录
        os.makedirs("cache", exist_ok=True)
        
        # 加载现有池子
        self._load_pool_cache()
    
    def _load_pool_cache(self):
        """加载合约池缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.contract_pool = set(data.get('contracts', []))
                print(f"📋 加载合约池缓存: {len(self.contract_pool)} 个合约")
            except Exception as e:
                print(f"⚠️ 加载缓存失败: {e}")
                self.contract_pool = set()
    
    def _save_pool_cache(self):
        """保存合约池缓存"""
        data = {
            'contracts': list(self.contract_pool),
            'last_update': datetime.now().isoformat(),
            'threshold': self.threshold
        }
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def update_h1_contracts_cache(self):
        """更新1小时结算合约缓存"""
        print("🔄 更新1小时结算合约缓存...")
        try:
            contracts = self.funding.update_1h_contracts_cache()
            if contracts:
                print(f"✅ 缓存更新成功: {len(contracts)} 个1小时结算合约")
                return True
            else:
                print("❌ 缓存更新失败")
                return False
        except Exception as e:
            print(f"❌ 缓存更新异常: {e}")
            return False
    
    def scan_qualified_contracts(self):
        """扫描符合条件的合约"""
        print(f"🔍 扫描资金费率 >= {self.threshold:.4%} 的合约...")
        
        # 获取1小时结算合约
        h1_contracts = self.funding.get_1h_contracts_from_cache()
        
        if not h1_contracts:
            print("⚠️ 没有1小时结算合约缓存，开始扫描...")
            h1_contracts = self.funding.scan_1h_funding_contracts(contract_type="UM")
        
        if not h1_contracts:
            print("❌ 无法获取1小时结算合约")
            return {}
        
        print(f"📊 检测 {len(h1_contracts)} 个1小时结算合约")
        
        # 检测资金费率
        qualified_contracts = {}
        
        for i, symbol in enumerate(h1_contracts.keys()):
            try:
                info = self.funding.get_comprehensive_info(symbol, "UM")
                if info and info.get('current_funding_rate'):
                    rate = float(info['current_funding_rate'])
                    if abs(rate) >= self.threshold:
                        qualified_contracts[symbol] = info
                        direction = "做多" if rate > 0 else "做空"
                        print(f"  ✅ {symbol}: {rate:.4%} ({direction})")
                
                # 限流控制
                if (i + 1) % 20 == 0:
                    print(f"    进度: {i + 1}/{len(h1_contracts)}")
                    time.sleep(0.5)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                if "rate limit" in str(e).lower():
                    print(f"  ⚠️ {symbol}: 限流，跳过")
                    time.sleep(1)
                else:
                    print(f"  ❌ {symbol}: 检测失败 - {e}")
                continue
        
        return qualified_contracts
    
    def update_contract_pool(self):
        """更新合约池"""
        print("🔄 更新合约池...")
        
        # 扫描符合条件的合约
        qualified_contracts = self.scan_qualified_contracts()
        
        # 更新池子
        new_pool = set(qualified_contracts.keys())
        
        # 检查变化
        added_contracts = new_pool - self.contract_pool
        removed_contracts = self.contract_pool - new_pool
        
        # 发送变化通知
        if added_contracts or removed_contracts:
            self._send_pool_change_notification(added_contracts, removed_contracts, qualified_contracts)
        
        # 更新池子
        self.contract_pool = new_pool
        self._save_pool_cache()
        
        # 发送状态通知
        self._send_pool_status_notification(qualified_contracts)
        
        print(f"✅ 合约池更新完成: {len(self.contract_pool)} 个合约")
        return added_contracts, removed_contracts
    
    def _send_pool_change_notification(self, added_contracts, removed_contracts, qualified_contracts):
        """发送池子变化通知"""
        message = f"🔄 资金费率合约池变化通知\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📊 阈值: {self.threshold:.4%}\n\n"
        
        if added_contracts:
            message += f"🟢 新增合约 ({len(added_contracts)}个):\n"
            for symbol in added_contracts:
                info = qualified_contracts[symbol]
                rate = info.get('current_funding_rate', 'N/A')
                direction = "做多" if float(rate) > 0 else "做空"
                message += f"  • {symbol}: {rate:.4%} ({direction})\n"
            message += "\n"
        
        if removed_contracts:
            message += f"🔴 移除合约 ({len(removed_contracts)}个):\n"
            for symbol in removed_contracts:
                message += f"  • {symbol}\n"
            message += "\n"
        
        send_telegram_message(message)
    
    def _send_pool_status_notification(self, qualified_contracts):
        """发送池子状态通知"""
        if self.contract_pool:
            message = f"📊 当前资金费率合约池状态\n"
            message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"📈 合约数量: {len(self.contract_pool)}个\n"
            message += f"🎯 阈值: {self.threshold:.4%}\n\n"
            
            # 按资金费率排序显示
            pool_contracts = []
            for symbol in self.contract_pool:
                info = qualified_contracts.get(symbol, {})
                rate = info.get('current_funding_rate', 0)
                if rate is not None:
                    pool_contracts.append((symbol, float(rate)))
            
            # 按绝对值排序
            pool_contracts.sort(key=lambda x: abs(x[1]), reverse=True)
            
            for symbol, rate in pool_contracts:
                direction = "做多" if rate > 0 else "做空"
                message += f"  • {symbol}: {rate:.4%} ({direction})\n"
        else:
            message = f"📊 资金费率合约池状态\n"
            message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"📈 合约数量: 0个\n"
            message += f"🎯 阈值: {self.threshold:.4%}\n"
            message += f"💡 当前没有合约满足条件"
        
        send_telegram_message(message)
    
    def start_monitoring(self, scan_interval=1800, cache_update_interval=21600):
        """开始监控"""
        print("🚀 开始资金费率合约池监控")
        print(f"📊 阈值: {self.threshold:.4%}")
        print(f"⏰ 扫描间隔: {scan_interval}秒")
        print(f"🔄 缓存更新间隔: {cache_update_interval}秒")
        print("=" * 60)
        
        self.running = True
        
        # 启动扫描线程
        def scan_loop():
            while self.running:
                try:
                    self.update_contract_pool()
                    time.sleep(scan_interval)
                except Exception as e:
                    print(f"❌ 扫描异常: {e}")
                    time.sleep(60)
        
        # 启动缓存更新线程
        def cache_update_loop():
            while self.running:
                try:
                    self.update_h1_contracts_cache()
                    time.sleep(cache_update_interval)
                except Exception as e:
                    print(f"❌ 缓存更新异常: {e}")
                    time.sleep(3600)
        
        # 启动线程
        scan_thread = threading.Thread(target=scan_loop, daemon=True)
        cache_thread = threading.Thread(target=cache_update_loop, daemon=True)
        
        scan_thread.start()
        cache_thread.start()
        
        try:
            # 主循环
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️ 监控已停止")
            self.running = False
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False

def main():
    """主函数"""
    print("🚀 资金费率合约池监控器")
    print("=" * 60)
    
    # 配置参数
    threshold = 0.005  # 0.5%
    scan_interval = 1800  # 30分钟
    cache_update_interval = 21600  # 6小时
    
    print(f"📊 配置参数:")
    print(f"  资金费率阈值: {threshold:.4%}")
    print(f"  扫描间隔: {scan_interval}秒 ({scan_interval//60}分钟)")
    print(f"  缓存更新间隔: {cache_update_interval}秒 ({cache_update_interval//3600}小时)")
    
    # 创建监控器
    monitor = FundingPoolMonitor(threshold=threshold)
    
    # 选择模式
    print("\n请选择运行模式:")
    print("1. 单次扫描")
    print("2. 持续监控")
    
    choice = input("请输入选择 (1/2): ").strip()
    
    if choice == "1":
        print("\n🔍 执行单次扫描...")
        added, removed = monitor.update_contract_pool()
        print(f"✅ 扫描完成")
        print(f"  新增: {len(added)} 个合约")
        print(f"  移除: {len(removed)} 个合约")
        print(f"  当前池子: {len(monitor.contract_pool)} 个合约")
        
    elif choice == "2":
        print("\n🚀 开始持续监控...")
        monitor.start_monitoring(scan_interval, cache_update_interval)
        
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main() 