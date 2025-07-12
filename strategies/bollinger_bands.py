import pandas as pd
import ta
from typing import Dict, List
from .base import BaseStrategy, Signal

class BollingerBandsStrategy(BaseStrategy):
    """布林带策略"""
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            'window': 20,
            'num_std': 2,
            'rsi_period': 14
        }
        params = {**default_params, **(parameters or {})}
        super().__init__("布林带策略", params)
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = data.copy()
        
        # 计算布林带
        bb = ta.volatility.BollingerBands(df['close_price'], 
                                        window=self.parameters['window'],
                                        window_dev=self.parameters['num_std'])
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
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
            bb_upper = df['bb_upper'].iloc[i]
            bb_lower = df['bb_lower'].iloc[i]
            bb_middle = df['bb_middle'].iloc[i]
            rsi = df['rsi'].iloc[i]
            
            signal = None
            strength = 0.5
            
            # 买入信号：价格触及下轨 + RSI超卖
            if price <= bb_lower and rsi < 30:
                signal = 'buy'
                strength = min(1.0, (30 - rsi) / 30)
            
            # 卖出信号：价格触及上轨 + RSI过热
            elif price >= bb_upper and rsi > 70:
                signal = 'sell'
                strength = min(1.0, (rsi - 70) / 30)
            
            if signal:
                signals.append(Signal(
                    timestamp=timestamp,
                    symbol=data.get('symbol', 'UNKNOWN'),
                    signal=signal,
                    strength=strength,
                    price=price,
                    strategy_name=self.name,
                    metadata={'rsi': rsi, 'bb_position': (price - bb_lower) / (bb_upper - bb_lower)}
                ))
        
        return signals 