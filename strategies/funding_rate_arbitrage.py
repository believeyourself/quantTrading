import time
import json
import os
from typing import Dict, Set, Optional, List
from datetime import datetime, timedelta
from .base import BaseStrategy, Signal
from utils.notifier import send_telegram_message
from config.proxy_settings import get_proxy_dict, get_ccxt_proxy_config, test_proxy_connection
import threading
import schedule
from utils.binance_funding import BinanceFunding
import pandas as pd

class FundingRateArbitrageStrategy(BaseStrategy):
    """资金费率套利策略 - 仅支持币安，全部用binance_interface"""
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            'funding_rate_threshold': 0.005,  # 0.5% 阈值
            'max_positions': 20,              # 最大持仓数量
            'min_volume': 1000000,            # 最小24小时成交量
            'cache_duration': 7200,           # 缓存时间（秒）
            'update_interval': 1800,          # 更新间隔（秒，30分钟）
            'funding_interval': 28800,        # 资金费率结算周期（秒，8小时）
            'contract_refresh_interval': 3600 # 合约池刷新间隔（秒，1小时）
        }
        params = {**default_params, **(parameters or {})}
        super().__init__("资金费率套利策略", params)
        
        # 合约池管理
        self.contract_pool: Set[str] = set()  # 当前池子中的合约
        self.cached_contracts = {}  # 缓存的合约信息
        self.last_update_time = None
        self.cache_file = "cache/funding_rate_contracts.json"
        self._updating = False
        self._update_lock = threading.Lock()
        self.funding = BinanceFunding()
        os.makedirs("cache", exist_ok=True)
        self._load_cache()
        self._start_update_thread()
        self._start_contract_refresh_thread()
        self._start_cache_update_thread()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cached_contracts = json.load(f)
            self.contract_pool = set(self.cached_contracts.keys())
            self.last_update_time = datetime.now()
        else:
            self.cached_contracts = {}
            self.contract_pool = set()
            self.last_update_time = None

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cached_contracts, f, ensure_ascii=False, indent=2)

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

    def _start_update_thread(self):
        def update_loop():
            while True:
                if not self._is_cache_valid():
                    print("⚠️ 缓存已过期，正在更新...")
                    self._update_cached_contracts()
                time.sleep(self.parameters['update_interval'])
        t = threading.Thread(target=update_loop, daemon=True)
        t.start()

    def _start_contract_refresh_thread(self):
        def refresh_loop():
            while True:
                print("🔄 定时刷新合约池...")
                self._refresh_contract_pool()
                time.sleep(self.parameters['contract_refresh_interval'])
        t = threading.Thread(target=refresh_loop, daemon=True)
        t.start()

    def _start_cache_update_thread(self):
        """启动缓存更新线程"""
        def cache_update_loop():
            while True:
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

    # 其余策略逻辑可继续复用原有代码，只需调用get_funding_rates()获取资金费率池

    def update_contract_pool(self, funding_rates: Dict[str, Dict]):
        """更新合约池（只保留币安，字段统一）"""
        threshold = self.parameters['funding_rate_threshold']
        min_volume = self.parameters['min_volume']
        max_positions = self.parameters['max_positions']
        
        # 筛选符合条件的合约
        qualified_contracts = []
        for contract_id, info in funding_rates.items():
            funding_rate = info.get('current_funding_rate') or info.get('funding_rate')
            # volume_24h 字段兼容
            volume_24h = info.get('volume_24h', 0)
            symbol = info.get('symbol', contract_id)
            
            # 检查资金费率阈值和成交量
            if (funding_rate is not None and abs(float(funding_rate)) >= threshold and 
                float(volume_24h) >= min_volume):
                qualified_contracts.append({
                    'contract_id': contract_id,
                    'funding_rate': float(funding_rate),
                    'volume_24h': float(volume_24h),
                    'exchange': 'binance',
                    'symbol': symbol
                })
        
        # 按资金费率绝对值排序，选择最优的合约
        qualified_contracts.sort(key=lambda x: abs(x['funding_rate']), reverse=True)
        new_pool = set()
        
        # 选择前N个合约
        for contract in qualified_contracts[:max_positions]:
            new_pool.add(contract['contract_id'])
        
        # 检查池子变化
        added_contracts = new_pool - self.contract_pool
        removed_contracts = self.contract_pool - new_pool
        
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
                    direction = "做多" if float(rate) > 0 else "做空"
                    change_message += f"  • {symbol}: {float(rate):.4%} ({direction})\n"
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
            status_message += f"🎯 阈值: {threshold:.4%}\n\n"
            
            # 按资金费率排序显示
            pool_contracts = []
            for contract_id in self.contract_pool:
                info = funding_rates.get(contract_id, {})
                symbol = info.get('symbol', contract_id)
                rate = info.get('current_funding_rate') or info.get('funding_rate')
                if rate is not None:
                    pool_contracts.append((symbol, float(rate)))
            
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
            
            # 更新合约池
            self.update_contract_pool(funding_rates)
            
            # 为池子中的合约生成信号
            signals = []
            for contract_id in self.contract_pool:
                if contract_id in funding_rates:
                    info = funding_rates[contract_id]
                    funding_rate = info['funding_rate']
                    
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
                            'exchange': info['exchange'],
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
            'cache_valid': self._is_cache_valid()
        }
    
    def force_update_cache(self):
        """强制更新缓存"""
        print("🔄 强制更新合约缓存...")
        self._update_cached_contracts()
        return {"message": "缓存更新完成", "contracts_count": len(self.cached_contracts)} 