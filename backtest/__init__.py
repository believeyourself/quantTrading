"""
回测模块
包含回测引擎、回测管理器等
"""

from .engine import BacktestEngine
from .manager import BacktestManager

__all__ = ['BacktestEngine', 'BacktestManager'] 