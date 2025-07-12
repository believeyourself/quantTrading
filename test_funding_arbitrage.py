#!/usr/bin/env python3
"""
资金费率套利策略测试脚本
"""

import pandas as pd
from strategies.factory import StrategyFactory
from utils.notifier import send_telegram_message

def test_funding_rate_arbitrage():
    """测试资金费率套利策略"""
    print("开始测试资金费率套利策略...")
    
    # 创建策略实例
    strategy = StrategyFactory.create_strategy("funding_rate_arbitrage", {
        'funding_rate_threshold': 0.005,  # 0.5%
        'max_positions': 5,
        'min_volume': 1000000,
        'exchanges': ['binance']  # 只使用Binance
    })
    
    print(f"策略名称: {strategy.name}")
    print(f"策略参数: {strategy.parameters}")
    
    # 获取资金费率数据
    print("\n获取资金费率数据...")
    funding_rates = strategy.get_funding_rates()
    
    print(f"获取到 {len(funding_rates)} 个合约的资金费率")
    
    # 显示前5个资金费率
    count = 0
    for contract_id, info in funding_rates.items():
        count += 1
        print(f"{count}. {contract_id}: {info['funding_rate']:.4%}")
        if count >= 5:
            break
    
    # 生成交易信号
    print("\n生成交易信号...")
    signals = strategy.generate_signals(pd.DataFrame())
    print(f"生成了 {len(signals)} 个交易信号")
    
    # 获取池子状态
    print("\n获取池子状态...")
    pool_status = strategy.get_pool_status()
    print(f"池子大小: {pool_status['pool_size']}")
    print(f"最大持仓: {pool_status['max_positions']}")
    print(f"阈值: {pool_status['threshold']:.4%}")
    
    # 发送测试完成通知
    send_telegram_message("🧪 资金费率套利策略测试完成！")
    
    print("\n测试完成！")

if __name__ == "__main__":
    test_funding_rate_arbitrage() 