"""
通知桥接模块
============
统一将 Web 端游戏事件推送到 Telegram。

提供底层消息发送接口和高级游戏事件通知接口，
被 game_state.notify_state_change 等模块调用。
通知发送失败时只记录 warning 日志，不抛出异常（通知不是关键路径）。
"""

import asyncio
import functools
import logging
import random
from typing import Optional, Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================
# 重试装饰器
# ============================================================

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: tuple = (Exception,),
):
    """重试装饰器，支持指数退避和抖动。

    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟秒数
        max_delay: 最大延迟秒数
        exponential_base: 指数退避基数
        jitter: 是否添加随机抖动
        retry_exceptions: 触发重试的异常类型元组

    Returns:
        装饰后的函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # 最后一次尝试失败，不再重试
                        logger.error(
                            f"[重试] {func.__name__} 失败，已重试 {max_retries} 次: {e}"
                        )
                        raise

                    # 计算延迟（指数退避）
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    # 添加抖动（防止重试风暴）
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"[重试] {func.__name__} 第 {attempt + 1} 次失败: {e}，"
                        f"{delay:.2f}s 后重试"
                    )

                    await asyncio.sleep(delay)

            # 理论上不会到达这里
            raise last_exception

        return wrapper
    return decorator


# ============================================================
# tg_app 实例管理
# ============================================================

# 运行时保存的 tg_app 实例引用（由 set_tg_app 设置）
_tg_app_instance = None


def set_tg_app(app):
    """设置全局 tg_app 实例引用。

    在 main.py 的 post_init 回调中调用，
    将 tg_app 实例保存到 notification 模块中。

    Args:
        app: telegram.ext.Application 实例
    """
    global _tg_app_instance
    _tg_app_instance = app
    logger.info("[通知] tg_app 实例已设置")


# ============================================================
# 底层消息发送（带重试）
# ============================================================

@with_retry(max_retries=3, base_delay=1.0, exponential_base=2.0)
async def _send_message_with_retry(
    bot,
    chat_id: int,
    text: str,
    parse_mode: str = "HTML"
) -> bool:
    """带重试的消息发送核心逻辑。

    Args:
        bot: Telegram Bot 实例
        chat_id: 目标 chat_id
        text: 消息文本
        parse_mode: 解析模式

    Returns:
        发送是否成功
    """
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
    )
    return True


async def send_telegram_notification(user_id: int, message: str, parse_mode: str = "HTML") -> bool:
    """发送 Telegram 通知消息（带重试机制）。

    通过 main.py 中创建的 tg_app 实例发送消息。
    遇到网络错误时自动重试 3 次（指数退避：1s, 2s, 4s）。
    失败时只记录日志，不抛出异常（通知不是关键路径）。

    Args:
        user_id: 目标用户的 Telegram chat_id
        message: 要发送的消息文本
        parse_mode: 消息解析模式，默认 "HTML"

    Returns:
        bool: 发送是否成功
    """
    try:
        app = _tg_app_instance
        if app is None:
            logger.warning("[通知] tg_app 实例不可用，无法发送通知")
            return False

        await _send_message_with_retry(
            bot=app.bot,
            chat_id=user_id,
            text=message,
            parse_mode=parse_mode,
        )
        logger.info(f"[通知] 已发送通知给用户 {user_id}")
        return True

    except Exception as e:
        # 所有重试失败后，只记录日志，不抛出异常
        logger.error(f"[通知] 发送 Telegram 通知失败（已重试 3 次）: {e}")
        return False


# ============================================================
# 高级游戏事件通知
# ============================================================

# 事件类型对应的通知模板
_EVENT_TEMPLATES = {
    "crop_ready": (
        "\U0001F33E <b>作物成熟</b>\n"
        "学长，农场里的作物已经成熟了，快去收获吧！"
    ),
    "heart_event": (
        "\u2764\uFE0F <b>心级事件</b>\n"
        "和如云的关系发生了变化……"
    ),
    "cooking_complete": (
        "\U0001F373 <b>烹饪完成</b>\n"
        "学长，料理做好了！快来尝尝吧。"
    ),
    "level_up": (
        "\U0001F31F <b>升级</b>\n"
        "恭喜学长升级了！如云……稍微有点开心。"
    ),
}


async def notify_game_event(user_id: int, event_type: str, event_data: Optional[dict] = None) -> bool:
    """发送游戏事件通知。

    根据事件类型生成友好的中文通知消息，并发送到 Telegram。

    Args:
        user_id: 目标用户的 Telegram chat_id
        event_type: 事件类型，支持:
            - "crop_ready": 作物成熟
            - "heart_event": 心级事件
            - "cooking_complete": 烹饪完成
            - "level_up": 升级
        event_data: 事件附加数据（可选），可用于生成更详细的通知消息

    Returns:
        bool: 发送是否成功
    """
    event_data = event_data or {}

    if event_type in _EVENT_TEMPLATES:
        message = _EVENT_TEMPLATES[event_type]
    else:
        logger.warning(f"[通知] 未知事件类型: {event_type}")
        message = f"\u26A0\uFE0F <b>游戏事件</b>\n{event_type}"

    # 如果有附加数据，追加到消息中
    if event_data:
        detail_parts = []
        if "detail" in event_data:
            detail_parts.append(str(event_data["detail"]))
        if "crop_name" in event_data:
            detail_parts.append(f"作物: {event_data['crop_name']}")
        if "new_level" in event_data:
            detail_parts.append(f"新等级: Lv.{event_data['new_level']}")
        if "hearts" in event_data:
            detail_parts.append(f"心级: {event_data['hearts']}")
        if detail_parts:
            message += "\n\n" + "\n".join(detail_parts)

    return await send_telegram_notification(user_id, message)


# ============================================================
# Web -> Telegram 状态变更桥接
# ============================================================

# 需要通知的重要变更 key 关键词
_IMPORTANT_CHANGE_KEYS = {
    "crop_ready",            # 作物成熟
    "heart",                 # 心级事件
    "hearts",                # 心级数值变化
    "relationship",          # 关系变化
    "relationshipStatus",    # 关系状态变化
    "level",                 # 等级变化
    "cooking",               # 烹饪相关
}


async def bridge_web_to_telegram(user_id: int, changed_keys: list):
    """桥接 Web 端游戏状态变更到 Telegram 通知。

    被 game_state.notify_state_change 调用。
    根据变更的 keys 判断是否需要发送 Telegram 通知（不是所有变更都通知）。

    只通知重要事件：作物成熟、心级事件、关系变化。

    Args:
        user_id: 用户 ID
        changed_keys: 发生变更的状态 key 列表
    """
    if not changed_keys:
        return

    # 判断是否有重要变更
    important_events = []
    for key in changed_keys:
        # 检查 key 是否包含重要关键词
        for important_key in _IMPORTANT_CHANGE_KEYS:
            if important_key in key:
                important_events.append((key, important_key))
                break

    if not important_events:
        return

    # 根据重要事件类型调度通知
    for key, event_keyword in important_events:
        try:
            if event_keyword == "crop_ready":
                await notify_game_event(user_id, "crop_ready", {"detail": key})
            elif event_keyword in ("heart", "hearts"):
                await notify_game_event(user_id, "heart_event", {"detail": key})
            elif event_keyword in ("relationship", "relationshipStatus"):
                await notify_game_event(user_id, "heart_event", {"detail": key})
            elif event_keyword == "level":
                await notify_game_event(user_id, "level_up", {"detail": key})
            elif event_keyword == "cooking":
                await notify_game_event(user_id, "cooking_complete", {"detail": key})
        except Exception as e:
            # 通知失败不应该影响主流程
            logger.warning(f"[通知] 桥接通知失败 ({key}): {e}")
