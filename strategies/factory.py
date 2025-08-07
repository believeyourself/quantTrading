from .funding_rate_arbitrage import FundingRateMonitor

class StrategyFactory:
    @staticmethod
    def create_strategy(strategy_type, parameters=None):
        if strategy_type == "funding_rate_arbitrage":
            return FundingRateMonitor(parameters)
        else:
            raise ValueError("未知策略类型")