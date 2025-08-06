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
    
    # 数据源配置
    DATA_SOURCE: str = "yfinance"  # yfinance, ccxt
    DEFAULT_SYMBOLS: List[str] = ["BTC-USD", "ETH-USD", "AAPL", "GOOGL"]
    
    # 交易配置
    DEFAULT_CAPITAL: float = 10.0
    MAX_POSITION_SIZE: float = 0.1  # 最大仓位10%
    STOP_LOSS_RATIO: float = 0.5   # 止损5%
    TAKE_PROFIT_RATIO: float = 5  # 止盈10%
    
    # 交易所配置
    EXCHANGE_NAME: str = "binance"
    API_KEY: str = ""
    API_SECRET: str = ""
    
    # 策略配置
    DEFAULT_STRATEGY_PARAMS: Dict = {
        "ma_cross": {
            "short_window": 10,
            "long_window": 30,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30
        },
        "bollinger_bands": {
            "window": 20,
            "num_std": 2,
            "rsi_period": 14
        },
        "macd": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9
        },
        "rsi": {
            "rsi_period": 14,
            "overbought": 70,
            "oversold": 30,
            "exit_overbought": 60,
            "exit_oversold": 40
        },
        "funding_rate_arbitrage": {
            "funding_rate_threshold": 0.005,
            "max_positions": 10,
            "min_volume": 1000000,
            "exchanges": ["binance"],
            "cache_duration": 3600,
            "update_interval": 1800,
            "funding_interval": 3600,
            "auto_trade": False  # 默认关闭自动交易
        }
    }
    
    TELEGRAM_BOT_TOKEN: str = "7913734952:AAF65AZeiNEPbU-6TqLIcbIujj6qln0qY0k"
    TELEGRAM_CHAT_ID: str = "1394654481"
    
    class Config:
        env_file = ".env"

# 创建全局配置实例
settings = Settings()

# 支持的交易所
SUPPORTED_EXCHANGES = ["binance", "coinbase", "kraken", "okx"]

# 支持的时间周期
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

# 默认策略参数
DEFAULT_STRATEGY_PARAMS = settings.DEFAULT_STRATEGY_PARAMS 