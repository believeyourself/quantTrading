#!/usr/bin/env python3
"""
配置验证工具
"""

from typing import Dict, List, Tuple, Any
from config.settings import settings

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_funding_rate_config() -> Tuple[bool, List[str]]:
        """
        验证资金费率相关配置
        
        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []
        
        # 验证资金费率阈值
        threshold = settings.FUNDING_RATE_THRESHOLD
        if not isinstance(threshold, (int, float)):
            errors.append("资金费率阈值必须是数字类型")
        elif threshold <= 0:
            errors.append("资金费率阈值必须大于0")
        elif threshold > 0.1:  # 10%
            errors.append("资金费率阈值不应超过10%，当前值过高")
        
        # 验证最小成交量
        min_volume = settings.MIN_VOLUME
        if not isinstance(min_volume, (int, float)):
            errors.append("最小成交量必须是数字类型")
        elif min_volume <= 0:
            errors.append("最小成交量必须大于0")
        elif min_volume < 100000:  # 10万USDT
            errors.append("最小成交量不应低于10万USDT，可能过于严格")
        
        # 验证最大池大小
        max_pool_size = settings.MAX_POOL_SIZE
        if not isinstance(max_pool_size, int):
            errors.append("最大池大小必须是整数")
        elif max_pool_size <= 0:
            errors.append("最大池大小必须大于0")
        elif max_pool_size > 100:
            errors.append("最大池大小不应超过100，可能影响性能")
        
        # 验证缓存时间
        cache_duration = settings.CACHE_DURATION
        if not isinstance(cache_duration, int):
            errors.append("缓存时间必须是整数")
        elif cache_duration <= 0:
            errors.append("缓存时间必须大于0")
        elif cache_duration < 300:  # 5分钟
            errors.append("缓存时间不应少于5分钟，可能过于频繁")
        elif cache_duration > 86400:  # 24小时
            errors.append("缓存时间不应超过24小时，数据可能过时")
        
        # 验证更新间隔
        update_interval = settings.UPDATE_INTERVAL
        if not isinstance(update_interval, int):
            errors.append("更新间隔必须是整数")
        elif update_interval <= 0:
            errors.append("更新间隔必须大于0")
        elif update_interval < 60:  # 1分钟
            errors.append("更新间隔不应少于1分钟，可能过于频繁")
        
        # 验证合约刷新间隔
        contract_refresh_interval = settings.CONTRACT_REFRESH_INTERVAL
        if not isinstance(contract_refresh_interval, int):
            errors.append("合约刷新间隔必须是整数")
        elif contract_refresh_interval <= 0:
            errors.append("合约刷新间隔必须大于0")
        elif contract_refresh_interval < 300:  # 5分钟
            errors.append("合约刷新间隔不应少于5分钟，可能过于频繁")
        
        # 验证资金费率检查间隔
        funding_rate_check_interval = settings.FUNDING_RATE_CHECK_INTERVAL
        if not isinstance(funding_rate_check_interval, int):
            errors.append("资金费率检查间隔必须是整数")
        elif funding_rate_check_interval <= 0:
            errors.append("资金费率检查间隔必须大于0")
        elif funding_rate_check_interval < 30:  # 30秒
            errors.append("资金费率检查间隔不应少于30秒，可能过于频繁")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_telegram_config() -> Tuple[bool, List[str]]:
        """
        验证Telegram配置
        
        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []
        
        # 验证Bot Token
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            errors.append("Telegram Bot Token未配置")
        elif not isinstance(bot_token, str):
            errors.append("Telegram Bot Token必须是字符串")
        elif len(bot_token) < 10:
            errors.append("Telegram Bot Token格式不正确")
        
        # 验证Chat ID
        chat_id = settings.TELEGRAM_CHAT_ID
        if not chat_id:
            errors.append("Telegram Chat ID未配置")
        elif not isinstance(chat_id, str):
            errors.append("Telegram Chat ID必须是字符串")
        elif not chat_id.replace('-', '').isdigit():
            errors.append("Telegram Chat ID格式不正确")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_database_config() -> Tuple[bool, List[str]]:
        """
        数据库配置验证已移除
        
        Returns:
            (是否有效, 错误消息列表)
        """
        # 数据库功能已移除，直接返回成功
        return True, []
    
    @staticmethod
    def validate_api_config() -> Tuple[bool, List[str]]:
        """
        验证API配置
        
        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []
        
        # 验证API端口
        port = settings.API_PORT
        if not isinstance(port, int):
            errors.append("API端口必须是整数")
        elif port <= 0 or port > 65535:
            errors.append("API端口必须在1-65535范围内")
        
        # 验证API主机
        host = settings.API_HOST
        if not isinstance(host, str):
            errors.append("API主机必须是字符串")
        elif host not in ['0.0.0.0', 'localhost', '127.0.0.1']:
            errors.append("API主机配置可能不安全")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_all_configs() -> Tuple[bool, Dict[str, List[str]]]:
        """
        验证所有配置
        
        Returns:
            (是否全部有效, 各配置类别的错误消息)
        """
        results = {}
        
        # 验证各类配置
        results['funding_rate'] = ConfigValidator.validate_funding_rate_config()[1]
        results['telegram'] = ConfigValidator.validate_telegram_config()[1]
        results['database'] = ConfigValidator.validate_database_config()[1]
        results['api'] = ConfigValidator.validate_api_config()[1]
        
        # 检查是否全部有效
        all_valid = all(len(errors) == 0 for errors in results.values())
        
        return all_valid, results
    
    @staticmethod
    def print_config_summary():
        """打印配置摘要"""
        print("📋 配置验证摘要")
        print("=" * 50)
        
        is_valid, errors_by_category = ConfigValidator.validate_all_configs()
        
        if is_valid:
            print("✅ 所有配置验证通过")
        else:
            print("❌ 发现配置问题:")
            for category, errors in errors_by_category.items():
                if errors:
                    print(f"\n🔴 {category.upper()} 配置:")
                    for error in errors:
                        print(f"   • {error}")
        
        print("\n📊 当前配置值:")
        print(f"   资金费率阈值: {settings.FUNDING_RATE_THRESHOLD:.4%}")
        print(f"   最小成交量: {settings.MIN_VOLUME:,} USDT")
        print(f"   最大池大小: {settings.MAX_POOL_SIZE}")
        print(f"   缓存时间: {settings.CACHE_DURATION} 秒")
        print(f"   更新间隔: {settings.UPDATE_INTERVAL} 秒")
        print(f"   合约刷新间隔: {settings.CONTRACT_REFRESH_INTERVAL} 秒")
        print(f"   资金费率检查间隔: {settings.FUNDING_RATE_CHECK_INTERVAL} 秒")
        print(f"   API端口: {settings.API_PORT}")
        print(f"   Telegram通知: {'已配置' if settings.TELEGRAM_BOT_TOKEN else '未配置'}")
        
        return is_valid
