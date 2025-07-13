#!/usr/bin/env python3
"""
币安资金费率统一工具（基于 binance_interface）
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
import json

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
            return None
        try:
            if contract_type == "UM":
                res = self.um.market.get_premiumIndex(symbol=symbol)
            else:
                res = self.cm.market.get_premiumIndex(symbol=symbol)
            if res and res.get('code') == 200:
                data = self._parse_single(res['data'])
                return {
                    'symbol': data.get('symbol', symbol),
                    'funding_rate': data.get('lastFundingRate'),
                    'next_funding_time': data.get('nextFundingTime'),
                    'mark_price': data.get('markPrice'),
                    'index_price': data.get('indexPrice'),
                    'raw': data
                }
            return None
        except Exception as e:
            print(f"❌ 获取当前资金费率失败: {e}")
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

    def get_comprehensive_info(self, symbol: str, contract_type: str = "UM") -> dict:
        current = self.get_current_funding(symbol, contract_type)
        history = self.get_funding_history(symbol, contract_type, limit=5)
        interval = self.detect_funding_interval(symbol, contract_type)
        next_time = self.get_next_funding_time(symbol, contract_type)
        return {
            'symbol': symbol,
            'contract_type': contract_type,
            'current_funding_rate': current['funding_rate'] if current else None,
            'funding_interval_hours': interval,
            'next_funding_time': next_time.isoformat() if next_time else None,
            'history_rates': history,
            'last_updated': datetime.now().isoformat()
        }

    def scan_1h_funding_contracts(self, contract_type="UM", force_refresh=False):
        """扫描1小时结算周期的合约并缓存"""
        cache_file = "cache/1h_funding_contracts_full.json"
        cache_duration = 3600  # 1小时缓存
        
        # 检查缓存是否有效
        if not force_refresh and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 检查缓存时间
                cache_time = datetime.fromisoformat(cache_data.get('cache_time', '2000-01-01'))
                if (datetime.now() - cache_time).total_seconds() < cache_duration:
                    print(f"📋 使用缓存的1小时结算合约 ({len(cache_data.get('contracts', {}))}个)")
                    return cache_data.get('contracts', {})
                else:
                    print("⏰ 缓存已过期，重新扫描...")
            except Exception as e:
                print(f"⚠️ 读取缓存失败: {e}")
        
        print("🔍 开始扫描1小时结算周期合约...")
        
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
            
            # 检测1小时结算周期合约
            h1_contracts = {}
            
            for i, symbol in enumerate(perpetual_symbols):
                try:
                    # 使用detect_funding_interval方法检测结算周期
                    interval = self.detect_funding_interval(symbol, contract_type)
                    
                    if interval:
                        # 检查是否为1小时结算周期（允许0.1小时的误差）
                        if abs(interval - 1.0) < 0.1:
                            # 获取合约详细信息
                            contract_info = self.get_comprehensive_info(symbol, contract_type)
                            if contract_info:
                                h1_contracts[symbol] = contract_info
                                print(f"  ✅ {symbol}: 1小时结算周期 (检测到: {interval:.2f}小时)")
                        elif abs(interval - 8.0) < 0.1:
                            print(f"  📊 {symbol}: 8小时结算周期 (检测到: {interval:.2f}小时)")
                        else:
                            print(f"  📊 {symbol}: {interval:.1f}小时结算周期")
                    else:
                        # 如果detect_funding_interval失败，尝试其他方法
                        current_info = self.get_current_funding(symbol, contract_type)
                        if current_info and current_info.get('next_funding_time'):
                            next_time = datetime.fromtimestamp(current_info['next_funding_time'] / 1000)
                            now = datetime.now()
                            time_diff = (next_time - now).total_seconds()
                            
                            # 如果距离下次结算时间在1小时内，可能是1小时结算
                            if 0 <= time_diff <= 3600:
                                # 再次尝试获取历史数据来确认
                                history = self.get_funding_history(symbol, contract_type, limit=3)
                                if len(history) >= 2:
                                    # 计算最近两次结算的时间间隔
                                    t1 = history[0]['funding_time']
                                    t2 = history[1]['funding_time']
                                    if t1 and t2:
                                        calc_interval = abs(t1 - t2) / (1000 * 3600)
                                        if abs(calc_interval - 1.0) < 0.1:
                                            contract_info = self.get_comprehensive_info(symbol, contract_type)
                                            if contract_info:
                                                h1_contracts[symbol] = contract_info
                                                print(f"  ✅ {symbol}: 1小时结算周期 (备用检测: {calc_interval:.2f}小时)")
                    
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
            
            # 保存缓存
            cache_data = {
                'cache_time': datetime.now().isoformat(),
                'contracts': h1_contracts,
                'total_scanned': len(perpetual_symbols),
                'h1_contracts_count': len(h1_contracts)
            }
            
            os.makedirs("cache", exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 1小时结算合约扫描完成，找到 {len(h1_contracts)} 个合约")
            print(f"💾 已缓存到 {cache_file}")
            
            return h1_contracts
            
        except Exception as e:
            print(f"❌ 扫描1小时结算合约失败: {e}")
            return {}
    
    def get_1h_contracts_from_cache(self, tg_notifier=None):
        """从缓存获取1小时结算周期合约，只读取不刷新"""
        cache_file = "cache/1h_funding_contracts_full.json"
        cache_duration = 3600  # 1小时缓存有效期
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                cache_time = datetime.fromisoformat(cache_data.get('cache_time', '2000-01-01'))
                cache_age = (datetime.now() - cache_time).total_seconds()
                
                print(f"📋 缓存时间: {cache_age:.0f}秒前")
                print(f"📊 1小时结算合约: {len(cache_data.get('contracts', {}))}个")
                
                # 检查缓存是否过期
                if cache_age > cache_duration:
                    msg = f"⚠️ 1小时结算合约缓存已过期 {cache_age/3600:.2f} 小时，定时任务可能未正常更新！"
                    print(msg)
                    if tg_notifier:
                        try:
                            tg_notifier(msg)
                        except Exception as e:
                            print(f"❌ 发送Telegram通知失败: {e}")
                
                return cache_data.get('contracts', {})
            except Exception as e:
                print(f"⚠️ 读取缓存失败: {e}")
                if tg_notifier:
                    try:
                        tg_notifier(f"❌ 读取1小时结算合约缓存失败: {e}")
                    except Exception as notify_e:
                        print(f"❌ 发送Telegram通知失败: {notify_e}")
        
        return {}
    
    def update_1h_contracts_cache(self):
        """更新1小时结算周期合约缓存"""
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

# 测试
if __name__ == "__main__":
    bf = BinanceFunding()
    print(bf.get_comprehensive_info("BTCUSDT", "UM"))
    print(bf.get_comprehensive_info("BTCUSD_PERP", "CM")) 