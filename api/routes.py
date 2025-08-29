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

# 数据库相关导入已移除，直接从settings.py读取配置
from strategies.factory import StrategyFactory
from strategies.funding_rate_arbitrage import FundingRateMonitor
# 内联数据读取功能，不再依赖data模块
from config.settings import settings
from utils.notifier import send_telegram_message, send_email_notification

# 在文件顶部导入os
import os

app = FastAPI(title="加密货币资金费率监控系统", version="1.0.0")

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

@app.get("/funding_monitor/latest-rates")
def get_latest_funding_rates():
    """获取所有结算周期合约的最新资金费率并保存到缓存"""
    try:
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        
        print("🔄 开始获取最新资金费率...")
        
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
        
        for interval, contracts in all_contracts_data['contracts_by_interval'].items():
            for symbol in contracts.keys():
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
                        

                    
                    # 添加延迟避免API限流
                    time.sleep(0.1)
                    
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
                    
                    
        print(f"📊 资金费率获取完成: 实时 {real_time_count} 个，缓存 {cached_count} 个，总计 {len(latest_rates)} 个")
        
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