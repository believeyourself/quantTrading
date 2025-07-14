from .funding_rate_arbitrage import FundingRateArbitrageStrategy

class StrategyFactory:
    @staticmethod
    def create_strategy(strategy_type, parameters=None):
        if strategy_type == "funding_rate_arbitrage":
            return FundingRateArbitrageStrategy(parameters)
        else:
            raise ValueError("未知策略类型") 