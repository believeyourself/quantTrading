import time
import json
import os
from typing import Dict, Set, Optional, List, Tuple
from datetime import datetime, timedelta
from .base import BaseStrategy, Signal
from utils.notifier import send_telegram_message
from config.proxy_settings import get_proxy_dict, get_ccxt_proxy_config, test_proxy_connection
import threading
import schedule
from utils.binance_funding import BinanceFunding
import pandas as pd
from dataclasses import dataclass

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: str  # 'long' 或 'short'
    quantity: float
    entry_price: float
    entry_time: datetime
    funding_rate: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    def update_pnl(self, current_price: float):
        """更新未实现盈亏"""
        if self.side == 'long':
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity

class FundingRateArbitrageStrategy(BaseStrategy):
    """资金费率套利策略 - 自动交易版本"""
    
    def __init__(self, parameters: Dict = None):
        # 首先尝试从配置文件加载参数
        config_file = "config/funding_monitor_config.json"
        config_params = {}
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    config_params = {
                        'funding_rate_threshold': config_data.get('funding_rate_threshold', 0.005),
                        'max_positions': config_data.get('max_contracts_in_pool', 20),
                        'min_volume': config_data.get('min_volume_24h', 1000000),
                        'cache_duration': config_data.get('cache_settings', {}).get('pool_cache_duration', 7200),
                        'update_interval': config_data.get('scan_interval_seconds', 1800),
                        'funding_interval': 28800,  # 资金费率结算周期（秒，8小时）
                        'contract_refresh_interval': 60, # 合约池刷新间隔（秒，1小时）
                        'funding_rate_check_interval': 30, # 资金费率检测间隔（秒，5分钟）
                        'position_size_ratio': 0.05,      # 每个仓位占总资金的比例
                        'max_total_exposure': 0.8,        # 最大总敞口比例
                        'stop_loss_ratio': 0.05,          # 止损比例
                        'take_profit_ratio': 0.10,        # 止盈比例
                        'auto_trade': True,               # 是否自动交易
                        'paper_trading': True,            # 是否模拟交易
                        'min_position_hold_time': 3600    # 最小持仓时间（秒）
                    }
                print(f"📋 从配置文件加载参数: funding_rate_threshold={config_params['funding_rate_threshold']:.4%}")
            except Exception as e:
                print(f"⚠️ 读取配置文件失败: {e}")
        
        # 默认参数（如果配置文件不存在或读取失败）
        default_params = {
            'funding_rate_threshold': 0.005,  # 0.5% 阈值
            'max_positions': 20,              # 最大持仓数量
            'min_volume': 1000000,            # 最小24小时成交量
            'cache_duration': 7200,           # 缓存时间（秒）
            'update_interval': 1800,          # 更新间隔（秒，30分钟）
            'funding_interval': 28800,        # 资金费率结算周期（秒，8小时）
            'contract_refresh_interval': 60, # 合约池刷新间隔（秒，1小时）
            'funding_rate_check_interval': 30, # 资金费率检测间隔（秒，5分钟）
            'position_size_ratio': 0.05,      # 每个仓位占总资金的比例
            'max_total_exposure': 0.8,        # 最大总敞口比例
            'stop_loss_ratio': 0.05,          # 止损比例
            'take_profit_ratio': 0.10,        # 止盈比例
            'auto_trade': True,               # 是否自动交易
            'paper_trading': True,            # 是否模拟交易
            'min_position_hold_time': 3600    # 最小持仓时间（秒）
        }
        
        # 合并参数：默认参数 < 外部传参 < 配置文件（配置文件优先级最高）
        params = {**default_params, **(parameters or {}), **config_params}
        super().__init__("资金费率套利策略", params)
        
        # 合约池管理
        self.contract_pool: Set[str] = set()  # 当前池子中的合约
        self.cached_contracts = {}  # 缓存的合约信息
        self.last_update_time = None
        self.cache_file = "cache/funding_rate_contracts.json"
        self._updating = False
        self._update_lock = threading.Lock()
        self.funding = BinanceFunding()
        
        # 持仓管理
        self.positions: Dict[str, Position] = {}  # 当前持仓
        self.position_history: List[Position] = []  # 历史持仓
        self.total_capital = 10000.0  # 总资金
        self.available_capital = 10000.0  # 可用资金
        
        # 交易统计
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        
        # 风险控制
        self.max_position_value = self.total_capital * self.parameters['position_size_ratio']
        self.max_total_exposure = self.total_capital * self.parameters['max_total_exposure']
        
        os.makedirs("cache", exist_ok=True)
        self._load_cache(load_on_startup=True) # 启动时加载缓存
        self._load_positions()
        # 不立即启动更新线程，等待策略启动时再启动
        self._update_threads_started = False

    def _load_cache(self, load_on_startup=True):
        """加载缓存，可选择是否在启动时加载"""
        if load_on_startup and os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cached_contracts = json.load(f)
            self.contract_pool = set(self.cached_contracts.keys())
            self.last_update_time = datetime.now()
            print(f"📋 从缓存加载了 {len(self.contract_pool)} 个合约")
        else:
            self.cached_contracts = {}
            self.contract_pool = set()
            self.last_update_time = None
            print("🔄 清空合约池，准备重新检测")

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cached_contracts, f, ensure_ascii=False, indent=2)

    def _load_positions(self):
        """加载持仓信息"""
        positions_file = "cache/positions.json"
        if os.path.exists(positions_file):
            try:
                with open(positions_file, 'r', encoding='utf-8') as f:
                    positions_data = json.load(f)
                
                for symbol, pos_data in positions_data.items():
                    self.positions[symbol] = Position(
                        symbol=pos_data['symbol'],
                        side=pos_data['side'],
                        quantity=pos_data['quantity'],
                        entry_price=pos_data['entry_price'],
                        entry_time=datetime.fromisoformat(pos_data['entry_time']),
                        funding_rate=pos_data['funding_rate'],
                        unrealized_pnl=pos_data.get('unrealized_pnl', 0.0),
                        realized_pnl=pos_data.get('realized_pnl', 0.0)
                    )
                print(f"📊 加载了 {len(self.positions)} 个持仓")
            except Exception as e:
                print(f"❌ 加载持仓失败: {e}")

    def _save_positions(self):
        """保存持仓信息"""
        positions_file = "cache/positions.json"
        positions_data = {}
        
        for symbol, position in self.positions.items():
            positions_data[symbol] = {
                'symbol': position.symbol,
                'side': position.side,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'entry_time': position.entry_time.isoformat(),
                'funding_rate': position.funding_rate,
                'unrealized_pnl': position.unrealized_pnl,
                'realized_pnl': position.realized_pnl
            }
        
        with open(positions_file, 'w', encoding='utf-8') as f:
            json.dump(positions_data, f, ensure_ascii=False, indent=2)

    def _is_cache_valid(self) -> bool:
        if not self.last_update_time:
            return False
        cache_age = (datetime.now() - self.last_update_time).total_seconds()
        return cache_age < self.parameters['cache_duration']

    def _update_cached_contracts(self):
        with self._update_lock:
            if self._updating:
                return
            self._updating = True
        try:
            # 只用缓存的合约池，批量获取资金费率
            updated = {}
            for symbol in self.contract_pool:
                info = self.funding.get_comprehensive_info(symbol, contract_type="UM")
                if info:
                    updated[symbol] = info
                time.sleep(0.1)
            self.cached_contracts = updated
            self.last_update_time = datetime.now()
            self._save_cache()
        finally:
            self._updating = False

    def _check_all_1h_contracts_funding_rates(self):
        """检测所有1小时结算合约的资金费率，项目启动时调用一次"""
        print("🔍 项目启动：检测所有1小时结算合约的资金费率...")
        
        # 获取所有1小时结算合约
        h1_contracts = self.funding.get_1h_contracts_from_cache()
        
        if not h1_contracts:
            print("⚠️ 没有找到缓存的1小时结算合约，开始扫描...")
            h1_contracts = self.funding.scan_1h_funding_contracts(contract_type="UM")
        
        if not h1_contracts:
            print("❌ 无法获取1小时结算合约")
            return {}
        
        print(f"📊 获取到 {len(h1_contracts)} 个1小时结算合约，开始检测资金费率...")
        
        # 检测所有合约的资金费率
        all_contracts_info = {}
        threshold = self.parameters['funding_rate_threshold']
        
        for i, symbol in enumerate(h1_contracts.keys()):
            try:
                # 获取合约详细信息
                info = self.funding.get_comprehensive_info(symbol, "UM")
                if info and info.get('current_funding_rate'):
                    rate = float(info['current_funding_rate'])
                    volume_24h = info.get('volume_24h', 0)
                    
                    # 确保volume_24h是数值类型
                    try:
                        volume_24h = float(volume_24h) if volume_24h is not None else 0.0
                    except (ValueError, TypeError):
                        volume_24h = 0.0
                    
                    # 检查是否符合条件
                    if abs(rate) >= float(threshold) and volume_24h >= self.parameters['min_volume']:
                        direction = "做多" if rate > 0 else "做空"
                        print(f"  ✅ {symbol}: {rate:.4%} ({direction}) - 符合条件")
                    else:
                        print(f"  📊 {symbol}: {rate:.4%} - 不符合条件")
                    
                    all_contracts_info[symbol] = info
                
                # 限流控制
                if (i + 1) % 10 == 0:
                    print(f"    进度: {i + 1}/{len(h1_contracts)}")
                    time.sleep(0.5)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                if "rate limit" in str(e).lower():
                    print(f"  ⚠️ {symbol}: 限流，跳过")
                    time.sleep(1)
                else:
                    print(f"  ❌ {symbol}: 检测失败 - {e}")
                continue
        
        # 更新缓存
        self.cached_contracts = all_contracts_info
        self.last_update_time = datetime.now()
        self._save_cache()
        
        print(f"✅ 资金费率检测完成，共检测 {len(all_contracts_info)} 个合约")
        
        # 项目启动时执行一次合约池更新和交易
        print("🚀 项目启动：执行初始合约池更新和交易...")
        self.update_contract_pool(all_contracts_info)
        
        return all_contracts_info

    def _refresh_contract_pool(self):
        """刷新合约池 - 使用缓存的1小时结算合约，筛选符合资金费率阈值的合约"""
        print("🔄 开始刷新合约池...")
        
        # 获取缓存的1小时结算合约
        h1_contracts = self.funding.get_1h_contracts_from_cache()
        
        if not h1_contracts:
            print("⚠️ 没有找到缓存的1小时结算合约，开始扫描...")
            h1_contracts = self.funding.scan_1h_funding_contracts(contract_type="UM")
        
        if not h1_contracts:
            print("❌ 无法获取1小时结算合约")
            return
        
        print(f"📊 获取到 {len(h1_contracts)} 个1小时结算合约")
        
        # 检测资金费率，筛选符合条件的合约
        qualified_contracts = {}
        threshold = self.parameters['funding_rate_threshold']
        
        for i, symbol in enumerate(h1_contracts.keys()):
            try:
                # 更新资金费率信息
                info = self.funding.get_comprehensive_info(symbol, "UM")
                if info and info.get('current_funding_rate'):
                    rate = float(info['current_funding_rate'])
                    if abs(rate) >= threshold:
                        qualified_contracts[symbol] = info
                        direction = "做多" if rate > 0 else "做空"
                        print(f"  ✅ {symbol}: {rate:.4%} ({direction}) - 符合条件")
                    else:
                        print(f"  📊 {symbol}: {rate:.4%} - 不符合条件")
                
                # 限流控制
                if (i + 1) % 10 == 0:
                    print(f"    进度: {i + 1}/{len(h1_contracts)}")
                    time.sleep(0.5)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                if "rate limit" in str(e).lower():
                    print(f"  ⚠️ {symbol}: 限流，跳过")
                    time.sleep(1)
                else:
                    print(f"  ❌ {symbol}: 检测失败 - {e}")
                continue
        
        # 更新合约池
        self.cached_contracts = qualified_contracts
        self.contract_pool = set(qualified_contracts.keys())
        self.last_update_time = datetime.now()
        self._save_cache()
        
        print(f"✅ 合约池刷新完成，找到 {len(qualified_contracts)} 个符合条件的合约")

    def _start_funding_rate_check_thread(self):
        print(">>> 启动资金费率检测线程")
        def funding_rate_check_loop():
            print(">>> 进入funding_rate_check_loop循环体")
            while self._update_threads_started:
                try:
                    print(f"🔍 [{datetime.now()}] 定时检测资金费率...")
                    self._check_funding_rates_and_trade()
                    time.sleep(self.parameters['funding_rate_check_interval'])
                except Exception as e:
                    print(f"❌ 资金费率检测失败: {e}")
                    time.sleep(60)
        t = threading.Thread(target=funding_rate_check_loop, daemon=True)
        t.start()

    def _check_funding_rates_and_trade(self):
        """检测资金费率并执行交易（每次都获取最新数据，不用缓存）"""
        print("📊 检测资金费率并更新合约池（实时获取最新数据）...")
        from utils.binance_funding import get_all_funding_rates, get_all_24h_volumes
        # 1. 加载候选池（所有1小时结算合约，严格按json结构）
        all_1h_file = "cache/1h_funding_contracts_full.json"
        contracts = {}
        if os.path.exists(all_1h_file):
            with open(all_1h_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                contracts = data.get("contracts", {})
        else:
            print("⚠️ 未找到1小时合约池缓存，候选池为空")
            return

        # 2. 批量获取资金费率和24h成交量
        all_funding_rates = get_all_funding_rates()  # symbol -> info
        all_24h_volumes = get_all_24h_volumes()      # symbol -> quoteVolume
        threshold = self.parameters['funding_rate_threshold']
        min_volume = self.parameters['min_volume']
        funding_rates = {}
        for symbol, info in contracts.items():
            rate_info = all_funding_rates.get(symbol)
            volume_24h = all_24h_volumes.get(symbol, 0.0)
            merged_info = dict(info)
            if rate_info and rate_info.get('lastFundingRate') is not None:
                merged_info['current_funding_rate'] = float(rate_info['lastFundingRate'])
                merged_info['mark_price'] = float(rate_info.get('markPrice', 0))
            merged_info['volume_24h'] = float(volume_24h)
            funding_rates[symbol] = merged_info
            # 新增日志打印
            rate_str = merged_info.get('current_funding_rate', 'N/A')
            print(f"合约: {symbol}, 资金费率: {rate_str}, 24h成交量: {merged_info['volume_24h']}")
        # 3. 更新合约池并执行交易
        self.update_contract_pool(funding_rates)

    def _start_update_thread(self):
        def update_loop():
            while self._update_threads_started:
                if not self._is_cache_valid():
                    print("⚠️ 缓存已过期，正在更新...")
                    self._update_cached_contracts()
                time.sleep(self.parameters['update_interval'])
        t = threading.Thread(target=update_loop, daemon=True)
        t.start()

    def _start_contract_refresh_thread(self):
        def refresh_loop():
            while self._update_threads_started:
                print("🔄 定时更新1小时结算合约列表...")
                self.funding.update_1h_contracts_cache()
                time.sleep(self.parameters['contract_refresh_interval'])
        t = threading.Thread(target=refresh_loop, daemon=True)
        t.start()

    def _start_cache_update_thread(self):
        """启动缓存更新线程"""
        def cache_update_loop():
            while self._update_threads_started:
                try:
                    print("🔄 定时更新1小时结算合约缓存...")
                    self.funding.update_1h_contracts_cache()
                    # 每6小时更新一次缓存
                    time.sleep(6 * 3600)
                except Exception as e:
                    print(f"❌ 缓存更新失败: {e}")
                    time.sleep(3600)  # 出错后1小时再试
        t = threading.Thread(target=cache_update_loop, daemon=True)
        t.start()

    def _start_risk_monitor_thread(self):
        """启动风险监控线程"""
        def risk_monitor_loop():
            while self._update_threads_started:
                try:
                    self._check_risk_limits()
                    time.sleep(300)  # 每5分钟检查一次
                except Exception as e:
                    print(f"❌ 风险监控失败: {e}")
                    time.sleep(60)
        t = threading.Thread(target=risk_monitor_loop, daemon=True)
        t.start()

    def _start_scheduled_update_thread(self):
        """启动定时更新线程 - 定期更新1小时结算合约列表"""
        def scheduled_update_loop():
            while self._update_threads_started:
                try:
                    now = datetime.now()
                    # 计算到下一个整点的等待时间
                    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    wait_seconds = (next_hour - now).total_seconds()
                    
                    print(f"⏰ 等待到下一个整点更新1小时结算合约列表，还需等待 {wait_seconds/60:.1f} 分钟")
                    time.sleep(wait_seconds)
                    
                    # 整点触发更新1小时结算合约列表
                    print("🕐 整点时间到，开始更新1小时结算合约列表...")
                    self.funding.update_1h_contracts_cache()
                    
                    # 之后每小时更新一次
                    time.sleep(3600)
                    
                except Exception as e:
                    print(f"❌ 定时更新失败: {e}")
                    time.sleep(300)  # 出错后5分钟再试
        t = threading.Thread(target=scheduled_update_loop, daemon=True)
        t.start()

    def start_strategy(self):
        """启动策略（三池分离版）"""
        if self._update_threads_started:
            print("⚠️ 策略已经在运行中")
            return
        print("🚀 启动资金费率套利策略（三池分离版）...")
        print(f"📊 自动交易: {'开启' if self.parameters['auto_trade'] else '关闭'}")
        print(f"📊 模拟交易: {'开启' if self.parameters['paper_trading'] else '关闭'}")

        # 1. 加载持仓池
        self._load_positions()
        held_symbols = set(self.positions.keys())
        print(f"📊 当前持仓池合约: {held_symbols}")

        # 2. 加载候选池（所有1小时结算合约，严格按json结构）
        all_1h_file = "cache/1h_funding_contracts_full.json"
        contracts = {}
        h1_contracts_count = None
        if os.path.exists(all_1h_file):
            with open(all_1h_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                contracts = data.get("contracts", {})
                h1_contracts_count = data.get("h1_contracts_count")
            print(f"📋 加载候选池（1小时合约）: {len(contracts)} 个，h1_contracts_count: {h1_contracts_count}")
        else:
            print("⚠️ 未找到1小时合约池缓存，候选池为空")

        # 3. 初始化可交易池（只包含持仓合约）
        tradable_info = {}
        for symbol in held_symbols:
            try:
                info = self.funding.get_comprehensive_info(symbol, contract_type="UM")
                if info:
                    tradable_info[symbol] = info
                    print(f"🔒 持仓合约 {symbol} 加入初始可交易池")
            except Exception as e:
                print(f"❌ {symbol}: 持仓合约补充失败 - {e}")

        # 4. 保存初始可交易池到缓存
        self.cached_contracts = tradable_info
        self.contract_pool = set(tradable_info.keys())
        self.last_update_time = datetime.now()
        self._save_cache()
        print(f"✅ 初始可交易合约池完成，共 {len(self.contract_pool)} 个")

        # 5. 启动后立即批量获取所有候选池合约的资金费率和成交量，筛选所有满足条件的合约进新池
        from utils.binance_funding import get_all_funding_rates, get_all_24h_volumes
        all_funding_rates = get_all_funding_rates()  # symbol -> info
        all_24h_volumes = get_all_24h_volumes()      # symbol -> quoteVolume
        threshold = self.parameters['funding_rate_threshold']
        min_volume = self.parameters['min_volume']
        funding_rates = {}
        for symbol, info in contracts.items():
            rate_info = all_funding_rates.get(symbol)
            volume_24h = all_24h_volumes.get(symbol, 0.0)
            merged_info = dict(info)
            if rate_info and rate_info.get('lastFundingRate') is not None:
                merged_info['current_funding_rate'] = float(rate_info['lastFundingRate'])
                merged_info['mark_price'] = float(rate_info.get('markPrice', 0))
            merged_info['volume_24h'] = float(volume_24h)
            funding_rates[symbol] = merged_info
            # 新增日志打印
            rate_str = merged_info.get('current_funding_rate', 'N/A')
            print(f"合约: {symbol}, 资金费率: {rate_str}, 24h成交量: {merged_info['volume_24h']}")
        # 只要满足条件的都能进新池
        self.update_contract_pool(funding_rates)

        # 启动所有更新线程
        self._start_update_thread()
        self._start_contract_refresh_thread()
        self._start_cache_update_thread()
        self._start_risk_monitor_thread()
        self._start_scheduled_update_thread()
        self._start_funding_rate_check_thread()
        self._update_threads_started = True
        print("✅ 策略启动完成，开始定时检测资金费率")

    def stop_strategy(self):
        """停止策略"""
        print("🛑 停止资金费率套利策略...")
        self._update_threads_started = False
        print("✅ 策略已停止")

    def _check_risk_limits(self):
        """检查风险限制"""
        total_exposure = sum(abs(pos.quantity * pos.entry_price) for pos in self.positions.values())
        
        if total_exposure > self.max_total_exposure:
            print(f"⚠️ 总敞口 {total_exposure:.2f} 超过限制 {self.max_total_exposure:.2f}")
            self._reduce_exposure()
        
        # 检查止损止盈
        for symbol, position in list(self.positions.items()):
            self._check_stop_loss_take_profit(symbol, position)

    def _reduce_exposure(self):
        """减少敞口"""
        # 按持仓时间排序，优先平掉较早的持仓
        sorted_positions = sorted(
            self.positions.items(),
            key=lambda x: x[1].entry_time
        )
        
        for symbol, position in sorted_positions:
            if self._get_total_exposure() <= self.max_total_exposure * 0.9:
                break
            
            print(f"🔄 减少敞口：平仓 {symbol}")
            self._close_position(symbol, "风险控制")

    def _check_stop_loss_take_profit(self, symbol: str, position: Position):
        """检查止损止盈"""
        # 这里需要获取当前价格，简化处理
        current_price = position.entry_price  # 实际应该从API获取
        
        if position.side == 'long':
            loss_ratio = (position.entry_price - current_price) / position.entry_price
            profit_ratio = (current_price - position.entry_price) / position.entry_price
        else:
            loss_ratio = (current_price - position.entry_price) / position.entry_price
            profit_ratio = (position.entry_price - current_price) / position.entry_price
        
        if loss_ratio >= self.parameters['stop_loss_ratio']:
            print(f"🛑 触发止损：{symbol}")
            self._close_position(symbol, "止损")
        elif profit_ratio >= self.parameters['take_profit_ratio']:
            print(f"🎯 触发止盈：{symbol}")
            self._close_position(symbol, "止盈")

    def _get_total_exposure(self) -> float:
        """获取总敞口"""
        return sum(abs(pos.quantity * pos.entry_price) for pos in self.positions.values())

    def _can_open_position(self, symbol: str, side: str, funding_rate: float) -> bool:
        """检查是否可以开仓"""
        print(f"🔍 检查开仓条件: {symbol} {side} 费率:{funding_rate:.4%}")
        
        # 检查是否已有持仓
        if symbol in self.positions:
            print(f"❌ {symbol}: 已有持仓")
            return False
        
        # 检查持仓数量限制
        if len(self.positions) >= self.parameters['max_positions']:
            print(f"❌ {symbol}: 持仓数量已达上限 ({len(self.positions)}/{self.parameters['max_positions']})")
            return False
        
        # 检查资金是否足够
        position_value = self.max_position_value
        if self._get_total_exposure() + position_value > self.max_total_exposure:
            print(f"❌ {symbol}: 总敞口超限 ({self._get_total_exposure():.2f} + {position_value:.2f} > {self.max_total_exposure:.2f})")
            return False
        
        # 检查资金费率是否仍然符合条件
        if abs(funding_rate) < self.parameters['funding_rate_threshold']:
            print(f"❌ {symbol}: 资金费率不符合条件 ({abs(funding_rate):.4%} < {self.parameters['funding_rate_threshold']:.4%})")
            return False
        
        print(f"✅ {symbol}: 开仓条件检查通过")
        return True

    def _open_position(self, symbol: str, side: str, funding_rate: float, price: float):
        """开仓"""
        print(f"🚀 尝试开仓: {symbol} {side} 费率:{funding_rate:.4%} 价格:{price:.4f}")
        
        if not self._can_open_position(symbol, side, funding_rate):
            print(f"❌ {symbol}: 开仓条件检查失败")
            return False
        
        # 检查价格有效性
        if price <= 0:
            print(f"❌ {symbol}: 价格无效 ({price})")
            return False
        
        # 计算仓位大小
        position_value = min(self.max_position_value, self.available_capital * 0.8)
        quantity = position_value / price
        
        print(f"📊 {symbol}: 仓位计算 - 价值:{position_value:.2f} 数量:{quantity:.4f} 价格:{price:.4f}")
        
        # 创建持仓
        position = Position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(),
            funding_rate=funding_rate
        )
        
        self.positions[symbol] = position
        self.available_capital -= position_value
        self._save_positions()
        
        # 发送通知
        trade_type = "模拟交易" if self.parameters['paper_trading'] else "实盘交易"
        message = f"🟢 开仓通知 ({trade_type})\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📊 合约: {symbol}\n"
        message += f"📈 方向: {'做多' if side == 'long' else '做空'}\n"
        message += f"💰 数量: {quantity:.4f}\n"
        message += f"💵 价格: {price:.4f}\n"
        message += f"📊 资金费率: {funding_rate:.4%}\n"
        message += f"💸 仓位价值: {position_value:.2f}"
        
        send_telegram_message(message)
        print(f"✅ 开仓成功: {symbol} {side} {quantity:.4f} @ {price:.4f}")
        
        return True

    def _close_position(self, symbol: str, reason: str = "策略平仓"):
        """平仓"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        # 类型自愈：如果position是dict，自动转为Position对象
        if isinstance(position, dict):
            try:
                position = Position(
                    symbol=position['symbol'],
                    side=position['side'],
                    quantity=position['quantity'],
                    entry_price=position['entry_price'],
                    entry_time=datetime.fromisoformat(position['entry_time']),
                    funding_rate=position['funding_rate'],
                    unrealized_pnl=position.get('unrealized_pnl', 0.0),
                    realized_pnl=position.get('realized_pnl', 0.0)
                )
                self.positions[symbol] = position
            except Exception as e:
                print(f"❌ 平仓时自动修正Position对象失败: {e}")
                return False
        
        # 计算盈亏（简化处理，实际应该获取当前价格）
        current_price = position.entry_price  # 实际应该从API获取
        if position.side == 'long':
            pnl = (current_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - current_price) * position.quantity
        
        # 更新统计
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
        self.total_pnl += pnl
        
        # 释放资金
        position_value = position.quantity * position.entry_price
        self.available_capital += position_value + pnl
        
        # 记录历史
        position.realized_pnl = pnl
        self.position_history.append(position)
        
        # 移除持仓
        del self.positions[symbol]
        self._save_positions()
        
        # 发送通知
        trade_type = "模拟交易" if self.parameters['paper_trading'] else "实盘交易"
        message = f"🔴 平仓通知 ({trade_type})\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📊 合约: {symbol}\n"
        message += f"📈 方向: {'做多' if position.side == 'long' else '做空'}\n"
        message += f"💰 数量: {position.quantity:.4f}\n"
        message += f"💵 开仓价: {position.entry_price:.4f}\n"
        message += f"💵 平仓价: {current_price:.4f}\n"
        message += f"📊 盈亏: {pnl:.2f}\n"
        message += f"📝 原因: {reason}"
        
        send_telegram_message(message)
        print(f"✅ 平仓成功: {symbol} 盈亏: {pnl:.2f} 原因: {reason}")
        
        return True

    def get_funding_rates(self) -> Dict[str, Dict]:
        # 只用缓存
        if not self._is_cache_valid():
            with self._update_lock:
                if not self._updating:
                    print("⚠️ 缓存已过期，正在更新...")
                    self._update_cached_contracts()
                else:
                    print("⚠️ 缓存已过期，但更新正在进行中，使用现有缓存")
        return self.cached_contracts.copy()

    def update_contract_pool(self, funding_rates: Dict[str, Dict]):
        """更新合约池并生成交易信号 - 检测所有缓存的合约"""
        threshold = self.parameters['funding_rate_threshold']
        min_volume = self.parameters['min_volume']
        max_positions = self.parameters['max_positions']
        
        print(f"🔍 检测 {len(funding_rates)} 个合约的资金费率...")
        
        # 筛选符合条件的合约
        qualified_contracts = []
        for contract_id, info in funding_rates.items():
            funding_rate = info.get('current_funding_rate') or info.get('funding_rate')
            volume_24h = info.get('volume_24h', 0)
            symbol = info.get('symbol', contract_id)
            
            # 确保volume_24h是数值类型
            try:
                volume_24h = float(volume_24h) if volume_24h is not None else 0.0
            except (ValueError, TypeError):
                volume_24h = 0.0
            
            # 检查资金费率阈值和成交量
            if (funding_rate is not None and abs(float(funding_rate)) >= threshold and 
                volume_24h >= min_volume):
                qualified_contracts.append({
                    'contract_id': contract_id,
                    'funding_rate': float(funding_rate),
                    'volume_24h': volume_24h,
                    'exchange': 'binance',
                    'symbol': symbol
                })
        
        # 按资金费率绝对值排序，选择最优的合约
        qualified_contracts.sort(key=lambda x: abs(x['funding_rate']), reverse=True)
        new_pool = set()
        
        # 选择前N个合约
        for contract in qualified_contracts[:max_positions]:
            new_pool.add(contract['contract_id'])
        
        # 检测池子变化
        added_contracts = new_pool - self.contract_pool
        removed_contracts = self.contract_pool - new_pool
        
        print(f"📊 当前池子: {len(self.contract_pool)}个, 新池子: {len(new_pool)}个")
        print(f"🟢 新增: {len(added_contracts)}个, 🔴 移除: {len(removed_contracts)}个")
        
        # 处理新增合约（开仓信号）
        if added_contracts and self.parameters['auto_trade']:
            print(f"🟢 发现 {len(added_contracts)} 个新增合约，开始处理开仓...")
            for contract_id in added_contracts:
                print(f"🔍 处理新增合约: {contract_id}")
                if contract_id in funding_rates:
                    info = funding_rates[contract_id]
                    funding_rate = info.get('current_funding_rate') or info.get('funding_rate')
                    
                    print(f"📊 {contract_id}: 资金费率={funding_rate}, 价格={info.get('mark_price', 'N/A')}")
                    
                    # 获取当前价格，避免除零错误
                    current_price = info.get('mark_price', 0.0)
                    
                    # 确保current_price是数值类型
                    try:
                        current_price = float(current_price) if current_price is not None else 0.0
                    except (ValueError, TypeError):
                        current_price = 0.0
                    
                    if current_price <= 0:
                        # 如果无法获取价格，尝试从历史数据中获取最新价格
                        if info.get('history_rates') and len(info['history_rates']) > 0:
                            try:
                                current_price = float(info['history_rates'][0].get('mark_price', 0.0))
                                print(f"📊 {contract_id}: 从历史数据获取价格={current_price}")
                            except (ValueError, TypeError):
                                current_price = 0.0
                        
                        if current_price <= 0:
                            print(f"⚠️ {contract_id}: 无法获取有效价格，跳过开仓")
                            continue
                    
                    print(f"🚀 {contract_id}: 准备开仓，价格={current_price:.4f}")
                    
                    # 确保funding_rate是float类型
                    try:
                        funding_rate = float(funding_rate)
                    except (ValueError, TypeError):
                        print(f"⚠️ {contract_id}: 资金费率无法转换为数值，跳过开仓")
                        continue
                    
                    if funding_rate > 0:
                        # 正费率：做多
                        print(f"📈 {contract_id}: 正费率，准备做多")
                        self._open_position(contract_id, 'long', funding_rate, current_price)
                    else:
                        # 负费率：做空
                        print(f"📉 {contract_id}: 负费率，准备做空")
                        self._open_position(contract_id, 'short', funding_rate, current_price)
                else:
                    print(f"❌ {contract_id}: 在funding_rates中未找到信息")
        elif added_contracts:
            print(f"⚠️ 发现 {len(added_contracts)} 个新增合约，但自动交易已关闭")
        else:
            print("📊 没有新增合约")
        
        # 处理移除合约（平仓信号）
        if removed_contracts and self.parameters['auto_trade']:
            for contract_id in removed_contracts:
                if contract_id in self.positions:
                    self._close_position(contract_id, "合约出池")
        
        # 检查池子变化并发送Telegram通知
        if added_contracts or removed_contracts:
            # 构建变化消息
            change_message = f"🔄 合约池变化通知\n"
            change_message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            change_message += f"📊 阈值: {threshold:.4%}\n\n"
            
            if added_contracts:
                change_message += f"🟢 新增合约 ({len(added_contracts)}个):\n"
                for contract_id in added_contracts:
                    info = funding_rates[contract_id]
                    symbol = info.get('symbol', contract_id)
                    rate = info.get('current_funding_rate') or info.get('funding_rate')
                    try:
                        rate = float(rate)
                    except (ValueError, TypeError):
                        rate = 0.0 # 确保是数值类型
                    direction = "做多" if rate > 0 else "做空"
                    change_message += f"  • {symbol}: {rate:.4%} ({direction})\n"
                change_message += "\n"
            
            if removed_contracts:
                change_message += f"🔴 移除合约 ({len(removed_contracts)}个):\n"
                for contract_id in removed_contracts:
                    info = funding_rates.get(contract_id, {})
                    symbol = info.get('symbol', contract_id)
                    change_message += f"  • {symbol}\n"
                change_message += "\n"
            
            # 发送变化通知
            send_telegram_message(change_message)
        
        # 更新池子
        self.contract_pool = new_pool
        
        # 发送当前池子状态（每次更新都发送）
        if self.contract_pool:
            status_message = f"📊 当前合约池状态\n"
            status_message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_message += f"📈 合约数量: {len(self.contract_pool)}个\n"
            status_message += f"🎯 阈值: {threshold:.4%}\n"
            status_message += f"💰 当前持仓: {len(self.positions)}个\n"
            status_message += f"💵 总盈亏: {self.total_pnl:.2f}\n\n"
            
            # 按资金费率排序显示
            pool_contracts = []
            for contract_id in self.contract_pool:
                info = funding_rates.get(contract_id, {})
                symbol = info.get('symbol', contract_id)
                rate = info.get('current_funding_rate') or info.get('funding_rate')
                try:
                    rate = float(rate)
                except (ValueError, TypeError):
                    rate = 0.0 # 确保是数值类型
                if rate is not None:
                    pool_contracts.append((symbol, rate))
            
            # 按绝对值排序
            pool_contracts.sort(key=lambda x: abs(x[1]), reverse=True)
            
            for symbol, rate in pool_contracts:
                direction = "做多" if rate > 0 else "做空"
                status_message += f"  • {symbol}: {rate:.4%} ({direction})\n"
            
            send_telegram_message(status_message)
        else:
            empty_message = f"📊 合约池状态\n"
            empty_message += f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            empty_message += f"📈 合约数量: 0个\n"
            empty_message += f"🎯 阈值: {threshold:.4%}\n"
            empty_message += f"💡 当前没有合约满足条件"
            send_telegram_message(empty_message)

    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """生成交易信号"""
        try:
            # 获取资金费率数据（使用缓存）
            funding_rates = self.get_funding_rates()
            
            # 更新合约池并执行交易
            self.update_contract_pool(funding_rates)
            
            # 为池子中的合约生成信号（用于其他系统集成）
            signals = []
            for contract_id in self.contract_pool:
                if contract_id in funding_rates:
                    info = funding_rates[contract_id]
                    funding_rate = info.get('current_funding_rate') or info.get('funding_rate')
                    
                    # 确保funding_rate是float类型
                    try:
                        funding_rate = float(funding_rate)
                    except (ValueError, TypeError):
                        print(f"⚠️ {contract_id}: 资金费率无法转换为数值，跳过信号生成")
                        continue
                    
                    # 根据资金费率方向生成信号
                    if funding_rate > 0:
                        # 正费率：做多获得资金费
                        signal = 'buy'
                        strength = min(1.0, abs(funding_rate) / 0.01)
                    else:
                        # 负费率：做空获得资金费
                        signal = 'sell'
                        strength = min(1.0, abs(funding_rate) / 0.01)
                    
                    signals.append(Signal(
                        timestamp=pd.Timestamp.now(),
                        symbol=contract_id,
                        signal=signal,
                        strength=strength,
                        price=0,  # 资金费率策略不依赖价格
                        strategy_name=self.name,
                        metadata={
                            'funding_rate': funding_rate,
                            'exchange': info.get('exchange', 'binance'),
                            'next_funding_time': info.get('next_funding_time')
                        }
                    ))
            
            return signals
            
        except Exception as e:
            print(f"生成资金费率套利信号失败: {e}")
            return []

    def get_pool_status(self) -> Dict:
        """获取池子状态"""
        return {
            'pool_size': len(self.contract_pool),
            'contracts': list(self.contract_pool),
            'max_positions': self.parameters['max_positions'],
            'threshold': self.parameters['funding_rate_threshold'],
            'cached_contracts_count': len(self.cached_contracts),
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None,
            'cache_valid': self._is_cache_valid(),
            'current_positions': len(self.positions),
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0,
            'total_exposure': self._get_total_exposure(),
            'available_capital': self.available_capital
        }

    def get_positions(self) -> Dict[str, Position]:
        """获取当前持仓"""
        return self.positions.copy()

    def force_update_cache(self):
        """强制更新缓存"""
        print("🔄 强制更新合约缓存...")
        self._update_cached_contracts()
        return {"message": "缓存更新完成", "contracts_count": len(self.cached_contracts)}

    def close_all_positions(self, reason: str = "手动平仓"):
        """平掉所有持仓，返回被平掉的持仓信息列表"""
        closed_positions = []
        closed_count = 0
        all_symbols = list(self.positions.keys())
        for symbol in all_symbols:
            pos = self.positions[symbol]
            if isinstance(pos, dict):
                try:
                    pos = Position(
                        symbol=pos['symbol'],
                        side=pos['side'],
                        quantity=pos['quantity'],
                        entry_price=pos['entry_price'],
                        entry_time=datetime.fromisoformat(pos['entry_time']),
                        funding_rate=pos['funding_rate'],
                        unrealized_pnl=pos.get('unrealized_pnl', 0.0),
                        realized_pnl=pos.get('realized_pnl', 0.0)
                    )
                    self.positions[symbol] = pos
                except Exception as e:
                    print(f"❌ 批量平仓时自动修正Position对象失败: {e}")
                    del self.positions[symbol]
                    continue
            elif not isinstance(pos, Position):
                print(f"❌ 批量平仓时发现无法识别的持仓类型: {type(pos)}, symbol={symbol}，已自动删除")
                del self.positions[symbol]
                continue
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            # 记录平仓前的持仓信息
            closed_positions.append({
                'symbol': pos.symbol,
                'side': pos.side,
                'quantity': pos.quantity,
                'entry_price': pos.entry_price,
                'entry_time': pos.entry_time.isoformat(),
                'funding_rate': pos.funding_rate,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl
            })
            if self._close_position(symbol, reason):
                closed_count += 1
        # ... 发送通知等 ...
        return closed_positions

    def set_auto_trade(self, enabled: bool):
        """设置自动交易开关"""
        self.parameters['auto_trade'] = enabled
        status = "开启" if enabled else "关闭"
        message = f"🔄 自动交易已{status}\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📊 状态: {status}"
        
        send_telegram_message(message)
        return {"message": f"自动交易已{status}"} 