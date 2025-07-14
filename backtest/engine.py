import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import json

from strategies.base import BaseStrategy, Signal
from data.manager import data_manager
from utils.models import Backtest, BacktestTrade, SessionLocal
from utils.binance_funding import BinanceFunding

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    funding_income: float = 0.0  # 新增，累计资金费率收益
    last_funding_time: datetime = None  # 上次结算时间
    funding_rate: float = 0.0  # 当前持仓资金费率
    side: str = 'long'  # 'long' or 'short'
    
    def update_price(self, price: float):
        """更新当前价格"""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity

@dataclass
class Trade:
    """交易记录"""
    timestamp: datetime
    symbol: str
    side: str  # 'buy', 'sell'
    quantity: float
    price: float
    commission: float
    pnl: float = 0.0
    strategy_signal: str = ""

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = 10000.0, commission_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.current_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []
        self.db = SessionLocal()
        
    def run_backtest(self, strategy: BaseStrategy, symbol: str, 
                    start_date: str, end_date: str, timeframe: str = "1d") -> Dict:
        """资金费率套利专用回测：以资金费率事件为主线"""
        try:
            logger.info(f"开始回测: {strategy.name} on {symbol}")
            # 获取历史K线
            data = data_manager.get_historical_data(symbol, timeframe, start_date, end_date)
            if data.empty:
                raise ValueError(f"无法获取 {symbol} 的历史数据")
            data['symbol'] = symbol
            # 获取资金费率历史
            funding = BinanceFunding()
            funding_history = funding.get_funding_history(symbol, contract_type="UM", limit=1000)
            if not funding_history:
                raise ValueError(f"无法获取 {symbol} 的历史资金费率")
            df_funding = pd.DataFrame(funding_history)
            df_funding['funding_time'] = pd.to_datetime(df_funding['funding_time'], unit='ms')
            df_funding.set_index('funding_time', inplace=True)
            # 资金费率阈值
            threshold = strategy.parameters.get('funding_rate_threshold', 0.001)
            min_volume = strategy.parameters.get('min_volume', 1000000)
            # 回测主循环
            position = None
            funding_income = 0.0
            trades = []
            equity_curve = []
            capital = self.initial_capital
            quantity = None
            last_equity = capital
            for idx, (funding_time, row) in enumerate(df_funding.iterrows()):
                funding_rate = float(row['funding_rate'])
                # 取该时刻最近的K线收盘价
                kline_row = data[data.index <= funding_time].tail(1)
                if kline_row.empty:
                    continue
                price = float(kline_row['close_price'].values[0])
                # 建仓逻辑
                if position is None:
                    if abs(funding_rate) >= threshold:
                        # 假设每次用80%资金建仓
                        available_capital = capital * 0.8
                        quantity = available_capital / price
                        side = 'long' if funding_rate > 0 else 'short'
                        position = {
                            'entry_time': funding_time,
                            'entry_price': price,
                            'funding_rate': funding_rate,
                            'side': side,
                            'quantity': quantity,
                            'funding_income': 0.0
                        }
                        capital -= quantity * price  # 扣除建仓资金
                        trade = {
                            'timestamp': funding_time,
                            'symbol': symbol,
                            'side': 'buy' if side == 'long' else 'sell',
                            'quantity': quantity,
                            'price': price,
                            'commission': 0.0,
                            'pnl': 0.0,
                            'strategy_signal': strategy.name,
                            'funding_rate': funding_rate
                        }
                        trades.append(trade)
                else:
                    # 持仓期间累加资金费率收益
                    direction = 1 if position['side'] == 'long' else -1
                    funding_income = position['funding_income'] + quantity * price * funding_rate * direction
                    position['funding_income'] = funding_income
                    # 平仓逻辑：资金费率绝对值低于阈值时平仓
                    if abs(funding_rate) < threshold:
                        exit_price = price
                        pnl = (exit_price - position['entry_price']) * quantity * direction
                        total_pnl = pnl + funding_income
                        capital += quantity * exit_price + total_pnl  # 卖出返还+资金费率收益
                        trade = {
                            'timestamp': funding_time,
                            'symbol': symbol,
                            'side': 'sell' if position['side'] == 'long' else 'buy',
                            'quantity': quantity,
                            'price': exit_price,
                            'commission': 0.0,
                            'pnl': total_pnl,
                            'strategy_signal': strategy.name,
                            'funding_rate': funding_rate
                        }
                        trades.append(trade)
                        position = None
                        funding_income = 0.0
                # 记录资金曲线
                equity_curve.append({
                    'timestamp': funding_time,
                    'equity': capital,
                    'capital': capital,
                    'positions_value': (quantity * price if position else 0.0)
                })
                last_equity = capital + (quantity * price if position else 0.0)
            # 若最后还持仓，强制平仓
            if position is not None:
                exit_price = price
                direction = 1 if position['side'] == 'long' else -1
                pnl = (exit_price - position['entry_price']) * quantity * direction
                total_pnl = pnl + position['funding_income']
                capital += quantity * exit_price + total_pnl
                trade = {
                    'timestamp': funding_time,
                    'symbol': symbol,
                    'side': 'sell' if position['side'] == 'long' else 'buy',
                    'quantity': quantity,
                    'price': exit_price,
                    'commission': 0.0,
                    'pnl': total_pnl,
                    'strategy_signal': strategy.name,
                    'funding_rate': funding_rate
                }
                trades.append(trade)
                equity_curve.append({
                    'timestamp': funding_time,
                    'equity': capital,
                    'capital': capital,
                    'positions_value': 0.0
                })
            # 统计结果
            initial_equity = self.initial_capital
            final_equity = last_equity
            total_return = (final_equity - initial_equity) / initial_equity
            max_drawdown = 0.0
            if equity_curve:
                eq_df = pd.DataFrame(equity_curve)
                eq_df.set_index('timestamp', inplace=True)
                eq_df['peak'] = eq_df['equity'].expanding().max()
                eq_df['drawdown'] = (eq_df['equity'] - eq_df['peak']) / eq_df['peak']
                max_drawdown = eq_df['drawdown'].min()
            daily_returns = eq_df['equity'].pct_change().dropna() if equity_curve else pd.Series([])
            sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() > 0 else 0
            win_trades = [t for t in trades if t.get('pnl', 0) > 0]
            win_rate = len(win_trades) / len(trades) if trades else 0
            total_trades = len(trades)
            total_pnl = sum(t.get('pnl', 0) for t in trades)
            avg_trade_pnl = total_pnl / total_trades if total_trades > 0 else 0
            results = {
                'initial_capital': initial_equity,
                'final_capital': final_equity,
                'total_return': total_return,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'avg_trade_pnl': avg_trade_pnl
            }
            return {
                'backtest_id': 0,
                'results': results,
                'trades': trades,
                'equity_curve': equity_curve
            }
        except Exception as e:
            logger.error(f"回测失败: {e}")
            raise
    
    def _execute_backtest(self, data: pd.DataFrame, signals: List[Signal]):
        """执行回测逻辑，支持资金费率收益模拟"""
        signals.sort(key=lambda x: x.timestamp)
        signal_idx = 0
        signals_len = len(signals)
        for timestamp in data.index:
            current_price = data.loc[timestamp, 'close_price']
            # 资金费率结算点：每小时K线的bar都算一次
            # 遍历所有持仓，累加资金费率收益
            for symbol, position in list(self.positions.items()):
                # 获取当前bar的资金费率（可用信号metadata或默认0）
                funding_rate = position.funding_rate
                # 若有信号在此bar，优先用信号的metadata
                for s in signals[signal_idx:]:
                    if s.symbol == symbol and s.timestamp == timestamp and 'funding_rate' in (s.metadata or {}):
                        funding_rate = s.metadata['funding_rate']
                        break
                # 资金费率收益 = 持仓数量 × 当前价格 × 资金费率 × 方向
                direction = 1 if position.side == 'long' else -1
                funding_income = position.quantity * current_price * funding_rate * direction
                position.funding_income += funding_income
                self.current_capital += funding_income
            # 更新持仓的未实现盈亏
            self._update_positions(current_price)
            # 检查是否有交易信号
            day_signals = [s for s in signals if s.timestamp == timestamp]
            for signal in day_signals:
                # 只处理当前symbol
                symbol = signal.symbol
                side = signal.signal
                if side == 'buy':
                    if symbol not in self.positions or self.positions[symbol].quantity <= 0:
                        available_capital = self.current_capital * 0.8
                        quantity = available_capital / current_price
                        commission = quantity * current_price * self.commission_rate
                        if quantity * current_price + commission <= available_capital:
                            self.positions[symbol] = Position(
                                symbol=symbol,
                                quantity=quantity,
                                entry_price=current_price,
                                entry_time=timestamp,
                                funding_income=0.0,
                                last_funding_time=timestamp,
                                funding_rate=signal.metadata.get('funding_rate', 0.0) if signal.metadata else 0.0,
                                side='long'
                            )
                            self.trades.append(Trade(
                                timestamp=timestamp,
                                symbol=symbol,
                                side='buy',
                                quantity=quantity,
                                price=current_price,
                                commission=commission,
                                strategy_signal=signal.strategy_name
                            ))
                            self.current_capital -= (quantity * current_price + commission)
                elif side == 'sell':
                    if symbol in self.positions and self.positions[symbol].quantity > 0:
                        position = self.positions[symbol]
                        quantity = position.quantity
                        commission = quantity * current_price * self.commission_rate
                        # 价差盈亏
                        pnl = (current_price - position.entry_price) * quantity
                        if position.side == 'short':
                            pnl = -pnl
                        # 总盈亏 = 价差 + 资金费率
                        total_pnl = pnl + position.funding_income
                        self.trades.append(Trade(
                            timestamp=timestamp,
                            symbol=symbol,
                            side='sell',
                            quantity=quantity,
                            price=current_price,
                            commission=commission,
                            pnl=total_pnl,
                            strategy_signal=signal.strategy_name
                        ))
                        self.current_capital += (quantity * current_price - commission)
                        del self.positions[symbol]
            # 记录权益曲线
            self._record_equity(timestamp, current_price)
    
    def _execute_signal(self, signal: Signal, current_price: float, timestamp: datetime):
        """执行交易信号"""
        symbol = signal.symbol
        
        if signal.signal == 'buy':
            # 买入逻辑
            if symbol not in self.positions or self.positions[symbol].quantity <= 0:
                # 计算购买数量（使用可用资金的80%）
                available_capital = self.current_capital * 0.8
                quantity = available_capital / current_price
                commission = quantity * current_price * self.commission_rate
                
                if quantity * current_price + commission <= available_capital:
                    # 创建新持仓
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        quantity=quantity,
                        entry_price=current_price,
                        entry_time=timestamp
                    )
                    
                    # 记录交易
                    self.trades.append(Trade(
                        timestamp=timestamp,
                        symbol=symbol,
                        side='buy',
                        quantity=quantity,
                        price=current_price,
                        commission=commission,
                        strategy_signal=signal.strategy_name
                    ))
                    
                    # 更新资金
                    self.current_capital -= (quantity * current_price + commission)
                    
        elif signal.signal == 'sell':
            # 卖出逻辑
            if symbol in self.positions and self.positions[symbol].quantity > 0:
                position = self.positions[symbol]
                quantity = position.quantity
                commission = quantity * current_price * self.commission_rate
                
                # 计算盈亏
                pnl = (current_price - position.entry_price) * quantity - commission
                
                # 记录交易
                self.trades.append(Trade(
                    timestamp=timestamp,
                    symbol=symbol,
                    side='sell',
                    quantity=quantity,
                    price=current_price,
                    commission=commission,
                    pnl=pnl,
                    strategy_signal=signal.strategy_name
                ))
                
                # 更新资金
                self.current_capital += (quantity * current_price - commission)
                
                # 清除持仓
                del self.positions[symbol]
    
    def _update_positions(self, current_price: float):
        """更新持仓信息"""
        for position in self.positions.values():
            position.update_price(current_price)
    
    def _record_equity(self, timestamp: datetime, current_price: float):
        """记录权益曲线"""
        # 计算当前总资产
        total_equity = self.current_capital
        
        for position in self.positions.values():
            total_equity += position.quantity * current_price
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': total_equity,
            'capital': self.current_capital,
            'positions_value': total_equity - self.current_capital
        })
    
    def _calculate_results(self) -> Dict:
        """计算回测结果"""
        if not self.equity_curve:
            return {}
        
        # 转换为DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('timestamp', inplace=True)
        
        # 计算基础指标
        initial_equity = self.initial_capital
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity - initial_equity) / initial_equity
        
        # 计算最大回撤
        equity_df['peak'] = equity_df['equity'].expanding().max()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
        max_drawdown = equity_df['drawdown'].min()
        
        # 计算夏普比率
        daily_returns = equity_df['equity'].pct_change().dropna()
        sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() > 0 else 0
        
        # 计算胜率
        winning_trades = [t for t in self.trades if t.pnl > 0]
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0
        
        # 计算其他指标
        total_trades = len(self.trades)
        total_commission = sum(t.commission for t in self.trades)
        total_pnl = sum(t.pnl for t in self.trades)
        
        return {
            'initial_capital': initial_equity,
            'final_capital': final_equity,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'total_commission': total_commission,
            'total_pnl': total_pnl,
            'avg_trade_pnl': total_pnl / total_trades if total_trades > 0 else 0
        }
    
    def _save_backtest_results(self, strategy: BaseStrategy, symbol: str, timeframe: str,
                             start_date: str, end_date: str, results: Dict) -> int:
        """保存回测结果到数据库"""
        try:
            # 创建回测记录
            backtest = Backtest(
                strategy_id=1,  # 这里应该从数据库获取策略ID
                name=f"{strategy.name}_{symbol}_{start_date}_{end_date}",
                symbol=symbol,
                timeframe=timeframe,
                start_date=datetime.strptime(start_date, "%Y-%m-%d"),
                end_date=datetime.strptime(end_date, "%Y-%m-%d"),
                initial_capital=results['initial_capital'],
                final_capital=results['final_capital'],
                total_return=results['total_return'],
                max_drawdown=results['max_drawdown'],
                sharpe_ratio=results['sharpe_ratio'],
                win_rate=results['win_rate'],
                total_trades=results['total_trades'],
                status='completed',
                results=json.dumps(results)
            )
            
            self.db.add(backtest)
            self.db.commit()
            self.db.refresh(backtest)
            
            # 保存交易记录
            for trade in self.trades:
                backtest_trade = BacktestTrade(
                    backtest_id=backtest.id,
                    timestamp=trade.timestamp,
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    commission=trade.commission,
                    pnl=trade.pnl,
                    strategy_signal=trade.strategy_signal
                )
                self.db.add(backtest_trade)
            
            self.db.commit()
            
            return backtest.id
            
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
            self.db.rollback()
            return 0
    
    def get_backtest_summary(self) -> Dict:
        """获取回测摘要"""
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'total_trades': len(self.trades),
            'open_positions': len(self.positions),
            'equity_curve_length': len(self.equity_curve)
        }
    
    def reset(self):
        """重置回测引擎"""
        self.current_capital = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'db'):
            self.db.close()

# 回测管理器
class BacktestManager:
    """回测管理器"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def create_backtest(self, strategy_id: int, symbol: str, timeframe: str,
                       start_date: str, end_date: str, initial_capital: float) -> int:
        """创建回测任务"""
        try:
            backtest = Backtest(
                strategy_id=strategy_id,
                name=f"Backtest_{symbol}_{start_date}_{end_date}",
                symbol=symbol,
                timeframe=timeframe,
                start_date=datetime.strptime(start_date, "%Y-%m-%d"),
                end_date=datetime.strptime(end_date, "%Y-%m-%d"),
                initial_capital=initial_capital,
                status='running'
            )
            
            self.db.add(backtest)
            self.db.commit()
            self.db.refresh(backtest)
            
            return backtest.id
            
        except Exception as e:
            logger.error(f"创建回测任务失败: {e}")
            self.db.rollback()
            return 0
    
    def get_backtest(self, backtest_id: int) -> Optional[Backtest]:
        """获取回测记录"""
        return self.db.query(Backtest).filter(Backtest.id == backtest_id).first()
    
    def get_backtest_trades(self, backtest_id: int) -> List[BacktestTrade]:
        """获取回测交易记录"""
        return self.db.query(BacktestTrade).filter(
            BacktestTrade.backtest_id == backtest_id
        ).order_by(BacktestTrade.timestamp).all()
    
    def list_backtests(self, strategy_id: Optional[int] = None) -> List[Backtest]:
        """列出回测记录"""
        query = self.db.query(Backtest)
        if strategy_id:
            query = query.filter(Backtest.strategy_id == strategy_id)
        return query.order_by(Backtest.created_at.desc()).all()
    
    def delete_backtest(self, backtest_id: int) -> bool:
        """删除回测记录"""
        try:
            backtest = self.get_backtest(backtest_id)
            if backtest:
                self.db.delete(backtest)
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"删除回测记录失败: {e}")
            self.db.rollback()
            return False
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'db'):
            self.db.close() 