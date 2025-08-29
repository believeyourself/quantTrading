#!/usr/bin/env python3
"""
加密货币资金费率监控系统主程序
"""

import os
import sys
import asyncio
import signal
from loguru import logger
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from strategies.factory import StrategyFactory
from api.routes import app
from utils.notifier import send_telegram_message, send_email_notification

# 导入新的监控策略
from strategies.funding_rate_arbitrage import FundingRateMonitor

class MonitorSystem:
    def __init__(self):
        self.monitors = []
        self.running = False
        # 设置信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，正在停止监控系统...")
        self.stop()
        sys.exit(0)

    async def start(self):
        """启动监控系统"""
        try:
            self.running = True
            logger.info("监控系统启动中...")

            # 直接创建监控策略，从settings.py读取配置
            self.create_monitor_from_settings()

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
            
            # 发送系统启动邮件通知
            try:
                send_email_notification(
                    "系统启动通知", 
                    "量化交易资金费率监控系统已成功启动，所有监控策略已激活。"
                )
            except Exception as e:
                logger.warning(f"发送系统启动邮件通知失败: {e}")
            
            # 保持系统运行
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"监控系统启动失败: {e}")
            self.running = False

    def stop(self):
        """停止监控系统"""
        self.running = False
        
        # 发送系统停止邮件通知
        try:
            send_email_notification(
                "系统停止通知", 
                "量化交易资金费率监控系统已停止运行。"
            )
        except Exception as e:
            logger.warning(f"发送系统停止邮件通知失败: {e}")
        
        for monitor in self.monitors:
            monitor.stop_monitoring()
        logger.info("监控系统已停止")

    def create_monitor_from_settings(self):
        """直接从settings.py创建监控策略"""
        try:
            logger.info("从settings.py创建监控策略...")
            
            # 从settings.py读取配置参数
            monitor_params = {
                "funding_rate_threshold": settings.FUNDING_RATE_THRESHOLD,
                "max_contracts_in_pool": settings.MAX_POOL_SIZE,
                "min_volume": settings.MIN_VOLUME,
                "cache_duration": settings.CACHE_DURATION,
                "update_interval": settings.UPDATE_INTERVAL,
                "contract_refresh_interval": settings.CONTRACT_REFRESH_INTERVAL,
                "funding_rate_check_interval": settings.FUNDING_RATE_CHECK_INTERVAL,
            }
            
            logger.info(f"📋 监控策略参数: {monitor_params}")
            
            # 创建监控实例
            monitor = StrategyFactory.create_strategy("funding_rate_arbitrage", monitor_params)
            self.monitors.append(monitor)
            
            logger.info("✅ 监控策略创建成功")
            
        except Exception as e:
            logger.error(f"创建监控策略失败: {e}")

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

def test_data_connection():
    """测试数据连接"""
    try:
        logger.info("测试数据连接...")
        
        # 内联数据读取功能
        symbols = []
        try:
            import json
            cache_file = "cache/all_funding_contracts_full.json"
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 从全量缓存中获取所有合约
                    contracts_by_interval = data.get('contracts_by_interval', {})
                    all_contracts = {}
                    for interval, contracts in contracts_by_interval.items():
                        all_contracts.update(contracts)
                    symbols = list(all_contracts.keys())
        except Exception as e:
            logger.warning(f"读取缓存文件失败: {e}")
        
        logger.info(f"获取到 {len(symbols)} 个交易对")
        
        # 测试获取最新价格
        if symbols:
            test_symbol = symbols[0]
            price = 0
            try:
                if os.path.exists(cache_file):
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 从全量缓存中查找合约
                        contracts_by_interval = data.get('contracts_by_interval', {})
                        all_contracts = {}
                        for interval, contracts in contracts_by_interval.items():
                            all_contracts.update(contracts)
                        
                        if test_symbol in all_contracts:
                            price = all_contracts[test_symbol].get('mark_price', 0)
            except Exception as e:
                logger.warning(f"读取价格失败: {e}")
            
            if price:
                logger.info(f"{test_symbol} 最新价格: {price}")
            else:
                logger.warning(f"无法获取 {test_symbol} 的价格")
        
        logger.info("数据连接测试完成")
        
    except Exception as e:
        logger.error(f"数据连接测试失败: {e}")

def run_monitor():
    """启动监控系统（包括定时任务）"""
    monitor_system = None
    try:
        logger.info("启动资金费率监控系统...")

        # 创建监控系统实例
        monitor_system = MonitorSystem()

        # 启动监控系统（包括定时任务）
        logger.info("🚀 启动监控系统...")
        asyncio.run(monitor_system.start())
        
    except KeyboardInterrupt:
        logger.info("系统被用户中断")
    except Exception as e:
        logger.error(f"监控系统启动失败: {e}")
    finally:
        # 确保在退出时停止所有监控
        if monitor_system:
            logger.info("正在停止所有监控...")
            try:
                monitor_system.stop()
                logger.info("✅ 所有监控已停止")
            except Exception as e:
                logger.error(f"停止监控时发生错误: {e}")
        
        logger.info("监控系统已退出")

def main():
    """主函数"""
    try:
        # 设置日志
        setup_logging()
        logger.info("=== 加密货币资金费率监控系统 启动 ===")

        # 测试数据连接
        test_data_connection()

        # 启动监控系统
        run_monitor()

    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()