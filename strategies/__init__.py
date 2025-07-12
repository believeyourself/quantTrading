"""
交易策略模块
包含各种技术分析策略的实现
"""

from .base import BaseStrategy, Signal
from .factory import StrategyFactory
from .ma_cross import MACrossStrategy
from .bollinger_bands import BollingerBandsStrategy
from .macd import MACDStrategy
from .rsi import RSIStrategy
from .funding_rate_arbitrage import FundingRateArbitrageStrategy

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