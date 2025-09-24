from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import threading
import time
import traceback
import os
import requests # Added for direct API calls
import asyncio
from concurrent.futures import ThreadPoolExecutor
import queue

# 数据库相关导入已移除，直接从settings.py读取配置
from strategies.factory import StrategyFactory
from strategies.funding_rate_arbitrage import FundingRateMonitor
# 内联数据读取功能，不再依赖data模块
from config.settings import settings
from utils.notifier import send_telegram_message, send_email_notification

# 在文件顶部导入os
import os

app = FastAPI(title="加密货币资金费率监控系统", version="1.0.0")

# 异步任务管理器
class AsyncTaskManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.task_queue = queue.Queue()
        self.running_tasks = {}
        self.task_results = {}
    
    def submit_task(self, task_id: str, func, *args, **kwargs):
        """提交异步任务"""
        if task_id in self.running_tasks:
            return {"status": "already_running", "task_id": task_id}
        
        future = self.executor.submit(func, *args, **kwargs)
        self.running_tasks[task_id] = {
            "future": future,
            "start_time": time.time(),
            "status": "running"
        }
        
        # 启动结果处理线程
        threading.Thread(target=self._handle_task_result, args=(task_id, future), daemon=True).start()
        
        return {"status": "submitted", "task_id": task_id}
    
    def _handle_task_result(self, task_id: str, future):
        """处理任务结果"""
        try:
            result = future.result()
            self.task_results[task_id] = {
                "status": "completed",
                "result": result,
                "end_time": time.time()
            }
        except Exception as e:
            self.task_results[task_id] = {
                "status": "failed",
                "error": str(e),
                "end_time": time.time()
            }
            print(f"❌ 异步任务 {task_id} 执行失败: {e}")
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    def get_task_status(self, task_id: str):
        """获取任务状态"""
        if task_id in self.running_tasks:
            task_info = self.running_tasks[task_id]
            return {
                "status": "running",
                "start_time": task_info["start_time"],
                "duration": time.time() - task_info["start_time"]
            }
        elif task_id in self.task_results:
            return self.task_results[task_id]
        else:
            return {"status": "not_found"}

# 创建全局任务管理器
task_manager = AsyncTaskManager()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic模型
class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str
    parameters: Optional[Dict[str, Any]] = None

class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class FundingMonitorRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = None

# 全局资金费率监控策略实例
funding_monitor_instance = None
funding_monitor_thread = None
funding_monitor_running = False

def create_funding_monitor(params: dict = None):
    """创建资金费率监控策略实例"""
    global funding_monitor_instance
    
    default_params = {
        'funding_rate_threshold': 0.005,
        'contract_refresh_interval': 60,
        'funding_rate_check_interval': 60,
        'max_pool_size': 20,
        'min_volume': 1000000,
        'exchanges': ['binance', 'okx', 'bybit']
    }
    
    if params:
        default_params.update(params)
    
    funding_monitor_instance = FundingRateMonitor(default_params)
    return funding_monitor_instance
    
# 数据API
@app.get("/symbols")
def get_symbols():
    """获取所有交易对"""
    try:
        # 内联数据读取功能
        symbols = []
        try:
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
            print(f"读取缓存文件失败: {e}")
        
        return {
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        print(f"获取交易对异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取交易对失败: {str(e)}")

@app.get("/funding_rates")
def get_funding_rates(symbol: Optional[str] = None, exchange: Optional[str] = None):
    """获取资金费率"""
    try:
        if symbol:
            # 使用 BinanceFunding 获取历史资金费率
            from utils.binance_funding import BinanceFunding
            funding = BinanceFunding()
            history = funding.get_funding_history(symbol, "UM", limit=20)
            
            # 转换数据格式
            formatted_history = []
            for item in history:
                formatted_history.append({
                    "funding_time": datetime.fromtimestamp(item['funding_time']/1000).strftime('%Y-%m-%d %H:%M:%S'),
                    "funding_rate": float(item['funding_rate']),
                    "mark_price": float(item['mark_price']) if item.get('mark_price') else 0
                })
            
            return {
                "symbol": symbol,
                "exchange": exchange or "binance",
                "funding_rate": formatted_history
            }
        else:
            # 获取所有合约的当前资金费率
            from utils.binance_funding import BinanceFunding
            funding = BinanceFunding()
            all_contracts = funding.get_1h_contracts_from_cache()
            
            rates = []
            for symbol, info in all_contracts.items():
                rates.append({
                    "symbol": symbol,
                    "funding_rate": float(info.get("current_funding_rate", 0)),
                    "mark_price": float(info.get("mark_price", 0))
                })
            
            return {
                "exchange": exchange or "binance",
                "funding_rates": rates,
                "count": len(rates)
            }
    except Exception as e:
        print(f"获取资金费率异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取资金费率失败: {str(e)}")

@app.post("/funding_monitor/refresh-candidates")
def refresh_funding_candidates():
    """刷新备选合约池 - 使用现成的币安API方法"""
    try:
        # 使用现成的方法获取币安数据
        from utils.binance_funding import get_all_funding_rates, get_all_24h_volumes
        
        try:
            funding_rates = get_all_funding_rates()
        except Exception as e:
            error_msg = f"获取资金费率数据失败: {str(e)}"
            print(f"❌ {error_msg}")
            # API失败时直接抛出异常，不回退到缓存
            raise HTTPException(status_code=500, detail=error_msg)
        
        try:
            volumes = get_all_24h_volumes()
        except Exception as e:
            error_msg = f"获取成交量数据失败: {str(e)}"
            print(f"❌ {error_msg}")
            # API失败时直接抛出异常，不回退到缓存
            raise HTTPException(status_code=500, detail=error_msg)
        
        # 筛选符合条件的合约（资金费率超过阈值）
        try:
            from config.settings import settings
            threshold = settings.FUNDING_RATE_THRESHOLD
            min_volume = settings.MIN_VOLUME
        except ImportError:
            threshold = 0.005  # 0.5% 默认值
            min_volume = 1000000  # 100万USDT 默认值
        
        filtered_contracts = {}
        contracts_by_interval = {}  # 按结算周期分组存储
        
        for symbol, funding_info in funding_rates.items():
            try:
                funding_rate = float(funding_info.get('lastFundingRate', 0))
                volume_24h = volumes.get(symbol, 0)
                
                # 使用现有的专业方法检测结算周期
                from utils.binance_funding import BinanceFunding
                funding = BinanceFunding()
                funding_interval_hours = funding.detect_funding_interval(symbol, "UM")
                
                if funding_interval_hours:
                    # 将结算周期分类到最接近的标准间隔
                    if abs(funding_interval_hours - 1.0) < 0.1:
                        funding_interval_hours = 1.0
                    elif abs(funding_interval_hours - 8.0) < 0.1:
                        funding_interval_hours = 8.0
                    elif abs(funding_interval_hours - 4.0) < 0.1:
                        funding_interval_hours = 4.0
                    elif abs(funding_interval_hours - 2.0) < 0.1:
                        funding_interval_hours = 2.0
                    elif abs(funding_interval_hours - 12.0) < 0.1:
                        funding_interval_hours = 12.0
                    elif abs(funding_interval_hours - 24.0) < 0.1:
                        funding_interval_hours = 24.0
                    else:
                        # 其他间隔，按小时四舍五入
                        funding_interval_hours = round(funding_interval_hours)
                    
                else:
                    continue  # 直接跳过无法检测结算周期的合约
                
                # 格式化下次结算时间为北京时间
                next_funding_timestamp = funding_info.get('nextFundingTime', '')
                next_funding_time_str = ''
                if next_funding_timestamp:
                    try:
                        # 转换为北京时间
                        next_time = datetime.fromtimestamp(int(next_funding_timestamp) / 1000)
                        beijing_time = next_time + timedelta(hours=8)
                        next_funding_time_str = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(f"⚠️ 时间格式化失败 {next_funding_timestamp}: {e}")
                        next_funding_time_str = str(next_funding_timestamp)
                
                # 构建合约信息
                contract_info = {
                    'symbol': symbol,
                    'contract_type': 'UM',
                    'current_funding_rate': funding_rate,
                    'next_funding_time': next_funding_time_str,
                    'funding_interval_hours': funding_interval_hours,
                    'mark_price': float(funding_info.get('markPrice', 0)),
                    'index_price': float(funding_info.get('indexPrice', 0)),
                    'volume_24h': volume_24h,
                    'last_updated': datetime.now().isoformat()
                }
                
                # 按结算周期分组存储
                interval_key = f"{int(funding_interval_hours)}h"
                if interval_key not in contracts_by_interval:
                    contracts_by_interval[interval_key] = {}
                contracts_by_interval[interval_key][symbol] = contract_info
                
                # 筛选符合条件的合约
                if abs(funding_rate) >= threshold and volume_24h >= min_volume:
                    filtered_contracts[symbol] = contract_info
                    
            except (ValueError, TypeError) as e:
                print(f"⚠️ 处理合约 {symbol} 时出错: {e}")
                continue
        
        # 不再单独保存监控合约缓存，所有数据都保存在统一缓存中
        
        # 统计结算周期和合约数量
        intervals_found = []
        total_contracts = 0
        
        for interval, contracts in contracts_by_interval.items():
            if contracts:  # 只统计有合约的结算周期
                intervals_found.append(interval)
                total_contracts += len(contracts)
        
        # 保存到统一的缓存文件
        main_cache_data = {
            'cache_time': datetime.now().isoformat(),
            'contracts_by_interval': contracts_by_interval,
            'total_scanned': len(funding_rates),
            'intervals_found': intervals_found,
            'monitor_pool': filtered_contracts  # 添加监控合约池
        }
        
        with open("cache/all_funding_contracts_full.json", 'w', encoding='utf-8') as f:
            json.dump(main_cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 监控合约池更新完成，共 {len(filtered_contracts)} 个符合条件合约，总计 {total_contracts} 个合约")
        
        # 发送Telegram通知
        try:
            from utils.notifier import send_telegram_message
            message = f"🔄 备选合约池已刷新\n" \
                     f"📊 总计: {total_contracts}个合约，结算周期: {', '.join(intervals_found)}\n" \
                     f"🎯 符合条件合约: {len(filtered_contracts)}个\n" \
                     f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_telegram_message(message)
        except Exception as e:
            print(f"⚠️ 发送Telegram通知失败: {e}")
        
        return {
            "status": "success",
            "message": "备选合约池刷新成功（使用最新数据）",
            "timestamp": datetime.now().isoformat(),
            "contracts_count": total_contracts,
            "filtered_count": len(filtered_contracts),
            "intervals_found": intervals_found
        }

    except Exception as e:
        print(f"刷新备选合约池异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"刷新备选合约池失败: {str(e)}")



@app.get("/funding_monitor/pool")
def get_funding_pool():
    """获取当前监控合约池"""
    try:
        # 从统一缓存文件读取数据
        cache_file = "cache/all_funding_contracts_full.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
                    # 直接从缓存中获取监控合约池
        monitor_pool = cached_data.get('monitor_pool', {})
        
        # 如果没有监控合约池，直接返回空结果
        if not monitor_pool:
            print("⚠️ 监控合约池为空，返回空结果")
            return {
                "status": "success",
                "contracts": [],
                "count": 0,
                "timestamp": datetime.now().isoformat(),
                "message": "监控合约池为空，请先刷新合约池"
            }
        
        # 转换为列表格式
        contracts_list = []
        for symbol, info in monitor_pool.items():
            try:
                contracts_list.append({
                    "symbol": symbol,
                    "exchange": info.get("exchange", "binance"),
                    "funding_rate": float(info.get("current_funding_rate", 0)),
                    "funding_time": info.get("next_funding_time", ""),
                    "funding_interval": info.get("funding_interval", "1h"),  # 添加结算周期
                    "volume_24h": info.get("volume_24h", 0),
                    "mark_price": info.get("mark_price", 0)
                })
            except (ValueError, TypeError) as e:
                print(f"⚠️ 处理合约 {symbol} 时出错: {e}")
                continue
        
        return {
            "status": "success",
            "contracts": contracts_list,
            "count": len(contracts_list),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取合约池异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取合约池失败: {str(e)}")

@app.get("/funding_monitor/candidates")
def get_funding_candidates():
    """获取备选合约池"""
    try:
        # 从统一缓存文件读取数据
        cache_file = "cache/all_funding_contracts_full.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # 从统一缓存中获取所有合约作为备选
            all_contracts = {}
            contracts_by_interval = cached_data.get('contracts_by_interval', {})
            
            for interval, contracts in contracts_by_interval.items():
                all_contracts.update(contracts)
            
            return {
                "status": "success",
                "contracts": all_contracts,
                "count": len(all_contracts),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "success",
                "contracts": {},
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        print(f"获取备选合约异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取备选合约失败: {str(e)}")

@app.get("/funding_monitor/all-contracts")
def get_all_contracts():
    """获取所有结算周期合约"""
    try:
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        
        # 获取所有结算周期合约基础信息
        all_contracts_data = funding.get_all_intervals_from_cache()
        
        if not all_contracts_data or not all_contracts_data.get('contracts_by_interval'):
            return {
                "status": "error",
                "message": "没有合约缓存数据，请先刷新合约缓存",
                "timestamp": datetime.now().isoformat()
            }
        
        # 转换数据格式以匹配Web界面期望的格式，并获取最新资金费率
        formatted_contracts = {}
        total_contracts = 0
        
        for interval, contracts in all_contracts_data['contracts_by_interval'].items():
            for symbol, info in contracts.items():
                try:
                    # 获取最新的资金费率信息
                    current_info = funding.get_current_funding(symbol, "UM")
                    if current_info:
                        # 使用最新的资金费率数据
                        funding_rate = float(current_info.get('funding_rate', 0))
                        next_funding_time = current_info.get('next_funding_time')
                        if next_funding_time:
                            next_time = datetime.fromtimestamp(next_funding_time / 1000)
                            funding_time_str = next_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            funding_time_str = info.get("next_funding_time", "")
                    else:
                        # 如果获取失败，使用缓存数据
                        funding_rate = float(info.get("current_funding_rate", 0))
                        funding_time_str = info.get("next_funding_time", "")
                    
                    formatted_contracts[symbol] = {
                        "symbol": symbol,
                        "exchange": "binance",
                        "funding_rate": funding_rate,
                        "funding_time": funding_time_str,
                        "funding_interval": interval,
                        "volume_24h": info.get("volume_24h", 0),
                        "mark_price": info.get("mark_price", 0)
                    }
                    total_contracts += 1
                    
                    # 添加小延迟避免API限流
                    time.sleep(0.05)
                    
                except Exception as e:
                    print(f"处理合约 {symbol} 时出错: {e}")
                    # 使用缓存数据作为备选
                    formatted_contracts[symbol] = {
                        "symbol": symbol,
                        "exchange": "binance",
                        "funding_rate": float(info.get("current_funding_rate", 0)),
                        "funding_time": info.get("next_funding_time", ""),
                        "funding_interval": interval,
                        "volume_24h": info.get("volume_24h", 0),
                        "mark_price": info.get("mark_price", 0)
                    }
                    total_contracts += 1
        
        return {
            "status": "success",
            "contracts": formatted_contracts,
            "count": total_contracts,
            "intervals": list(all_contracts_data.get('contracts_by_interval', {}).keys()),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取所有结算周期合约异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取所有结算周期合约失败: {str(e)}")

@app.get("/funding_monitor/contracts-by-interval/{interval}")
def get_contracts_by_interval(interval: str):
    """获取指定结算周期的合约"""
    try:
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        
        # 获取指定结算周期的合约
        contracts = funding.get_contracts_by_interval_from_cache(interval)
        
        if not contracts:
            return {
                "status": "error",
                "message": f"没有找到{interval}结算周期的合约缓存数据",
                "timestamp": datetime.now().isoformat()
            }
        
        # 转换数据格式
        formatted_contracts = {}
        for symbol, info in contracts.items():
            try:
                # 直接使用缓存数据，不调用API获取最新信息
                funding_rate = float(info.get("current_funding_rate", 0))
                funding_time_str = info.get("next_funding_time", "")
                
                # 格式化时间显示
                funding_time_display = funding_time_str
                if funding_time_str and funding_time_str != "未知":
                    try:
                        # 如果已经是格式化的时间字符串，直接使用
                        if isinstance(funding_time_str, str) and "-" in funding_time_str:
                            funding_time_display = funding_time_str
                        else:
                            # 如果是时间戳，转换为北京时间
                            timestamp = int(funding_time_str)
                            if timestamp > 1e10:  # 毫秒时间戳
                                timestamp = timestamp / 1000
                            next_time = datetime.fromtimestamp(timestamp)
                            beijing_time = next_time + timedelta(hours=8)
                            funding_time_display = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(f"⚠️ 时间格式化失败 {funding_time_str}: {e}")
                        funding_time_display = str(funding_time_str)
                
                formatted_contracts[symbol] = {
                    "symbol": symbol,
                    "exchange": "binance",
                    "funding_rate": funding_rate,
                    "funding_time": funding_time_display,
                    "funding_interval": interval,
                    "volume_24h": info.get("volume_24h", 0),
                    "mark_price": info.get("mark_price", 0)
                }
                
            except Exception as e:
                print(f"处理合约 {symbol} 时出错: {e}")
                formatted_contracts[symbol] = {
                    "symbol": symbol,
                    "exchange": "binance",
                    "funding_rate": float(info.get("current_funding_rate", 0)),
                    "funding_time": info.get("next_funding_time", ""),
                    "funding_interval": interval,
                    "volume_24h": info.get("volume_24h", 0),
                    "mark_price": info.get("mark_price", 0)
                }
        
        return {
            "status": "success",
            "interval": interval,
            "contracts": formatted_contracts,
            "count": len(formatted_contracts),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取{interval}结算周期合约异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取{interval}结算周期合约失败: {str(e)}")

@app.get("/funding_monitor/cache-status")
def get_cache_status():
    """获取缓存状态概览"""
    try:
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        
        cache_status = funding.get_all_intervals_from_cache()
        
        if not cache_status:
            return {
                "status": "error",
                "message": "没有缓存数据",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "status": "success",
            "cache_time": cache_status.get('cache_time'),
            "intervals": cache_status.get('intervals', []),
            "total_contracts": cache_status.get('total_contracts', 0),
            "contracts_by_interval": {
                interval: len(contracts) 
                for interval, contracts in cache_status.get('contracts_by_interval', {}).items()
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取缓存状态异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取缓存状态失败: {str(e)}")

@app.get("/funding_monitor/latest-rates-async")
def get_latest_funding_rates_async(fast_mode: bool = False, cache_only: bool = False):
    """异步获取所有结算周期合约的最新资金费率 - 立即返回，后台执行"""
    try:
        # 生成任务ID
        task_id = f"latest_rates_{int(time.time())}"
        
        # 提交异步任务
        result = task_manager.submit_task(
            task_id, 
            _execute_latest_rates_task, 
            fast_mode, 
            cache_only
        )
        
        if result["status"] == "submitted":
            return {
                "status": "success",
                "message": "任务已提交，正在后台执行",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "note": "使用异步模式，立即返回结果"
            }
        else:
            return {
                "status": "error",
                "message": f"任务提交失败: {result['status']}",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"❌ 异步任务提交失败: {e}")
        return {
            "status": "error",
            "message": f"异步任务提交失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

def _execute_latest_rates_task(fast_mode: bool = False, cache_only: bool = False):
    """执行latest-rates任务的真实逻辑"""
    try:
        print(f"🔄 异步任务开始执行: fast_mode={fast_mode}, cache_only={cache_only}")
        
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        start_time = time.time()
        
        print("🔄 开始获取最新资金费率（异步执行）...")
        
        # 获取所有结算周期合约基础信息
        all_contracts_data = funding.get_all_intervals_from_cache()
        
        if not all_contracts_data or not all_contracts_data.get('contracts_by_interval'):
            print("❌ 没有合约缓存数据，请先刷新合约缓存")
            return {
                "status": "error",
                "message": "没有合约缓存数据，请先刷新合约缓存",
                "timestamp": datetime.now().isoformat()
            }
        
        # 获取最新资金费率
        latest_rates = {}
        real_time_count = 0
        cached_count = 0
        processed_count = 0
        total_contracts = sum(len(contracts) for contracts in all_contracts_data['contracts_by_interval'].values())
        
        print(f"📊 总合约数: {total_contracts}")
        
        # 优先处理监控池中的合约
        monitor_pool_symbols = set()
        try:
            with open("cache/all_funding_contracts_full.json", 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                monitor_pool = cache_data.get('monitor_pool', {})
                monitor_pool_symbols = set(monitor_pool.keys())
                print(f"🎯 监控池合约数: {len(monitor_pool_symbols)}")
        except Exception as e:
            print(f"⚠️ 读取监控池失败: {e}")
        
        # 快速模式：只处理监控池中的合约
        if fast_mode:
            print("🚀 快速模式：只处理监控池中的合约")
            total_contracts = len(monitor_pool_symbols)
            print(f"📊 快速模式总合约数: {total_contracts}")
        
        # 纯缓存模式：完全避免API调用
        if cache_only:
            print("💾 纯缓存模式：完全避免API调用")
            latest_rates = {}
            cached_count = 0
            
            for interval, contracts in all_contracts_data['contracts_by_interval'].items():
                for symbol, contract_info in contracts.items():
                    # 只处理监控池中的合约
                    if fast_mode and symbol not in monitor_pool_symbols:
                        continue
                    
                    funding_rate = contract_info.get('current_funding_rate', 0)
                    mark_price = contract_info.get('mark_price', 0)
                    
                    # 确保数据类型正确
                    try:
                        funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                    except (ValueError, TypeError):
                        funding_rate = 0.0
                    
                    try:
                        mark_price = float(mark_price) if mark_price is not None else 0.0
                    except (ValueError, TypeError):
                        mark_price = 0.0
                    
                    latest_rates[symbol] = {
                        "symbol": symbol,
                        "exchange": "binance",
                        "funding_rate": funding_rate,
                        "next_funding_time": contract_info.get('next_funding_time'),
                        "funding_interval": interval,
                        "mark_price": mark_price,
                        "index_price": contract_info.get('index_price'),
                        "last_updated": "cached",
                        "data_source": "cached",
                        "note": "纯缓存模式，无API调用"
                    }
                    cached_count += 1
            
            execution_time = time.time() - start_time
            print(f"📊 纯缓存模式完成: 合约数 {len(latest_rates)}, 执行时间: {execution_time:.2f}秒")
            
            # 保存历史数据到JSON文件
            try:
                save_monitor_history_data(latest_rates)
            except Exception as e:
                print(f"⚠️ 保存历史数据失败: {e}")
            
            print(f"✅ 异步任务执行完成: {execution_time:.2f}秒")
            
            return {
                "status": "success",
                "contracts": latest_rates,
                "count": len(latest_rates),
                "real_time_count": 0,
                "cached_count": cached_count,
                "processed_count": cached_count,
                "execution_time": execution_time,
                "mode": "cache_only",
                "timestamp": datetime.now().isoformat(),
                "note": "纯缓存模式，完全避免API调用"
            }
        
        # 分批处理，每批处理10个合约（减少批次大小）
        batch_size = 10
        batch_count = 0
        
        for interval, contracts in all_contracts_data['contracts_by_interval'].items():
            symbols = list(contracts.keys())
            
            # 快速模式：只处理监控池中的合约
            if fast_mode:
                symbols = [s for s in symbols if s in monitor_pool_symbols]
                if not symbols:
                    continue  # 跳过没有监控池合约的间隔
            
            # 优先处理监控池中的合约
            monitor_symbols = [s for s in symbols if s in monitor_pool_symbols]
            other_symbols = [s for s in symbols if s not in monitor_pool_symbols]
            
            # 先处理监控池合约
            all_symbols = monitor_symbols + other_symbols
            
            # 分批处理
            for i in range(0, len(all_symbols), batch_size):
                batch_symbols = all_symbols[i:i + batch_size]
                batch_count += 1
                
                monitor_count = len([s for s in batch_symbols if s in monitor_pool_symbols])
                print(f"🔄 处理第 {batch_count} 批，合约数: {len(batch_symbols)} (监控池: {monitor_count})")
                
                for symbol in batch_symbols:
                    # 检查执行时间
                    current_time = time.time()
                    max_execution_time = 300  # 5分钟超时
                    if current_time - start_time > max_execution_time:
                        print(f"⏰ 执行时间超限 ({max_execution_time}秒)，停止处理")
                        break
                    
                    try:
                        current_info = funding.get_current_funding(symbol, "UM")
                        
                        if current_info:
                            funding_rate = current_info.get('funding_rate', 0)
                            mark_price = current_info.get('mark_price', 0)
                            
                            # 确保数据类型正确
                            try:
                                funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                            except (ValueError, TypeError):
                                funding_rate = 0.0
                            
                            try:
                                mark_price = float(mark_price) if mark_price is not None else 0.0
                            except (ValueError, TypeError):
                                mark_price = 0.0
                            
                            latest_rates[symbol] = {
                                "symbol": symbol,
                                "exchange": "binance",
                                "funding_rate": funding_rate,
                                "next_funding_time": current_info.get('next_funding_time'),
                                "funding_interval": interval,
                                "mark_price": mark_price,
                                "index_price": current_info.get('index_price'),
                                "last_updated": datetime.now().isoformat(),
                                "data_source": "real_time"
                            }
                            real_time_count += 1
                            processed_count += 1
                            
                        else:
                            # 使用缓存数据
                            cached_info = contracts.get(symbol, {})
                            funding_rate = cached_info.get('current_funding_rate', 0)
                            mark_price = cached_info.get('mark_price', 0)
                            
                            # 确保数据类型正确
                            try:
                                funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                            except (ValueError, TypeError):
                                funding_rate = 0.0
                            
                            try:
                                mark_price = float(mark_price) if mark_price is not None else 0.0
                            except (ValueError, TypeError):
                                mark_price = 0.0
                            
                            latest_rates[symbol] = {
                                "symbol": symbol,
                                "exchange": "binance",
                                "funding_rate": funding_rate,
                                "next_funding_time": cached_info.get('next_funding_time'),
                                "funding_interval": interval,
                                "mark_price": mark_price,
                                "index_price": cached_info.get('index_price'),
                                "last_updated": "cached",
                                "data_source": "cached",
                                "note": "使用缓存数据"
                            }
                            cached_count += 1
                            processed_count += 1
                        
                        # 添加延迟避免API限流
                        time.sleep(0.05)  # 减少延迟到50ms
                        
                    except Exception as e:
                        print(f"    ❌ 获取 {symbol} 最新资金费率失败: {e}")
                        # 使用缓存数据
                        cached_info = contracts.get(symbol, {})
                        funding_rate = cached_info.get('current_funding_rate', 0)
                        mark_price = cached_info.get('mark_price', 0)
                        
                        # 确保数据类型正确
                        try:
                            funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                        except (ValueError, TypeError):
                            funding_rate = 0.0
                        
                        try:
                            mark_price = float(mark_price) if mark_price is not None else 0.0
                        except (ValueError, TypeError):
                            mark_price = 0.0
                        
                        latest_rates[symbol] = {
                            "symbol": symbol,
                            "exchange": "binance",
                            "funding_rate": funding_rate,
                            "next_funding_time": cached_info.get('next_funding_time'),
                            "funding_interval": interval,
                            "mark_price": mark_price,
                            "index_price": cached_info.get('index_price'),
                            "last_updated": "cached",
                            "data_source": "cached",
                            "note": "使用缓存数据"
                        }
                        cached_count += 1
                        processed_count += 1
                
                # 批次间延迟
                time.sleep(0.1)
                
                # 检查是否需要提前结束
                current_time = time.time()
                if current_time - start_time > max_execution_time:
                    print(f"⏰ 执行时间超限，提前结束处理")
                    break
            
            # 检查是否需要提前结束
            current_time = time.time()
            if current_time - start_time > max_execution_time:
                break
        
        execution_time = time.time() - start_time
        print(f"📊 资金费率获取完成: 实时 {real_time_count} 个，缓存 {cached_count} 个，总计 {len(latest_rates)} 个")
        print(f"⏱️ 执行时间: {execution_time:.2f}秒，处理合约: {processed_count}/{total_contracts}")
        
        # 保存历史数据到JSON文件
        try:
            save_monitor_history_data(latest_rates)
        except Exception as e:
            print(f"⚠️ 保存历史数据失败: {e}")
        
        print(f"✅ 异步任务执行完成: {execution_time:.2f}秒")
        
        return {
            "status": "success",
            "contracts": latest_rates,
            "count": len(latest_rates),
            "real_time_count": real_time_count,
            "cached_count": cached_count,
            "processed_count": processed_count,
            "execution_time": execution_time,
            "intervals": list(all_contracts_data.get('contracts_by_interval', {}).keys()),
            "timestamp": datetime.now().isoformat(),
            "note": "异步执行完成"
        }
        
    except Exception as e:
        print(f"❌ 异步任务执行失败: {e}")
        return {
            "status": "error",
            "message": f"异步任务执行失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/funding_monitor/task-status/{task_id}")
def get_task_status(task_id: str):
    """获取异步任务状态"""
    try:
        status = task_manager.get_task_status(task_id)
        return {
            "status": "success",
            "task_id": task_id,
            "task_status": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取任务状态失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/funding_monitor/latest-rates")
def get_latest_funding_rates(fast_mode: bool = False, cache_only: bool = False):
    """获取所有结算周期合约的最新资金费率并保存到缓存 - 优化版本
    
    Args:
        fast_mode: 快速模式，只处理监控池中的合约
        cache_only: 纯缓存模式，完全避免API调用
    """
    try:
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        
        import time
        from config.settings import settings
        
        start_time = time.time()
        max_execution_time = settings.API_REQUEST_TIMEOUT - 10  # 留10秒缓冲时间
        
        print("🔄 开始获取最新资金费率（优化版本）...")
        
        # 获取所有结算周期合约基础信息
        all_contracts_data = funding.get_all_intervals_from_cache()
        
        if not all_contracts_data or not all_contracts_data.get('contracts_by_interval'):
            print("❌ 没有合约缓存数据，请先刷新合约缓存")
            return {
                "status": "error",
                "message": "没有合约缓存数据，请先刷新合约缓存",
                "timestamp": datetime.now().isoformat()
            }
        
        # 获取最新资金费率
        latest_rates = {}
        real_time_count = 0
        cached_count = 0
        processed_count = 0
        total_contracts = sum(len(contracts) for contracts in all_contracts_data['contracts_by_interval'].values())
        
        print(f"📊 总合约数: {total_contracts}")
        
        # 优先处理监控池中的合约
        monitor_pool_symbols = set()
        try:
            with open("cache/all_funding_contracts_full.json", 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                monitor_pool = cache_data.get('monitor_pool', {})
                monitor_pool_symbols = set(monitor_pool.keys())
                print(f"🎯 监控池合约数: {len(monitor_pool_symbols)}")
        except Exception as e:
            print(f"⚠️ 读取监控池失败: {e}")
        
        # 快速模式：只处理监控池中的合约
        if fast_mode:
            print("🚀 快速模式：只处理监控池中的合约")
            total_contracts = len(monitor_pool_symbols)
            print(f"📊 快速模式总合约数: {total_contracts}")
        
        # 纯缓存模式：完全避免API调用
        if cache_only:
            print("💾 纯缓存模式：完全避免API调用")
            latest_rates = {}
            cached_count = 0
            
            for interval, contracts in all_contracts_data['contracts_by_interval'].items():
                for symbol, contract_info in contracts.items():
                    # 只处理监控池中的合约
                    if fast_mode and symbol not in monitor_pool_symbols:
                        continue
                    
                    funding_rate = contract_info.get('current_funding_rate', 0)
                    mark_price = contract_info.get('mark_price', 0)
                    
                    # 确保数据类型正确
                    try:
                        funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                    except (ValueError, TypeError):
                        funding_rate = 0.0
                    
                    try:
                        mark_price = float(mark_price) if mark_price is not None else 0.0
                    except (ValueError, TypeError):
                        mark_price = 0.0
                    
                    latest_rates[symbol] = {
                        "symbol": symbol,
                        "exchange": "binance",
                        "funding_rate": funding_rate,
                        "next_funding_time": contract_info.get('next_funding_time'),
                        "funding_interval": interval,
                        "mark_price": mark_price,
                        "index_price": contract_info.get('index_price'),
                        "last_updated": "cached",
                        "data_source": "cached",
                        "note": "纯缓存模式，无API调用"
                    }
                    cached_count += 1
            
            execution_time = time.time() - start_time
            print(f"📊 纯缓存模式完成: 合约数 {len(latest_rates)}, 执行时间: {execution_time:.2f}秒")
            
            # 保存历史数据到JSON文件
            try:
                save_monitor_history_data(latest_rates)
            except Exception as e:
                print(f"⚠️ 保存历史数据失败: {e}")
            
            return {
                "status": "success",
                "contracts": latest_rates,
                "count": len(latest_rates),
                "real_time_count": 0,
                "cached_count": cached_count,
                "processed_count": cached_count,
                "execution_time": execution_time,
                "mode": "cache_only",
                "timestamp": datetime.now().isoformat(),
                "note": "纯缓存模式，完全避免API调用"
            }
        
        # 分批处理，每批处理10个合约（减少批次大小）
        batch_size = 10
        batch_count = 0
        
        for interval, contracts in all_contracts_data['contracts_by_interval'].items():
            symbols = list(contracts.keys())
            
            # 快速模式：只处理监控池中的合约
            if fast_mode:
                symbols = [s for s in symbols if s in monitor_pool_symbols]
                if not symbols:
                    continue  # 跳过没有监控池合约的间隔
            
            # 优先处理监控池中的合约
            monitor_symbols = [s for s in symbols if s in monitor_pool_symbols]
            other_symbols = [s for s in symbols if s not in monitor_pool_symbols]
            
            # 先处理监控池合约
            all_symbols = monitor_symbols + other_symbols
            
            # 分批处理
            for i in range(0, len(all_symbols), batch_size):
                batch_symbols = all_symbols[i:i + batch_size]
                batch_count += 1
                
                monitor_count = len([s for s in batch_symbols if s in monitor_pool_symbols])
                print(f"🔄 处理第 {batch_count} 批，合约数: {len(batch_symbols)} (监控池: {monitor_count})")
                
                for symbol in batch_symbols:
                    # 检查执行时间
                    current_time = time.time()
                    if current_time - start_time > max_execution_time:
                        print(f"⏰ 执行时间超限 ({max_execution_time}秒)，停止处理")
                        break
                    
                    try:
                        current_info = funding.get_current_funding(symbol, "UM")
                        
                        if current_info:
                            funding_rate = current_info.get('funding_rate', 0)
                            mark_price = current_info.get('mark_price', 0)
                            
                            # 确保数据类型正确
                            try:
                                funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                            except (ValueError, TypeError):
                                funding_rate = 0.0
                            
                            try:
                                mark_price = float(mark_price) if mark_price is not None else 0.0
                            except (ValueError, TypeError):
                                mark_price = 0.0
                            
                            latest_rates[symbol] = {
                                "symbol": symbol,
                                "exchange": "binance",
                                "funding_rate": funding_rate,
                                "next_funding_time": current_info.get('next_funding_time'),
                                "funding_interval": interval,
                                "mark_price": mark_price,
                                "index_price": current_info.get('index_price'),
                                "last_updated": datetime.now().isoformat(),
                                "data_source": "real_time"
                            }
                            real_time_count += 1
                            processed_count += 1
                            
                        else:
                            # 使用缓存数据
                            cached_info = contracts.get(symbol, {})
                            funding_rate = cached_info.get('current_funding_rate', 0)
                            mark_price = cached_info.get('mark_price', 0)
                            
                            # 确保数据类型正确
                            try:
                                funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                            except (ValueError, TypeError):
                                funding_rate = 0.0
                            
                            try:
                                mark_price = float(mark_price) if mark_price is not None else 0.0
                            except (ValueError, TypeError):
                                mark_price = 0.0
                            
                            latest_rates[symbol] = {
                                "symbol": symbol,
                                "exchange": "binance",
                                "funding_rate": funding_rate,
                                "next_funding_time": cached_info.get('next_funding_time'),
                                "funding_interval": interval,
                                "mark_price": mark_price,
                                "index_price": cached_info.get('index_price'),
                                "last_updated": "cached",
                                "data_source": "cached",
                                "note": "使用缓存数据"
                            }
                            cached_count += 1
                            processed_count += 1
                        
                        # 添加延迟避免API限流
                        time.sleep(0.05)  # 减少延迟到50ms
                        
                    except Exception as e:
                        print(f"    ❌ 获取 {symbol} 最新资金费率失败: {e}")
                        # 使用缓存数据
                        cached_info = contracts.get(symbol, {})
                        funding_rate = cached_info.get('current_funding_rate', 0)
                        mark_price = cached_info.get('mark_price', 0)
                        
                        # 确保数据类型正确
                        try:
                            funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                        except (ValueError, TypeError):
                            funding_rate = 0.0
                        
                        try:
                            mark_price = float(mark_price) if mark_price is not None else 0.0
                        except (ValueError, TypeError):
                            mark_price = 0.0
                        
                        latest_rates[symbol] = {
                            "symbol": symbol,
                            "exchange": "binance",
                            "funding_rate": funding_rate,
                            "next_funding_time": cached_info.get('next_funding_time'),
                            "funding_interval": interval,
                            "mark_price": mark_price,
                            "index_price": cached_info.get('index_price'),
                            "last_updated": "cached",
                            "data_source": "cached",
                            "note": "使用缓存数据"
                        }
                        cached_count += 1
                        processed_count += 1
                
                # 批次间延迟
                time.sleep(0.1)
                
                # 检查是否需要提前结束
                current_time = time.time()
                if current_time - start_time > max_execution_time:
                    print(f"⏰ 执行时间超限，提前结束处理")
                    break
            
            # 检查是否需要提前结束
            current_time = time.time()
            if current_time - start_time > max_execution_time:
                break
        
        execution_time = time.time() - start_time
        print(f"📊 资金费率获取完成: 实时 {real_time_count} 个，缓存 {cached_count} 个，总计 {len(latest_rates)} 个")
        print(f"⏱️ 执行时间: {execution_time:.2f}秒，处理合约: {processed_count}/{total_contracts}")
        
        # 保存历史数据到JSON文件
        try:
            save_monitor_history_data(latest_rates)
        except Exception as e:
            print(f"⚠️ 保存历史数据失败: {e}")
        
        # 根据最新资金费率重新筛选符合条件的合约，更新监控池
        try:
            from config.settings import settings
            threshold = settings.FUNDING_RATE_THRESHOLD
            min_volume = settings.MIN_VOLUME
        except ImportError:
            threshold = 0.005  # 0.5% 默认值
            min_volume = 1000000  # 100万USDT 默认值
        
        # 从缓存中获取成交量数据
        volume_data = {}
        try:
            with open("cache/all_funding_contracts_full.json", 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                contracts_by_interval = cache_data.get('contracts_by_interval', {})
                for interval, contracts in contracts_by_interval.items():
                    for symbol, info in contracts.items():
                        volume_data[symbol] = info.get('volume_24h', 0)
        except Exception as e:
            print(f"⚠️ 读取成交量数据失败: {e}")
        
        # 重新筛选符合条件的合约
        new_monitor_pool = {}
        for symbol, info in latest_rates.items():
            try:
                funding_rate = abs(float(info.get('funding_rate', 0)))
                volume_24h = volume_data.get(symbol, 0)
                
                if funding_rate >= threshold and volume_24h >= min_volume:
                    # 构建完整的合约信息
                    new_monitor_pool[symbol] = {
                        'symbol': symbol,
                        'exchange': info.get('exchange', 'binance'),
                        'current_funding_rate': info.get('funding_rate', 0),
                        'next_funding_time': info.get('next_funding_time', ''),
                        'funding_interval': info.get('funding_interval', ''),
                        'mark_price': info.get('mark_price', 0),
                        'index_price': info.get('index_price', 0),
                        'volume_24h': volume_24h,
                        'last_updated': info.get('last_updated', datetime.now().isoformat())
                    }
            except (ValueError, TypeError) as e:
                print(f"⚠️ 筛选合约 {symbol} 时出错: {e}")
                continue
        
        # 获取旧的监控池
        old_monitor_pool = cache_data.get('monitor_pool', {})
        
        # 分析入池出池合约
        old_symbols = set(old_monitor_pool.keys())
        new_symbols = set(new_monitor_pool.keys())
        
        added_contracts = new_symbols - old_symbols
        removed_contracts = old_symbols - new_symbols
        
        # 发送入池出池通知
        if added_contracts or removed_contracts:
            try:
                from utils.notifier import send_telegram_message
                
                if added_contracts:
                    print(f"🔺 入池合约: {', '.join(added_contracts)}")
                    for symbol in added_contracts:
                        if symbol in new_monitor_pool:
                            info = new_monitor_pool[symbol]
                            funding_rate = info.get('current_funding_rate', 0)
                            mark_price = info.get('mark_price', 0)
                            volume_24h = info.get('volume_24h', 0)
                            
                            message = f"🔺 合约入池: {symbol}\n" \
                                     f"资金费率: {funding_rate:.4%}\n" \
                                     f"标记价格: ${mark_price:.4f}\n" \
                                     f"24h成交量: {volume_24h:,.0f}"
                            send_telegram_message(message)
                
                if removed_contracts:
                    print(f"🔻 出池合约: {', '.join(removed_contracts)}")
                    for symbol in removed_contracts:
                        if symbol in old_monitor_pool:
                            info = old_monitor_pool[symbol]
                            funding_rate = info.get('current_funding_rate', 0)
                            mark_price = info.get('mark_price', 0)
                            volume_24h = info.get('volume_24h', 0)
                            
                            message = f"🔻 合约出池: {symbol}\n" \
                                     f"资金费率: {funding_rate:.4%}\n" \
                                     f"标记价格: ${mark_price:.4f}\n" \
                                     f"24h成交量: {volume_24h:,.0f}"
                            send_telegram_message(message)
                
                print(f"📢 发送了 {len(added_contracts)} 个入池通知，{len(removed_contracts)} 个出池通知")
                
            except Exception as e:
                print(f"⚠️ 发送Telegram通知失败: {e}")
        
        # 更新缓存文件，添加最新资金费率数据和新的监控池
        updated_cache_data = {
            'cache_time': datetime.now().isoformat(),
            'contracts_by_interval': contracts_by_interval,
            'latest_rates': latest_rates,
            'monitor_pool': new_monitor_pool,
            'total_scanned': len(latest_rates),
            'intervals_found': list(contracts_by_interval.keys()),
            'pool_update_time': datetime.now().isoformat(),
            'pool_changes': {
                'added': list(added_contracts),
                'removed': list(removed_contracts),
                'total_added': len(added_contracts),
                'total_removed': len(removed_contracts)
            }
        }
        
        # 保存更新后的缓存
        with open("cache/all_funding_contracts_full.json", 'w', encoding='utf-8') as f:
            json.dump(updated_cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 监控池更新完成: 新增 {len(added_contracts)} 个，移除 {len(removed_contracts)} 个，当前池内 {len(new_monitor_pool)} 个")
        
        return {
            "status": "success",
            "contracts": latest_rates,
            "count": len(latest_rates),
            "real_time_count": real_time_count,
            "cached_count": cached_count,
            "processed_count": processed_count,
            "execution_time": execution_time,
            "intervals": list(all_contracts_data.get('contracts_by_interval', {}).keys()),
            "timestamp": datetime.now().isoformat(),
            "monitor_pool_updated": True,
            "pool_changes": {
                "added": list(added_contracts),
                "removed": list(removed_contracts),
                "total_added": len(added_contracts),
                "total_removed": len(removed_contracts)
            },
            "note": "包含最新实时资金费率数据，监控池已更新，入池出池通知已发送"
        }

    except Exception as e:
        print(f"❌ 获取最新资金费率异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取最新资金费率失败: {str(e)}")

def save_monitor_history_data(latest_rates):
    """保存监控合约的历史数据到JSON文件 - 优化版本：按合约分文件存储"""
    try:
        # 创建历史数据目录
        history_dir = "cache/monitor_history"
        os.makedirs(history_dir, exist_ok=True)
        
        # 获取当前监控池中的合约
        cache_file = "cache/all_funding_contracts_full.json"
        monitor_pool = {}
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                monitor_pool = cache_data.get('monitor_pool', {})
        
        # 只保存监控池中合约的历史数据
        current_time = datetime.now().isoformat()
        
        # 按合约分别保存历史数据
        for symbol in monitor_pool.keys():
            if symbol in latest_rates:
                contract_data = latest_rates[symbol]
                
                # 构建历史记录
                history_record = {
                    "timestamp": current_time,
                    "funding_rate": contract_data.get("funding_rate", 0),
                    "mark_price": contract_data.get("mark_price", 0),
                    "index_price": contract_data.get("index_price", 0),
                    "last_updated": contract_data.get("last_updated", current_time),
                    "data_source": contract_data.get("data_source", "unknown")
                }
                
                # 每个合约一个文件
                contract_file = os.path.join(history_dir, f"{symbol}_history.json")
                
                # 如果文件已存在，追加数据；否则创建新文件
                if os.path.exists(contract_file):
                    with open(contract_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if "history" not in existing_data:
                            existing_data["history"] = []
                        existing_data["history"].append(history_record)
                        
                        # 限制历史记录数量，避免文件过大（保留最近1000条记录）
                        if len(existing_data["history"]) > 1000:
                            existing_data["history"] = existing_data["history"][-1000:]
                else:
                    existing_data = {
                        "symbol": symbol,
                        "created_time": current_time,
                        "history": [history_record]
                    }
                
                with open(contract_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 监控合约历史数据已保存（按合约分文件）")
        
    except Exception as e:
        print(f"❌ 保存监控历史数据失败: {e}")
        raise


# 邮件通知测试端点
@app.post("/test/email")
def test_email_notification():
    """测试邮件通知功能"""
    try:
        # 发送测试邮件
        success = send_email_notification(
            "邮件通知测试", 
            "这是一封测试邮件，用于验证邮件配置是否正确。\n\n如果您收到这封邮件，说明邮件通知功能正常工作。"
        )
        
        if success:
            return {
                "status": "success",
                "message": "测试邮件发送成功",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "测试邮件发送失败",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试邮件发送失败: {str(e)}")


@app.post("/test/email/funding-warning")
def test_funding_rate_warning_email():
    """测试资金费率警告邮件"""
    try:
        from utils.email_sender import send_funding_rate_warning_email
        
        # 发送测试资金费率警告邮件
        success = send_funding_rate_warning_email(
            symbol="BTCUSDT",
            funding_rate=0.008,  # 0.8%
            mark_price=50000.0,
            volume_24h=10000000,
            next_funding_time="2024-01-01 08:00:00"
        )
        
        if success:
            return {
                "status": "success",
                "message": "资金费率警告测试邮件发送成功",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "资金费率警告测试邮件发送失败",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试资金费率警告邮件发送失败: {str(e)}")


@app.post("/test/email/pool-change")
def test_pool_change_email():
    """测试监控池变化邮件"""
    try:
        from utils.email_sender import send_pool_change_email
        
        # 发送测试监控池变化邮件
        success = send_pool_change_email(
            added_contracts=["BTCUSDT", "ETHUSDT"],
            removed_contracts=["DOGEUSDT"]
        )
        
        if success:
            return {
                "status": "success",
                "message": "监控池变化测试邮件发送成功",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "监控池变化测试邮件发送失败",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试监控池变化邮件发送失败: {str(e)}")

@app.get("/funding_monitor/history/{symbol}")
def get_monitor_contract_history(symbol: str, days: int = 7):
    """获取监控合约的历史数据 - 优化版本：直接从合约文件读取"""
    try:
        # 验证合约是否在监控池中
        cache_file = "cache/all_funding_contracts_full.json"
        if not os.path.exists(cache_file):
            return {
                "status": "error",
                "message": "监控池数据不存在",
                "timestamp": datetime.now().isoformat()
            }
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            monitor_pool = cache_data.get('monitor_pool', {})
        
        if symbol not in monitor_pool:
            return {
                "status": "error",
                "message": f"合约 {symbol} 不在监控池中",
                "timestamp": datetime.now().isoformat()
            }
        
        # 直接从合约历史文件读取数据
        history_dir = "cache/monitor_history"
        contract_file = os.path.join(history_dir, f"{symbol}_history.json")
        
        if not os.path.exists(contract_file):
            return {
                "status": "success",
                "symbol": symbol,
                "history": [],
                "count": 0,
                "days_requested": days,
                "message": "该合约暂无历史数据",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            with open(contract_file, 'r', encoding='utf-8') as f:
                contract_data = json.load(f)
                history_data = contract_data.get('history', [])
                
                # 如果需要按天数过滤，可以在这里添加过滤逻辑
                if days < 7:  # 如果请求的天数少于7天，可以过滤最近的数据
                    # 这里可以根据需要实现按天数过滤的逻辑
                    pass
                
                # 按时间排序（最新的在前）
                history_data.sort(key=lambda x: x['timestamp'], reverse=True)
                
                return {
                    "status": "success",
                    "symbol": symbol,
                    "history": history_data,
                    "count": len(history_data),
                    "days_requested": days,
                    "created_time": contract_data.get('created_time', ''),
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"⚠️ 读取合约历史文件 {contract_file} 失败: {e}")
            return {
                "status": "error",
                "message": f"读取合约历史数据失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        print(f"❌ 获取监控合约历史数据异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取监控合约历史数据失败: {str(e)}")


@app.get("/funding_monitor/history-summary")
def get_monitor_history_summary():
    """获取监控合约历史数据概览 - 优化版本：统计合约文件"""
    try:
        history_dir = "cache/monitor_history"
        if not os.path.exists(history_dir):
            return {
                "status": "success",
                "summary": {
                    "total_contracts": 0,
                    "contracts": [],
                    "total_records": 0
                },
                "timestamp": datetime.now().isoformat()
            }
        
        # 获取所有合约历史文件
        contract_files = []
        for filename in os.listdir(history_dir):
            if filename.endswith("_history.json"):
                contract_files.append(filename)
        
        contract_files.sort()  # 按文件名排序
        
        # 统计信息
        total_records = 0
        contracts_info = []
        
        for filename in contract_files:
            try:
                file_path = os.path.join(history_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    symbol = file_data.get('symbol', filename.replace('_history.json', ''))
                    history_list = file_data.get('history', [])
                    record_count = len(history_list)
                    total_records += record_count
                    
                    # 获取最新记录的时间
                    latest_time = ""
                    if history_list:
                        latest_record = max(history_list, key=lambda x: x.get('timestamp', ''))
                        latest_time = latest_record.get('timestamp', '')
                    
                    contracts_info.append({
                        "symbol": symbol,
                        "records": record_count,
                        "latest_time": latest_time,
                        "created_time": file_data.get('created_time', '')
                    })
            except Exception as e:
                print(f"⚠️ 读取合约历史文件 {filename} 失败: {e}")
                continue
        
        return {
            "status": "success",
            "summary": {
                "total_contracts": len(contract_files),
                "contracts": contracts_info,
                "total_records": total_records
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 获取监控历史概览异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取监控历史概览失败: {str(e)}")

@app.get("/funding_monitor/health")
def get_health_status():
    """获取系统健康状态"""
    try:
        funding_monitor = create_funding_monitor()
        health_status = funding_monitor.get_health_status()
        
        return {
            "status": "success",
            "health": health_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取健康状态异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取健康状态失败: {str(e)}")

@app.get("/funding_monitor/task-stats")
def get_task_stats():
    """获取任务统计信息"""
    try:
        funding_monitor = create_funding_monitor()
        task_stats = funding_monitor.get_task_stats()
        
        return {
            "status": "success",
            "task_stats": task_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取任务统计异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取任务统计失败: {str(e)}")

@app.get("/funding_monitor/config")
def get_monitor_config():
    """获取监控配置信息"""
    try:
        from config.settings import settings
        
        config_info = {
            "funding_rate_threshold": settings.FUNDING_RATE_THRESHOLD,
            "max_pool_size": settings.MAX_POOL_SIZE,
            "min_volume": settings.MIN_VOLUME,
            "cache_duration": settings.CACHE_DURATION,
            "update_interval": settings.UPDATE_INTERVAL,
            "contract_refresh_interval": settings.CONTRACT_REFRESH_INTERVAL,
            "funding_rate_check_interval": settings.FUNDING_RATE_CHECK_INTERVAL,
            "api_request_timeout": settings.API_REQUEST_TIMEOUT,
            "api_retry_count": settings.API_RETRY_COUNT,
            "api_retry_delay": settings.API_RETRY_DELAY,
            "cache_fallback_enabled": settings.CACHE_FALLBACK_ENABLED
        }
        
        return {
            "status": "success",
            "config": config_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取监控配置异常: {e}\n{traceback.format_exc()}")
@app.get("/funding_monitor/history-contracts")
def get_history_contracts():
    """获取历史入池合约列表"""
    try:
        import os
        import json
        from datetime import datetime
        
        history_dir = "cache/monitor_history"
        if not os.path.exists(history_dir):
            return {
                "status": "success",
                "contracts": [],
                "count": 0,
                "timestamp": datetime.now().isoformat(),
                "message": "历史数据目录不存在"
            }
        
        # 获取所有历史合约文件
        history_files = []
        for filename in os.listdir(history_dir):
            if filename.endswith("_history.json"):
                file_path = os.path.join(history_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    symbol = data.get('symbol', filename.replace('_history.json', ''))
                    created_time = data.get('created_time', '')
                    history_records = data.get('history', [])
                    
                    # 计算统计信息
                    total_records = len(history_records)
                    if history_records:
                        first_record = history_records[-1]  # 最早的记录
                        last_record = history_records[0]   # 最新的记录
                        
                        # 计算资金费率统计
                        funding_rates = [record.get('funding_rate', 0) for record in history_records]
                        max_funding_rate = max(funding_rates) if funding_rates else 0
                        min_funding_rate = min(funding_rates) if funding_rates else 0
                        avg_funding_rate = sum(funding_rates) / len(funding_rates) if funding_rates else 0
                        
                        # 计算价格统计
                        mark_prices = [record.get('mark_price', 0) for record in history_records]
                        max_price = max(mark_prices) if mark_prices else 0
                        min_price = min(mark_prices) if mark_prices else 0
                        avg_price = sum(mark_prices) / len(mark_prices) if mark_prices else 0
                        
                        # 计算时间范围
                        start_time = first_record.get('timestamp', '')
                        end_time = last_record.get('timestamp', '')
                        
                        history_files.append({
                            "symbol": symbol,
                            "created_time": created_time,
                            "total_records": total_records,
                            "start_time": start_time,
                            "end_time": end_time,
                            "max_funding_rate": max_funding_rate,
                            "min_funding_rate": min_funding_rate,
                            "avg_funding_rate": avg_funding_rate,
                            "max_price": max_price,
                            "min_price": min_price,
                            "avg_price": avg_price,
                            "last_funding_rate": last_record.get('funding_rate', 0),
                            "last_mark_price": last_record.get('mark_price', 0),
                            "last_updated": last_record.get('last_updated', '')
                        })
                    else:
                        history_files.append({
                            "symbol": symbol,
                            "created_time": created_time,
                            "total_records": 0,
                            "start_time": "",
                            "end_time": "",
                            "max_funding_rate": 0,
                            "min_funding_rate": 0,
                            "avg_funding_rate": 0,
                            "max_price": 0,
                            "min_price": 0,
                            "avg_price": 0,
                            "last_funding_rate": 0,
                            "last_mark_price": 0,
                            "last_updated": ""
                        })
                        
                except Exception as e:
                    print(f"⚠️ 读取历史文件 {filename} 失败: {e}")
                    continue
        
        # 按创建时间排序（最新的在前）
        history_files.sort(key=lambda x: x['created_time'], reverse=True)
        
        return {
            "status": "success",
            "contracts": history_files,
            "count": len(history_files),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取历史合约列表异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取历史合约列表失败: {str(e)}")

@app.get("/funding_monitor/history-contract/{symbol}")
def get_history_contract_detail(symbol: str):
    """获取指定合约的历史详情"""
    try:
        import os
        import json
        from datetime import datetime
        
        history_dir = "cache/monitor_history"
        contract_file = os.path.join(history_dir, f"{symbol}_history.json")
        
        if not os.path.exists(contract_file):
            raise HTTPException(status_code=404, detail=f"合约 {symbol} 的历史数据不存在")
        
        try:
            with open(contract_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            symbol_name = data.get('symbol', symbol)
            created_time = data.get('created_time', '')
            history_records = data.get('history', [])
            
            # 按时间排序（最新的在前）
            history_records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return {
                "status": "success",
                "symbol": symbol_name,
                "history": history_records,
                "total_records": len(history_records),
                "created_time": created_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ 读取合约历史文件 {contract_file} 失败: {e}")
            raise HTTPException(status_code=500, detail=f"读取合约历史数据失败: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取合约 {symbol} 历史详情异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取合约历史详情失败: {str(e)}")

@app.get("/funding_monitor/archive/sessions/{symbol}")
def get_contract_archive_sessions(symbol: str):
    """获取指定合约的所有归档会话"""
    try:
        from utils.archive_manager import archive_manager
        
        sessions = archive_manager.get_contract_sessions(symbol)
        
        return {
            "status": "success",
            "symbol": symbol,
            "sessions": sessions,
            "total_sessions": len(sessions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取合约 {symbol} 归档会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取归档会话失败: {str(e)}")

@app.get("/funding_monitor/archive/session/{session_id}")
def get_archive_session_detail(session_id: str):
    """获取指定会话的详细信息"""
    try:
        from utils.archive_manager import archive_manager
        
        session_detail = archive_manager.get_session_detail(session_id)
        
        if not session_detail:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        
        return {
            "status": "success",
            "session": session_detail,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取会话 {session_id} 详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")

@app.get("/funding_monitor/archive/statistics")
def get_archive_statistics():
    """获取归档统计信息"""
    try:
        from utils.archive_manager import archive_manager
        
        statistics = archive_manager.get_archive_statistics()
        
        return {
            "status": "success",
            "statistics": statistics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取归档统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取归档统计失败: {str(e)}")

@app.post("/funding_monitor/archive/cleanup")
def cleanup_old_archives(days_to_keep: int = 30):
    """清理旧的归档数据"""
    try:
        from utils.archive_manager import archive_manager
        
        archive_manager.cleanup_old_archives(days_to_keep)
        
        return {
            "status": "success",
            "message": f"已清理超过 {days_to_keep} 天的归档数据",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"清理归档数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理归档数据失败: {str(e)}")

@app.get("/funding_monitor/archive/contracts")
def get_archived_contracts():
    """获取所有有归档数据的合约列表"""
    try:
        from utils.archive_manager import archive_manager
        
        sessions_summary = archive_manager.sessions_summary
        contracts = []
        
        for symbol, sessions in sessions_summary.items():
            total_sessions = len(sessions)
            if sessions:
                latest_session = max(sessions, key=lambda x: x.get('created_time', ''))
                contracts.append({
                    "symbol": symbol,
                    "total_sessions": total_sessions,
                    "latest_session_id": latest_session.get('session_id', ''),
                    "latest_entry_time": latest_session.get('entry_time', ''),
                    "latest_exit_time": latest_session.get('exit_time', ''),
                    "latest_duration_minutes": latest_session.get('duration_minutes', 0)
                })
        
        # 按最新入池时间排序
        contracts.sort(key=lambda x: x['latest_entry_time'], reverse=True)
        
        return {
            "status": "success",
            "contracts": contracts,
            "total_contracts": len(contracts),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取归档合约列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取归档合约列表失败: {str(e)}")
