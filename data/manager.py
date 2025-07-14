import yfinance as yf
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger
from config.settings import settings
from utils.models import MarketData, SessionLocal
import asyncio
import aiohttp
from utils.binance_funding import get_klines

class DataManager:
    """数据管理器"""
    
    def __init__(self, source: str = "yfinance"):
        self.source = source
        self.db = SessionLocal()
        
        if source == "ccxt":
            self.exchange = ccxt.binance({
                'apiKey': settings.API_KEY,
                'secret': settings.API_SECRET,
                'sandbox': settings.TESTNET,
                'enableRateLimit': True
            })
    
    def get_historical_data(self, symbol: str, timeframe: str = "1d", 
                          start_date: Optional[str] = None, 
                          end_date: Optional[str] = None,
                          limit: int = 1000) -> pd.DataFrame:
        """只用binance_interface获取历史数据，不再尝试yfinance/ccxt。"""
        try:
            import pandas as pd
            interval_map = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w"
            }
            interval = interval_map.get(timeframe, "1h")
            start_ts = int(pd.to_datetime(start_date).timestamp() * 1000) if start_date else None
            end_ts = int(pd.to_datetime(end_date).timestamp() * 1000) if end_date else None
            if start_ts and end_ts:
                df = get_klines(symbol, interval, start_ts, end_ts)
                if not df.empty:
                    df['timeframe'] = timeframe
                    df['source'] = 'binance_interface'
                    return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return pd.DataFrame()
    
    def _get_yfinance_data(self, symbol: str, timeframe: str, 
                          start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
        """从Yahoo Finance获取数据"""
        try:
            # 转换时间周期格式
            interval_map = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1wk"
            }
            interval = interval_map.get(timeframe, "1d")
            
            # 获取数据
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max" if not start_date else None,
                              start=start_date,
                              end=end_date,
                              interval=interval)
            
            if df.empty:
                logger.warning(f"未获取到 {symbol} 的数据")
                return df
            
            # 标准化列名
            df.columns = [col.lower() for col in df.columns]
            df = df.rename(columns={'open': 'open_price', 'high': 'high_price', 
                                  'low': 'low_price', 'close': 'close_price'})
            
            # 添加时间周期信息
            df['timeframe'] = timeframe
            df['source'] = 'yfinance'
            
            return df
            
        except Exception as e:
            logger.error(f"从Yahoo Finance获取数据失败: {e}")
            return pd.DataFrame()
    
    def _get_ccxt_data(self, symbol: str, timeframe: str, 
                      start_date: Optional[str], end_date: Optional[str], 
                      limit: int) -> pd.DataFrame:
        """从CCXT获取数据"""
        try:
            # 转换时间周期格式
            timeframe_map = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w"
            }
            tf = timeframe_map.get(timeframe, "1d")
            
            # 获取OHLCV数据
            ohlcv = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
            
            if not ohlcv:
                logger.warning(f"未获取到 {symbol} 的数据")
                return pd.DataFrame()
            
            # 转换为DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open_price', 'high_price', 
                                            'low_price', 'close_price', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 添加时间周期和来源信息
            df['timeframe'] = timeframe
            df['source'] = 'ccxt'
            
            return df
            
        except Exception as e:
            logger.error(f"从CCXT获取数据失败: {e}")
            return pd.DataFrame()
    
    def save_to_database(self, df: pd.DataFrame, symbol: str):
        """保存数据到数据库"""
        try:
            for index, row in df.iterrows():
                market_data = MarketData(
                    symbol=symbol,
                    timestamp=index,
                    open_price=row['open_price'],
                    high_price=row['high_price'],
                    low_price=row['low_price'],
                    close_price=row['close_price'],
                    volume=row['volume'],
                    timeframe=row['timeframe'],
                    source=row['source']
                )
                self.db.add(market_data)
            
            self.db.commit()
            logger.info(f"成功保存 {len(df)} 条 {symbol} 数据到数据库")
            
        except Exception as e:
            logger.error(f"保存数据到数据库失败: {e}")
            self.db.rollback()
    
    def get_from_database(self, symbol: str, timeframe: str = "1d",
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> pd.DataFrame:
        """从数据库获取数据"""
        try:
            query = self.db.query(MarketData).filter(
                MarketData.symbol == symbol,
                MarketData.timeframe == timeframe
            )
            
            if start_date:
                query = query.filter(MarketData.timestamp >= start_date)
            if end_date:
                query = query.filter(MarketData.timestamp <= end_date)
            
            data = query.order_by(MarketData.timestamp).all()
            
            if not data:
                return pd.DataFrame()
            
            # 转换为DataFrame
            df_data = []
            for record in data:
                df_data.append({
                    'timestamp': record.timestamp,
                    'open_price': record.open_price,
                    'high_price': record.high_price,
                    'low_price': record.low_price,
                    'close_price': record.close_price,
                    'volume': record.volume,
                    'timeframe': record.timeframe,
                    'source': record.source
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"从数据库获取数据失败: {e}")
            return pd.DataFrame()
    
    def update_market_data(self, symbol: str, timeframe: str = "1d"):
        """更新市场数据"""
        try:
            # 获取最新数据
            df = self.get_historical_data(symbol, timeframe, limit=100)
            
            if not df.empty:
                # 保存到数据库
                self.save_to_database(df, symbol)
                logger.info(f"成功更新 {symbol} 的 {timeframe} 数据")
            else:
                logger.warning(f"无法获取 {symbol} 的数据进行更新")
                
        except Exception as e:
            logger.error(f"更新市场数据失败: {e}")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        try:
            if self.source == "yfinance":
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return info.get('regularMarketPrice')
            elif self.source == "ccxt":
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker['last']
            else:
                return None
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return None
    
    def get_symbols(self) -> List[str]:
        """获取支持的交易对列表"""
        try:
            # 优先从1h_funding_contracts_full.json配置文件读取交易对
            import json
            import os
            
            cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                    "cache", "1h_funding_contracts_full.json")
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'contracts' in data:
                        # 提取所有交易对符号
                        symbols = list(data['contracts'].keys())
                        logger.info(f"从配置文件加载了 {len(symbols)} 个交易对")
                        return symbols
            
            # 如果配置文件不存在，则使用默认方法
            if self.source == "yfinance":
                # 返回一些常见的加密货币
                return ["BTC-USD", "ETH-USD", "BNB-USD", "ADA-USD", "SOL-USD"]
            elif self.source == "ccxt":
                try:
                    markets = self.exchange.load_markets()
                    return list(markets.keys())
                except Exception as e:
                    logger.error(f"获取交易对列表失败: {e}")
                    return []
            else:
                return []
                
        except Exception as e:
            logger.error(f"从配置文件读取交易对失败: {e}")
            # 返回默认交易对
            return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
    
    def __del__(self):
        """析构函数，关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()

# 全局数据管理器实例
data_manager = DataManager(settings.DATA_SOURCE) 