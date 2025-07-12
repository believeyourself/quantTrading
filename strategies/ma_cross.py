import pandas as pd
import numpy as np
import ta
from typing import Dict, List
from .base import BaseStrategy, Signal

class MACrossStrategy(BaseStrategy):
    """移动平均线交叉策略"""
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            'short_window': 10,
            'long_window': 30,
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30
        }
        params = {**default_params, **(parameters or {})}
        super().__init__("MA交叉策略", params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = data.copy()
        
        # 计算移动平均线
        df['ma_short'] = df['close_price'].rolling(window=self.parameters['short_window']).mean()
        df['ma_long'] = df['close_price'].rolling(window=self.parameters['long_window']).mean()
        
        # 计算RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close_price'], 
                                           window=self.parameters['rsi_period']).rsi()
        
        # 计算交叉信号
        df['ma_cross'] = np.where(df['ma_short'] > df['ma_long'], 1, -1)
        df['ma_cross_signal'] = df['ma_cross'].diff()
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """生成交易信号"""
        if not self.validate_data(data):
            return []
        
        df = self.calculate_indicators(data)
        signals = []
        
        for i in range(1, len(df)):
            timestamp = df.index[i]
            price = df['close_price'].iloc[i]
            rsi = df['rsi'].iloc[i]
            cross_signal = df['ma_cross_signal'].iloc[i]
            
            signal = None
            strength = 0.5
            
            # 买入信号：短期均线上穿长期均线 + RSI不过热
            if cross_signal == 2 and rsi < self.parameters['rsi_overbought']:
                signal = 'buy'
                strength = min(1.0, (self.parameters['rsi_overbought'] - rsi) / 50)
            
            # 卖出信号：短期均线下穿长期均线 + RSI不超卖
            elif cross_signal == -2 and rsi > self.parameters['rsi_oversold']:
                signal = 'sell'
                strength = min(1.0, (rsi - self.parameters['rsi_oversold']) / 50)
            
            if signal:
                signals.append(Signal(
                    timestamp=timestamp,
                    symbol=data.get('symbol', 'UNKNOWN'),
                    signal=signal,
                    strength=strength,
                    price=price,
                    strategy_name=self.name,
                    metadata={'rsi': rsi, 'ma_cross': cross_signal}
                ))
        
        return signals 