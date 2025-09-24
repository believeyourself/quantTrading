#!/usr/bin/env python3
"""
测试币安API连接和JSON解析修复效果
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入SSL警告修复
from utils.ssl_warning_fix import *

print("🧪 测试币安API连接和JSON解析修复...")

try:
    from utils.binance_funding import BinanceFunding
    
    # 创建币安API实例
    funding = BinanceFunding()
    
    if not funding.available:
        print("❌ binance_interface 未安装或不可用")
        print("请运行: pip install binance-interface")
        sys.exit(1)
    
    # 测试获取当前资金费率
    print("\n📊 测试获取当前资金费率...")
    test_symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
    
    for symbol in test_symbols:
        print(f"\n测试 {symbol}:")
        try:
            result = funding.get_current_funding(symbol, "UM")
            if result:
                print(f"✅ {symbol}: 资金费率={result['funding_rate']:.6f}, 标记价格=${result['mark_price']:.4f}")
            else:
                print(f"⚠️ {symbol}: 获取失败，但不会显示错误")
        except Exception as e:
            print(f"❌ {symbol}: 异常 {type(e).__name__}: {e}")
    
    # 测试获取历史资金费率
    print("\n📈 测试获取历史资金费率...")
    for symbol in test_symbols:
        print(f"\n测试 {symbol} 历史数据:")
        try:
            history = funding.get_funding_history(symbol, "UM", limit=3)
            if history:
                print(f"✅ {symbol}: 获取到 {len(history)} 条历史记录")
                for i, record in enumerate(history[:2]):  # 只显示前2条
                    print(f"  {i+1}. 时间: {record.get('funding_time', 'N/A')}, 费率: {record.get('funding_rate', 'N/A')}")
            else:
                print(f"⚠️ {symbol}: 获取失败，但不会显示错误")
        except Exception as e:
            print(f"❌ {symbol}: 异常 {type(e).__name__}: {e}")
    
    print("\n🎉 测试完成！")
    print("✅ 如果看到 '⚠️' 而不是 '❌'，说明错误处理已经改进")
    print("✅ 不再显示大量的 'Expecting value: line 1 column 1' 错误")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
