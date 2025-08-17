#!/usr/bin/env python3
"""
统一日志工具
"""

import logging
import sys
from datetime import datetime
from typing import Optional

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record):
        # 添加时间戳
        record.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 添加颜色
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # 格式化消息
        if record.levelname == 'INFO':
            # 特殊处理INFO级别的emoji
            if '✅' in record.getMessage():
                record.msg = f"{color}✅{reset} {record.msg}"
            elif '❌' in record.getMessage():
                record.msg = f"{color}❌{reset} {record.msg}"
            elif '⚠️' in record.getMessage():
                record.msg = f"{color}⚠️{reset} {record.msg}"
            elif '📢' in record.getMessage():
                record.msg = f"{color}📢{reset} {record.msg}"
            elif '💾' in record.getMessage():
                record.msg = f"{color}💾{reset} {record.msg}"
            elif '📋' in record.getMessage():
                record.msg = f"{color}📋{reset} {record.msg}"
            elif '🔄' in record.getMessage():
                record.msg = f"{color}🔄{reset} {record.msg}"
            elif '📊' in record.getMessage():
                record.msg = f"{color}📊{reset} {record.msg}"
            elif '📈' in record.getMessage():
                record.msg = f"{color}📈{reset} {record.msg}"
            elif '📡' in record.getMessage():
                record.msg = f"{color}📡{reset} {record.msg}"
            elif '🧪' in record.getMessage():
                record.msg = f"{color}🧪{reset} {record.msg}"
            elif '🚀' in record.getMessage():
                record.msg = f"{color}🚀{reset} {record.msg}"
            elif '🛑' in record.getMessage():
                record.msg = f"{color}🛑{reset} {record.msg}"
            else:
                record.msg = f"{color}ℹ️{reset} {record.msg}"
        
        return super().format(record)

def setup_logger(name: str = "quant_trading", level: str = "INFO", 
                log_file: Optional[str] = None) -> logging.Logger:
    """
    设置统一的日志器
    
    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        
    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建格式化器
    formatter = ColoredFormatter(
        '%(timestamp)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了日志文件）
    if log_file:
        try:
            import os
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        except Exception as e:
            logger.warning(f"无法创建文件日志处理器: {e}")
    
    return logger

def get_logger(name: str = "quant_trading") -> logging.Logger:
    """
    获取日志器实例
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    return logging.getLogger(name)

# 预定义的日志消息模板
class LogMessages:
    """日志消息模板"""
    
    @staticmethod
    def api_call_start(endpoint: str) -> str:
        return f"开始调用API: {endpoint}"
    
    @staticmethod
    def api_call_success(endpoint: str, data_count: int = 0) -> str:
        if data_count > 0:
            return f"API调用成功: {endpoint}，获取到 {data_count} 条数据"
        return f"API调用成功: {endpoint}"
    
    @staticmethod
    def api_call_failed(endpoint: str, error: str) -> str:
        return f"API调用失败: {endpoint}，错误: {error}"
    
    @staticmethod
    def cache_save_success(file_path: str, description: str = "数据") -> str:
        return f"{description}已保存到缓存: {file_path}"
    
    @staticmethod
    def cache_load_success(file_path: str, description: str = "数据") -> str:
        return f"从缓存加载了{description}: {file_path}"
    
    @staticmethod
    def funding_rate_check_start(source: str) -> str:
        return f"{source}: 开始检查资金费率"
    
    @staticmethod
    def funding_rate_warning_count(count: int, source: str) -> str:
        return f"{source}: 发送了 {count} 个资金费率警告通知"
    
    @staticmethod
    def funding_rate_all_normal(source: str) -> str:
        return f"{source}: 所有合约资金费率都在正常范围内"
    
    @staticmethod
    def task_start(task_name: str) -> str:
        return f"开始执行任务: {task_name}"
    
    @staticmethod
    def task_complete(task_name: str) -> str:
        return f"任务完成: {task_name}"
    
    @staticmethod
    def task_failed(task_name: str, error: str) -> str:
        return f"任务失败: {task_name}，错误: {error}"
