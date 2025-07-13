#!/usr/bin/env python3
"""
快速测试缓存读取功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.binance_funding import BinanceFunding

def test_cache_reading():
    """测试缓存读取"""
    print("🔍 测试缓存读取功能")
    print("=" * 50)
    
    funding = BinanceFunding()
    
    # 测试读取缓存（不带TG通知）
    print("📋 读取1小时结算合约缓存...")
    contracts = funding.get_1h_contracts_from_cache()
    
    if contracts:
        print(f"✅ 成功读取 {len(contracts)} 个1小时结算合约")
        
        # 显示前3个合约
        print("\n📋 合约池预览:")
        for i, (symbol, info) in enumerate(list(contracts.items())[:3]):
            print(f"  {i+1}. {symbol}")
            print(f"     资金费率: {info.get('current_funding_rate', 'N/A')}")
            print(f"     结算周期: {info.get('funding_interval_hours', 'N/A')}小时")
    else:
        print("❌ 未读取到1小时结算合约")
        print("💡 请先运行缓存更新进程或手动扫描")

if __name__ == "__main__":
    test_cache_reading() 