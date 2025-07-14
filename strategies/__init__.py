"""
交易策略模块
包含各种技术分析策略的实现
"""

# __init__.py 可留空，仅保留资金费率套利策略（如有需要）
# from .funding_rate_arbitrage import FundingRateArbitrageStrategy

__all__ = [
    'BaseStrategy', 
    'Signal', 
    'StrategyFactory',
    'MACrossStrategy',
    'BollingerBandsStrategy', 
    'MACDStrategy',
    'RSIStrategy',
    'FundingRateArbitrageStrategy'
] 