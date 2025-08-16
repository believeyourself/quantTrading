from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class Strategy(Base):
    """交易策略模型"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    strategy_type = Column(String(50), nullable=False)  # funding_rate_arbitrage
    parameters = Column(Text)  # JSON格式的策略参数
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_parameters(self) -> dict:
        """获取策略参数"""
        return json.loads(self.parameters) if self.parameters else {}
    
    def set_parameters(self, params: dict):
        """设置策略参数"""
        self.parameters = json.dumps(params)

class MarketData(Base):
    """市场数据模型"""
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Float)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
    source = Column(String(50), default="binance_interface")  # 数据源
    created_at = Column(DateTime, default=datetime.utcnow)
    
    class Config:
        orm_mode = True 