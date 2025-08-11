#!/usr/bin/env python3
"""
资金费率合约池监控脚本
功能：
1. 缓存所有结算周期的合约
2. 监控资金费率 >= 0.5% 或 <= -0.5% 的合约
3. 合约池变化时发送TG消息
4. 手动更新缓存和检测
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
        self.all_contracts_cache_file = "cache/all_funding_contracts_full.json"
        
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
    
    def update_all_contracts_cache(self):
        """更新所有结算周期合约缓存"""
        print("🔄 更新所有结算周期合约缓存...")
        try:
            contracts_by_interval = self.funding.update_all_contracts_cache()
            if contracts_by_interval:
                total_contracts = sum(len(contracts) for contracts in contracts_by_interval.values())
                print(f"✅ 缓存更新成功: 总计 {total_contracts} 个合约")
                for interval, contracts in contracts_by_interval.items():
                    print(f"  {interval}: {len(contracts)} 个合约")
                return True
            else:
                print("❌ 缓存更新失败")
                return False
        except Exception as e:
            print(f"❌ 缓存更新异常: {e}")
            return False
    
    def update_h1_contracts_cache(self):
        """更新1小时结算合约缓存（保持向后兼容）"""
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
        
        # 获取所有结算周期合约
        all_contracts = self.funding.get_all_intervals_from_cache()
        
        if not all_contracts or not all_contracts.get('contracts_by_interval'):
            print("⚠️ 没有合约缓存，开始扫描...")
            contracts_by_interval = self.funding.scan_all_funding_contracts(contract_type="UM")
            if not contracts_by_interval:
                print("❌ 无法获取合约数据")
                return {}
        else:
            contracts_by_interval = all_contracts['contracts_by_interval']
        
        # 统计各结算周期的合约数量
        total_contracts = 0
        for interval, contracts in contracts_by_interval.items():
            total_contracts += len(contracts)
            print(f"📊 {interval}结算周期: {len(contracts)} 个合约")
        
        print(f"📊 总计检测 {total_contracts} 个合约")
        
        # 检测资金费率
        qualified_contracts = {}
        
        for interval, contracts in contracts_by_interval.items():
            print(f"🔍 检测 {interval} 结算周期合约...")
            
            for i, (symbol, contract_info) in enumerate(contracts.items()):
                try:
                    # 获取最新资金费率
                    info = self.funding.get_comprehensive_info(symbol, "UM")
                    if info and info.get('current_funding_rate'):
                        funding_rate = info['current_funding_rate']
                        if abs(funding_rate) >= self.threshold:
                            qualified_contracts[symbol] = info
                            print(f"✅ {symbol} ({interval}): {funding_rate:.4%}")
                        else:
                            print(f"❌ {symbol} ({interval}): {funding_rate:.4%} (低于阈值)")
                    else:
                        print(f"⚠️ {symbol} ({interval}): 无法获取资金费率")
                    
                    # 添加延迟避免API限流
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"❌ {symbol} ({interval}): 检测异常 - {e}")
                    continue
                
                # 进度显示
                if (i + 1) % 20 == 0:
                    print(f"    进度: {i + 1}/{len(contracts)} ({interval})")
        
        print(f"🎯 符合条件的合约: {len(qualified_contracts)} 个")
        return qualified_contracts
    
    def update_contract_pool(self, force_refresh=False):
        """更新合约池"""
        print("🔄 更新合约池...")
        
        # 扫描符合条件的合约
        qualified_contracts = self.scan_qualified_contracts()
        
        if not qualified_contracts:
            print("⚠️ 没有符合条件的合约")
            # 清空池子
            old_pool = self.contract_pool.copy()
            self.contract_pool.clear()
            self._save_pool_cache()
            
            if old_pool:
                self._send_pool_change_notification(set(), old_pool, {})
            return set(), old_pool
        
        # 获取新的合约池
        new_pool = set(qualified_contracts.keys())
        
        # 计算变化
        added_contracts = new_pool - self.contract_pool
        removed_contracts = self.contract_pool - new_pool
        
        # 更新池子
        old_pool = self.contract_pool.copy()
        self.contract_pool = new_pool
        self._save_pool_cache()
        
        # 发送通知
        if added_contracts or removed_contracts:
            self._send_pool_change_notification(added_contracts, removed_contracts, qualified_contracts)
        else:
            self._send_pool_status_notification(qualified_contracts)
        
        print(f"✅ 合约池更新完成")
        print(f"  新增: {len(added_contracts)} 个")
        print(f"  移除: {len(removed_contracts)} 个")
        print(f"  当前: {len(self.contract_pool)} 个")
        
        return added_contracts, removed_contracts
    
    def _send_pool_change_notification(self, added_contracts, removed_contracts, qualified_contracts):
        """发送池子变化通知"""
        message = f"🔄 资金费率合约池变化通知\n"
        message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📈 新增合约: {len(added_contracts)} 个\n"
        message += f"📉 移除合约: {len(removed_contracts)} 个\n"
        message += f"🎯 当前池子: {len(qualified_contracts)} 个\n"
        message += f"💡 阈值: {self.threshold:.4%}\n"
        
        if added_contracts:
            message += f"\n➕ 新增:\n"
            for symbol in sorted(added_contracts):
                info = qualified_contracts.get(symbol, {})
                funding_rate = info.get('current_funding_rate', 'N/A')
                interval = info.get('funding_interval_hours', 'N/A')
                if interval:
                    interval_str = f"{interval:.1f}h"
                else:
                    interval_str = "N/A"
                message += f"  {symbol} ({interval_str}): {funding_rate:.4%}\n"
        
        if removed_contracts:
            message += f"\n➖ 移除:\n"
            for symbol in sorted(removed_contracts):
                message += f"  {symbol}\n"
        
        send_telegram_message(message)
    
    def _send_pool_status_notification(self, qualified_contracts):
        """发送池子状态通知"""
        if qualified_contracts:
            message = f"📊 资金费率合约池状态\n"
            message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"📈 合约数量: {len(qualified_contracts)}个\n"
            message += f"🎯 阈值: {self.threshold:.4%}\n"
            message += f"\n📋 当前合约:\n"
            
            # 按资金费率排序
            sorted_contracts = sorted(
                qualified_contracts.items(),
                key=lambda x: abs(x[1].get('current_funding_rate', 0)),
                reverse=True
            )
            
            for symbol, info in sorted_contracts[:10]:  # 显示前10个
                funding_rate = info.get('current_funding_rate', 'N/A')
                interval = info.get('funding_interval_hours', 'N/A')
                if interval:
                    interval_str = f"{interval:.1f}h"
                else:
                    interval_str = "N/A"
                message += f"  {symbol} ({interval_str}): {funding_rate:.4%}\n"
            
            if len(qualified_contracts) > 10:
                message += f"  ... 还有 {len(qualified_contracts) - 10} 个合约"
        else:
            message = f"📊 资金费率合约池状态\n"
            message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"📈 合约数量: 0个\n"
            message += f"🎯 阈值: {self.threshold:.4%}\n"
            message += f"💡 当前没有合约满足条件"
        
        send_telegram_message(message)
    
    def get_current_pool(self):
        """获取当前合约池状态"""
        return {
            'contracts': list(self.contract_pool),
            'count': len(self.contract_pool),
            'threshold': self.threshold,
            'last_update': datetime.now().isoformat()
        }
    
    def refresh_contract_pool(self, force_refresh=False):
        """手动刷新合约池"""
        print("🔄 手动刷新合约池...")
        return self.update_contract_pool(force_refresh=force_refresh)
    
    def get_cache_status(self):
        """获取缓存状态概览"""
        return self.funding.get_all_intervals_from_cache()

def main():
    """主函数 - 手动模式"""
    print("🚀 资金费率合约池监控器")
    print("=" * 60)
    
    # 配置参数
    threshold = 0.005  # 0.5%
    
    print(f"📊 配置参数:")
    print(f"  资金费率阈值: {threshold:.4%}")
    print("💡 此版本为手动触发模式，通过Web界面或API调用")
    
    # 创建监控器
    monitor = FundingPoolMonitor(threshold=threshold)
    
    print("\n🔍 执行单次扫描...")
    added, removed = monitor.update_contract_pool()
    print(f"✅ 扫描完成")
    print(f"  新增: {len(added)} 个合约")
    print(f"  移除: {len(removed)} 个合约")
    print(f"  当前池子: {len(monitor.contract_pool)} 个合约")
    
    # 显示缓存状态
    cache_status = monitor.get_cache_status()
    if cache_status:
        print(f"\n📋 缓存状态:")
        print(f"  缓存时间: {cache_status.get('cache_time', 'N/A')}")
        print(f"  结算周期: {', '.join(cache_status.get('intervals', []))}")
        print(f"  总合约数: {cache_status.get('total_contracts', 0)}")
    
    print("\n💡 后续可通过Web界面或API手动触发更新")

if __name__ == "__main__":
    main() 