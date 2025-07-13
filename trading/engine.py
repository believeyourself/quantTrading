import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import asyncio
import ccxt
import json

from strategies.base import BaseStrategy, Signal
from data.manager import data_manager
from utils.models import Trade, Account, SessionLocal
from config.settings import settings

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    def update_price(self, price: float):
        """更新当前价格"""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity

@dataclass
class Order:
    """订单信息"""
    id: str
    symbol: str
    side: str  # 'buy', 'sell'
    quantity: float
    price: float
    status: str  # 'pending', 'filled', 'cancelled', 'failed'
    timestamp: datetime
    strategy_name: str = ""

class TradingEngine:
    """交易引擎"""
    
    def __init__(self, trade_type: str = "paper", exchange_name: str = "binance"):
        self.trade_type = trade_type  # 'paper' 或 'live'
        self.exchange_name = exchange_name
        self.db = SessionLocal()
        
        # 模拟交易账户
        self.paper_account = {
            'balance': settings.DEFAULT_CAPITAL,
            'equity': settings.DEFAULT_CAPITAL,
            'positions': {},
            'orders': [],
            'trades': []
        }
        
        # 实盘交易
        if trade_type == "live":
            self.exchange = self._setup_exchange()
        
        # 策略和信号
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_signals: List[Signal] = []
        
        # 风险控制
        self.max_position_size = settings.MAX_POSITION_SIZE
        self.stop_loss_ratio = settings.STOP_LOSS_RATIO
        self.take_profit_ratio = settings.TAKE_PROFIT_RATIO
    
    def _setup_exchange(self) -> ccxt.Exchange:
        """设置交易所连接"""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            exchange = exchange_class({
                'apiKey': settings.API_KEY,
                'secret': settings.API_SECRET,
                'sandbox': settings.TESTNET,
                'enableRateLimit': True
            })
            
            # 测试连接
            exchange.load_markets()
            logger.info(f"成功连接到 {self.exchange_name} 交易所")
            return exchange
            
        except Exception as e:
            logger.error(f"连接交易所失败: {e}")
            raise
    
    def add_strategy(self, strategy: BaseStrategy):
        """添加交易策略"""
        self.strategies[strategy.name] = strategy
        logger.info(f"添加策略: {strategy.name}")
    
    def remove_strategy(self, strategy_name: str):
        """移除交易策略"""
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            logger.info(f"移除策略: {strategy_name}")
    
    def update_market_data(self, symbol: str, timeframe: str = "1d"):
        """更新市场数据"""
        try:
            data_manager.update_market_data(symbol, timeframe)
            logger.info(f"更新 {symbol} 市场数据完成")
        except Exception as e:
            logger.error(f"更新市场数据失败: {e}")
    
    def generate_signals(self, symbol: str, timeframe: str = "1d") -> List[Signal]:
        """生成交易信号"""
        signals = []
        
        try:
            # 获取最新数据
            data = data_manager.get_historical_data(symbol, timeframe, limit=100)
            if data.empty:
                return signals
            
            data['symbol'] = symbol
            
            # 为每个策略生成信号
            for strategy in self.strategies.values():
                strategy_signals = strategy.generate_signals(data)
                signals.extend(strategy_signals)
            
            # 更新活跃信号
            self.active_signals = signals
            
            logger.info(f"为 {symbol} 生成了 {len(signals)} 个交易信号")
            
        except Exception as e:
            logger.error(f"生成交易信号失败: {e}")
        
        return signals
    
    def execute_signals(self, signals: List[Signal]):
        """执行交易信号"""
        for signal in signals:
            try:
                if signal.signal == 'buy':
                    self._execute_buy_signal(signal)
                elif signal.signal == 'sell':
                    self._execute_sell_signal(signal)
            except Exception as e:
                logger.error(f"执行信号失败: {e}")
    
    def _execute_buy_signal(self, signal: Signal):
        """执行买入信号"""
        symbol = signal.symbol
        
        if self.trade_type == "paper":
            self._execute_paper_buy(signal)
        else:
            self._execute_live_buy(signal)
    
    def _execute_sell_signal(self, signal: Signal):
        """执行卖出信号"""
        symbol = signal.symbol
        
        if self.trade_type == "paper":
            self._execute_paper_sell(signal)
        else:
            self._execute_live_sell(signal)
    
    def _execute_paper_buy(self, signal: Signal):
        """执行模拟买入"""
        symbol = signal.symbol
        price = signal.price
        
        # 检查是否已有持仓
        if symbol in self.paper_account['positions']:
            logger.info(f"已有 {symbol} 持仓，跳过买入信号")
            return
        
        # 计算购买数量
        available_capital = self.paper_account['balance'] * self.max_position_size
        quantity = available_capital / price
        
        if quantity * price <= available_capital:
            # 创建持仓
            self.paper_account['positions'][symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=price,
                entry_time=signal.timestamp
            )
            
            # 更新账户余额
            self.paper_account['balance'] -= quantity * price
            
            # 记录交易
            trade = Trade(
                strategy_id=1,  # 这里应该从数据库获取策略ID
                exchange=self.exchange_name,
                symbol=symbol,
                side='buy',
                quantity=quantity,
                price=price,
                commission=0.0,
                timestamp=signal.timestamp,
                status='filled',
                trade_type='paper'
            )
            
            self._save_trade(trade)
            
            logger.info(f"模拟买入 {symbol}: {quantity} @ {price}")
    
    def _execute_paper_sell(self, signal: Signal):
        """执行模拟卖出"""
        symbol = signal.symbol
        price = signal.price
        
        # 检查是否有持仓
        if symbol not in self.paper_account['positions']:
            logger.info(f"没有 {symbol} 持仓，跳过卖出信号")
            return
        
        position = self.paper_account['positions'][symbol]
        quantity = position.quantity
        
        # 计算盈亏
        pnl = (price - position.entry_price) * quantity
        
        # 更新账户余额
        self.paper_account['balance'] += quantity * price
        
        # 记录交易
        trade = Trade(
            strategy_id=1,  # 这里应该从数据库获取策略ID
            exchange=self.exchange_name,
            symbol=symbol,
            side='sell',
            quantity=quantity,
            price=price,
            commission=0.0,
            timestamp=signal.timestamp,
            status='filled',
            trade_type='paper'
        )
        
        self._save_trade(trade)
        
        # 清除持仓
        del self.paper_account['positions'][symbol]
        
        logger.info(f"模拟卖出 {symbol}: {quantity} @ {price}, PnL: {pnl:.2f}")
    
    def _execute_live_buy(self, signal: Signal):
        """执行实盘买入"""
        try:
            symbol = signal.symbol
            price = signal.price
            
            # 获取账户余额
            balance = self._get_account_balance()
            available_capital = balance * self.max_position_size
            
            # 计算购买数量
            quantity = available_capital / price
            
            if quantity * price <= available_capital:
                # 创建市价订单
                order = self.exchange.create_market_buy_order(symbol, quantity)
                
                # 记录订单
                self._save_order(order, signal.strategy_name)
                
                logger.info(f"实盘买入 {symbol}: {quantity} @ {price}")
            
        except Exception as e:
            logger.error(f"实盘买入失败: {e}")
    
    def _execute_live_sell(self, signal: Signal):
        """执行实盘卖出"""
        try:
            symbol = signal.symbol
            price = signal.price
            
            # 获取持仓
            position = self._get_position(symbol)
            if not position or position['quantity'] <= 0:
                logger.info(f"没有 {symbol} 持仓，跳过卖出信号")
                return
            
            quantity = position['quantity']
            
            # 创建市价订单
            order = self.exchange.create_market_sell_order(symbol, quantity)
            
            # 记录订单
            self._save_order(order, signal.strategy_name)
            
            logger.info(f"实盘卖出 {symbol}: {quantity} @ {price}")
            
        except Exception as e:
            logger.error(f"实盘卖出失败: {e}")
    
    def _get_account_balance(self) -> float:
        """获取账户余额"""
        try:
            if self.trade_type == "paper":
                return self.paper_account['balance']
            else:
                balance = self.exchange.fetch_balance()
                return balance['total']['USDT']
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return 0.0
    
    def _get_position(self, symbol: str) -> Optional[Dict]:
        """获取持仓信息"""
        try:
            if self.trade_type == "paper":
                return self.paper_account['positions'].get(symbol)
            else:
                positions = self.exchange.fetch_positions([symbol])
                return positions[0] if positions else None
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return None
    
    def _save_trade(self, trade: Trade):
        """保存交易记录到数据库"""
        try:
            self.db.add(trade)
            self.db.commit()
        except Exception as e:
            logger.error(f"保存交易记录失败: {e}")
            self.db.rollback()
    
    def _save_order(self, order: Dict, strategy_name: str):
        """保存订单记录"""
        try:
            # 这里可以保存订单信息到数据库
            logger.info(f"订单已保存: {order['id']}")
        except Exception as e:
            logger.error(f"保存订单失败: {e}")
    
    def get_account_summary(self) -> Dict:
        """获取账户摘要"""
        try:
            if self.trade_type == "paper":
                # 计算总权益（余额 + 未实现盈亏）
                total_equity = self.paper_account['balance']
                for position in self.paper_account['positions'].values():
                    total_equity += position.unrealized_pnl
                
                return {
                    'account_type': 'paper',
                    'balance': self.paper_account['balance'],
                    'equity': total_equity,
                    'positions_count': len(self.paper_account['positions']),
                    'total_trades': len(self.paper_account['trades'])
                }
            else:
                balance = self.exchange.fetch_balance()
                return {
                    'account_type': 'live',
                    'balance': balance['total']['USDT'],
                    'equity': balance['total']['USDT'],
                    'free_balance': balance['free']['USDT'],
                    'used_balance': balance['used']['USDT']
                }
        except Exception as e:
            logger.error(f"获取账户摘要失败: {e}")
            return {
                'account_type': 'paper',
                'balance': 0.0,
                'equity': 0.0,
                'positions_count': 0,
                'total_trades': 0
            }
    
    def get_positions(self) -> List[Dict]:
        """获取所有持仓"""
        try:
            if self.trade_type == "paper":
                positions = []
                for symbol, position in self.paper_account['positions'].items():
                    positions.append({
                        'symbol': symbol,
                        'quantity': position.quantity,
                        'entry_price': position.entry_price,
                        'current_price': position.current_price,
                        'unrealized_pnl': position.unrealized_pnl
                    })
                return positions
            else:
                return self.exchange.fetch_positions()
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []
    
    def get_trade_history(self, symbol: str = None, limit: int = 100) -> List[Trade]:
        """获取交易历史"""
        try:
            query = self.db.query(Trade)
            if symbol:
                query = query.filter(Trade.symbol == symbol)
            return query.order_by(Trade.timestamp.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []
    
    def risk_check(self, signal: Signal) -> bool:
        """风险检查"""
        try:
            # 检查止损
            if signal.signal == 'buy':
                position = self._get_position(signal.symbol)
                if position:
                    loss_ratio = (position['entry_price'] - signal.price) / position['entry_price']
                    if loss_ratio > self.stop_loss_ratio:
                        logger.warning(f"触发止损: {signal.symbol}")
                        return False
            
            # 检查止盈
            if signal.signal == 'sell':
                position = self._get_position(signal.symbol)
                if position:
                    profit_ratio = (signal.price - position['entry_price']) / position['entry_price']
                    if profit_ratio > self.take_profit_ratio:
                        logger.info(f"触发止盈: {signal.symbol}")
                        return True
            
            return True
            
        except Exception as e:
            logger.error(f"风险检查失败: {e}")
            return False
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'db'):
            self.db.close()

# 交易管理器
class TradingManager:
    """交易管理器"""
    
    def __init__(self):
        self.engines: Dict[str, TradingEngine] = {}
    
    def create_engine(self, name: str, trade_type: str = "paper", 
                     exchange_name: str = "binance") -> TradingEngine:
        """创建交易引擎"""
        engine = TradingEngine(trade_type, exchange_name)
        self.engines[name] = engine
        logger.info(f"创建交易引擎: {name} ({trade_type})")
        return engine
    
    def get_engine(self, name: str) -> Optional[TradingEngine]:
        """获取交易引擎"""
        return self.engines.get(name)
    
    def remove_engine(self, name: str):
        """移除交易引擎"""
        if name in self.engines:
            del self.engines[name]
            logger.info(f"移除交易引擎: {name}")
    
    def list_engines(self) -> List[str]:
        """列出所有交易引擎"""
        return list(self.engines.keys())
    
    def run_strategy(self, engine_name: str, strategy: BaseStrategy, 
                    symbol: str, timeframe: str = "1d"):
        """运行策略"""
        engine = self.get_engine(engine_name)
        if not engine:
            logger.error(f"交易引擎不存在: {engine_name}")
            return
        
        try:
            # 添加策略
            engine.add_strategy(strategy)
            
            # 生成信号
            signals = engine.generate_signals(symbol, timeframe)
            
            # 执行信号
            engine.execute_signals(signals)
            
            logger.info(f"策略 {strategy.name} 运行完成")
            
        except Exception as e:
            logger.error(f"运行策略失败: {e}")

# 全局交易管理器实例
trading_manager = TradingManager() 