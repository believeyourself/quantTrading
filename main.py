#!/usr/bin/env python3
"""
加密货币资金费率监控系统主程序
"""

import os
import sys
import asyncio
import json
from loguru import logger
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import init_db, SessionLocal
from config.settings import settings
from data.manager import data_manager
from strategies.factory import StrategyFactory
from api.routes import app
from utils.notifier import send_telegram_message

# 导入新的监控策略
from strategies.funding_rate_arbitrage import FundingRateMonitor

class MonitorSystem:
    def __init__(self):
        self.monitors = []
        self.running = False

    async def start(self):
        """启动监控系统"""
        try:
            self.running = True
            logger.info("监控系统启动中...")

            # 从数据库加载监控配置
            self.load_monitors_from_db()

            # 如果没有监控配置，创建默认配置
            if not self.monitors:
                self.create_default_monitor()

            # 启动所有监控（包括定时任务）
            logger.info("启动监控策略...")
            for monitor in self.monitors:
                try:
                    # 启动监控（包括定时任务）
                    monitor.start_monitoring()
                    logger.info(f"✅ 监控策略已启动: {monitor.name}")
                except Exception as e:
                    logger.error(f"❌ 启动监控策略失败: {e}")

            logger.info("✅ 所有监控策略已启动")
            logger.info("💡 系统将自动执行定时任务")
            
            # 保持系统运行
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"监控系统启动失败: {e}")
            self.running = False

        except Exception as e:
            logger.error(f"监控系统启动失败: {e}")
            self.running = False

    def stop(self):
        """停止监控系统"""
        self.running = False
        for monitor in self.monitors:
            monitor.stop_monitoring()
        logger.info("监控系统已停止")

    def load_monitors_from_db(self):
        """从数据库加载监控配置"""
        try:
            logger.info("从数据库加载监控配置...")
            db = SessionLocal()

            from utils.models import Strategy
            monitor_strategies = db.query(Strategy).filter(
                Strategy.strategy_type == "funding_rate_arbitrage"
            ).all()

            for strategy in monitor_strategies:
                params = json.loads(strategy.parameters)
                monitor = StrategyFactory.create_strategy("funding_rate_arbitrage", params)
                self.monitors.append(monitor)
                logger.info(f"加载监控配置: {strategy.name}")

            logger.info(f"成功加载 {len(self.monitors)} 个监控配置")

        except Exception as e:
            logger.error(f"从数据库加载监控配置失败: {e}")
        finally:
            db.close()

    def create_default_monitor(self):
        """创建默认监控配置"""
        try:
            logger.info("创建默认监控配置...")
            db = SessionLocal()

            from utils.models import Strategy
            # 检查是否已有资金费率监控策略
            existing = db.query(Strategy).filter(
                Strategy.strategy_type == "funding_rate_arbitrage"
            ).first()

            if not existing:
                # 默认监控配置
                default_params = {
                    "funding_rate_threshold": 0.005,
                    "contract_refresh_interval": 60,
                    "funding_rate_check_interval": 60,
                    "max_pool_size": 20,
                    "min_volume": 1000000,
                    "exchanges": ["binance", "okx", "bybit"]
                }

                strategy = Strategy(
                    name="资金费率监控策略-默认",
                    description="资金费率监控策略的默认配置",
                    strategy_type="funding_rate_arbitrage",
                    parameters=json.dumps(default_params)
                )
                db.add(strategy)
                db.commit()
                logger.info("成功创建默认监控配置")

                # 创建监控实例
                monitor = StrategyFactory.create_strategy("funding_rate_arbitrage", default_params)
                self.monitors.append(monitor)
            else:
                logger.info("数据库中已有监控配置，跳过默认创建")

        except Exception as e:
            logger.error(f"创建默认监控配置失败: {e}")
            db.rollback()
        finally:
            db.close()

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
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

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

def run_monitor():
    """启动监控系统（包括定时任务）"""
    try:
        logger.info("启动资金费率监控系统...")

        # 创建监控系统实例
        monitor_system = MonitorSystem()

        # 启动监控系统（包括定时任务）
        logger.info("🚀 启动监控系统...")
        asyncio.run(monitor_system.start())
        
    except KeyboardInterrupt:
        logger.info("系统被用户中断")
        # 停止所有监控
        for monitor in monitor_system.monitors:
            try:
                monitor.stop_monitoring()
            except Exception as e:
                logger.error(f"停止监控失败: {e}")
        logger.info("✅ 所有监控已停止")
    except Exception as e:
        logger.error(f"监控系统启动失败: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"监控系统初始化失败: {e}")

def main():
    """主函数"""
    try:
        # 设置日志
        setup_logging()
        logger.info("=== 加密货币资金费率监控系统 启动 ===")

        # 初始化数据库
        initialize_database()

        # 测试数据连接
        test_data_connection()

        # 初始化监控系统（不自动启动）
        asyncio.run(run_monitor())

    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()