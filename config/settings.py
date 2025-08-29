import os
from typing import Dict, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """系统配置"""
    
    # 数据库配置已移除，系统现在直接从配置文件读取设置
    
    # API配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/quant_trading.log"
    
    # 资金费率监控策略配置
    FUNDING_RATE_THRESHOLD: float = 0.003  # 0.3% 资金费率阈值
    MAX_POOL_SIZE: int = 20                # 合约池最大合约数量
    MIN_VOLUME: float = 1000000            # 最小24小时成交量（USDT）
    CACHE_DURATION: int = 7200             # 缓存有效期（秒，2小时）
    UPDATE_INTERVAL: int = 1800            # 更新间隔（秒，30分钟）
    CONTRACT_REFRESH_INTERVAL: int = 10800  # 合约池刷新间隔（秒，3小时）
    FUNDING_RATE_CHECK_INTERVAL: int = 600 # 资金费率检查间隔（秒，10分钟）
    
    # 交易所配置
    EXCHANGES: List[str] = ["binance", "okx", "bybit"]
    
    # Telegram通知配置
    TELEGRAM_BOT_TOKEN: str = "7913734952:AAF65AZeiNEPbU-6TqLIcbIujj6qln0qY0k"
    TELEGRAM_CHAT_ID: str = "1394654481"
    
    # 邮件通知配置
    SMTP_SERVER: str = "smtp.163.com"           # SMTP服务器地址
    SMTP_PORT: int = 465                        # SMTP端口（使用SSL端口）
    SMTP_USERNAME: str = "farmerlzj@163.com"   # 发件人邮箱
    SMTP_AUTH_CODE: str = "LCvVGTXXSEgQNkmj"      # 邮箱授权码（不是登录密码）
    SMTP_RECIPIENT: str = "634206380@qq.com"  # 收件人邮箱
    SMTP_USE_SSL: bool = True                   # 是否使用SSL
    SMTP_USE_TLS: bool = False                  # 是否使用TLS
    EMAIL_ENABLED: bool = True                  # 是否启用邮件通知
    
    class Config:
        env_file = ".env"

# 创建全局配置实例
settings = Settings() 