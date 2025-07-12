"""
交易模块
包含交易引擎、交易管理器等
"""

from .engine import TradingEngine
from .manager import TradingManager, trading_manager

__all__ = ['TradingEngine', 'TradingManager', 'trading_manager'] 