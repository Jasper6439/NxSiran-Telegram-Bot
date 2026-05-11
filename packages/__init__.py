"""
NxSiran Telegram Bot - 模块化包
================================
bot.py 已拆分为以下子模块：
- commands/    : Telegram 命令处理器
- handlers/    : 消息处理器（核心对话逻辑）
- web/         : Web API 路由
- importers/   : 视频和聊天记录导入
- services/    : TTS/语音等服务
- analysis/    : 聊天记录解析分析
- bridge/      : VM 桥接功能
"""
import sys
import os

# 确保项目根目录在 Python 路径中，以便子模块可以导入 auth、prompts 等
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
