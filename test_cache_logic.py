#!/usr/bin/env python3
"""
测试新的缓存读取逻辑
验证过期检测和异常通知功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.binance_funding import BinanceFunding
from utils.notifier import send_telegram_message

def test_cache_reading():
    """测试缓存读取逻辑"""
    print("🔍 测试新的缓存读取逻辑")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 测试1: 正常读取缓存（带TG通知）
    print("\n📋 测试1: 正常读取缓存（带TG通知）")
    contracts = funding.get_1h_contracts_from_cache(tg_notifier=send_telegram_message)
    print(f"读取到 {len(contracts)} 个合约")
    
    # 测试2: 不带TG通知读取
    print("\n📋 测试2: 不带TG通知读取")
    contracts = funding.get_1h_contracts_from_cache()
    print(f"读取到 {len(contracts)} 个合约")
    
    # 测试3: 模拟缓存过期情况
    print("\n📋 测试3: 模拟缓存过期情况")
    cache_file = "cache/1h_funding_contracts_full.json"
    if os.path.exists(cache_file):
        # 修改缓存时间为2小时前（过期）
        import json
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 修改为2小时前的时间
        from datetime import datetime, timedelta
        old_time = datetime.now() - timedelta(hours=2)
        cache_data['cache_time'] = old_time.isoformat()
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        print("已修改缓存时间为2小时前，测试过期检测...")
        contracts = funding.get_1h_contracts_from_cache(tg_notifier=send_telegram_message)
        print(f"读取到 {len(contracts)} 个合约")
        
        # 恢复缓存时间
        cache_data['cache_time'] = datetime.now().isoformat()
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print("已恢复缓存时间")

def test_strategy_integration():
    """测试策略集成"""
    print("\n🔍 测试策略集成")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 模拟策略中的使用方式
    print("📊 策略中获取1小时结算合约池...")
    contracts = funding.get_1h_contracts_from_cache(tg_notifier=send_telegram_message)
    
    if contracts:
        print(f"✅ 成功获取 {len(contracts)} 个1小时结算合约")
        
        # 显示前几个合约的信息
        print("\n📋 合约池预览:")
        for i, (symbol, info) in enumerate(list(contracts.items())[:5]):
            print(f"  {i+1}. {symbol}:")
            print(f"     资金费率: {info.get('current_funding_rate', 'N/A')}")
            print(f"     结算周期: {info.get('funding_interval_hours', 'N/A')}小时")
            print(f"     下次结算: {info.get('next_funding_time', 'N/A')}")
    else:
        print("❌ 未获取到1小时结算合约")

def main():
    """主函数"""
    print("🚀 测试新的缓存读取逻辑")
    print("=" * 80)
    
    print("请选择测试模式:")
    print("1. 测试缓存读取逻辑")
    print("2. 测试策略集成")
    print("3. 完整测试")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        test_cache_reading()
    elif choice == "2":
        test_strategy_integration()
    elif choice == "3":
        test_cache_reading()
        test_strategy_integration()
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main() 