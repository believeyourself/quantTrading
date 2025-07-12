import pandas as pd
import numpy as np
import time
from typing import Dict, List, Set
from datetime import datetime, timedelta
from .base import BaseStrategy, Signal
from utils.notifier import send_telegram_message
from config.proxy_settings import get_proxy_dict, test_proxy_connection
import ccxt

class FundingRateArbitrageStrategy(BaseStrategy):
    """资金费率套利策略"""
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            'funding_rate_threshold': 0.005,  # 0.5% 阈值
            'max_positions': 10,              # 最大持仓数量
            'min_volume': 1000000,            # 最小24小时成交量
            'exchanges': ['binance']  # 只使用Binance
        }
        params = {**default_params, **(parameters or {})}
        super().__init__("资金费率套利策略", params)
        
        # 合约池管理
        self.contract_pool: Set[str] = set()  # 当前池子中的合约
        self.exchange_instances = {}
        self._init_exchanges()
    
    def _init_exchanges(self):
        """初始化交易所连接"""
        # 测试代理连接
        print("🔍 测试代理连接...")
        if test_proxy_connection():
            print("✅ 代理连接正常")
        else:
            print("⚠️ 代理连接失败，将尝试不使用代理")
        
        # 获取代理配置
        proxy_config = get_proxy_dict()
        
        for exchange_name in self.parameters['exchanges']:
            try:
                exchange_class = getattr(ccxt, exchange_name)
                
                # 针对不同交易所的配置
                config = {
                    'enableRateLimit': True,
                    'timeout': 30000,  # 30秒超时
                    'rateLimit': 2000,  # 请求间隔2秒，避免频率限制
                }
                
                # 添加代理配置（如果可用）
                if proxy_config:
                    config['proxies'] = proxy_config
                    print(f"使用代理: {proxy_config}")
                
                # 针对Binance的特殊配置
                if exchange_name == 'binance':
                    config.update({
                        'timeout': 60000,  # 增加到60秒
                        'options': {
                            'defaultType': 'swap',
                            'adjustForTimeDifference': True,
                        },
                        'urls': {
                            'api': {
                                'public': 'https://api.binance.com/api/v3',
                                'private': 'https://api.binance.com/api/v3',
                            }
                        }
                    })
                else:
                    config['options'] = {'defaultType': 'swap'}
                
                self.exchange_instances[exchange_name] = exchange_class(config)
                print(f"✅ 成功初始化交易所: {exchange_name}")
                
                # 测试连接
                try:
                    server_time = self.exchange_instances[exchange_name].fetch_time()
                    print(f"✅ {exchange_name} 连接测试成功")
                except Exception as e:
                    print(f"⚠️ {exchange_name} 连接测试失败: {e}")
                    
            except Exception as e:
                print(f"❌ 初始化交易所 {exchange_name} 失败: {e}")
                continue
    
    def get_funding_rates(self) -> Dict[str, Dict]:
        """获取所有交易所的资金费率"""
        funding_rates = {}
        
        for exchange_name, exchange in self.exchange_instances.items():
            try:
                print(f"正在获取 {exchange_name} 的资金费率...")
                
                # 预定义的主要永续合约（30个交易对）
                predefined_symbols = [
                    'BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT',
                    'ADA/USDT:USDT', 'SOL/USDT:USDT', 'DOT/USDT:USDT',
                    'LINK/USDT:USDT', 'UNI/USDT:USDT', 'AVAX/USDT:USDT',
                    'ATOM/USDT:USDT', 'LTC/USDT:USDT', 'BCH/USDT:USDT',
                    'XRP/USDT:USDT', 'DOGE/USDT:USDT', 'SHIB/USDT:USDT',
                    'TRX/USDT:USDT', 'EOS/USDT:USDT', 'XLM/USDT:USDT',
                    'VET/USDT:USDT', 'FIL/USDT:USDT', 'NEAR/USDT:USDT',
                    'FTM/USDT:USDT', 'ALGO/USDT:USDT', 'ICP/USDT:USDT',
                    'SAND/USDT:USDT', 'MANA/USDT:USDT', 'AXS/USDT:USDT',
                    'GALA/USDT:USDT', 'CHZ/USDT:USDT', 'HOT/USDT:USDT'
                ]
                
                success_count = 0
                for i, symbol in enumerate(predefined_symbols):
                    try:
                        # 添加延迟避免频率限制
                        if i > 0:
                            time.sleep(0.5)  # 减少延迟到0.5秒
                        
                        print(f"正在获取 {symbol} 的资金费率...")
                        funding_info = exchange.fetch_funding_rate(symbol)
                        
                        if funding_info and 'fundingRate' in funding_info:
                            funding_rates[f"{exchange_name}:{symbol}"] = {
                                'exchange': exchange_name,
                                'symbol': symbol,
                                'funding_rate': funding_info['fundingRate'],
                                'next_funding_time': funding_info.get('nextFundingTime'),
                                'volume_24h': funding_info.get('volume24h', 0)
                            }
                            success_count += 1
                            print(f"✅ {exchange_name}:{symbol} 资金费率: {funding_info['fundingRate']:.6f}")
                        else:
                            print(f"⚠️ {symbol} 资金费率数据为空")
                            
                    except Exception as e:
                        print(f"⚠️ {exchange_name}:{symbol} 获取资金费率失败: {e}")
                        continue
                
                print(f"✅ {exchange_name} 成功获取 {success_count} 个资金费率")
                        
            except Exception as e:
                print(f"❌ 获取 {exchange_name} 资金费率失败: {e}")
                continue
        
        print(f"📊 总共获取到 {len(funding_rates)} 个资金费率")
        return funding_rates
    
    def update_contract_pool(self, funding_rates: Dict[str, Dict]):
        """更新合约池"""
        threshold = self.parameters['funding_rate_threshold']
        min_volume = self.parameters['min_volume']
        max_positions = self.parameters['max_positions']
        
        # 筛选符合条件的合约
        qualified_contracts = []
        for contract_id, info in funding_rates.items():
            funding_rate = info['funding_rate']
            volume_24h = info.get('volume_24h', 0)
            
            # 检查资金费率阈值和成交量
            if (abs(funding_rate) >= threshold and 
                volume_24h >= min_volume):
                qualified_contracts.append({
                    'contract_id': contract_id,
                    'funding_rate': funding_rate,
                    'volume_24h': volume_24h,
                    'exchange': info['exchange'],
                    'symbol': info['symbol']
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
        
        # 发送Telegram通知
        if added_contracts:
            added_list = []
            for contract_id in added_contracts:
                info = funding_rates[contract_id]
                added_list.append(f"{info['exchange']}:{info['symbol']} (费率: {info['funding_rate']:.4%})")
            
            message = f"🟢 合约进入池子:\n" + "\n".join(added_list)
            send_telegram_message(message)
        
        if removed_contracts:
            removed_list = []
            for contract_id in removed_contracts:
                # 从funding_rates中查找信息，如果不存在则使用contract_id
                if contract_id in funding_rates:
                    info = funding_rates[contract_id]
                    removed_list.append(f"{info['exchange']}:{info['symbol']}")
                else:
                    removed_list.append(contract_id)
            
            message = f"🔴 合约移出池子:\n" + "\n".join(removed_list)
            send_telegram_message(message)
        
        # 更新池子
        self.contract_pool = new_pool
        
        # 发送当前池子状态
        if self.contract_pool:
            pool_list = []
            for contract_id in self.contract_pool:
                if contract_id in funding_rates:
                    info = funding_rates[contract_id]
                    pool_list.append(f"{info['exchange']}:{info['symbol']} (费率: {info['funding_rate']:.4%})")
                else:
                    pool_list.append(contract_id)
            
            message = f"📊 当前池子状态 ({len(self.contract_pool)}个合约):\n" + "\n".join(pool_list)
            send_telegram_message(message)
        else:
            send_telegram_message("📊 当前池子为空")
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """生成交易信号"""
        try:
            # 获取资金费率数据
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
            'threshold': self.parameters['funding_rate_threshold']
        } 