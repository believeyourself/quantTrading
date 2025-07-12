import pandas as pd
import ta
from typing import Dict, List
from .base import BaseStrategy, Signal

class MACDStrategy(BaseStrategy):
    """MACD策略"""
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9
        }
        params = {**default_params, **(parameters or {})}
        super().__init__("MACD策略", params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = data.copy()
        
        # 计算MACD
        macd = ta.trend.MACD(df['close_price'],
                           window_fast=self.parameters['fast_period'],
                           window_slow=self.parameters['slow_period'],
                           window_sign=self.parameters['signal_period'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
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
            macd = df['macd'].iloc[i]
            macd_signal = df['macd_signal'].iloc[i]
            macd_hist = df['macd_histogram'].iloc[i]
            prev_macd_hist = df['macd_histogram'].iloc[i-1]
            
            signal = None
            strength = 0.5
            
            # 买入信号：MACD上穿信号线
            if macd > macd_signal and prev_macd_hist < 0 and macd_hist > 0:
                signal = 'buy'
                strength = min(1.0, abs(macd_hist) / 0.01)
            
            # 卖出信号：MACD下穿信号线
            elif macd < macd_signal and prev_macd_hist > 0 and macd_hist < 0:
                signal = 'sell'
                strength = min(1.0, abs(macd_hist) / 0.01)
            
            if signal:
                signals.append(Signal(
                    timestamp=timestamp,
                    symbol=data.get('symbol', 'UNKNOWN'),
                    signal=signal,
                    strength=strength,
                    price=price,
                    strategy_name=self.name,
                    metadata={'macd': macd, 'macd_signal': macd_signal, 'macd_histogram': macd_hist}
                ))
        
        return signals 