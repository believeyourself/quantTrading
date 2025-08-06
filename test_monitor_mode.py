#!/usr/bin/env python3
"""
测试资金费率套利策略的监控模式
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.funding_rate_arbitrage import FundingRateArbitrageStrategy
from utils.notifier import send_telegram_message

def test_monitor_mode():
    """测试监控模式"""
    print("🧪 测试资金费率套利策略监控模式...")
    
    # 创建策略实例
    params = {
        'funding_rate_threshold': 0.005,  # 0.5%
        'max_positions': 5,
        'min_volume': 1000000,
        'auto_trade': False,  # 确保关闭自动交易
        'funding_rate_check_interval': 10  # 10秒检测一次，便于测试
    }
    
    strategy = FundingRateArbitrageStrategy(params)
    
    print(f"📊 策略参数:")
    print(f"  - 资金费率阈值: {strategy.parameters['funding_rate_threshold']:.4%}")
    print(f"  - 最大池子大小: {strategy.parameters['max_positions']}")
    print(f"  - 自动交易: {'开启' if strategy.parameters['auto_trade'] else '关闭'}")
    print(f"  - 检测间隔: {strategy.parameters['funding_rate_check_interval']}秒")
    
    # 启动策略
    print("\n🚀 启动策略...")
    strategy.start_strategy()
    
    # 等待一段时间让策略运行
    import time
    print("\n⏰ 等待30秒让策略运行...")
    time.sleep(30)
    
    # 获取池子状态
    print("\n📊 获取池子状态...")
    pool_status = strategy.get_pool_status()
    print(f"池子大小: {pool_status['pool_size']}")
    print(f"最后更新: {pool_status['last_update']}")
    
    # 停止策略
    print("\n🛑 停止策略...")
    strategy.stop_strategy()
    
    print("\n✅ 测试完成！")
    print("💡 请检查Telegram是否收到了通知消息")

if __name__ == "__main__":
    test_monitor_mode() 