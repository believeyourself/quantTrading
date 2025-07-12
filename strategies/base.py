import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from loguru import logger
from dataclasses import dataclass

@dataclass
class Signal:
    """交易信号"""
    timestamp: pd.Timestamp
    symbol: str
    signal: str  # 'buy', 'sell', 'hold'
    strength: float  # 信号强度 0-1
    price: float
    strategy_name: str
    metadata: Dict = None

class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, parameters: Dict = None):
        self.name = name
        self.parameters = parameters or {}
        self.signals = []
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """生成交易信号"""
        pass
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据有效性"""
        if data.empty:
            return False
        
        required_columns = ['open_price', 'high_price', 'low_price', 'close_price', 'volume']
        for col in required_columns:
            if col not in data.columns:
                logger.error(f"数据缺少必要列: {col}")
                return False
        
        return True 