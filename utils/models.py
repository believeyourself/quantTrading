from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional, List
import json

Base = declarative_base()

class Strategy(Base):
    """交易策略模型"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    strategy_type = Column(String(50), nullable=False)  # ma_cross, bollinger_bands, macd等
    parameters = Column(Text)  # JSON格式的策略参数
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    backtests = relationship("Backtest", back_populates="strategy")
    trades = relationship("Trade", back_populates="strategy")
    
    def get_parameters(self) -> dict:
        """获取策略参数"""
        return json.loads(self.parameters) if self.parameters else {}
    
    def set_parameters(self, params: dict):
        """设置策略参数"""
        self.parameters = json.dumps(params)

class Backtest(Base):
    """回测记录模型"""
    __tablename__ = "backtests"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=False)  # 交易对
    timeframe = Column(String(10), nullable=False)  # 时间周期
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float)
    total_return = Column(Float)  # 总收益率
    max_drawdown = Column(Float)  # 最大回撤
    sharpe_ratio = Column(Float)  # 夏普比率
    win_rate = Column(Float)  # 胜率
    total_trades = Column(Integer)  # 总交易次数
    status = Column(String(20), default="running")  # running, completed, failed
    results = Column(Text)  # JSON格式的详细结果
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联关系
    strategy = relationship("Strategy", back_populates="backtests")
    trades = relationship("BacktestTrade", back_populates="backtest")

class BacktestTrade(Base):
    """回测交易记录模型"""
    __tablename__ = "backtest_trades"
    
    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("backtests.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    pnl = Column(Float)  # 盈亏
    strategy_signal = Column(String(50))  # 策略信号
    
    # 关联关系
    backtest = relationship("Backtest", back_populates="trades")

class Trade(Base):
    """实盘交易记录模型"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    timestamp = Column(DateTime, nullable=False)
    order_id = Column(String(100))  # 交易所订单ID
    status = Column(String(20), default="pending")  # pending, filled, cancelled, failed
    trade_type = Column(String(20), default="live")  # live, paper
    
    # 关联关系
    strategy = relationship("Strategy", back_populates="trades")

class MarketData(Base):
    """市场数据模型"""
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    timeframe = Column(String(10), nullable=False)
    source = Column(String(50), default="yfinance")
    
    class Config:
        indexes = [
            ("symbol", "timestamp", "timeframe")
        ]

class Account(Base):
    """账户信息模型"""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50), nullable=False)
    account_type = Column(String(20), default="spot")  # spot, futures, margin
    balance = Column(Float, default=0.0)
    equity = Column(Float, default=0.0)
    margin_used = Column(Float, default=0.0)
    free_margin = Column(Float, default=0.0)
    currency = Column(String(10), default="USDT")
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

# 数据库连接
from config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine) 