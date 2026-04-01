"""
通知服务模块

支持多种通知渠道：企业微信、钉钉、邮件、WebSocket 推送。
"""

import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

import aiohttp

from .config import settings
from .websocket import broadcast_notification

logger = logging.getLogger(__name__)


# ========== 通知数据结构 ==========

@dataclass
class Notification:
    """通知对象"""
    title: str
    content: str
    channel: str  # signal/trade/position/system/alert
    level: str = "info"  # info/warning/error/critical
    data: Dict[str, Any] = field(default_factory=dict)
    recipients: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "content": self.content,
            "channel": self.channel,
            "level": self.level,
            "data": self.data,
            "recipients": self.recipients,
            "timestamp": datetime.now().isoformat()
        }


# ========== 通知模板 ==========

TEMPLATES = {
    "signal_created": {
        "title": "新交易信号: {symbol} {side}",
        "content": "策略 {strategy} 产生{side}信号\n股票: {symbol} ({market})\n目标价: {price}\n止损: {stop_loss}\n止盈: {take_profit}\n理由: {reason}",
    },
    "signal_executed": {
        "title": "信号已执行: {symbol}",
        "content": "信号 #{signal_id} 已发送到 FMZ 机器人执行\n股票: {symbol}\n方向: {side}\n数量: {quantity}",
    },
    "signal_failed": {
        "title": "信号执行失败: {symbol}",
        "content": "信号 #{signal_id} 执行失败\n股票: {symbol}\n原因: {reason}",
    },
    "trade_filled": {
        "title": "交易成交: {symbol} {side}",
        "content": "股票: {symbol}\n方向: {side}\n数量: {quantity}\n价格: {price}\n金额: {amount}",
    },
    "position_changed": {
        "title": "持仓变动: {symbol}",
        "content": "股票: {symbol}\n数量: {quantity}\n成本: {avg_cost}\n当前价: {current_price}\n盈亏: {profit_pct}%",
    },
    "stop_loss_triggered": {
        "title": "⚠️ 止损触发: {symbol}",
        "content": "股票: {symbol}\n止损价: {stop_loss}\n当前价: {current_price}\n亏损: {loss_pct}%",
    },
    "system_alert": {
        "title": "系统告警: {alert_type}",
        "content": "{message}\n时间: {time}\n级别: {level}",
    },
}


def render_template(template_name: str, **kwargs) -> Dict[str, str]:
    """
    渲染通知模板

    Returns:
        {"title": str, "content": str}
    """
    template = TEMPLATES.get(template_name)
    if not template:
        return {"title": template_name, "content": str(kwargs)}

    title = template["title"].format(**kwargs)
    content = template["content"].format(**kwargs)
    return {"title": title, "content": content}


# ========== 通知渠道实现 ==========

class WechatNotifier:
    """企业微信 Webhook 通知"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    async def send(self, notification: Notification) -> bool:
        if not self.webhook_url:
            logger.debug("企业微信 Webhook 未配置，跳过通知")
            return False

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {notification.title}\n\n{notification.content}"
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        logger.info(f"企业微信通知发送成功: {notification.title}")
                        return True
                    else:
                        logger.error(f"企业微信通知失败: {result}")
                        return False
        except Exception as e:
            logger.error(f"企业微信通知异常: {e}")
            return False


class DingtalkNotifier:
    """钉钉 Webhook 通知"""

    def __init__(self, webhook_url: Optional[str] = None, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret

    async def send(self, notification: Notification) -> bool:
        if not self.webhook_url:
            logger.debug("钉钉 Webhook 未配置，跳过通知")
            return False

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": notification.title,
                "text": f"## {notification.title}\n\n{notification.content}"
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        logger.info(f"钉钉通知发送成功: {notification.title}")
                        return True
                    else:
                        logger.error(f"钉钉通知失败: {result}")
                        return False
        except Exception as e:
            logger.error(f"钉钉通知异常: {e}")
            return False


class EmailNotifier:
    """邮件通知"""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_addr: Optional[str] = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr or smtp_user

    async def send(self, notification: Notification) -> bool:
        if not self.smtp_host or not self.smtp_user:
            logger.debug("邮件 SMTP 未配置，跳过通知")
            return False

        if not notification.recipients:
            logger.debug("无收件人，跳过邮件通知")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[OpenClaw] {notification.title}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(notification.recipients)

        # 纯文本版本
        text_content = notification.content
        msg.attach(MIMEText(text_content, "plain", "utf-8"))

        # HTML 版本
        html_content = f"""
        <html><body>
        <h2>{notification.title}</h2>
        <pre style="font-size:14px;line-height:1.6">{notification.content}</pre>
        <hr>
        <p style="color:#999;font-size:12px">
            OpenClaw 量化交易平台 · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
        </body></html>
        """
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_smtp,
                msg
            )
            logger.info(f"邮件通知发送成功: {notification.title} -> {notification.recipients}")
            return True
        except Exception as e:
            logger.error(f"邮件通知异常: {e}")
            return False

    def _send_smtp(self, msg):
        """同步发送 SMTP 邮件"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.smtp_port == 587:
                server.starttls()
            if self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)


# ========== 通知调度器 ==========

class NotificationService:
    """统一通知调度服务"""

    def __init__(self):
        self._notifiers = {}
        self._setup_default_notifiers()

    def _setup_default_notifiers(self):
        """根据配置初始化通知渠道"""
        # 企业微信
        wechat_url = getattr(settings, 'wechat_webhook_url', None)
        if wechat_url:
            self._notifiers['wechat'] = WechatNotifier(wechat_url)

        # 钉钉
        dingtalk_url = getattr(settings, 'dingtalk_webhook_url', None)
        if dingtalk_url:
            self._notifiers['dingtalk'] = DingtalkNotifier(dingtalk_url)

        # 邮件
        smtp_host = getattr(settings, 'smtp_host', None)
        if smtp_host:
            self._notifiers['email'] = EmailNotifier(
                smtp_host=smtp_host,
                smtp_port=getattr(settings, 'smtp_port', 587),
                smtp_user=getattr(settings, 'smtp_user', None),
                smtp_password=getattr(settings, 'smtp_password', None),
            )

    def add_notifier(self, name: str, notifier):
        """添加自定义通知渠道"""
        self._notifiers[name] = notifier

    async def send(self, notification: Notification, channels: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        发送通知到多个渠道

        Args:
            notification: 通知对象
            channels: 指定渠道列表（None 则发送到所有已配置渠道）

        Returns:
            {channel_name: success_bool}
        """
        targets = channels or list(self._notifiers.keys())
        results = {}

        for name in targets:
            notifier = self._notifiers.get(name)
            if notifier:
                try:
                    results[name] = await notifier.send(notification)
                except Exception as e:
                    logger.error(f"通知渠道 {name} 发送失败: {e}")
                    results[name] = False

        # 始终通过 WebSocket 推送
        try:
            await broadcast_notification(notification.to_dict())
            results["websocket"] = True
        except Exception as e:
            logger.error(f"WebSocket 推送失败: {e}")
            results["websocket"] = False

        return results

    async def send_from_template(
        self,
        template_name: str,
        channel: str,
        level: str = "info",
        recipients: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, bool]:
        """
        从模板发送通知

        Args:
            template_name: 模板名称
            channel: 通知频道
            level: 通知级别
            recipients: 收件人列表（邮件用）
            **kwargs: 模板参数
        """
        rendered = render_template(template_name, **kwargs)
        notification = Notification(
            title=rendered["title"],
            content=rendered["content"],
            channel=channel,
            level=level,
            data=kwargs,
            recipients=recipients or [],
        )
        return await self.send(notification)


# 全局通知服务实例
notification_service = NotificationService()
