import pandas as pd
import ta
from typing import Dict, List
from .base import BaseStrategy, Signal

class RSIStrategy(BaseStrategy):
    """RSI策略"""
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            'rsi_period': 14,
            'overbought': 70,
            'oversold': 30,
            'exit_overbought': 60,
            'exit_oversold': 40
        }
        params = {**default_params, **(parameters or {})}
        super().__init__("RSI策略", params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = data.copy()
        
        # 计算RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close_price'], 
                                           window=self.parameters['rsi_period']).rsi()
        
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
            prev_rsi = df['rsi'].iloc[i-1]
            
            signal = None
            strength = 0.5
            
            # 买入信号：RSI从超卖区域回升
            if prev_rsi <= self.parameters['oversold'] and rsi > self.parameters['oversold']:
                signal = 'buy'
                strength = min(1.0, (rsi - self.parameters['oversold']) / 20)
            
            # 卖出信号：RSI从过热区域回落
            elif prev_rsi >= self.parameters['overbought'] and rsi < self.parameters['overbought']:
                signal = 'sell'
                strength = min(1.0, (self.parameters['overbought'] - rsi) / 20)
            
            if signal:
                signals.append(Signal(
                    timestamp=timestamp,
                    symbol=data.get('symbol', 'UNKNOWN'),
                    signal=signal,
                    strength=strength,
                    price=price,
                    strategy_name=self.name,
                    metadata={'rsi': rsi, 'prev_rsi': prev_rsi}
                ))
        
        return signals 