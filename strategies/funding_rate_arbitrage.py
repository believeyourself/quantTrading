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
        self.cache_file = "cache/all_funding_contracts_full.json"
        self._updating = False
        self._update_lock = threading.Lock()
        self.funding = BinanceFunding()
        
        # 添加停止标志和调度器线程
        self._stop_event = threading.Event()
        self._scheduler_thread = None
        
        os.makedirs("cache", exist_ok=True)
        self._load_cache(load_on_startup=True) # 启动时加载缓存
        # 不立即启动更新线程，等待策略启动时再启动
        self._update_threads_started = False

    def _load_cache(self, load_on_startup=True):
        """加载缓存"""
        if load_on_startup and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 优先从监控合约池加载合约
                monitor_pool = cache_data.get('monitor_pool', {})
                if monitor_pool:
                    # 如果有监控合约池，直接使用
                    self.cached_contracts = monitor_pool
                    self.contract_pool = set(monitor_pool.keys())
                    print(f"📋 从监控合约池加载了 {len(self.contract_pool)} 个合约")
                else:
                    # 如果没有监控合约池，则从所有合约中筛选符合条件的
                    try:
                        from config.settings import settings
                        threshold = settings.FUNDING_RATE_THRESHOLD
                        min_volume = settings.MIN_VOLUME
                    except ImportError:
                        threshold = 0.005  # 0.5% 默认值
                        min_volume = 1000000  # 100万USDT 默认值
                    
                    # 筛选符合条件的合约
                    contracts_by_interval = cache_data.get('contracts_by_interval', {})
                    filtered_contracts = {}
                    
                    for interval, contracts in contracts_by_interval.items():
                        for symbol, info in contracts.items():
                            try:
                                funding_rate = abs(float(info.get('current_funding_rate', 0)))
                                volume_24h = float(info.get('volume_24h', 0))
                                
                                if funding_rate >= threshold and volume_24h >= min_volume:
                                    filtered_contracts[symbol] = info
                            except (ValueError, TypeError):
                                continue
                    
                    # 只选择前N个合约
                    sorted_contracts = sorted(
                        filtered_contracts.items(), 
                        key=lambda x: abs(float(x[1]['current_funding_rate'])), 
                        reverse=True
                    )
                    selected_contracts = dict(sorted_contracts[:self.parameters['max_contracts_in_pool']])
                    
                    self.cached_contracts = selected_contracts
                    self.contract_pool = set(selected_contracts.keys())
                    print(f"📋 从所有合约中筛选出 {len(self.contract_pool)} 个符合条件的合约")
                
                self.last_update_time = datetime.now()
                
            except Exception as e:
                print(f"❌ 加载统一缓存失败: {e}")
                self.cached_contracts = {}
                self.contract_pool = set()
                self.last_update_time = None
        else:
            self.cached_contracts = {}
            self.contract_pool = set()
            self.last_update_time = None
            print("🔄 清空合约池，准备重新检测")

    def _save_cache(self):
        """保存缓存 - 现在使用统一缓存，不再单独保存"""
        # 策略不再单独保存缓存，统一缓存由API维护
        pass

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

    def update_existing_contracts_funding_rates(self):
        """更新现有合约池中合约的最新资金费率（不改变合约池大小）"""
        try:
            print("🔄 开始更新现有合约池中合约的最新资金费率...")
            
            if not self.contract_pool:
                print("⚠️ 合约池为空，无法更新资金费率")
                return
            
            # 从合并后的全量缓存获取最新资金费率数据
            all_cache_file = "cache/all_funding_contracts_full.json"
            if not os.path.exists(all_cache_file):
                print("⚠️ 全量缓存文件不存在")
                return
            
            try:
                with open(all_cache_file, 'r', encoding='utf-8') as f:
                    all_cache_data = json.load(f)
                
                # 获取latest_rates字段
                latest_rates = all_cache_data.get('latest_rates', {})
                if not latest_rates:
                    print("⚠️ 全量缓存中没有最新资金费率数据")
                    return
                updated_count = 0
                
                # 只更新现有合约池中的合约
                for symbol in list(self.contract_pool):
                    if symbol in latest_rates:
                        latest_info = latest_rates[symbol]
                        
                        # 更新缓存中的合约信息
                        if symbol in self.cached_contracts:
                            # 保持原有结构，只更新资金费率相关字段
                            self.cached_contracts[symbol].update({
                                'current_funding_rate': latest_info.get('funding_rate', 0),
                                'mark_price': latest_info.get('mark_price', 0),
                                'index_price': latest_info.get('index_price'),
                                'next_funding_time': latest_info.get('next_funding_time'),
                                'last_updated': latest_info.get('last_updated', datetime.now().isoformat())
                            })
                            updated_count += 1
                
                if updated_count > 0:
                    # 保存更新后的缓存
                    self._save_cache()
                    self.last_update_time = datetime.now()
                    print(f"✅ 成功更新了 {updated_count} 个合约的最新资金费率")
                else:
                    print("⚠️ 没有找到需要更新的合约")
                    
            except Exception as e:
                print(f"❌ 更新现有合约资金费率失败: {e}")
                
        except Exception as e:
            print(f"❌ 更新现有合约资金费率异常: {e}")

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
                # 只有在非首次刷新时才发送出池通知
                if self.last_update_time and (datetime.now() - self.last_update_time).total_seconds() > 60:
                    for symbol in removed_contracts:
                        if symbol in self.cached_contracts:
                            info = self.cached_contracts[symbol]
                            funding_rate = info.get('current_funding_rate', 0)
                            mark_price = info.get('mark_price', 0)
                            volume_24h = info.get('volume_24h', 0)
                            
                            message = f"🔻 合约出池: {symbol}\n" \
                                     f"资金费率: {funding_rate:.4%}\n" \
                                     f"标记价格: ${mark_price:.4f}\n" \
                                     f"24h成交量: {volume_24h:,.0f}"
                            send_telegram_message(message)
                        else:
                            # 如果没有详细信息，发送简单通知
                            send_telegram_message(f"🔻 合约出池: {symbol}")
                else:
                    print(f"⚠️ 首次刷新，跳过出池通知")
            
            # 入池合约
            added_contracts = new_pool - self.contract_pool
            if added_contracts:
                print(f"🔺 入池合约: {', '.join(added_contracts)}")
                # 只有在非首次刷新时才发送入池通知
                if self.last_update_time and (datetime.now() - self.last_update_time).total_seconds() > 60:
                    for symbol in added_contracts:
                        if symbol in selected_contracts:
                            info = selected_contracts[symbol]
                            funding_rate = info.get('current_funding_rate', 0)
                            mark_price = info.get('mark_price', 0)
                            volume_24h = info.get('volume_24h', 0)
                            
                            message = f"🔺 合约入池: {symbol}\n" \
                                     f"资金费率: {funding_rate:.4%}\n" \
                                     f"标记价格: ${mark_price:.4f}\n" \
                                     f"24h成交量: {volume_24h:,.0f}"
                            send_telegram_message(message)
                        else:
                            # 如果没有详细信息，发送简单通知
                            send_telegram_message(f"🔺 合约入池: {symbol}")
                else:
                    print(f"⚠️ 首次刷新，跳过入池通知")
            
            # 更新合约池和缓存
            self.contract_pool = new_pool
            self.cached_contracts = selected_contracts
            self.last_update_time = datetime.now()
            self._save_cache()
            
            print(f"✅ 合约池刷新完成，当前池内合约数: {len(self.contract_pool)}")
        except Exception as e:
            print(f"❌ 刷新合约池失败: {e}")

    def check_funding_rates(self):
        """检查资金费率并发送通知 - 使用统一的API端点"""
        try:
            print("🔄 定时任务: 开始检查资金费率...")
            
            # 调用统一的API端点获取最新资金费率
            try:
                import requests
                api_url = "http://localhost:8000/funding_monitor/latest-rates"
                response = requests.get(api_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    contracts = data.get('contracts', {})
                    real_time_count = data.get('real_time_count', 0)
                    cached_count = data.get('cached_count', 0)
                    
                    print(f"✅ 定时任务: 成功获取最新资金费率数据")
                    print(f"📊 合约数量: {len(contracts)}, 实时: {real_time_count}, 缓存: {cached_count}")
                    
                    # 不再发送资金费率警告，避免与入池出池通知重复
                    # 资金费率警告现在由API的入池出池逻辑统一处理
                    print(f"✅ 定时任务: 资金费率数据已获取，共 {len(contracts)} 个合约")
                    
                    # 更新本地缓存数据
                    self.cached_contracts = contracts
                    self.last_update_time = datetime.now()
                    print(f"💾 定时任务: 本地缓存已更新")
                    
                    # 同时更新现有合约池中合约的最新资金费率
                    self.update_existing_contracts_funding_rates()
                    
                else:
                    print(f"❌ 定时任务: API调用失败，状态码: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print("❌ 定时任务: 无法连接到API服务器，使用现有缓存数据")
                self._check_existing_cache()
            except requests.exceptions.Timeout:
                print("❌ 定时任务: API请求超时，使用现有缓存数据")
                self._check_existing_cache()
            except Exception as e:
                print(f"❌ 定时任务: API调用异常: {e}")
                # API异常时，使用现有缓存数据进行检查
                self._check_existing_cache()
            
            print("✅ 定时任务: 资金费率检查完成")
            
        except Exception as e:
            print(f"❌ 定时任务: 检查资金费率失败: {e}")

    def _check_existing_cache(self):
        """使用现有缓存数据检查资金费率（备用方案）"""
        try:
            print("🔄 定时任务: 使用现有缓存数据进行检查...")
            
            if not self._is_cache_valid():
                print("⚠️ 定时任务: 本地缓存已过期，尝试更新...")
                self._update_cached_contracts()
            
            # 使用统一的资金费率检查逻辑
            self._check_funding_rates_from_cache()
                
        except Exception as e:
            print(f"❌ 定时任务: 使用缓存数据检查失败: {e}")

    def _check_funding_rates_from_cache(self):
        """从缓存检查资金费率（不再发送警告）"""
        try:
            print(f"✅ 定时任务(缓存): 使用缓存数据检查完成，共 {len(self.cached_contracts)} 个合约")
            print("ℹ️  资金费率警告现在由API的入池出池逻辑统一处理，避免重复通知")
                
        except Exception as e:
            print(f"❌ 定时任务: 缓存资金费率检查失败: {e}")

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
        
        # 启动调度器线程
        self._stop_event.clear()  # 清除停止标志
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        print("✅ 调度器线程已启动")
    
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
        while not self._stop_event.is_set():
            try:
                schedule.run_pending()
                # 使用更短的睡眠时间，以便更快响应停止信号
                if self._stop_event.wait(timeout=1):
                    break
            except Exception as e:
                print(f"❌ 调度器异常: {e}")
                # 检查停止信号，如果被设置则退出
                if self._stop_event.wait(timeout=5):
                    break
        
        print("🛑 调度器已停止")
    
    def get_current_pool(self):
        """获取当前合约池"""
        return list(self.contract_pool)
    
    def stop_monitoring(self):
        """停止监控系统"""
        print("🛑 停止资金费率监控系统...")
        
        # 设置停止标志
        self._stop_event.set()
        print("✅ 停止标志已设置")
        
        # 等待调度器线程结束
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            print("🔄 等待调度器线程结束...")
            self._scheduler_thread.join(timeout=10)  # 最多等待10秒
            if self._scheduler_thread.is_alive():
                print("⚠️ 调度器线程未能在10秒内结束，强制终止")
            else:
                print("✅ 调度器线程已正常结束")
        
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