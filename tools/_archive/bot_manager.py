#!/usr/bin/env python3
"""
bot_manager.py - 多 Bot 实例管理器
===================================
为每个角色启动独立的 bot.py 进程，共享代码但隔离数据。
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Dict, List

logging.basicConfig(
    format="%(asctime)s [Manager] %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot_manager")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bots_config.json")

running_processes: Dict[str, subprocess.Popen] = {}


def load_config() -> dict:
    """加载多 Bot 配置"""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"配置文件不存在: {CONFIG_FILE}")
        return {"bots": []}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def start_bot(bot_config: dict) -> subprocess.Popen:
    """启动单个 Bot 进程"""
    bot_id = bot_config["id"]
    bot_name = bot_config["name"]
    token = bot_config["token"]
    data_dir = bot_config.get("data_dir", f"/opt/NxSiran/data/{bot_id}")
    character_id = bot_config.get("character_id", bot_id)
    owner_chat_id = bot_config.get("owner_chat_id", 0)

    logger.info(f"🚀 启动 {bot_name} ({bot_id})...")

    # 设置环境变量，供 bot.py 读取
    env = os.environ.copy()
    env["TELEGRAM_TOKEN"] = token
    env["DATA_DIR"] = data_dir
    env["BOT_ID"] = bot_id
    env["BOT_CHARACTER_ID"] = character_id
    if owner_chat_id:
        env["YOUR_CHAT_ID"] = str(owner_chat_id)

    # 启动 bot.py 子进程
    bot_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
    proc = subprocess.Popen(
        [sys.executable, bot_script],
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    running_processes[bot_id] = proc
    logger.info(f"✅ {bot_name} 进程已启动 (PID: {proc.pid})")
    return proc


def stop_bot(bot_id: str):
    """停止单个 Bot 进程"""
    if bot_id in running_processes:
        proc = running_processes[bot_id]
        if proc.poll() is None:
            logger.info(f"🛑 停止 {bot_id} (PID: {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        del running_processes[bot_id]


def monitor():
    """监控所有 Bot 进程"""
    while running_processes:
        time.sleep(5)
        for bot_id, proc in list(running_processes.items()):
            if proc.poll() is not None:
                # 进程已退出
                exit_code = proc.poll()
                logger.warning(f"⚠️ {bot_id} 已退出 (code: {exit_code})")
                # 读取最后几行日志
                if proc.stdout:
                    try:
                        lines = proc.stdout.readlines()
                        for line in lines[-10:]:
                            logger.warning(f"  {line.strip()}")
                    except:
                        pass
                del running_processes[bot_id]


def main():
    """主入口"""
    config = load_config()
    bots = config.get("bots", [])

    if not bots:
        logger.error("没有配置任何 Bot，请在 bots_config.json 中添加")
        sys.exit(1)

    enabled_bots = [b for b in bots if b.get("enabled", True)]
    if not enabled_bots:
        logger.warning("所有 Bot 都已禁用")
        sys.exit(0)

    logger.info(f"准备启动 {len(enabled_bots)} 个 Bot 实例")

    for bot_config in enabled_bots:
        start_bot(bot_config)

    # 设置信号处理
    def handle_signal(signum, frame):
        logger.info("收到退出信号，正在停止所有 Bot...")
        for bot_id in list(running_processes.keys()):
            stop_bot(bot_id)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # 监控
    try:
        monitor()
    except KeyboardInterrupt:
        handle_signal(signal.SIGINT, None)


if __name__ == "__main__":
    main()
