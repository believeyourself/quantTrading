#!/usr/bin/env python3
"""
币安资金费率统一工具（基于 binance_interface）
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
import json
import requests
"""
注意: 为了提升在不同 Python 版本/环境下的可用性，本模块避免在导入阶段强依赖 pandas。
涉及 CSV 缓存的读写仅在运行到相应函数时尝试按需导入 pandas；
当环境缺失 pandas 时，将跳过缓存读写或返回空数据，以保证核心扫描与监控功能可用。
"""

class BinanceFunding:
    def __init__(self):
        try:
            from binance_interface.api import UM, CM
            self.um = UM()
            self.cm = CM()
            self.available = True
        except ImportError:
            print("❌ binance_interface 未安装，请先 pip install binance-interface")
            self.available = False

    def _parse_single(self, data: Any) -> dict:
        """自动从dict或list[dict]中取第一个dict"""
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0]
        return {}

    def get_current_funding(self, symbol: str, contract_type: str = "UM") -> Optional[dict]:
        if not self.available:
            print(f"❌ {symbol}: binance_interface 未安装或不可用")
            return None
        try:
            if contract_type == "UM":
                res = self.um.market.get_premiumIndex(symbol=symbol)
            else:
                res = self.cm.market.get_premiumIndex(symbol=symbol)
                
            if res and res.get('code') == 200:
                data = self._parse_single(res['data'])
                funding_rate = data.get('lastFundingRate', 0)
                mark_price = data.get('markPrice', 0)
                next_time = data.get('nextFundingTime')
                
                # 确保funding_rate是数值类型
                try:
                    funding_rate = float(funding_rate) if funding_rate is not None else 0.0
                except (ValueError, TypeError):
                    funding_rate = 0.0
                
                # 确保mark_price是数值类型
                try:
                    mark_price = float(mark_price) if mark_price is not None else 0.0
                except (ValueError, TypeError):
                    mark_price = 0.0
                
                result = {
                    'symbol': data.get('symbol', symbol),
                    'funding_rate': funding_rate,
                    'next_funding_time': next_time,
                    'mark_price': mark_price,
                    'index_price': data.get('indexPrice'),
                    'raw': data
                }
                
                # 格式化日志输出
                rate_percent = funding_rate * 100
                direction = "多头" if rate_percent > 0 else "空头" if rate_percent < 0 else "中性"
                print(f"    📊 {symbol}: API调用成功 | 费率: {rate_percent:+.4f}% ({direction}) | 价格: ${mark_price:.4f}")
                
                return result
            else:
                print(f"    ❌ {symbol}: API响应异常 | 状态码: {res.get('code') if res else 'None'} | 响应: {res}")
                return None
        except Exception as e:
            print(f"    ❌ {symbol}: API调用异常 | 错误: {e}")
            return None

    def get_funding_history(self, symbol: str, contract_type: str = "UM", limit: int = 10) -> List[dict]:
        if not self.available:
            return []
        try:
            if contract_type == "UM":
                res = self.um.market.get_fundingRate(symbol=symbol, limit=limit)
            else:
                res = self.cm.market.get_fundingRate(symbol=symbol, limit=limit)
            if res and res.get('code') == 200:
                data = res['data']
                return [
                    {
                        'symbol': d.get('symbol', symbol),
                        'funding_time': d.get('fundingTime'),
                        'funding_rate': d.get('fundingRate'),
                        'mark_price': d.get('markPrice'),
                        'raw': d
                    } for d in data
                ]
            return []
        except Exception as e:
            print(f"❌ 获取历史资金费率失败: {e}")
            return []

    def detect_funding_interval(self, symbol: str, contract_type: str = "UM") -> Optional[float]:
        """检测结算周期（小时）"""
        history = self.get_funding_history(symbol, contract_type, limit=2)
        if len(history) < 2:
            return None
        t1 = history[0]['funding_time']
        t2 = history[1]['funding_time']
        if t1 and t2:
            return abs(t1 - t2) / (1000 * 3600)
        return None

    def get_next_funding_time(self, symbol: str, contract_type: str = "UM") -> Optional[datetime]:
        info = self.get_current_funding(symbol, contract_type)
        if info and info['next_funding_time']:
            return datetime.fromtimestamp(info['next_funding_time']/1000)
        return None

    def get_24h_volume(self, symbol: str, contract_type: str = "UM") -> float:
        """获取24小时成交量"""
        if not self.available:
            return 0.0
        try:
            if contract_type == "UM":
                res = self.um.market.get_ticker_24hr(symbol=symbol)
            else:
                res = self.cm.market.get_ticker_24hr(symbol=symbol)
            if res and res.get('code') == 200:
                data = self._parse_single(res['data'])
                return float(data.get('volume', 0))
            return 0.0
        except Exception as e:
            print(f"❌ 获取24小时成交量失败: {e}")
            return 0.0

    def get_comprehensive_info(self, symbol: str, contract_type: str = "UM") -> dict:
        """获取合约综合信息"""
        try:
            # 获取当前资金费率
            current_funding = self.get_current_funding(symbol, contract_type)
            if not current_funding:
                return {}
            
            # 获取24小时成交量
            volume_24h = self.get_24h_volume(symbol, contract_type)
            
            # 检测结算周期
            funding_interval = self.detect_funding_interval(symbol, contract_type)
            
            # 获取下次结算时间
            next_funding_time = self.get_next_funding_time(symbol, contract_type)
            next_funding_str = next_funding_time.strftime('%Y-%m-%d %H:%M:%S') if next_funding_time else ""
            
            return {
                'symbol': symbol,
                'contract_type': contract_type,
                'current_funding_rate': current_funding.get('funding_rate', 0),
                'next_funding_time': next_funding_str,
                'funding_interval_hours': funding_interval,
                'mark_price': current_funding.get('mark_price', 0),
                'index_price': current_funding.get('index_price', 0),
                'volume_24h': volume_24h,
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ 获取合约综合信息失败: {e}")
            return {}

    def scan_all_funding_contracts(self, contract_type="UM", force_refresh=False):
        """扫描所有结算周期的合约并按周期分类缓存"""
        cache_file = "cache/all_funding_contracts_full.json"
        cache_duration = 3600  # 1小时缓存
        
        # 检查缓存是否有效
        if not force_refresh and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 检查缓存时间
                cache_time = datetime.fromisoformat(cache_data.get('cache_time', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < cache_duration:
                    print(f"📋 使用缓存的所有结算周期合约")
                    for interval, contracts in cache_data.get('contracts_by_interval', {}).items():
                        print(f"  {interval}: {len(contracts)}个合约")
                    return cache_data.get('contracts_by_interval', {})
                else:
                    print("⏰ 缓存已过期，重新扫描...")
            except Exception as e:
                print(f"⚠️ 读取缓存失败: {e}")
        
        print("🔍 开始扫描所有结算周期合约...")
        
        # 获取所有合约信息
        try:
            info = self.um.market.get_exchangeInfo()
            if isinstance(info, dict) and 'data' in info:
                symbols = info.get('data', {}).get('symbols', [])
            else:
                symbols = info.get('symbols', [])
            
            # 筛选永续合约
            perpetual_symbols = []
            for s in symbols:
                if s.get('contractType') == 'PERPETUAL':
                    perpetual_symbols.append(s['symbol'])
            
            print(f"📊 获取到 {len(perpetual_symbols)} 个永续合约")
            
            # 按结算周期分类合约
            contracts_by_interval = {}
            
            for i, symbol in enumerate(perpetual_symbols):
                try:
                    # 使用detect_funding_interval方法检测结算周期
                    interval = self.detect_funding_interval(symbol, contract_type)
                    
                    if interval:
                        # 将结算周期分类到最接近的标准间隔
                        if abs(interval - 1.0) < 0.1:
                            interval_key = "1h"
                        elif abs(interval - 8.0) < 0.1:
                            interval_key = "8h"
                        elif abs(interval - 4.0) < 0.1:
                            interval_key = "4h"
                        elif abs(interval - 2.0) < 0.1:
                            interval_key = "2h"
                        elif abs(interval - 12.0) < 0.1:
                            interval_key = "12h"
                        elif abs(interval - 24.0) < 0.1:
                            interval_key = "24h"
                        else:
                            # 其他间隔，按小时四舍五入
                            interval_key = f"{round(interval)}h"
                        
                        # 获取合约详细信息
                        contract_info = self.get_comprehensive_info(symbol, contract_type)
                        if contract_info:
                            if interval_key not in contracts_by_interval:
                                contracts_by_interval[interval_key] = {}
                            contracts_by_interval[interval_key][symbol] = contract_info
                            print(f"  ✅ {symbol}: {interval_key}结算周期 (检测到: {interval:.2f}小时)")
                    else:
                        print(f"  ⚠️ {symbol}: 无法检测结算周期")
                    
                    # 限流控制
                    if (i + 1) % 50 == 0:
                        print(f"    进度: {i + 1}/{len(perpetual_symbols)}")
                        time.sleep(1)
                    else:
                        time.sleep(0.1)
                        
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        print(f"  ⚠️ {symbol}: 限流，跳过")
                        time.sleep(2)
                    else:
                        print(f"  ❌ {symbol}: 检测失败 - {e}")
                    continue
            
            # 保存主缓存文件
            cache_data = {
                'cache_time': datetime.now().isoformat(),
                'contracts_by_interval': contracts_by_interval,
                'total_scanned': len(perpetual_symbols),
                'intervals_found': list(contracts_by_interval.keys())
            }
            
            os.makedirs("cache", exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # 为每个结算周期创建单独的缓存文件
            for interval_key, contracts in contracts_by_interval.items():
                interval_cache_file = f"cache/{interval_key}_funding_contracts_full.json"
                interval_cache_data = {
                    'cache_time': datetime.now().isoformat(),
                    'contracts': contracts,
                    'interval': interval_key,
                    'contract_count': len(contracts)
                }
                
                with open(interval_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(interval_cache_data, f, ensure_ascii=False, indent=2)
                
                print(f"💾 {interval_key}结算周期合约已缓存到 {interval_cache_file} ({len(contracts)}个)")
            
            print(f"✅ 所有结算周期合约扫描完成")
            for interval_key, contracts in contracts_by_interval.items():
                print(f"  {interval_key}: {len(contracts)}个合约")
            print(f"💾 主缓存已保存到 {cache_file}")
            
            return contracts_by_interval
            
        except Exception as e:
            print(f"❌ 扫描所有结算周期合约失败: {e}")
            return {}

    def scan_1h_funding_contracts(self, contract_type="UM", force_refresh=False):
        """扫描1小时结算周期的合约并缓存（保持向后兼容）"""
        # 调用新的综合扫描方法
        all_contracts = self.scan_all_funding_contracts(contract_type, force_refresh)
        return all_contracts.get("1h", {})

    def get_contracts_by_interval_from_cache(self, interval: str = "1h", tg_notifier=None):
        """从缓存获取指定结算周期的合约"""
        cache_file = f"cache/{interval}_funding_contracts_full.json"
        cache_duration = 3600  # 1小时缓存有效期
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                cache_time = datetime.fromisoformat(cache_data.get('cache_time', '2000-01-01'))
                cache_age = (datetime.now() - cache_time).total_seconds()
                
                print(f"📋 {interval}结算周期缓存时间: {cache_age:.0f}秒前")
                print(f"📊 {interval}结算周期合约: {len(cache_data.get('contracts', {}))}个")
                
                # 检查缓存是否过期
                if cache_age > cache_duration:
                    msg = f"⚠️ {interval}结算周期合约缓存已过期 {cache_age/3600:.2f} 小时，定时任务可能未正常更新！"
                    print(msg)
                    if tg_notifier:
                        try:
                            tg_notifier(msg)
                        except Exception as e:
                            print(f"❌ 发送Telegram通知失败: {e}")
                
                return cache_data.get('contracts', {})
            except Exception as e:
                print(f"⚠️ 读取{interval}结算周期缓存失败: {e}")
                if tg_notifier:
                    try:
                        tg_notifier(f"❌ 读取{interval}结算周期合约缓存失败: {e}")
                    except Exception as notify_e:
                        print(f"❌ 发送Telegram通知失败: {notify_e}")
        
        return {}

    def get_1h_contracts_from_cache(self, tg_notifier=None):
        """从缓存获取1小时结算周期合约（保持向后兼容）"""
        return self.get_contracts_by_interval_from_cache("1h", tg_notifier)

    def get_all_intervals_from_cache(self):
        """获取所有结算周期的合约缓存概览"""
        cache_file = "cache/all_funding_contracts_full.json"
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                return {
                    'cache_time': cache_data.get('cache_time'),
                    'intervals': cache_data.get('intervals_found', []),
                    'total_contracts': sum(len(contracts) for contracts in cache_data.get('contracts_by_interval', {}).values()),
                    'contracts_by_interval': cache_data.get('contracts_by_interval', {})
                }
            except Exception as e:
                print(f"⚠️ 读取所有结算周期缓存失败: {e}")
        
        return {}

    def update_all_contracts_cache(self):
        """更新所有结算周期合约缓存"""
        print("🔄 更新所有结算周期合约缓存...")
        return self.scan_all_funding_contracts(force_refresh=True)

    def update_1h_contracts_cache(self):
        """更新1小时结算周期合约缓存（保持向后兼容）"""
        print("🔄 更新1小时结算周期合约缓存...")
        return self.scan_1h_funding_contracts(force_refresh=True)

    def save_contracts(self, contracts: Dict[str, dict], filename: str = "1h_funding_contracts.json"):
        os.makedirs("cache", exist_ok=True)
        path = os.path.join("cache", filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(contracts, f, ensure_ascii=False, indent=2)
        print(f"✅ 合约信息已保存到: {path}")

    def load_contracts(self, filename: str = "1h_funding_contracts.json") -> Dict[str, dict]:
        path = os.path.join("cache", filename)
        if not os.path.exists(path):
            print(f"⚠️ 文件不存在: {path}")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

def get_all_funding_rates():
    """批量获取所有合约的资金费率等信息，返回symbol到资金费率等信息的映射"""
    from config.proxy_settings import get_proxy_dict
    
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    proxies = get_proxy_dict()
    
    try:
        resp = requests.get(url, proxies=proxies, timeout=30, verify=False)
        resp.raise_for_status()
        data = resp.json()
        # 构建symbol到资金费率等信息的映射
        data_map = {item['symbol']: item for item in data}
        return data_map
    except Exception as e:
        print(f"❌ 获取资金费率失败: {e}")
        # 抛出异常，让调用者知道API请求失败
        raise Exception(f"获取资金费率失败: {e}")

def get_all_24h_volumes():
    """批量获取所有合约的24小时成交额（USDT计价），返回symbol到成交额的映射"""
    from config.proxy_settings import get_proxy_dict
    
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    proxies = get_proxy_dict()
    
    try:
        resp = requests.get(url, proxies=proxies, timeout=30, verify=False)
        resp.raise_for_status()
        data = resp.json()
        return {item['symbol']: float(item['quoteVolume']) for item in data}
    except Exception as e:
        print(f"❌ 获取24小时成交量失败: {e}")
        # 抛出异常，让调用者知道API请求失败
        raise Exception(f"获取24小时成交量失败: {e}")

def get_funding_history(symbol, contract_type="UM", limit=1000):
    cache_dir = "data/funding"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = f"{cache_dir}/{symbol}_funding.csv"
    # 优先查本地缓存（按需导入 pandas）
    try:
        import pandas as pd  # 按需导入
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=['funding_time'])
            return df.to_dict('records')
    except Exception:
        # 缺少 pandas 或读取失败则跳过缓存
        pass
    # 否则请求API
    try:
        from binance_interface.api import UM, CM
        um = UM()
        cm = CM()
        if contract_type == "UM":
            res = um.market.get_fundingRate(symbol=symbol, limit=limit)
        else:
            res = cm.market.get_fundingRate(symbol=symbol, limit=limit)
        if res and res.get('code') == 200:
            data = res['data']
            result = [
                {
                    'symbol': d.get('symbol', symbol),
                    'funding_time': d.get('fundingTime'),
                    'funding_rate': d.get('fundingRate'),
                    'mark_price': d.get('markPrice'),
                    'raw': d
                } for d in data
            ]
            # 保存到本地（按需导入 pandas）
            try:
                import pandas as pd  # 按需导入
                df = pd.DataFrame(result)
                df['funding_time'] = pd.to_datetime(df['funding_time'], unit='ms')
                df.to_csv(cache_file, index=False)
            except Exception:
                # 环境缺少 pandas 或写入失败，忽略缓存
                pass
            return result
        return []
    except Exception as e:
        print(f"❌ 获取历史资金费率失败: {e}")
        return []

def get_klines(symbol, interval, start_time, end_time):
    cache_dir = "data/history"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = f"{cache_dir}/{symbol}_{interval}.csv"
    # 优先查本地缓存（按需导入 pandas）
    try:
        import pandas as pd  # 按需导入
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=['timestamp'], index_col='timestamp')
            # 过滤时间区间
            df = df[(df.index >= pd.to_datetime(start_time, unit='ms')) & (df.index <= pd.to_datetime(end_time, unit='ms'))]
            if not df.empty:
                return df
    except Exception:
        # 缺少 pandas 则跳过缓存读取
        pass
    # 否则请求API
    try:
        from binance_interface.api import UM
        um = UM()
        res = um.market.get_klines(symbol=symbol, interval=interval, startTime=start_time, endTime=end_time)
        if res and res.get('code') == 200:
            try:
                import pandas as pd  # 按需导入
                data = res['data']
                df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume','close_time','quote_asset_volume','number_of_trades','taker_buy_base','taker_buy_quote','ignore'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.rename(columns={'open':'open_price','high':'high_price','low':'low_price','close':'close_price'})
                df = df[['timestamp','open_price','high_price','low_price','close_price','volume']]
                df.set_index('timestamp', inplace=True)
                # 保存到本地
                df.to_csv(cache_file)
                return df
            except Exception:
                # 无 pandas 时返回空结果
                return []
        return pd.DataFrame()
    except Exception as e:
        print(f'get_klines异常: {e}')
        try:
            import pandas as pd
            return pd.DataFrame()
        except Exception:
            return []

def load_cached_funding_rates():
    """从缓存加载资金费率数据"""
    try:
        # 尝试从多个缓存文件加载数据
        cache_files = [
            "cache/funding_rate_contracts.json",
            "cache/1h_funding_contracts_full.json",
            "cache/2h_funding_contracts_full.json",
            "cache/4h_funding_contracts_full.json",
            "cache/8h_funding_contracts_full.json"
        ]
        
        result = {}
        
        for cache_file in cache_files:
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                        
                        # 处理不同的缓存格式
                        if 'contracts' in cached_data:
                            # 新格式：包含contracts字段
                            contracts = cached_data['contracts']
                            for symbol, data in contracts.items():
                                if isinstance(data, dict):
                                    result[symbol] = {
                                        'symbol': symbol,
                                        'lastFundingRate': data.get('current_funding_rate', '0'),
                                        'markPrice': data.get('mark_price', '0'),
                                        'indexPrice': data.get('index_price', '0')
                                    }
                        else:
                            # 旧格式：直接是合约数据
                            for symbol, data in cached_data.items():
                                if isinstance(data, dict) and 'funding_rate' in data:
                                    result[symbol] = {
                                        'symbol': symbol,
                                        'lastFundingRate': data['funding_rate'],
                                        'markPrice': data.get('mark_price', '0'),
                                        'indexPrice': data.get('index_price', '0')
                                    }
                                    
                except Exception as e:
                    print(f"⚠️ 读取缓存文件 {cache_file} 失败: {e}")
                    continue
        
        if result:
            print(f"📋 从缓存加载了 {len(result)} 个合约的资金费率数据")
            # 标记数据来源为缓存
            result['_from_cache'] = True
        else:
            print("⚠️ 所有缓存文件都无法读取或为空")
            
        return result
        
    except Exception as e:
        print(f"❌ 加载缓存资金费率失败: {e}")
        return {}

def load_cached_24h_volumes():
    """从缓存加载24小时成交量数据"""
    try:
        # 尝试从多个缓存文件加载数据
        cache_files = [
            "cache/funding_rate_contracts.json",
            "cache/1h_funding_contracts_full.json",
            "cache/2h_funding_contracts_full.json",
            "cache/4h_funding_contracts_full.json",
            "cache/8h_funding_contracts_full.json"
        ]
        
        result = {}
        
        for cache_file in cache_files:
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                        
                        # 处理不同的缓存格式
                        if 'contracts' in cached_data:
                            # 新格式：包含contracts字段
                            contracts = cached_data['contracts']
                            for symbol, data in contracts.items():
                                if isinstance(data, dict) and 'volume_24h' in data:
                                    try:
                                        result[symbol] = float(data['volume_24h'])
                                    except (ValueError, TypeError):
                                        continue
                        else:
                            # 旧格式：直接是合约数据
                            for symbol, data in cached_data.items():
                                if isinstance(data, dict) and 'volume_24h' in data:
                                    try:
                                        result[symbol] = float(data['volume_24h'])
                                    except (ValueError, TypeError):
                                        continue
                                    
                except Exception as e:
                    print(f"⚠️ 读取缓存文件 {cache_file} 失败: {e}")
                    continue
        
        if result:
            print(f"📋 从缓存加载了 {len(result)} 个合约的24小时成交量数据")
            # 标记数据来源为缓存
            result['_from_cache'] = True
        else:
            print("⚠️ 所有缓存文件都无法读取或为空")
            
        return result
        
    except Exception as e:
        print(f"❌ 加载缓存24小时成交量失败: {e}")
        return {}

# 测试
if __name__ == "__main__":
    bf = BinanceFunding()
    print(bf.get_comprehensive_info("BTCUSDT", "UM"))
    print(bf.get_comprehensive_info("BTCUSD_PERP", "CM")) 