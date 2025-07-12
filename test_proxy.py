#!/usr/bin/env python3
"""
代理测试脚本
"""

import requests
import ccxt
import time
from datetime import datetime

def test_proxy_connectivity():
    """测试代理连接性"""
    print("🔍 测试代理连接性...")
    
    # 代理配置
    proxies = {
        'http': 'http://127.0.0.1:7890',
        'https': 'http://127.0.0.1:7890'
    }
    
    # 测试基本网络连接
    try:
        response = requests.get("https://www.google.com", proxies=proxies, timeout=10)
        print("✅ 通过代理访问Google成功")
    except Exception as e:
        print(f"❌ 通过代理访问Google失败: {e}")
        return False
    
    # 测试Binance API
    try:
        response = requests.get("https://api.binance.com/api/v3/ping", proxies=proxies, timeout=10)
        if response.status_code == 200:
            print("✅ 通过代理访问Binance API成功")
        else:
            print(f"❌ Binance API响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 通过代理访问Binance API失败: {e}")
        return False
    
    return True

def test_ccxt_with_proxy():
    """测试CCXT使用代理"""
    print("\n🔍 测试CCXT使用代理...")
    
    try:
        # 创建带代理的Binance实例
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'timeout': 30000,
            'rateLimit': 2000,
            'proxies': {
                'http': 'http://127.0.0.1:7890',
                'https': 'http://127.0.0.1:7890'
            },
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
            }
        })
        
        print("✅ 带代理的Binance实例创建成功")
        
        # 测试服务器时间
        try:
            server_time = exchange.fetch_time()
            print(f"✅ 获取服务器时间成功: {datetime.fromtimestamp(server_time/1000)}")
        except Exception as e:
            print(f"❌ 获取服务器时间失败: {e}")
            return False
        
        # 测试获取资金费率
        try:
            print("正在获取BTC/USDT:USDT的资金费率...")
            funding_info = exchange.fetch_funding_rate('BTC/USDT:USDT')
            
            if funding_info and 'fundingRate' in funding_info:
                print(f"✅ 资金费率获取成功:")
                print(f"   资金费率: {funding_info['fundingRate']:.6f}")
                print(f"   下次结算时间: {funding_info.get('nextFundingTime', 'N/A')}")
                print(f"   24小时成交量: {funding_info.get('volume24h', 'N/A')}")
                return True
            else:
                print("⚠️ 资金费率数据为空")
                return False
                
        except Exception as e:
            print(f"❌ 获取资金费率失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            return False
        
    except Exception as e:
        print(f"❌ CCXT代理测试失败: {e}")
        return False

def test_different_proxy_ports():
    """测试不同的代理端口"""
    print("\n🔍 测试不同的代理端口...")
    
    # 常见的代理端口
    proxy_ports = [7890, 1080, 8080, 3128, 8888]
    
    for port in proxy_ports:
        print(f"\n测试端口 {port}...")
        proxies = {
            'http': f'http://127.0.0.1:{port}',
            'https': f'http://127.0.0.1:{port}'
        }
        
        try:
            response = requests.get("https://api.binance.com/api/v3/ping", proxies=proxies, timeout=5)
            if response.status_code == 200:
                print(f"✅ 端口 {port} 工作正常")
                return port
            else:
                print(f"❌ 端口 {port} 响应异常: {response.status_code}")
        except Exception as e:
            print(f"❌ 端口 {port} 连接失败: {e}")
    
    return None

def main():
    print("代理测试")
    print("=" * 50)
    
    # 测试代理连接性
    if test_proxy_connectivity():
        print("\n✅ 代理连接性测试通过")
    else:
        print("\n❌ 代理连接性测试失败")
        print("尝试检测代理端口...")
        working_port = test_different_proxy_ports()
        if working_port:
            print(f"找到工作端口: {working_port}")
            print(f"请将策略中的代理端口改为: {working_port}")
        return
    
    # 测试CCXT使用代理
    if test_ccxt_with_proxy():
        print("\n✅ CCXT代理测试通过")
        print("代理配置成功！现在可以正常获取资金费率了。")
    else:
        print("\n❌ CCXT代理测试失败")
    
    print("\n" + "=" * 50)
    print("测试完成！")

if __name__ == "__main__":
    main() 