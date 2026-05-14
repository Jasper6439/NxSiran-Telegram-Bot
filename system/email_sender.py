"""
邮件发送模块 - v1.4.12.13
支持 Gmail SMTP 发送验证码邮件
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def get_smtp_config():
    """从配置文件获取 SMTP 设置"""
    from config import load_config
    config = load_config()
    return {
        'smtp_email': config.get('smtp_email', ''),
        'smtp_password': config.get('smtp_password', ''),
        'smtp_server': config.get('smtp_server', 'smtp.gmail.com'),
        'smtp_port': int(config.get('smtp_port', 587)),
    }


def is_smtp_configured():
    """检查 SMTP 是否已配置"""
    cfg = get_smtp_config()
    return bool(cfg['smtp_email'] and cfg['smtp_password'])


async def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    发送邮件
    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        html_body: HTML 格式的邮件正文
    Returns:
        bool: 是否发送成功
    """
    cfg = get_smtp_config()
    if not cfg['smtp_email'] or not cfg['smtp_password']:
        logger.warning("[邮件] SMTP 未配置，跳过发送")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = cfg['smtp_email']
        msg['To'] = to_email

        # 纯文本备用
        import re
        text_body = re.sub(r'<[^>]+>', '', html_body)

        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # 使用 SMTP 发送
        server = smtplib.SMTP(cfg['smtp_server'], cfg['smtp_port'])
        server.starttls()
        server.login(cfg['smtp_email'], cfg['smtp_password'])
        server.sendmail(cfg['smtp_email'], to_email, msg.as_string())
        server.quit()

        logger.info(f"[邮件] 发送成功: {to_email} - {subject}")
        return True
    except Exception as e:
        logger.error(f"[邮件] 发送失败: {e}")
        return False


async def send_verification_code(to_email: str, code: str) -> bool:
    """发送验证码邮件"""
    subject = "恋爱至上主义区域 - 验证码"
    html_body = f"""
    <div style="max-width:480px;margin:0 auto;padding:24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
        <div style="text-align:center;margin-bottom:24px;">
            <div style="font-size:24px;font-weight:bold;color:#7c3aed;">恋爱至上主义区域</div>
            <div style="font-size:12px;color:#9ca3af;">LOVE SUPREMACY ZONE</div>
        </div>
        <div style="background:#f9fafb;border-radius:12px;padding:24px;text-align:center;">
            <div style="font-size:14px;color:#6b7280;margin-bottom:16px;">您的验证码是</div>
            <div style="font-size:36px;font-weight:bold;color:#7c3aed;letter-spacing:8px;margin-bottom:16px;">{code}</div>
            <div style="font-size:12px;color:#9ca3af;">验证码 10 分钟内有效，请勿泄露给他人</div>
        </div>
        <div style="text-align:center;margin-top:16px;font-size:11px;color:#d1d5db;">
            如果这不是您本人的操作，请忽略此邮件
        </div>
    </div>
    """
    return await send_email(to_email, subject, html_body)
