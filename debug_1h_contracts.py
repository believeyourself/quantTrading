#!/usr/bin/env python3
"""
调试1小时结算周期合约检测
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
from datetime import datetime
from utils.binance_funding import BinanceFunding

def test_funding_interval_detection():
    """测试资金费率结算周期检测"""
    print("🔍 测试资金费率结算周期检测")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 测试几个主流合约
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT', 'SOLUSDT']
    
    for symbol in test_symbols:
        try:
            print(f"\n📊 检测 {symbol}:")
            
            # 方法1: 使用detect_funding_interval
            interval = funding.detect_funding_interval(symbol, "UM")
            print(f"  结算周期检测: {interval:.2f}小时" if interval else "  结算周期检测: 无法检测")
            
            # 方法2: 获取当前资金费率信息
            current = funding.get_current_funding(symbol, "UM")
            if current:
                print(f"  当前资金费率: {current.get('funding_rate', 'N/A')}")
                print(f"  下次结算时间: {current.get('next_funding_time', 'N/A')}")
                
                # 计算距离下次结算的时间
                if current.get('next_funding_time'):
                    next_time = datetime.fromtimestamp(current['next_funding_time'] / 1000)
                    now = datetime.now()
                    time_diff = (next_time - now).total_seconds()
                    print(f"  距离下次结算: {time_diff:.0f}秒 ({time_diff/3600:.2f}小时)")
            
            # 方法3: 获取历史资金费率
            history = funding.get_funding_history(symbol, "UM", limit=3)
            if history:
                print(f"  历史资金费率数量: {len(history)}")
                for i, h in enumerate(history[:2]):
                    print(f"    第{i+1}次: {h.get('funding_time', 'N/A')} - {h.get('funding_rate', 'N/A')}")
            
            time.sleep(0.5)  # 限流
            
        except Exception as e:
            print(f"  ❌ {symbol}: 检测失败 - {e}")

def test_1h_contracts_scan():
    """测试1小时结算合约扫描"""
    print(f"\n🔍 测试1小时结算合约扫描")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 获取所有合约信息
    try:
        info = funding.um.market.get_exchangeInfo()
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
        
        # 测试前20个合约
        test_symbols = perpetual_symbols[:20]
        h1_contracts = []
        
        for symbol in test_symbols:
            try:
                # 检测结算周期
                interval = funding.detect_funding_interval(symbol, "UM")
                
                if interval:
                    print(f"  📊 {symbol}: {interval:.2f}小时结算周期")
                    
                    # 检查是否为1小时结算
                    if abs(interval - 1.0) < 0.1:  # 1小时结算
                        h1_contracts.append(symbol)
                        print(f"    ✅ {symbol}: 1小时结算周期")
                    elif abs(interval - 8.0) < 0.1:  # 8小时结算
                        print(f"    📊 {symbol}: 8小时结算周期")
                    else:
                        print(f"    📊 {symbol}: {interval:.1f}小时结算周期")
                else:
                    print(f"  ❌ {symbol}: 无法检测结算周期")
                
                time.sleep(0.1)  # 限流
                
            except Exception as e:
                print(f"  ❌ {symbol}: 检测失败 - {e}")
        
        print(f"\n📊 扫描结果:")
        print(f"  测试合约: {len(test_symbols)}个")
        print(f"  1小时结算: {len(h1_contracts)}个")
        
        if h1_contracts:
            print(f"  1小时结算合约列表:")
            for symbol in h1_contracts:
                print(f"    • {symbol}")
        
    except Exception as e:
        print(f"❌ 扫描失败: {e}")

def test_funding_rate_api():
    """测试资金费率API返回格式"""
    print(f"\n🔍 测试资金费率API返回格式")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 测试BTCUSDT
    symbol = "BTCUSDT"
    
    try:
        # 获取资金费率信息
        funding_info = funding.um.market.get_fundingRate(symbol=symbol)
        print(f"📊 {symbol} 资金费率API返回:")
        print(f"  类型: {type(funding_info)}")
        print(f"  内容: {funding_info}")
        
        if isinstance(funding_info, dict) and 'data' in funding_info:
            funding_data = funding_info.get('data', [])
        else:
            funding_data = funding_info if isinstance(funding_info, list) else []
        
        print(f"  解析后数据: {funding_data}")
        
        if funding_data:
            print(f"  数据条数: {len(funding_data)}")
            for i, data in enumerate(funding_data[:2]):
                print(f"    第{i+1}条: {data}")
        
    except Exception as e:
        print(f"❌ API测试失败: {e}")

def test_hyperusdt():
    """专门检测HYPERUSDT合约的结算周期和资金费率API返回"""
    print("\n🔍 检测 HYPERUSDT 结算周期和资金费率API")
    print("=" * 60)
    funding = BinanceFunding()
    symbol = "HYPERUSDT"
    try:
        # 检查是否在币安永续合约列表中
        info = funding.um.market.get_exchangeInfo()
        if isinstance(info, dict) and 'data' in info:
            symbols = info.get('data', {}).get('symbols', [])
        else:
            symbols = info.get('symbols', [])
        found = any(s.get('symbol') == symbol for s in symbols)
        print(f"是否在exchangeInfo永续合约列表: {'是' if found else '否'}")
        
        # 检测结算周期
        interval = funding.detect_funding_interval(symbol, "UM")
        print(f"HYPERUSDT 结算周期: {interval} 小时" if interval else "HYPERUSDT 结算周期: 无法检测")
        
        # 获取资金费率历史
        history = funding.get_funding_history(symbol, "UM", limit=5)
        print(f"资金费率历史条数: {len(history)}")
        for i, h in enumerate(history):
            print(f"  第{i+1}次: 时间={h.get('funding_time')} 费率={h.get('funding_rate')}")
        
        # 获取当前资金费率
        current = funding.get_current_funding(symbol, "UM")
        print(f"当前资金费率信息: {current}")
        if current and current.get('next_funding_time'):
            next_time = datetime.fromtimestamp(current['next_funding_time'] / 1000)
            now = datetime.now()
            time_diff = (next_time - now).total_seconds()
            print(f"距离下次结算: {time_diff:.0f}秒 ({time_diff/3600:.2f}小时)")
    except Exception as e:
        print(f"❌ 检测失败: {e}")

def test_improved_scan():
    """测试改进后的扫描逻辑"""
    print("\n🔍 测试改进后的1小时结算合约扫描逻辑")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 使用改进后的扫描方法
    print("🔄 开始改进后的扫描...")
    h1_contracts = funding.scan_1h_funding_contracts(force_refresh=True)
    
    print(f"\n📊 扫描结果:")
    print(f"  找到1小时结算合约: {len(h1_contracts)}个")
    
    if h1_contracts:
        print(f"\n📋 1小时结算合约详情:")
        for symbol, info in h1_contracts.items():
            print(f"  • {symbol}:")
            print(f"    结算周期: {info.get('funding_interval_hours', 'N/A')}小时")
            print(f"    当前资金费率: {info.get('current_funding_rate', 'N/A')}")
            print(f"    下次结算时间: {info.get('next_funding_time', 'N/A')}")
    else:
        print("❌ 未找到1小时结算周期合约")

def test_cache_functionality():
    """测试缓存功能"""
    print("\n🔍 测试缓存功能")
    print("=" * 60)
    
    funding = BinanceFunding()
    
    # 测试从缓存获取
    print("📋 从缓存获取1小时结算合约...")
    cached_contracts = funding.get_1h_contracts_from_cache()
    print(f"缓存中合约数量: {len(cached_contracts)}")
    
    if cached_contracts:
        print("缓存中的合约:")
        for symbol in list(cached_contracts.keys())[:5]:  # 显示前5个
            print(f"  • {symbol}")
    
    # 测试更新缓存
    print("\n🔄 更新缓存...")
    updated_contracts = funding.update_1h_contracts_cache()
    print(f"更新后合约数量: {len(updated_contracts)}")

def main():
    """主函数"""
    print("🚀 1小时结算合约检测调试")
    print("=" * 80)
    
    # 选择测试模式
    print("请选择测试模式:")
    print("1. 测试结算周期检测")
    print("2. 测试1小时结算合约扫描")
    print("3. 测试资金费率API")
    print("4. 完整测试")
    print("5. 检测HYPERUSDT合约")
    print("6. 测试改进后的扫描逻辑")
    print("7. 测试缓存功能")
    choice = input("请输入选择 (1/2/3/4/5/6/7): ").strip()
    
    if choice == "1":
        test_funding_interval_detection()
    elif choice == "2":
        test_1h_contracts_scan()
    elif choice == "3":
        test_funding_rate_api()
    elif choice == "4":
        test_funding_interval_detection()
        test_1h_contracts_scan()
        test_funding_rate_api()
    elif choice == "5":
        test_hyperusdt()
    elif choice == "6":
        test_improved_scan()
    elif choice == "7":
        test_cache_functionality()
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main() 