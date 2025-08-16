import time
import json
import os
from typing import Dict, Set, Optional, List, Tuple
from datetime import datetime, timedelta
from .base import BaseStrategy
from utils.notifier import send_telegram_message
from config.proxy_settings import get_proxy_dict, get_ccxt_proxy_config, test_proxy_connection
import threading
import schedule
from utils.binance_funding import BinanceFunding

class FundingRateMonitor(BaseStrategy):
    """资金费率监控系统 - 监控1小时资金费率结算的合约"""
    
    def __init__(self, parameters: Dict = None):
        # 从settings.py加载配置参数
        from config.settings import settings
        
        config_params = {
            'funding_rate_threshold': settings.FUNDING_RATE_THRESHOLD,
            'max_contracts_in_pool': settings.MAX_POOL_SIZE,
            'min_volume': settings.MIN_VOLUME,
            'cache_duration': settings.CACHE_DURATION,
            'update_interval': settings.UPDATE_INTERVAL,
            'contract_refresh_interval': settings.CONTRACT_REFRESH_INTERVAL,
            'funding_rate_check_interval': settings.FUNDING_RATE_CHECK_INTERVAL,
        }
        print(f"📋 从settings.py加载参数: funding_rate_threshold={config_params['funding_rate_threshold']:.4%}")
        
        # 默认参数（作为后备）
        default_params = {
            'funding_rate_threshold': 0.005,  # 0.5% 阈值
            'max_contracts_in_pool': 20,      # 池子里最大合约数量
            'min_volume': 1000000,            # 最小24小时成交量
            'cache_duration': 7200,           # 缓存时间（秒）
            'update_interval': 1800,          # 更新间隔（秒，30分钟）
            'contract_refresh_interval': 3600,  # 合约池刷新间隔（秒，1小时）
            'funding_rate_check_interval': 300,# 资金费率检测间隔（秒，5分钟）
        }
        
        # 合并参数：settings.py > 传入参数 > 默认参数
        params = {**default_params, **(parameters or {}), **config_params}
        super().__init__("资金费率监控系统", params)
        
        # 合约池管理
        self.contract_pool: Set[str] = set()  # 当前池子中的合约
        self.candidate_contracts: Dict[str, Dict] = {}  # 备选合约
        self.cached_contracts = {}  # 缓存的合约信息
        self.last_update_time = None
        self.cache_file = "cache/funding_rate_contracts.json"
        self._updating = False
        self._update_lock = threading.Lock()
        self.funding = BinanceFunding()
        
        os.makedirs("cache", exist_ok=True)
        self._load_cache(load_on_startup=True) # 启动时加载缓存
        # 不立即启动更新线程，等待策略启动时再启动
        self._update_threads_started = False

    def _load_cache(self, load_on_startup=True):
        """加载缓存"""
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
        """保存缓存"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cached_contracts, f, ensure_ascii=False, indent=2)

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self.last_update_time:
            return False
        cache_age = (datetime.now() - self.last_update_time).total_seconds()
        return cache_age < self.parameters['cache_duration']

    def _update_cached_contracts(self):
        """更新缓存的合约信息"""
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
            print(f"✅ 更新了 {len(updated)} 个合约的缓存")
        except Exception as e:
            print(f"❌ 更新合约缓存失败: {e}")
        finally:
            with self._update_lock:
                self._updating = False

    def refresh_contract_pool(self, force_refresh=False):
        """刷新合约池 - 入池出池逻辑"""
        try:
            print("🔄 开始刷新合约池...")
            # 获取所有合约 (使用scan_1h_funding_contracts替代get_all_funding_contracts)
            all_contracts = self.funding.scan_1h_funding_contracts(force_refresh=force_refresh)
            if not all_contracts:
                print("❌ 未能获取合约列表，尝试从缓存加载...")
                all_contracts = self.funding.get_1h_contracts_from_cache()
                if not all_contracts:
                    print("❌ 缓存中也没有合约数据")
                    return
            
            # 筛选符合条件的合约
            filtered_contracts = {}
            for symbol, info in all_contracts.items():
                # 检查24小时成交量
                if info.get('volume_24h', 0) < self.parameters['min_volume']:
                    continue
                
                # 检查资金费率
                # 检查资金费率
                funding_rate = float(info.get('current_funding_rate', 0))
                if abs(funding_rate) >= self.parameters['funding_rate_threshold']:
                    filtered_contracts[symbol] = info
                     
            # 按资金费率绝对值排序
            sorted_contracts = sorted(
                filtered_contracts.items(), 
                key=lambda x: abs(float(x[1]['current_funding_rate'])), 
                reverse=True
            )
            
            # 选取前N个合约
            selected_contracts = dict(sorted_contracts[:self.parameters['max_contracts_in_pool']])
            
            # 更新候选合约和合约池
            self.candidate_contracts = filtered_contracts
            new_pool = set(selected_contracts.keys())
            
            # 出池合约
            removed_contracts = self.contract_pool - new_pool
            if removed_contracts:
                print(f"🔻 出池合约: {', '.join(removed_contracts)}")
                # 发送出池通知
                send_telegram_message(f"🔻 出池合约: {', '.join(removed_contracts)}")
            
            # 入池合约
            added_contracts = new_pool - self.contract_pool
            if added_contracts:
                print(f"🔺 入池合约: {', '.join(added_contracts)}")
                # 发送入池通知
                send_telegram_message(f"🔺 入池合约: {', '.join(added_contracts)}")
            
            # 更新合约池和缓存
            self.contract_pool = new_pool
            self.cached_contracts = selected_contracts
            self.last_update_time = datetime.now()
            self._save_cache()
            
            print(f"✅ 合约池刷新完成，当前池内合约数: {len(self.contract_pool)}")
        except Exception as e:
            print(f"❌ 刷新合约池失败: {e}")

    def check_funding_rates(self):
        """检查资金费率并发送通知"""
        try:
            if not self._is_cache_valid():
                self._update_cached_contracts()
            
            # 检查每个合约的资金费率
            for symbol, info in self.cached_contracts.items():
                funding_rate = float(info.get('funding_rate', 0))
                if abs(funding_rate) >= self.parameters['funding_rate_threshold']:
                    # 资金费率超过阈值，发送通知
                    direction = "多头" if funding_rate > 0 else "空头"
                    message = f"⚠️ 资金费率警告: {symbol}\n" \
                             f"当前费率: {funding_rate:.4%} ({direction})\n" \
                             f"24h成交量: {info.get('volume_24h', 0):,.2f}\n" \
                             f"下次结算时间: {info.get('next_funding_time')}"
                    send_telegram_message(message)
            
            print("✅ 资金费率检查完成")
        except Exception as e:
            print(f"❌ 检查资金费率失败: {e}")

    def start_monitoring(self):
        """启动监控系统（包括定时任务）"""
        print("🚀 启动资金费率监控系统...")
        
        # 初始刷新合约池
        self.refresh_contract_pool()
        
        # 启动定时任务
        if not self._update_threads_started:
            self._start_update_threads()
            self._update_threads_started = True
        
        print("✅ 监控系统已启动（自动模式）")
        print("💡 系统将自动执行以下定时任务：")
        print(f"   - 合约池刷新: 每{self.parameters['contract_refresh_interval']}秒")
        print(f"   - 资金费率检查: 每{self.parameters['funding_rate_check_interval']}秒")
        print("💡 也可通过Web界面或API手动触发操作")
        
        # 启动调度器
        self._run_scheduler()
    
    def start_monitoring_manual(self):
        """初始化监控（手动模式，不启动定时任务）"""
        print("🚀 初始化资金费率监控系统（手动模式）...")
        
        # 初始刷新合约池
        self.refresh_contract_pool()
        
        print("✅ 监控系统已初始化（手动模式）")
        print("💡 可通过Web界面或API手动触发操作")
        print("   - 刷新合约池")
        print("   - 检查资金费率")
        print("   - 更新缓存")
        

    def _start_update_threads(self):
        """启动定时更新线程"""
        print("🔄 启动定时更新线程...")
        
        # 设置定时任务
        schedule.every(self.parameters['contract_refresh_interval']).seconds.do(self.refresh_contract_pool)
        schedule.every(self.parameters['funding_rate_check_interval']).seconds.do(self.check_funding_rates)
        
        print(f"✅ 定时任务已设置：")
        print(f"   📊 合约池刷新: 每{self.parameters['contract_refresh_interval']}秒")
        print(f"   💰 资金费率检查: 每{self.parameters['funding_rate_check_interval']}秒")
    
    def _run_scheduler(self):
        """运行调度器"""
        print("🔄 调度器已启动，开始执行定时任务...")
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                print("🛑 调度器被用户中断")
                break
            except Exception as e:
                print(f"❌ 调度器异常: {e}")
                time.sleep(5)  # 异常时等待5秒再继续
    
    def get_current_pool(self):
        """获取当前合约池"""
        return list(self.contract_pool)
    
    def stop_monitoring(self):
        """停止监控系统"""
        print("🛑 停止资金费率监控系统...")
        
        # 清除所有定时任务
        schedule.clear()
        print("✅ 定时任务已清除")
        
        # 重置状态
        self._update_threads_started = False
        print("✅ 监控系统已停止")
    
    def get_pool_status(self):
        """获取池子状态"""
        return {
            "pool_size": len(self.contract_pool),
            "candidate_size": len(self.candidate_contracts),
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None,
            "cache_valid": self._is_cache_valid(),
            "auto_update": self._update_threads_started
        }