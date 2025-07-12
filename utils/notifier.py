import os
import requests
from typing import Optional
from loguru import logger
from config.settings import settings

def send_telegram_message(message: str, chat_id: Optional[str] = None, bot_token: Optional[str] = None) -> bool:
    """
    发送Telegram消息
    
    Args:
        message: 要发送的消息内容
        chat_id: Telegram聊天ID，如果为None则从环境变量获取
        bot_token: Telegram机器人token，如果为None则从环境变量获取
    
    Returns:
        bool: 发送是否成功
    """
    try:
        # 优先从参数，其次从config.settings，最后从环境变量
        chat_id = chat_id or settings.TELEGRAM_CHAT_ID or os.getenv('TELEGRAM_CHAT_ID')
        bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN or os.getenv('TELEGRAM_BOT_TOKEN')
        
        if not chat_id or not bot_token:
            logger.warning("Telegram配置缺失，跳过消息发送")
            return False
        
        # 构建API URL
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # 发送消息
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Telegram消息发送成功: {message[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"发送Telegram消息失败: {e}")
        return False

def send_email_notification(subject: str, message: str, to_email: Optional[str] = None) -> bool:
    """
    发送邮件通知（预留功能）
    
    Args:
        subject: 邮件主题
        message: 邮件内容
        to_email: 收件人邮箱，如果为None则从环境变量获取
    
    Returns:
        bool: 发送是否成功
    """
    # TODO: 实现邮件发送功能
    logger.info(f"邮件通知功能待实现: {subject}")
    return False

def send_discord_notification(message: str, webhook_url: Optional[str] = None) -> bool:
    """
    发送Discord通知（预留功能）
    
    Args:
        message: 要发送的消息内容
        webhook_url: Discord webhook URL，如果为None则从环境变量获取
    
    Returns:
        bool: 发送是否成功
    """
    # TODO: 实现Discord通知功能
    logger.info(f"Discord通知功能待实现: {message[:50]}...")
    return False 