"""
bot_instance.py - 单个角色 Bot 实例
=====================================
每个角色（车如云等）对应一个独立的 Telegram Bot 实例。
共享 AI 客户端、数据库等基础设施，但拥有独立的数据目录和配置。
"""

import asyncio
import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest


class BotInstance:
    """单个角色 Bot 实例"""

    def __init__(self, bot_config: dict):
        self.bot_id = bot_config["id"]
        self.name = bot_config["name"]
        self.token = bot_config["token"]
        self.character_id = bot_config.get("character_id", self.bot_id)
        self.data_dir = bot_config.get("data_dir", f"/opt/NxSiran/data/{self.bot_id}")
        self.owner_chat_id = bot_config.get("owner_chat_id", 0)
        self.enabled = bot_config.get("enabled", True)

        # 确保数据目录
        os.makedirs(self.data_dir, exist_ok=True)

        # 子目录
        self.log_dir = os.path.join(self.data_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        # 全局状态（每个实例独立）
        self.TELEGRAM_TOKEN = self.token
        self.YOUR_CHAT_ID = self.owner_chat_id
        self.AI_API_BASE = os.environ.get("AI_API_BASE", "https://openrouter.ai/api/v1")
        self.AI_API_KEY = os.environ.get("AI_API_KEY", "")
        self.AI_MODEL = os.environ.get("AI_MODEL", "minimax/minimax-m2.5:free")
        self.PORT = int(os.environ.get("PORT", 8080))

        # Application 实例
        self.app: Optional[Application] = None

        # 初始化日志
        self._setup_logging()

    def _setup_logging(self):
        """为当前实例设置独立日志"""
        log_file = os.path.join(self.log_dir, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

        # 创建实例专用的 logger
        self.logger = logging.getLogger(f"bot.{self.bot_id}")
        self.logger.setLevel(logging.INFO)

        # 避免重复添加 handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            formatter = logging.Formatter(
                f"%(asctime)s [{self.name}] %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.addHandler(file_handler)

    def _load_json(self, filepath, default=None):
        """加载 JSON 文件"""
        if default is None:
            default = []
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"加载文件失败 {filepath}: {e}")
        return default

    def _save_json(self, filepath, data):
        """保存 JSON 文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存文件失败 {filepath}: {e}")

    def get_history(self, chat_id: int) -> list:
        """获取聊天记录"""
        history_file = os.path.join(self.data_dir, f"user_{chat_id}", "chat_history.json")
        data = self._load_json(history_file, {})
        return data.get(str(chat_id), data.get(chat_id, []))

    def save_history(self, chat_id: int, history: list):
        """保存聊天记录"""
        history_file = os.path.join(self.data_dir, f"user_{chat_id}", "chat_history.json")
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        data = self._load_json(history_file, {})
        data[str(chat_id)] = history
        self._save_json(history_file, data)

    def get_memory_file(self, chat_id: int) -> str:
        """获取记忆文件路径"""
        return os.path.join(self.data_dir, f"user_{chat_id}", "long_term_memory.json")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """消息处理入口（简化版，实际应复用 bot.py 的 handle_message）"""
        chat_id = update.effective_chat.id
        user_text = update.message.text

        if not user_text:
            return

        self.logger.info(f"[{chat_id}] {user_text[:50]}")

        # TODO: 复用 bot.py 的完整 handle_message 逻辑
        # 这里先提供一个简单的回复用于测试

        await update.message.reply_text(f"...（{self.name} 收到消息，功能迁移中）")

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """启动命令"""
        await update.message.reply_text(f"...{self.name} 已上线。")

    async def post_init(self, app: Application):
        """初始化后回调"""
        await app.bot.set_my_commands([
            BotCommand("start", "开始对话"),
            BotCommand("reset", "重置对话"),
            BotCommand("help", "帮助"),
        ])
        self.logger.info(f"✅ {self.name} 已上线！")

    async def run(self):
        """启动 Bot 实例"""
        if not self.enabled:
            self.logger.info(f"⏭️ {self.name} 已禁用，跳过")
            return

        self.logger.info(f"🚀 {self.name} Bot 启动中... (token: {self.token[:10]}...)")

        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=60.0,
            write_timeout=30.0,
            pool_timeout=30.0,
        )

        self.app = Application.builder().token(self.token).request(request).post_init(self.post_init).build()

        # 注册命令
        self.app.add_handler(CommandHandler("start", self.handle_start))
        self.app.add_handler(CommandHandler("reset", self.handle_start))
        self.app.add_handler(CommandHandler("help", self.handle_start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        self.logger.info(f"📋 {self.name} 命令处理器已注册")

        # 运行 polling
        try:
            await self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
        except Exception as e:
            self.logger.error(f"Bot 运行错误: {e}")
            raise

    def __repr__(self):
        return f"BotInstance(id={self.bot_id}, name={self.name}, enabled={self.enabled})"
