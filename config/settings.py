import os
from typing import Dict, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """系统配置"""
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./quant_trading.db"
    
    # API配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/quant_trading.log"
    
    # 资金费率监控策略配置
    FUNDING_RATE_THRESHOLD: float = 0.005  # 0.5%
    MAX_POOL_SIZE: int = 20
    MIN_VOLUME: float = 1000000
    CACHE_DURATION: int = 7200  # 2小时
    UPDATE_INTERVAL: int = 1800  # 30分钟
    CONTRACT_REFRESH_INTERVAL: int = 60  # 1小时
    FUNDING_RATE_CHECK_INTERVAL: int = 30  # 30秒
    
    # 交易所配置
    EXCHANGES: List[str] = ["binance", "okx", "bybit"]
    
    # Telegram通知配置
    TELEGRAM_BOT_TOKEN: str = "7913734952:AAF65AZeiNEPbU-6TqLIcbIujj6qln0qY0k"
    TELEGRAM_CHAT_ID: str = "1394654481"
    
    class Config:
        env_file = ".env"

# 创建全局配置实例
settings = Settings() 