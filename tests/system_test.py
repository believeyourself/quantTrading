#!/usr/bin/env python3
"""
系统测试脚本
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from config.settings import settings
from utils.models import init_db, SessionLocal
from data.manager import data_manager
from strategies.factory import StrategyFactory
from backtest.engine import BacktestEngine
from trading.manager import TradingManager

def test_data_manager():
    """测试数据管理器"""
    logger.info("测试数据管理器...")
    
    try:
        # 测试获取交易对列表
        symbols = data_manager.get_symbols()
        logger.info(f"获取到 {len(symbols)} 个交易对: {symbols[:5]}")
        
        if symbols:
            # 测试获取历史数据
            symbol = symbols[0]
            data = data_manager.get_historical_data(symbol, "1d", limit=10)
            logger.info(f"获取 {symbol} 历史数据: {len(data)} 条记录")
            
            # 测试获取最新价格
            price = data_manager.get_latest_price(symbol)
            if price:
                logger.info(f"{symbol} 最新价格: {price}")
            else:
                logger.warning(f"无法获取 {symbol} 价格")
        
        logger.info("数据管理器测试通过")
        return True
        
    except Exception as e:
        logger.error(f"数据管理器测试失败: {e}")
        return False

def test_strategies():
    """测试策略系统"""
    logger.info("测试策略系统...")
    
    try:
        # 测试策略工厂
        available_strategies = StrategyFactory.get_available_strategies()
        logger.info(f"可用策略: {available_strategies}")
        
        # 测试创建策略
        for strategy_type in available_strategies:
            strategy = StrategyFactory.create_strategy(strategy_type)
            logger.info(f"成功创建策略: {strategy.name}")
            
            # 测试策略描述
            description = StrategyFactory.get_strategy_description(strategy_type)
            logger.info(f"策略描述: {description}")
        
        logger.info("策略系统测试通过")
        return True
        
    except Exception as e:
        logger.error(f"策略系统测试失败: {e}")
        return False

def test_backtest_engine():
    """测试回测引擎"""
    logger.info("测试回测引擎...")
    
    try:
        # 创建策略
        strategy = StrategyFactory.create_strategy("ma_cross")
        
        # 创建回测引擎
        engine = BacktestEngine(initial_capital=10000.0)
        
        # 运行简单回测
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        results = engine.run_backtest(
            strategy=strategy,
            symbol="BTC-USD",
            start_date=start_date,
            end_date=end_date,
            timeframe="1d"
        )
        
        logger.info(f"回测完成，总收益率: {results['results']['total_return']:.2%}")
        logger.info(f"最大回撤: {results['results']['max_drawdown']:.2%}")
        logger.info(f"夏普比率: {results['results']['sharpe_ratio']:.2f}")
        logger.info(f"胜率: {results['results']['win_rate']:.2%}")
        logger.info(f"总交易次数: {results['results']['total_trades']}")
        
        logger.info("回测引擎测试通过")
        return True
        
    except Exception as e:
        logger.error(f"回测引擎测试失败: {e}")
        return False

def test_trading_engine():
    """测试交易引擎"""
    logger.info("测试交易引擎...")
    
    try:
        # 创建交易管理器
        trading_manager = TradingManager()
        
        # 创建模拟交易引擎
        engine = trading_manager.create_engine("test_engine", "paper", "binance")
        
        # 创建策略
        strategy = StrategyFactory.create_strategy("rsi")
        
        # 添加策略到引擎
        engine.add_strategy(strategy)
        
        # 生成信号
        signals = engine.generate_signals("BTC-USD", "1d")
        logger.info(f"生成了 {len(signals)} 个交易信号")
        
        # 获取账户摘要
        account_summary = engine.get_account_summary()
        logger.info(f"账户摘要: {account_summary}")
        
        # 获取持仓信息
        positions = engine.get_positions()
        logger.info(f"持仓信息: {positions}")
        
        logger.info("交易引擎测试通过")
        return True
        
    except Exception as e:
        logger.error(f"交易引擎测试失败: {e}")
        return False

def test_database():
    """测试数据库"""
    logger.info("测试数据库...")
    
    try:
        # 初始化数据库
        init_db()
        logger.info("数据库初始化成功")
        
        # 测试数据库连接
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("数据库连接测试成功")
        
        logger.info("数据库测试通过")
        return True
        
    except Exception as e:
        logger.error(f"数据库测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("=" * 50)
    logger.info("开始系统测试")
    logger.info("=" * 50)
    
    # 设置日志
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    
    # 测试结果
    test_results = []
    
    # 运行测试
    tests = [
        ("数据库", test_database),
        ("数据管理器", test_data_manager),
        ("策略系统", test_strategies),
        ("回测引擎", test_backtest_engine),
        ("交易引擎", test_trading_engine)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n开始测试: {test_name}")
        try:
            result = test_func()
            test_results.append((test_name, result))
        except Exception as e:
            logger.error(f"{test_name} 测试异常: {e}")
            test_results.append((test_name, False))
    
    # 输出测试结果
    logger.info("\n" + "=" * 50)
    logger.info("测试结果汇总")
    logger.info("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！系统运行正常。")
        return True
    else:
        logger.error("⚠️  部分测试失败，请检查系统配置。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 