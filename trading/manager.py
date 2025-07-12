from typing import Dict, List, Optional
from loguru import logger
from .engine import TradingEngine

class TradingManager:
    """交易管理器"""
    
    def __init__(self):
        self.engines: Dict[str, TradingEngine] = {}
    
    def create_engine(self, name: str, trade_type: str = "paper", 
                     exchange_name: str = "binance") -> TradingEngine:
        """创建交易引擎"""
        engine = TradingEngine(trade_type, exchange_name)
        self.engines[name] = engine
        logger.info(f"创建交易引擎: {name} ({trade_type})")
        return engine
    
    def get_engine(self, name: str) -> Optional[TradingEngine]:
        """获取交易引擎"""
        return self.engines.get(name)
    
    def remove_engine(self, name: str):
        """移除交易引擎"""
        if name in self.engines:
            del self.engines[name]
            logger.info(f"移除交易引擎: {name}")
    
    def list_engines(self) -> List[str]:
        """列出所有交易引擎"""
        return list(self.engines.keys())
    
    def run_strategy(self, engine_name: str, strategy, 
                    symbol: str, timeframe: str = "1d"):
        """运行策略"""
        engine = self.get_engine(engine_name)
        if not engine:
            logger.error(f"交易引擎不存在: {engine_name}")
            return
        
        try:
            # 添加策略
            engine.add_strategy(strategy)
            
            # 生成信号
            signals = engine.generate_signals(symbol, timeframe)
            
            # 执行信号
            engine.execute_signals(signals)
            
            logger.info(f"策略 {strategy.name} 运行完成")
            
        except Exception as e:
            logger.error(f"运行策略失败: {e}")

# 全局交易管理器实例
trading_manager = TradingManager() 