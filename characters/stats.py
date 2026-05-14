"""
统计和额度系统模块
==================
从 bot.py 提取的聊天统计、额度追踪和报告系统。
"""

from datetime import datetime

from config import (
    QUOTA_FILE,
    get_user_stats_file,
    get_user_memory_file,
    save_json,
    load_json,
    get_default_tz,
    YOUR_CHAT_ID,
    _migrate_user_data,
)

# ============================================================
# 额度限制常量
# ============================================================

QUOTA_LIMITS = {
    'requests': 2_000_000,       # 200万次请求
    'cpu_seconds': 180_000,      # 18万vCPU-秒（≈50小时）
    'memory_gib_seconds': 360_000,  # 36万GiB-秒
    'network_gb': 1,             # 1 GiB 出站流量
}

# 额度告警阈值
QUOTA_WARNING_THRESHOLD = 0.80    # 80% 警告
QUOTA_CRITICAL_THRESHOLD = 0.95   # 95% 严重警告
QUOTA_SHUTDOWN_THRESHOLD = 1.00   # 100% 自动断开

# 是否已触发断开
_quota_shutdown = False


# ============================================================
# [Skill: 对话统计] 聊天数据分析
# ============================================================

def load_stats(user_id=None) -> dict:
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    return load_json(get_user_stats_file(user_id), {})

def save_stats(stats: dict, user_id=None):
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    save_json(get_user_stats_file(user_id), stats)

def update_stats_on_message(chat_id: int):
    """每次收到消息时更新统计"""
    stats = load_stats()
    today = datetime.now(get_default_tz()).strftime("%Y-%m-%d")

    if not stats.get("first_chat_date"):
        stats["first_chat_date"] = today

    stats["total_messages"] = stats.get("total_messages", 0) + 1

    # 活跃天数
    active_days = stats.get("active_days_list", [])
    if today not in active_days:
        active_days.append(today)
        stats["active_days_list"] = active_days[-365:]  # 最多保留一年
    stats["total_days"] = len(active_days)

    # 今日消息数
    if stats.get("today_date") != today:
        stats["today_date"] = today
        stats["today_count"] = 0
    stats["today_count"] = stats.get("today_count", 0) + 1

    # 记忆数
    stats["memories_count"] = len(load_json(get_user_memory_file(chat_id), []))

    save_stats(stats, chat_id)


# ============================================================
# 额度追踪系统
# ============================================================

def get_current_month() -> str:
    """获取当前月份标识 YYYY-MM"""
    return datetime.now(get_default_tz()).strftime('%Y-%m')

def load_quota_usage() -> dict:
    """加载当月额度使用情况"""
    all_data = load_json(QUOTA_FILE, {})
    month = get_current_month()
    if month not in all_data:
        all_data[month] = {
            'requests': 0,
            'cpu_seconds': 0.0,
            'memory_gib_seconds': 0.0,
            'network_gb': 0.0,
            'ai_requests': 0,
            'image_generations': 0,
            'warnings_sent': [],
            'shutdown_triggered': False,
        }
    return all_data[month]

def save_quota_usage(usage: dict):
    """保存额度使用情况"""
    all_data = load_json(QUOTA_FILE, {})
    all_data[get_current_month()] = usage
    save_json(QUOTA_FILE, all_data)

def record_request(cpu_time: float = 0.1, memory_mb: float = 128):
    """记录一次请求的用量"""
    global _quota_shutdown
    if _quota_shutdown:
        return 'shutdown'

    usage = load_quota_usage()
    usage['requests'] += 1
    usage['cpu_seconds'] += cpu_time
    # 内存: MB 转 GiB-秒 (128MB 运行 0.1秒 = 0.0128 GiB-秒)
    usage['memory_gib_seconds'] += (memory_mb / 1024) * cpu_time
    save_quota_usage(usage)

    return check_quota_status(usage)

def record_ai_request():
    """记录一次AI请求"""
    usage = load_quota_usage()
    usage['ai_requests'] = usage.get('ai_requests', 0) + 1
    usage['cpu_seconds'] += 0.5  # AI请求消耗更多CPU
    usage['memory_gib_seconds'] += 0.05  # 额外内存消耗
    save_quota_usage(usage)

def record_image_generation():
    """记录一次图片生成"""
    usage = load_quota_usage()
    usage['image_generations'] = usage.get('image_generations', 0) + 1
    usage['network_gb'] += 0.001  # 估算图片大小
    save_quota_usage(usage)

def check_quota_status(usage: dict = None) -> str:
    """检查额度状态，返回: ok / warning / critical / shutdown"""
    global _quota_shutdown

    if usage is None:
        usage = load_quota_usage()

    if _quota_shutdown:
        return 'shutdown'

    get_current_month()
    warnings = usage.get('warnings_sent', [])

    # 检查各项额度
    checks = [
        ('请求', usage['requests'], QUOTA_LIMITS['requests']),
        ('CPU', usage['cpu_seconds'], QUOTA_LIMITS['cpu_seconds']),
        ('内存', usage['memory_gib_seconds'], QUOTA_LIMITS['memory_gib_seconds']),
        ('流量', usage['network_gb'], QUOTA_LIMITS['network_gb']),
    ]

    max_usage = 0.0
    triggered_items = []

    for name, used, limit in checks:
        ratio = used / limit if limit > 0 else 0
        max_usage = max(max_usage, ratio)

        if ratio >= QUOTA_SHUTDOWN_THRESHOLD and 'shutdown' not in warnings:
            triggered_items.append(('shutdown', name, ratio))
        elif ratio >= QUOTA_CRITICAL_THRESHOLD and f'critical_{name}' not in warnings:
            triggered_items.append(('critical', name, ratio))
        elif ratio >= QUOTA_WARNING_THRESHOLD and f'warning_{name}' not in warnings:
            triggered_items.append(('warning', name, ratio))

    # 处理触发的告警
    for level, name, ratio in triggered_items:
        if level == 'shutdown':
            warnings.append('shutdown')
            usage['warnings_sent'] = warnings
            usage['shutdown_triggered'] = True
            save_quota_usage(usage)
            _quota_shutdown = True
            return 'shutdown'
        elif level == 'critical':
            warnings.append(f'critical_{name}')
            usage['warnings_sent'] = warnings
            save_quota_usage(usage)
            return 'critical'
        elif level == 'warning':
            warnings.append(f'warning_{name}')
            usage['warnings_sent'] = warnings
            save_quota_usage(usage)
            return 'warning'

    return 'ok'

def reset_quota_warning(name: str = None):
    """重置指定项的告警状态"""
    usage = load_quota_usage()
    warnings = usage.get('warnings_sent', [])

    if name:
        warnings = [w for w in warnings if name not in w]
    else:
        warnings = []

    usage['warnings_sent'] = warnings
    save_quota_usage(usage)

def format_quota_report() -> str:
    """生成额度使用报告"""
    usage = load_quota_usage()
    month = get_current_month()

    def bar(used, limit, width=15):
        ratio = min(used / limit, 1.0) if limit > 0 else 0
        filled = int(ratio * width)
        if ratio >= QUOTA_SHUTDOWN_THRESHOLD:
            color = '🔴'
        elif ratio >= QUOTA_CRITICAL_THRESHOLD:
            color = '🟠'
        elif ratio >= QUOTA_WARNING_THRESHOLD:
            color = '🟡'
        else:
            color = '🟢'
        return f"{color}{'█' * filled}{'░' * (width - filled)} {ratio * 100:.1f}%"

    # 估算剩余天数
    days_in_month = 30
    current_day = datetime.now(get_default_tz()).day
    remaining_days = days_in_month - current_day

    # 估算每日用量
    daily_req = usage['requests'] / current_day if current_day > 0 else 0
    daily_cpu = usage['cpu_seconds'] / current_day if current_day > 0 else 0

    # 预计月底用量
    projected_req = daily_req * days_in_month
    projected_cpu = daily_cpu * days_in_month
    projected_req_pct = projected_req / QUOTA_LIMITS['requests'] * 100
    projected_cpu_pct = projected_cpu / QUOTA_LIMITS['cpu_seconds'] * 100

    report = (
        f"...明要看用量吗。\n\n"
        f"📊 免费额度使用报告（{month}）\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📨 请求次数\n"
        f"  {bar(usage['requests'], QUOTA_LIMITS['requests'])}\n"
        f"  {usage['requests']:,} / {QUOTA_LIMITS['requests']:,}\n"
        f"  预计月底: {projected_req:,.0f}（{projected_req_pct:.1f}%）\n\n"
        f"⚡ CPU 时间\n"
        f"  {bar(usage['cpu_seconds'], QUOTA_LIMITS['cpu_seconds'])}\n"
        f"  {usage['cpu_seconds']:,.0f}秒 / {QUOTA_LIMITS['cpu_seconds']:,}秒\n"
        f"  预计月底: {projected_cpu:,.0f}秒（{projected_cpu_pct:.1f}%）\n\n"
        f"💾 内存使用\n"
        f"  {bar(usage['memory_gib_seconds'], QUOTA_LIMITS['memory_gib_seconds'])}\n"
        f"  {usage['memory_gib_seconds']:,.1f} / {QUOTA_LIMITS['memory_gib_seconds']:,} GiB-秒\n\n"
        f"🌐 网络流量\n"
        f"  {bar(usage['network_gb'], QUOTA_LIMITS['network_gb'])}\n"
        f"  {usage['network_gb']:.3f} GB / {QUOTA_LIMITS['network_gb']} GB\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 AI请求: {usage.get('ai_requests', 0)} 次\n"
        f"🎨 图片生成: {usage.get('image_generations', 0)} 次\n"
        f"📅 剩余天数: {remaining_days} 天\n"
    )

    # 状态判断
    status = check_quota_status(usage)
    if status == 'shutdown':
        report += "\n\n🚫 已触发自动断开！额度已用完。"
        report += "\n下月1号自动恢复，或使用 /quota_reset 重置。"
    elif status == 'critical':
        report += "\n\n🟠 ⚠️ 额度即将用完！请注意控制使用。"
    elif status == 'warning':
        report += "\n\n🟡 额度已使用超过80%，请注意。"
    else:
        report += "\n\n🟢 状态正常，预计本月额度充足。"

    return report
