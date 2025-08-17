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

from utils.models import Strategy
from utils.database import SessionLocal, get_db
from strategies.factory import StrategyFactory
from strategies.funding_rate_arbitrage import FundingRateMonitor
# 内联数据读取功能，不再依赖data模块
from config.settings import settings
from utils.notifier import send_telegram_message

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
            cache_file = "cache/1h_funding_contracts_full.json"
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    contracts = data.get('contracts', {})
                    symbols = list(contracts.keys())
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
        print("🔄 开始刷新备选合约池...")
        
        # 使用现成的方法获取币安数据
        from utils.binance_funding import get_all_funding_rates, get_all_24h_volumes
        
        try:
            print("📡 正在从币安API获取最新资金费率数据...")
            funding_rates = get_all_funding_rates()
            print(f"✅ 获取到 {len(funding_rates)} 个合约的资金费率")
        except Exception as e:
            error_msg = f"获取资金费率数据失败: {str(e)}"
            print(f"❌ {error_msg}")
            # API失败时直接抛出异常，不回退到缓存
            raise HTTPException(status_code=500, detail=error_msg)
        
        try:
            print("📡 正在从币安API获取最新成交量数据...")
            volumes = get_all_24h_volumes()
            print(f"✅ 获取到 {len(volumes)} 个合约的成交量")
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
                    
                    print(f"  📊 {symbol}: 检测到结算周期 {funding_interval_hours}h")
                else:
                    print(f"  ❌ {symbol}: 无法检测结算周期，跳过该合约")
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
        
        # 保存到监控合约缓存
        monitor_cache = {
            'cache_time': datetime.now().isoformat(),
            'contracts': filtered_contracts,
            'count': len(filtered_contracts),
            'threshold': threshold,
            'min_volume': min_volume
        }
        
        os.makedirs("cache", exist_ok=True)
        with open("cache/funding_rate_contracts.json", 'w', encoding='utf-8') as f:
            json.dump(monitor_cache, f, ensure_ascii=False, indent=2)
        
        # 为每个结算周期创建对应的缓存文件
        intervals_found = []
        total_contracts = 0
        
        for interval, contracts in contracts_by_interval.items():
            if contracts:  # 只保存有合约的结算周期
                intervals_found.append(interval)
                total_contracts += len(contracts)
                
                # 保存到对应结算周期的缓存文件
                interval_cache_data = {
                    'cache_time': datetime.now().isoformat(),
                    'contracts': contracts,
                    'interval': interval,
                    'contract_count': len(contracts)
                }
                
                cache_filename = f"cache/{interval}_funding_contracts_full.json"
                with open(cache_filename, 'w', encoding='utf-8') as f:
                    json.dump(interval_cache_data, f, ensure_ascii=False, indent=2)
                
                print(f"📊 {interval}结算周期合约: {len(contracts)}个")
        
        # 保存到主缓存
        main_cache_data = {
            'cache_time': datetime.now().isoformat(),
            'contracts_by_interval': contracts_by_interval,
            'total_scanned': len(funding_rates),
            'intervals_found': intervals_found
        }
        
        with open("cache/all_funding_contracts_full.json", 'w', encoding='utf-8') as f:
            json.dump(main_cache_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 监控合约池更新完成，共 {len(filtered_contracts)} 个符合条件合约")
        print(f"📊 总计: {total_contracts}个合约，结算周期: {', '.join(intervals_found)}")
        
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
        # 直接从缓存文件读取监控合约数据
        cache_file = "cache/funding_rate_contracts.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # 检查新的缓存格式
            if 'contracts' in cached_data:
                # 新格式：{"contracts": {...}, "count": ..., ...}
                contracts = cached_data.get('contracts', {})
            else:
                # 旧格式：直接是合约数据
                contracts = cached_data
            
            # 转换为列表格式，包含合约详细信息
            contracts_list = []
            for symbol, info in contracts.items():
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
            
            print(f"📋 从缓存文件加载了 {len(contracts_list)} 个监控合约")
            return {
                "status": "success",
                "contracts": contracts_list,
                "count": len(contracts_list),
                "timestamp": datetime.now().isoformat()
            }
        else:
            print("📋 监控合约缓存文件不存在")
            return {
                "status": "success",
                "contracts": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        print(f"获取合约池异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取合约池失败: {str(e)}")

@app.get("/funding_monitor/candidates")
def get_funding_candidates():
    """获取备选合约池"""
    try:
        # 直接从缓存文件读取备选合约数据
        cache_file = "cache/funding_rate_contracts.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            print(f"📋 从缓存文件加载了 {len(cached_data)} 个备选合约")
            return {
                "status": "success",
                "contracts": cached_data,
                "count": len(cached_data),
                "timestamp": datetime.now().isoformat()
            }
        else:
            print("📋 备选合约缓存文件不存在")
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
        
        print(f"📊 从缓存获取到 {len(all_contracts_data.get('contracts_by_interval', {}))} 个结算周期的合约数据")
        
        # 获取最新资金费率
        latest_rates = {}
        real_time_count = 0
        cached_count = 0
        
        for interval, contracts in all_contracts_data['contracts_by_interval'].items():
            print(f"\n🔍 处理 {interval} 结算周期合约，共 {len(contracts)} 个...")
            
            for symbol in contracts.keys():
                try:
                    print(f"  📈 获取 {symbol} 最新资金费率...")
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
                        
                        # 格式化资金费率显示
                        rate_percent = funding_rate * 100
                        direction = "多头" if funding_rate > 0 else "空头" if funding_rate < 0 else "中性"
                        print(f"    ✅ {symbol}: {rate_percent:+.4f}% ({direction}) | 价格: ${mark_price:.4f} | 实时数据")
                        
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
                        
                        # 格式化资金费率显示
                        rate_percent = funding_rate * 100
                        direction = "多头" if funding_rate > 0 else "空头" if funding_rate < 0 else "中性"
                        print(f"    📋 {symbol}: {rate_percent:+.4f}% ({direction}) | 价格: ${mark_price:.4f} | 缓存数据")
                    
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
                    
                    # 格式化资金费率显示
                    rate_percent = funding_rate * 100
                    direction = "多头" if funding_rate > 0 else "空头" if funding_rate < 0 else "中性"
                    print(f"    📋 {symbol}: {rate_percent:+.4f}% ({direction}) | 价格: ${mark_price:.4f} | 缓存数据(错误回退)")
        
        print(f"\n📊 资金费率获取完成:")
        print(f"  📈 实时数据: {real_time_count} 个合约")
        print(f"  📋 缓存数据: {cached_count} 个合约")
        print(f"  📊 总计: {len(latest_rates)} 个合约")
        
        # 统计资金费率分布
        positive_rates = [info['funding_rate'] for info in latest_rates.values() if info['funding_rate'] > 0]
        negative_rates = [info['funding_rate'] for info in latest_rates.values() if info['funding_rate'] < 0]
        zero_rates = [info['funding_rate'] for info in latest_rates.values() if info['funding_rate'] == 0]
        
        if positive_rates:
            max_positive = max(positive_rates) * 100
            print(f"  🟢 最高正费率: {max_positive:.4f}%")
        if negative_rates:
            min_negative = min(negative_rates) * 100
            print(f"  🔴 最低负费率: {min_negative:.4f}%")
        if zero_rates:
            print(f"  ⚪ 零费率合约: {len(zero_rates)} 个")
        
        # 保存到缓存文件
        try:
            from utils.funding_rate_utils import FundingRateUtils
            
            cache_data = {
                'cache_time': datetime.now().isoformat(),
                'contracts': latest_rates,
                'count': len(latest_rates),
                'real_time_count': real_time_count,
                'cached_count': cached_count,
                'intervals': list(all_contracts_data.get('contracts_by_interval', {}).keys()),
                'note': '最新资金费率缓存数据'
            }
            
            cache_file = "cache/latest_funding_rates.json"
            success = FundingRateUtils.save_cache_data(cache_data, cache_file, "最新资金费率数据")
            
            if success:
                print(f"💾 最新资金费率数据已保存到缓存: {cache_file}")
            else:
                print(f"⚠️ 保存缓存失败")
            
        except ImportError:
            # 后备方案：直接保存
            try:
                cache_data = {
                    'cache_time': datetime.now().isoformat(),
                    'contracts': latest_rates,
                    'count': len(latest_rates),
                    'real_time_count': real_time_count,
                    'cached_count': cached_count,
                    'intervals': list(all_contracts_data.get('contracts_by_interval', {}).keys()),
                    'note': '最新资金费率缓存数据'
                }
                
                os.makedirs("cache", exist_ok=True)
                cache_file = "cache/latest_funding_rates.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                print(f"💾 最新资金费率数据已保存到缓存: {cache_file}")
                
            except Exception as e:
                print(f"⚠️ 保存缓存失败: {e}")
        except Exception as e:
            print(f"⚠️ 保存缓存失败: {e}")
        
        return {
            "status": "success",
            "contracts": latest_rates,
            "count": len(latest_rates),
            "real_time_count": real_time_count,
            "cached_count": cached_count,
            "intervals": list(all_contracts_data.get('contracts_by_interval', {}).keys()),
            "timestamp": datetime.now().isoformat(),
            "note": "包含最新实时资金费率数据，已保存到缓存"
        }

    except Exception as e:
        print(f"❌ 获取最新资金费率异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取最新资金费率失败: {str(e)}")