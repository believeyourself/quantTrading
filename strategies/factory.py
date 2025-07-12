from typing import Dict, List
from .ma_cross import MACrossStrategy
from .bollinger_bands import BollingerBandsStrategy
from .macd import MACDStrategy
from .rsi import RSIStrategy
from .funding_rate_arbitrage import FundingRateArbitrageStrategy

class StrategyFactory:
    """策略工厂类"""
    
    @staticmethod
    def create_strategy(strategy_type: str, parameters: Dict = None):
        """创建策略实例"""
        strategies = {
            'ma_cross': MACrossStrategy,
            'bollinger_bands': BollingerBandsStrategy,
            'macd': MACDStrategy,
            'rsi': RSIStrategy,
            'funding_rate_arbitrage': FundingRateArbitrageStrategy
        }
        
        if strategy_type not in strategies:
            raise ValueError(f"不支持的策略类型: {strategy_type}")
        
        return strategies[strategy_type](parameters)
    
    @staticmethod
    def get_available_strategies() -> List[str]:
        """获取可用策略列表"""
        return ['ma_cross', 'bollinger_bands', 'macd', 'rsi', 'funding_rate_arbitrage']
    
    @staticmethod
    def get_strategy_description(strategy_type: str) -> str:
        """获取策略描述"""
        descriptions = {
            'ma_cross': '移动平均线交叉策略，基于短期和长期移动平均线的交叉信号进行交易',
            'bollinger_bands': '布林带策略，基于价格在布林带中的位置和RSI指标进行交易',
            'macd': 'MACD策略，基于MACD指标与信号线的交叉进行交易',
            'rsi': 'RSI策略，基于RSI指标的超买超卖信号进行交易',
            'funding_rate_arbitrage': '资金费率套利策略，基于永续合约资金费率进行套利交易'
        }
        return descriptions.get(strategy_type, '未知策略') 