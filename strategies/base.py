from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Signal:
    timestamp: Any
    symbol: str
    signal: str  # 'buy' 或 'sell'
    strength: float = 1.0
    price: float = 0.0
    strategy_name: str = ""
    metadata: Dict = None

class BaseStrategy:
    def __init__(self, name: str, parameters: Dict = None):
        self.name = name
        self.parameters = parameters or {}
    def generate_signals(self, data):
        """生成交易信号，子类实现"""
        raise NotImplementedError 