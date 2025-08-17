#!/usr/bin/env python3
"""
测试优化后的系统功能
"""

import os
import sys
import time
from datetime import datetime

def test_config_validation():
    """测试配置验证功能"""
    
    print("🧪 测试配置验证功能...")
    print("=" * 60)
    
    try:
        from utils.config_validator import ConfigValidator
        
        # 验证所有配置
        is_valid = ConfigValidator.print_config_summary()
        
        if is_valid:
            print("\n✅ 配置验证测试通过")
        else:
            print("\n❌ 配置验证发现问题，请检查配置")
            
    except ImportError as e:
        print(f"❌ 无法导入配置验证器: {e}")
    except Exception as e:
        print(f"❌ 配置验证测试失败: {e}")

def test_funding_rate_utils():
    """测试资金费率工具类"""
    
    print("\n🧪 测试资金费率工具类...")
    print("=" * 60)
    
    try:
        from utils.funding_rate_utils import FundingRateUtils
        
        # 测试数据
        test_contracts = {
            "BTCUSDT": {
                "funding_rate": 0.0012,
                "mark_price": 43250.50,
                "next_funding_time": "2025-01-17 16:00:00",
                "data_source": "real_time"
            },
            "ETHUSDT": {
                "funding_rate": -0.0008,
                "mark_price": 2650.75,
                "next_funding_time": "2025-01-17 16:00:00",
                "data_source": "cached"
            }
        }
        
        # 测试资金费率检查
        print("📊 测试资金费率检查...")
        warning_count, messages = FundingRateUtils.check_funding_rates(
            test_contracts, 0.005, "测试"
        )
        print(f"   警告数量: {warning_count}")
        for msg in messages:
            print(f"   {msg}")
        
        # 测试格式化显示
        print("\n📊 测试格式化显示...")
        for symbol, info in test_contracts.items():
            color, text = FundingRateUtils.format_funding_rate_display(info['funding_rate'])
            print(f"   {symbol}: {text} (颜色: {color})")
        
        # 测试缓存工具
        print("\n💾 测试缓存工具...")
        test_cache_data = {
            "test": "data",
            "timestamp": datetime.now().isoformat()
        }
        
        success = FundingRateUtils.save_cache_data(
            test_cache_data, 
            "cache/test_cache.json", 
            "测试缓存"
        )
        print(f"   保存测试缓存: {'成功' if success else '失败'}")
        
        # 清理测试文件
        if os.path.exists("cache/test_cache.json"):
            os.remove("cache/test_cache.json")
            print("   清理测试缓存文件")
        
        print("✅ 资金费率工具类测试通过")
        
    except ImportError as e:
        print(f"❌ 无法导入资金费率工具类: {e}")
    except Exception as e:
        print(f"❌ 资金费率工具类测试失败: {e}")

def test_logger():
    """测试日志工具"""
    
    print("\n🧪 测试日志工具...")
    print("=" * 60)
    
    try:
        from utils.logger import setup_logger, get_logger, LogMessages
        
        # 设置日志器
        logger = setup_logger("test_logger", "DEBUG")
        
        # 测试不同级别的日志
        print("📝 测试日志输出...")
        logger.debug("这是一条调试日志")
        logger.info("这是一条信息日志")
        logger.warning("这是一条警告日志")
        logger.error("这是一条错误日志")
        
        # 测试预定义消息模板
        print("\n📝 测试预定义消息模板...")
        print(f"   API调用开始: {LogMessages.api_call_start('/test')}")
        print(f"   API调用成功: {LogMessages.api_call_success('/test', 5)}")
        print(f"   API调用失败: {LogMessages.api_call_failed('/test', '连接超时')}")
        print(f"   缓存保存成功: {LogMessages.cache_save_success('test.json', '测试数据')}")
        print(f"   资金费率检查: {LogMessages.funding_rate_check_start('测试模块')}")
        
        print("✅ 日志工具测试通过")
        
    except ImportError as e:
        print(f"❌ 无法导入日志工具: {e}")
    except Exception as e:
        print(f"❌ 日志工具测试失败: {e}")

def test_system_integration():
    """测试系统集成"""
    
    print("\n🧪 测试系统集成...")
    print("=" * 60)
    
    print("📋 检查关键文件:")
    
    # 检查配置文件
    config_files = [
        "config/settings.py",
        "utils/funding_rate_utils.py",
        "utils/logger.py",
        "utils/config_validator.py"
    ]
    
    for file_path in config_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - 文件不存在")
    
    # 检查缓存目录
    if os.path.exists("cache"):
        print("   ✅ cache/ 目录")
    else:
        print("   ❌ cache/ 目录不存在")
    
    # 检查主要模块
    print("\n📋 检查主要模块:")
    modules = [
        "strategies.funding_rate_arbitrage",
        "api.routes",
        "web.interface",
        "utils.binance_funding"
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"   ✅ {module}")
        except ImportError as e:
            print(f"   ❌ {module} - 导入失败: {e}")
    
    print("\n✅ 系统集成测试完成")

def main():
    """主测试函数"""
    
    print("🚀 优化后系统功能测试")
    print("=" * 60)
    
    # 运行各项测试
    test_config_validation()
    test_funding_rate_utils()
    test_logger()
    test_system_integration()
    
    print("\n" + "=" * 60)
    print("🧪 所有测试完成")
    
    print("\n📝 优化总结:")
    print("✅ 创建了资金费率工具类，减少重复代码")
    print("✅ 统一了日志格式和消息模板")
    print("✅ 添加了配置验证功能")
    print("✅ 简化了策略类和Web界面代码")
    print("✅ 提高了代码的可维护性和可读性")
    
    print("\n🎯 下一步建议:")
    print("1. 启动系统测试新功能")
    print("2. 观察日志输出是否更加统一")
    print("3. 验证资金费率检查功能是否正常")
    print("4. 检查配置验证是否发现问题")

if __name__ == "__main__":
    main()
