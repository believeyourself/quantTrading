#!/usr/bin/env python3
"""
量化交易系统主程序
"""

import os
import sys
import asyncio
from loguru import logger
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import init_db, SessionLocal
from config.settings import settings
from data.manager import data_manager
from strategies.factory import StrategyFactory
from backtest.engine import BacktestEngine
from trading.manager import trading_manager
from api.routes import app
from utils.notifier import send_telegram_message

def setup_logging():
    """设置日志"""
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)
    
    # 配置日志
    logger.remove()  # 移除默认处理器
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL
    )
    
    # 添加文件处理器
    logger.add(
        settings.LOG_FILE,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
        rotation="1 day",
        retention="30 days"
    )

def initialize_database():
    """初始化数据库"""
    try:
        logger.info("正在初始化数据库...")
        init_db()
        logger.info("数据库初始化完成")
        
        # 创建默认策略
        create_default_strategies()
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

def create_default_strategies():
    """创建默认策略"""
    try:
        db = SessionLocal()
        
        # 检查是否已有策略
        from utils.models import Strategy
        existing_strategies = db.query(Strategy).count()
        if existing_strategies > 0:
            logger.info("数据库中已有策略，跳过默认策略创建")
            return
        
        logger.info("创建默认策略...")
        
        # 默认策略配置
        default_strategies = [
            {
                "name": "MA交叉策略-默认",
                "description": "移动平均线交叉策略的默认配置",
                "strategy_type": "ma_cross",
                "parameters": {
                    "short_window": 10,
                    "long_window": 30,
                    "rsi_period": 14,
                    "rsi_overbought": 70,
                    "rsi_oversold": 30
                }
            },
            {
                "name": "布林带策略-默认",
                "description": "布林带策略的默认配置",
                "strategy_type": "bollinger_bands",
                "parameters": {
                    "window": 20,
                    "num_std": 2,
                    "rsi_period": 14
                }
            },
            {
                "name": "MACD策略-默认",
                "description": "MACD策略的默认配置",
                "strategy_type": "macd",
                "parameters": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9
                }
            },
            {
                "name": "RSI策略-默认",
                "description": "RSI策略的默认配置",
                "strategy_type": "rsi",
                "parameters": {
                    "rsi_period": 14,
                    "overbought": 70,
                    "oversold": 30,
                    "exit_overbought": 60,
                    "exit_oversold": 40
                }
            },
            {
                "name": "资金费率套利策略-默认",
                "description": "资金费率套利策略的默认配置",
                "strategy_type": "funding_rate_arbitrage",
                "parameters": {
                    "funding_rate_threshold": 0.005,
                    "max_positions": 10,
                    "min_volume": 1000000,
                    "exchanges": ["binance", "okx", "bybit"]
                }
            }
        ]
        
        for strategy_config in default_strategies:
            strategy = Strategy(
                name=strategy_config["name"],
                description=strategy_config["description"],
                strategy_type=strategy_config["strategy_type"],
                parameters=json.dumps(strategy_config["parameters"])
            )
            db.add(strategy)
        
        db.commit()
        logger.info(f"成功创建 {len(default_strategies)} 个默认策略")
        
    except Exception as e:
        logger.error(f"创建默认策略失败: {e}")
        db.rollback()
    finally:
        db.close()

def test_data_connection():
    """测试数据连接"""
    try:
        logger.info("测试数据连接...")
        
        # 测试获取交易对列表
        symbols = data_manager.get_symbols()
        logger.info(f"获取到 {len(symbols)} 个交易对")
        
        # 测试获取最新价格
        if symbols:
            test_symbol = symbols[0]
            price = data_manager.get_latest_price(test_symbol)
            if price:
                logger.info(f"{test_symbol} 最新价格: {price}")
            else:
                logger.warning(f"无法获取 {test_symbol} 的价格")
        
        logger.info("数据连接测试完成")
        
    except Exception as e:
        logger.error(f"数据连接测试失败: {e}")

def test_strategy_factory():
    """测试策略工厂"""
    try:
        logger.info("测试策略工厂...")
        
        # 获取可用策略
        available_strategies = StrategyFactory.get_available_strategies()
        logger.info(f"可用策略类型: {available_strategies}")
        
        # 测试创建策略实例
        for strategy_type in available_strategies:
            strategy = StrategyFactory.create_strategy(strategy_type)
            logger.info(f"成功创建策略: {strategy.name}")
        
        logger.info("策略工厂测试完成")
        
    except Exception as e:
        logger.error(f"策略工厂测试失败: {e}")

def run_demo_backtest():
    """运行演示回测"""
    try:
        logger.info("运行演示回测...")
        
        # 创建策略
        strategy = StrategyFactory.create_strategy("ma_cross")
        
        # 创建回测引擎
        engine = BacktestEngine(initial_capital=10000.0)
        
        # 运行回测
        results = engine.run_backtest(
            strategy=strategy,
            symbol="BTC-USD",
            start_date="2023-01-01",
            end_date="2023-12-31",
            timeframe="1d"
        )
        
        logger.info(f"演示回测完成，总收益率: {results['results']['total_return']:.2%}")
        send_telegram_message(f"回测完成，总收益率：{results['results']['total_return']:.2%}")
        
    except Exception as e:
        logger.error(f"演示回测失败: {e}")

def main():
    """主函数"""
    try:
        logger.info("=" * 50)
        logger.info("量化交易系统启动")
        logger.info("=" * 50)
        
        # 设置日志
        setup_logging()
        
        # 初始化数据库
        initialize_database()
        
        # 测试数据连接
        test_data_connection()
        
        # 测试策略工厂
        test_strategy_factory()
        
        # 运行演示回测
        run_demo_backtest()
        
        logger.info("系统初始化完成")
        logger.info(f"API服务地址: http://{settings.API_HOST}:{settings.API_PORT}")
        logger.info(f"Web界面地址: http://localhost:8050")
        logger.info("=" * 50)
        send_telegram_message("量化交易系统启动成功，欢迎使用！")
        
        # 启动API服务
        import uvicorn
        uvicorn.run(
            app,
            host=settings.API_HOST,
            port=settings.API_PORT,
            reload=settings.DEBUG
        )
        
    except KeyboardInterrupt:
        logger.info("系统被用户中断")
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # 导入必要的模块
    import json
    
    main() 