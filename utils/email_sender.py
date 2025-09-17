#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送工具类
支持SMTP邮件发送，用于系统通知

注意：
- 必须使用邮箱的授权码，不是登录密码
- 授权码获取方法：
  * QQ邮箱：设置 -> 账户 -> 开启SMTP服务 -> 生成授权码
  * 163邮箱：设置 -> POP3/SMTP/IMAP -> 开启SMTP服务 -> 客户端授权密码
  * Gmail：账户设置 -> 安全性 -> 应用专用密码
  * Outlook：账户设置 -> 安全性 -> 应用密码
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import List, Optional, Dict, Any
import traceback
import os

from config.settings import settings


class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        """初始化邮件发送器"""
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.auth_code = settings.SMTP_AUTH_CODE  # 使用授权码而不是密码
        self.recipient = settings.SMTP_RECIPIENT
        self.use_ssl = settings.SMTP_USE_SSL
        self.use_tls = settings.SMTP_USE_TLS
        self.enabled = settings.EMAIL_ENABLED
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证邮件配置"""
        print(f"🔍 验证邮件配置...")
        print(f"   邮件启用状态: {self.enabled}")
        print(f"   SMTP服务器: {self.smtp_server}")
        print(f"   SMTP端口: {self.smtp_port}")
        print(f"   用户名: {self.username}")
        print(f"   授权码: {'已设置' if self.auth_code else '未设置'}")
        print(f"   收件人: {self.recipient}")
        print(f"   使用SSL: {self.use_ssl}")
        print(f"   使用TLS: {self.use_tls}")
        
        if not self.enabled:
            print("⚠️ 邮件通知已禁用")
            return False
            
        if not all([self.smtp_server, self.username, self.auth_code, self.recipient]):
            print("⚠️ 邮件配置不完整，请检查SMTP_SERVER, SMTP_USERNAME, SMTP_AUTH_CODE, SMTP_RECIPIENT")
            return False
            
        print(f"✅ 邮件配置验证通过: {self.smtp_server}:{self.smtp_port}")
        return True
    
    def send_email(self, subject: str, body: str, recipients: Optional[List[str]] = None, 
                   html_body: Optional[str] = None, attachments: Optional[List[str]] = None) -> bool:
        """
        发送邮件
        
        Args:
            subject: 邮件主题
            body: 邮件正文（纯文本）
            recipients: 收件人列表，如果为None则使用配置中的默认收件人
            html_body: HTML格式的邮件正文（可选）
            attachments: 附件文件路径列表（可选）
            
        Returns:
            bool: 发送是否成功
        """
        if not self.enabled:
            print("⚠️ 邮件通知已禁用，跳过发送")
            return False
            
        if not self._validate_config():
            return False
            
        try:
            # 创建邮件对象
            msg = MIMEMultipart('alternative')
            msg['From'] = self.username
            msg['To'] = ', '.join(recipients) if recipients else self.recipient
            msg['Subject'] = subject
            
            # 添加纯文本正文
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # 添加HTML正文（如果提供）
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # 添加附件
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self._add_attachment(msg, file_path)
                    else:
                        print(f"⚠️ 附件文件不存在: {file_path}")
            
            # 发送邮件
            return self._send_message(msg, recipients)
            
        except Exception as e:
            print(f"❌ 发送邮件失败: {e}")
            traceback.print_exc()
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """添加附件到邮件"""
        try:
            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            filename = os.path.basename(file_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            msg.attach(part)
            print(f"✅ 已添加附件: {filename}")
            
        except Exception as e:
            print(f"⚠️ 添加附件失败 {file_path}: {e}")
    
    def _send_message(self, msg: MIMEMultipart, recipients: Optional[List[str]] = None) -> bool:
        """发送邮件消息"""
        try:
            # 确定收件人
            to_emails = recipients if recipients else [self.recipient]
            
            # 创建SMTP连接
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            # 启用TLS（如果需要）
            if self.use_tls and not self.use_ssl:
                server.starttls()
            
            # 登录（使用邮箱授权码）
            server.login(self.username, self.auth_code)
            
            # 发送邮件
            server.send_message(msg, from_addr=self.username, to_addrs=to_emails)
            
            # 关闭连接
            server.quit()
            
            print(f"✅ 邮件发送成功: {msg['Subject']} -> {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            print(f"❌ SMTP发送失败: {e}")
            return False
    
    def send_notification(self, title: str, content: str, notification_type: str = "info") -> bool:
        """
        发送系统通知邮件
        
        Args:
            title: 通知标题
            content: 通知内容
            notification_type: 通知类型 (info, warning, error, success)
            
        Returns:
            bool: 发送是否成功
        """
        # 根据类型设置主题前缀
        type_icons = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "error": "❌",
            "success": "✅"
        }
        
        icon = type_icons.get(notification_type, "ℹ️")
        subject = f"{icon} {title}"
        
        # 构建邮件正文
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        body = f"""
{content}

---
发送时间: {timestamp}
系统: 量化交易资金费率监控系统
        """.strip()
        
        # 构建HTML正文
        html_body = f"""
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; }}
        .footer {{ color: #666; font-size: 12px; margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee; }}
        .{notification_type} {{ color: {'#d32f2f' if notification_type == 'error' else '#f57c00' if notification_type == 'warning' else '#388e3c' if notification_type == 'success' else '#1976d2'}; }}
    </style>
</head>
<body>
    <div class="content">
        <h2 class="{notification_type}">{icon} {title}</h2>
        <p>{content.replace(chr(10), '<br>')}</p>
    </div>
    <div class="footer">
        <p>发送时间: {timestamp}</p>
        <p>系统: 量化交易资金费率监控系统</p>
    </div>
</body>
</html>
        """
        
        return self.send_email(subject, body, html_body=html_body)
    
    def send_funding_rate_warning(self, symbol: str, funding_rate: float, mark_price: float, 
                                volume_24h: float, next_funding_time: str = "未知") -> bool:
        """
        发送资金费率警告邮件
        
        Args:
            symbol: 合约符号
            funding_rate: 资金费率
            mark_price: 标记价格
            volume_24h: 24小时成交量
            next_funding_time: 下次结算时间
            
        Returns:
            bool: 发送是否成功
        """
        direction = "多头" if funding_rate > 0 else "空头"
        
        title = f"资金费率警告: {symbol}"
        content = f"""
合约: {symbol}
资金费率: {funding_rate:.4%} ({direction})
标记价格: ${mark_price:.4f}
24h成交量: {volume_24h:,.0f}
下次结算时间: {next_funding_time}

请注意：该合约资金费率已超过阈值 {settings.FUNDING_RATE_THRESHOLD:.1%}，建议关注。
        """.strip()
        
        return self.send_notification(title, content, "warning")
    
    def send_pool_change_notification(self, added_contracts: List[str], removed_contracts: List[str]) -> bool:
        """
        发送监控池变化通知邮件
        
        Args:
            added_contracts: 新增合约列表
            removed_contracts: 移除合约列表
            
        Returns:
            bool: 发送是否成功
        """
        title = "监控池变化通知"
        
        content_parts = []
        if added_contracts:
            content_parts.append(f"🔺 新增合约: {', '.join(added_contracts)}")
        if removed_contracts:
            content_parts.append(f"🔻 移除合约: {', '.join(removed_contracts)}")
        
        content = f"""
监控池已更新：

{chr(10).join(content_parts)}

当前监控池状态已同步更新。
        """.strip()
        
        notification_type = "info"
        if added_contracts and removed_contracts:
            notification_type = "warning"
        elif added_contracts:
            notification_type = "success"
        elif removed_contracts:
            notification_type = "warning"
        
        return self.send_notification(title, content, notification_type)
    
    def send_system_status_notification(self, status: str, details: str = "") -> bool:
        """
        发送系统状态通知邮件
        
        Args:
            status: 系统状态
            details: 详细信息
            
        Returns:
            bool: 发送是否成功
        """
        title = f"系统状态通知: {status}"
        content = f"""
系统状态: {status}

{details if details else "系统运行正常"}
        """.strip()
        
        return self.send_notification(title, content, "info")
    
    def send_test_email(self) -> bool:
        """发送测试邮件"""
        title = "邮件配置测试"
        content = """
这是一封测试邮件，用于验证邮件配置是否正确。

如果您收到这封邮件，说明：
1. SMTP服务器配置正确
2. 邮箱账号和密码有效
3. 邮件发送功能正常

系统将能够正常发送通知邮件。
        """.strip()
        
        return self.send_notification(title, content, "info")


# 便捷函数
def send_email_notification(title: str, content: str, notification_type: str = "info") -> bool:
    """便捷函数：发送邮件通知"""
    try:
        email_sender = EmailSender()
        return email_sender.send_notification(title, content, notification_type)
    except Exception as e:
        print(f"❌ 发送邮件通知失败: {e}")
        return False


def send_funding_rate_warning_email(symbol: str, funding_rate: float, mark_price: float, 
                                   volume_24h: float, next_funding_time: str = "未知") -> bool:
    """便捷函数：发送资金费率警告邮件"""
    try:
        email_sender = EmailSender()
        return email_sender.send_funding_rate_warning(symbol, funding_rate, mark_price, volume_24h, next_funding_time)
    except Exception as e:
        print(f"❌ 发送资金费率警告邮件失败: {e}")
        return False


def send_pool_change_email(added_contracts: List[str], removed_contracts: List[str]) -> bool:
    """便捷函数：发送监控池变化邮件"""
    try:
        print(f"📧 开始发送监控池变化邮件 - 入池: {added_contracts}, 出池: {removed_contracts}")
        email_sender = EmailSender()
        success = email_sender.send_pool_change_notification(added_contracts, removed_contracts)
        if success:
            print(f"✅ 监控池变化邮件发送成功")
        else:
            print(f"❌ 监控池变化邮件发送失败")
        return success
    except Exception as e:
        print(f"❌ 发送监控池变化邮件异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 测试邮件发送
    print("🧪 测试邮件发送功能...")
    
    email_sender = EmailSender()
    
    # 发送测试邮件
    success = email_sender.send_test_email()
    
    if success:
        print("✅ 测试邮件发送成功！")
    else:
        print("❌ 测试邮件发送失败")
