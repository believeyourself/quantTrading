#!/usr/bin/env python3
"""
专门测试Binance资金费率获取
"""

import ccxt
import time
import requests
from datetime import datetime

def test_binance_direct():
    """直接测试Binance API"""
    print("🔍 直接测试Binance API...")
    
    # 测试基本连接
    try:
        response = requests.get("https://api.binance.com/api/v3/ping", timeout=10)
        print(f"✅ Binance API ping成功: {response.status_code}")
    except Exception as e:
        print(f"❌ Binance API ping失败: {e}")
        return False
    
    # 测试exchangeInfo
    try:
        response = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=30)
        print(f"✅ Binance exchangeInfo成功: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"📊 交易对数量: {len(data.get('symbols', []))}")
        return True
    except Exception as e:
        print(f"❌ Binance exchangeInfo失败: {e}")
        return False

def test_binance_ccxt():
    """使用CCXT测试Binance"""
    print("\n🔍 使用CCXT测试Binance...")
    
    try:
        # 创建Binance实例
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'timeout': 30000,
            'rateLimit': 2000,
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
            }
        })
        
        print("✅ Binance实例创建成功")
        
        # 测试服务器时间
        try:
            server_time = exchange.fetch_time()
            print(f"✅ 服务器时间: {datetime.fromtimestamp(server_time/1000)}")
        except Exception as e:
            print(f"❌ 获取服务器时间失败: {e}")
        
        # 测试加载市场数据
        try:
            print("正在加载市场数据...")
            markets = exchange.load_markets()
            print(f"✅ 市场数据加载成功，共 {len(markets)} 个交易对")
            
            # 统计永续合约
            perpetual_count = 0
            perpetual_symbols = []
            for symbol, market in markets.items():
                if market.get('swap') or market.get('future'):
                    perpetual_count += 1
                    if len(perpetual_symbols) < 10:
                        perpetual_symbols.append(symbol)
            
            print(f"📊 永续合约数量: {perpetual_count}")
            print(f"📋 永续合约示例: {perpetual_symbols[:5]}")
            
            # 测试获取资金费率
            if perpetual_symbols:
                test_symbol = perpetual_symbols[0]
                print(f"\n测试获取 {test_symbol} 的资金费率...")
                
                try:
                    funding_info = exchange.fetch_funding_rate(test_symbol)
                    if funding_info:
                        print(f"✅ 资金费率获取成功:")
                        print(f"   资金费率: {funding_info.get('fundingRate', 'N/A')}")
                        print(f"   下次结算时间: {funding_info.get('nextFundingTime', 'N/A')}")
                        print(f"   24小时成交量: {funding_info.get('volume24h', 'N/A')}")
                    else:
                        print("⚠️ 资金费率数据为空")
                except Exception as e:
                    print(f"❌ 获取资金费率失败: {e}")
                    print(f"错误类型: {type(e).__name__}")
                    print(f"错误详情: {str(e)}")
            
        except Exception as e:
            print(f"❌ 加载市场数据失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            return False
        
    except Exception as e:
        print(f"❌ CCXT测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误详情: {str(e)}")
        return False
    
    return True

def test_alternative_approach():
    """测试替代方案"""
    print("\n🔍 测试替代方案...")
    
    try:
        # 使用不同的配置
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'timeout': 60000,  # 增加超时时间
            'rateLimit': 3000,  # 增加请求间隔
            'options': {
                'defaultType': 'swap',
            },
            'urls': {
                'api': {
                    'public': 'https://api.binance.com/api/v3',
                    'private': 'https://api.binance.com/api/v3',
                }
            }
        })
        
        print("✅ 替代配置Binance实例创建成功")
        
        # 直接获取资金费率（不先加载市场数据）
        test_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT']
        
        for symbol in test_symbols:
            try:
                print(f"\n直接测试 {symbol} 资金费率...")
                funding_info = exchange.fetch_funding_rate(symbol)
                
                if funding_info:
                    print(f"✅ {symbol} 资金费率获取成功:")
                    print(f"   资金费率: {funding_info.get('fundingRate', 'N/A')}")
                else:
                    print(f"⚠️ {symbol} 资金费率数据为空")
                    
            except Exception as e:
                print(f"❌ {symbol} 资金费率获取失败: {e}")
                print(f"错误类型: {type(e).__name__}")
        
    except Exception as e:
        print(f"❌ 替代方案测试失败: {e}")

def main():
    print("Binance资金费率获取问题诊断")
    print("=" * 50)
    
    # 测试直接API调用
    if test_binance_direct():
        print("\n✅ 直接API调用成功")
    else:
        print("\n❌ 直接API调用失败，可能是网络问题")
    
    # 测试CCXT
    if test_binance_ccxt():
        print("\n✅ CCXT测试成功")
    else:
        print("\n❌ CCXT测试失败")
    
    # 测试替代方案
    test_alternative_approach()
    
    print("\n" + "=" * 50)
    print("诊断完成！")

if __name__ == "__main__":
    main() 