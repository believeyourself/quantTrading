from typing import List, Optional
from datetime import datetime
from loguru import logger
from utils.database import SessionLocal
from utils.models import Backtest, BacktestTrade

class BacktestManager:
    """回测管理器"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def create_backtest(self, strategy_id: int, symbol: str, timeframe: str,
                       start_date: str, end_date: str, initial_capital: float) -> int:
        """创建回测任务"""
        try:
            backtest = Backtest(
                strategy_id=strategy_id,
                name=f"Backtest_{symbol}_{start_date}_{end_date}",
                symbol=symbol,
                timeframe=timeframe,
                start_date=datetime.strptime(start_date, "%Y-%m-%d"),
                end_date=datetime.strptime(end_date, "%Y-%m-%d"),
                initial_capital=initial_capital,
                status='running'
            )
            
            self.db.add(backtest)
            self.db.commit()
            self.db.refresh(backtest)
            
            return backtest.id
            
        except Exception as e:
            logger.error(f"创建回测任务失败: {e}")
            self.db.rollback()
            return 0
    
    def get_backtest(self, backtest_id: int) -> Optional[Backtest]:
        """获取回测记录"""
        return self.db.query(Backtest).filter(Backtest.id == backtest_id).first()
    
    def get_backtest_trades(self, backtest_id: int) -> List[BacktestTrade]:
        """获取回测交易记录"""
        return self.db.query(BacktestTrade).filter(
            BacktestTrade.backtest_id == backtest_id
        ).order_by(BacktestTrade.timestamp).all()
    
    def list_backtests(self, strategy_id: Optional[int] = None) -> List[Backtest]:
        """列出回测记录"""
        query = self.db.query(Backtest)
        if strategy_id:
            query = query.filter(Backtest.strategy_id == strategy_id)
        return query.order_by(Backtest.created_at.desc()).all()
    
    def delete_backtest(self, backtest_id: int) -> bool:
        """删除回测记录"""
        try:
            backtest = self.get_backtest(backtest_id)
            if backtest:
                self.db.delete(backtest)
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"删除回测记录失败: {e}")
            self.db.rollback()
            return False
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'db'):
            self.db.close() 