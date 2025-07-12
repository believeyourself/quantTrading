#!/usr/bin/env python3
"""
资金费率获取问题诊断脚本
"""

import ccxt
import time
import requests
from datetime import datetime

def test_network_connectivity():
    """测试网络连接"""
    print("🔍 测试网络连接...")
    
    # 测试基本网络连接
    try:
        response = requests.get("https://www.google.com", timeout=10)
        print("✅ 基本网络连接正常")
    except Exception as e:
        print(f"❌ 基本网络连接失败: {e}")
        return False
    
    # 测试Binance API连接
    try:
        response = requests.get("https://api.binance.com/api/v3/ping", timeout=10)
        if response.status_code == 200:
            print("✅ Binance API连接正常")
        else:
            print(f"❌ Binance API响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Binance API连接失败: {e}")
        return False
    
    return True

def test_exchange_initialization():
    """测试交易所初始化"""
    print("\n🔍 测试交易所初始化...")
    
    exchanges = ['binance', 'okx', 'bybit']
    
    for exchange_name in exchanges:
        try:
            print(f"\n测试 {exchange_name}...")
            
            # 创建交易所实例
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 30000,
                'rateLimit': 1000,
            })
            
            print(f"✅ {exchange_name} 实例创建成功")
            
            # 测试基本API调用
            try:
                # 获取服务器时间
                server_time = exchange.fetch_time()
                print(f"✅ {exchange_name} 服务器时间: {datetime.fromtimestamp(server_time/1000)}")
            except Exception as e:
                print(f"❌ {exchange_name} 获取服务器时间失败: {e}")
            
            # 测试市场数据加载
            try:
                markets = exchange.load_markets()
                print(f"✅ {exchange_name} 市场数据加载成功，共 {len(markets)} 个交易对")
                
                # 统计永续合约数量
                perpetual_count = 0
                for symbol, market in markets.items():
                    if market.get('swap') or market.get('future'):
                        perpetual_count += 1
                
                print(f"📊 {exchange_name} 永续合约数量: {perpetual_count}")
                
                # 显示前几个永续合约
                perpetual_symbols = []
                for symbol, market in markets.items():
                    if market.get('swap') or market.get('future'):
                        perpetual_symbols.append(symbol)
                        if len(perpetual_symbols) >= 5:
                            break
                
                print(f"📋 {exchange_name} 永续合约示例: {perpetual_symbols}")
                
            except Exception as e:
                print(f"❌ {exchange_name} 加载市场数据失败: {e}")
                print(f"错误详情: {type(e).__name__}: {str(e)}")
            
        except Exception as e:
            print(f"❌ {exchange_name} 初始化失败: {e}")
            print(f"错误详情: {type(e).__name__}: {str(e)}")

def test_funding_rate_fetch():
    """测试资金费率获取"""
    print("\n🔍 测试资金费率获取...")
    
    try:
        # 创建Binance实例
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'timeout': 30000,
            'rateLimit': 1000,
            'options': {'defaultType': 'swap'}
        })
        
        print("✅ Binance实例创建成功")
        
        # 加载市场数据
        markets = exchange.load_markets()
        print(f"✅ 市场数据加载成功，共 {len(markets)} 个交易对")
        
        # 找到永续合约
        perpetual_symbols = []
        for symbol, market in markets.items():
            if market.get('swap') or market.get('future'):
                perpetual_symbols.append(symbol)
        
        print(f"📊 找到 {len(perpetual_symbols)} 个永续合约")
        
        # 测试获取资金费率
        test_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT']
        
        for symbol in test_symbols:
            try:
                print(f"\n测试获取 {symbol} 的资金费率...")
                funding_info = exchange.fetch_funding_rate(symbol)
                
                if funding_info:
                    print(f"✅ {symbol} 资金费率获取成功:")
                    print(f"   资金费率: {funding_info.get('fundingRate', 'N/A')}")
                    print(f"   下次结算时间: {funding_info.get('nextFundingTime', 'N/A')}")
                    print(f"   24小时成交量: {funding_info.get('volume24h', 'N/A')}")
                else:
                    print(f"⚠️ {symbol} 资金费率数据为空")
                    
            except Exception as e:
                print(f"❌ {symbol} 资金费率获取失败: {e}")
                print(f"错误详情: {type(e).__name__}: {str(e)}")
        
    except Exception as e:
        print(f"❌ 资金费率测试失败: {e}")
        print(f"错误详情: {type(e).__name__}: {str(e)}")

def main():
    print("资金费率获取问题诊断")
    print("=" * 50)
    
    # 测试网络连接
    if not test_network_connectivity():
        print("\n❌ 网络连接问题，请检查网络设置")
        return
    
    # 测试交易所初始化
    test_exchange_initialization()
    
    # 测试资金费率获取
    test_funding_rate_fetch()
    
    print("\n" + "=" * 50)
    print("诊断完成！")

if __name__ == "__main__":
    main() 