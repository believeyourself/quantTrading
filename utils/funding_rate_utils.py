#!/usr/bin/env python3
"""
资金费率相关公共工具类
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from utils.notifier import send_telegram_message

class FundingRateUtils:
    """资金费率工具类"""
    
    @staticmethod
    def check_funding_rates(contracts: Dict, threshold: float, source: str = "未知") -> Tuple[int, List[str]]:
        """
        检查资金费率并发送通知
        
        Args:
            contracts: 合约数据字典
            threshold: 资金费率阈值
            source: 数据来源标识
            
        Returns:
            (警告数量, 警告消息列表)
        """
        warning_count = 0
        warning_messages = []
        
        for symbol, info in contracts.items():
            try:
                funding_rate = float(info.get('funding_rate', 0))
                if abs(funding_rate) >= threshold:
                    # 构建通知消息
                    message = FundingRateUtils._build_warning_message(symbol, info, source)
                    
                    # 发送通知
                    try:
                        send_telegram_message(message)
                        warning_count += 1
                        warning_messages.append(f"📢 {source}: 发送资金费率警告通知: {symbol}")
                    except Exception as e:
                        warning_messages.append(f"⚠️ {source}: 发送Telegram通知失败: {e}")
                        
            except (ValueError, TypeError) as e:
                warning_messages.append(f"⚠️ {source}: 处理合约 {symbol} 资金费率时出错: {e}")
                continue
        
        return warning_count, warning_messages
    
    @staticmethod
    def _build_warning_message(symbol: str, info: Dict, source: str) -> str:
        """构建警告消息"""
        funding_rate = float(info.get('funding_rate', 0))
        direction = "多头" if funding_rate > 0 else "空头"
        mark_price = info.get('mark_price', 0)
        next_funding_time = info.get('next_funding_time', '未知')
        data_source = info.get('data_source', 'unknown')
        
        message = f"⚠️ 资金费率警告({source}): {symbol}\n" \
                 f"当前费率: {funding_rate:.4%} ({direction})\n" \
                 f"标记价格: ${mark_price:.4f}\n" \
                 f"下次结算时间: {next_funding_time}\n" \
                 f"数据来源: {'实时' if data_source == 'real_time' else '缓存'}\n" \
                 f"24h成交量: {info.get('volume_24h', 0):,.0f}"
        
        return message
    
    @staticmethod
    def format_funding_rate_display(funding_rate: float) -> Tuple[str, str]:
        """
        格式化资金费率显示
        
        Args:
            funding_rate: 资金费率
            
        Returns:
            (颜色, 文本)
        """
        rate_percent = funding_rate * 100
        direction = "多头" if funding_rate > 0 else "空头" if funding_rate < 0 else "中性"
        
        # 根据阈值设置颜色
        if abs(funding_rate) >= 0.005:
            color = "success"
        else:
            color = "secondary"
        
        text = f"{rate_percent:+.4f}% ({direction})"
        return color, text
    
    @staticmethod
    def save_cache_data(cache_data: Dict, cache_file: str, description: str = "缓存数据") -> bool:
        """
        保存缓存数据到文件
        
        Args:
            cache_data: 要保存的数据
            cache_file: 缓存文件路径
            description: 数据描述
            
        Returns:
            是否保存成功
        """
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 {description}已保存到缓存: {cache_file}")
            return True
            
        except Exception as e:
            print(f"⚠️ 保存{description}失败: {e}")
            return False
    
    @staticmethod
    def load_cache_data(cache_file: str, description: str = "缓存数据") -> Optional[Dict]:
        """
        从文件加载缓存数据
        
        Args:
            cache_file: 缓存文件路径
            description: 数据描述
            
        Returns:
            缓存数据或None
        """
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"📋 从缓存加载了{description}")
                return data
            else:
                print(f"📋 {description}缓存文件不存在: {cache_file}")
                return None
                
        except Exception as e:
            print(f"⚠️ 读取{description}缓存失败: {e}")
            return None
    
    @staticmethod
    def is_cache_valid(cache_time: str, cache_duration: int) -> bool:
        """
        检查缓存是否有效
        
        Args:
            cache_time: 缓存时间字符串
            cache_duration: 缓存有效期（秒）
            
        Returns:
            缓存是否有效
        """
        try:
            if not cache_time:
                return False
            
            cache_dt = datetime.fromisoformat(cache_time)
            cache_age = (datetime.now() - cache_dt).total_seconds()
            return cache_age < cache_duration
            
        except Exception:
            return False
    
    @staticmethod
    def get_cache_age_display(cache_time: str) -> str:
        """
        获取缓存年龄的显示文本
        
        Args:
            cache_time: 缓存时间字符串
            
        Returns:
            年龄显示文本
        """
        try:
            if not cache_time:
                return "未知"
            
            cache_dt = datetime.fromisoformat(cache_time)
            cache_age = (datetime.now() - cache_dt).total_seconds()
            
            if cache_age < 60:
                return f"{cache_age:.0f}秒前"
            elif cache_age < 3600:
                return f"{cache_age/60:.0f}分钟前"
            elif cache_age < 86400:
                return f"{cache_age/3600:.1f}小时前"
            else:
                return f"{cache_age/86400:.1f}天前"
                
        except Exception:
            return "未知"
