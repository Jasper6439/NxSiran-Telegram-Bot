"""
车如云 Telegram Bot - Wispbyte 部署版 v3.5
=============================================
v3.5 Skill集成：
  [agent-orchestration] 5层Prompt架构优化系统提示词
  [gemini] Gemini API集成（备选AI + /gemini命令）
  [vision-sandbox] 图片深度分析（Gemini Vision）
  [deepread-ocr] 文档OCR文字提取（Gemini Vision替代）
  [gemini-deep-research] 深度研究（/research命令）
  [relay-for-telegram] Telegram消息历史搜索（/search_msg, /my_chats）
v3.4 Skill集成：
  [semantic-memory] 语义记忆系统（自动提取+搜索+删除）
  [claw-summarize-pro] 摘要生成（文本/URL/回复消息）
  [auto-updater] 自动更新检查（启动检测+版本管理）
v3.2 新增：
  [ui-ux-pro-max] 韩剧配色 Web 界面（聊天 + 仪表盘）
    - 访问 http://localhost:PORT/ 即可使用
    - 聊天界面：和车如云在浏览器中聊天
    - 仪表盘：查看统计数据、情绪分布、关系建议
v3.1 Skill整合：
  [notebooklm] 从原作小说提取剧情/角色设定注入AI
  [brainstorming] 深度角色设定 + OOC防护机制
  [meeting-insights] /analyze 对话模式分析
  [slack-gif-creator] /sticker 表情包生成
v3.0 功能：
  [情绪识别] [对话统计] [天气查询] [纪念日系统] [亲密度系统]
  [生活事件] [表情反应] [打字模拟] [增强记忆] [个性化主动]
原有功能：AI对话 + 6模型fallback + 长期记忆 + 主动消息 + 真人/AI自拍 + 场景生成 + 联网搜索 + 导出导入
"""

import asyncio
import threading
import base64
import hashlib
import json
import logging
import random
import os
import zipfile
import io
import re
import subprocess
from datetime import datetime

from telegram import Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from aiohttp import web

# [Skill: TTS 语音合成]
from tts_engine import TTSEngine
tts = TTSEngine()

# [统一 AI 调用模块]
from ai_client import call_ai as ai_client_call_ai

# [Phase 1 P0] 拆分模块
from config import *
from auth import *

# [Phase 2] 提示词和文本处理
from prompts import *

# [Phase 3] 拆分模块
from memory_legacy import *
from weather import *
from anniversary import *
from emotion import *
from stats import *

# [Phase 4] 拆分模块
from image_gen import *
from chat_history import *

# [v0.3 修复] bot.py 作为 __main__ 运行，但 game_api.py 用 "from bot import ..."
# 这会导致 Python 加载两个独立的模块实例，USER_SESSIONS 等全局变量不共享
# 将 bot 模块名指向 __main__，确保所有 "from bot import" 引用同一对象
import sys
if __name__ == "__main__":
    sys.modules['bot'] = sys.modules['__main__']
user_voice_enabled = {}  # {user_id: bool}

# [Skill: 音乐搜索与评价]
from music_skill import music_skill

# [Skill: Qdrant Cloud 记忆]
from qdrant_memory import search_memories

# [Skill: 小说知识库]
from novel_knowledge import query_novel, init_novel_knowledge

# [角色系统] 支持多蒸馏角色动态加载
from characters import (
    load_characters_from_dir,
    get_current_character,
    set_current_character,
    list_characters,
    register_character,
    get_character_count,
)
from characters.base import CharacterConfig
from characters.chayewoon import Character as ChayewoonCharacter

# ============================================================
# 消息自动删除装饰器
# ============================================================

def auto_delete_messages(delay: int = 5):
    """装饰器：命令完成后自动删除用户命令和Bot回复，减少非真人聊天感"""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_msg_id = update.message.message_id if update.message else None
            chat_id = update.effective_chat.id
            
            try:
                result = await func(update, context)
                
                # 延迟删除消息
                if user_msg_id and chat_id:
                    try:
                        await asyncio.sleep(delay)
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass  # 消息可能已被删除或权限不足
                
                return result
            except Exception as e:
                # 出错时也尝试删除用户消息
                if user_msg_id and chat_id:
                    try:
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass
                raise e
        return wrapper
    return decorator

# ============================================================
# 车如云系统提示词
# [Skill: agent-orchestration] 使用5层Prompt架构重构
# ============================================================


# ============================================================
# 主动消息模板（[Skill: 个性化主动] 增强）
# ============================================================





# 天气相关主动消息

# ============================================================
# 记忆系统（[Skill: 增强记忆] 增强）
# ============================================================

# ============================================================
# 微信聊天记录导入与分析
# ============================================================

def parse_wechat_chatlog(text_content: str) -> dict:
    """解析微信导出的聊天记录（支持TXT和JSON格式）"""
    
    # 尝试解析JSON格式
    try:
        data = json.loads(text_content)
        return parse_json_chatlog(data)
    except json.JSONDecodeError:
        pass
    
    # 降级到TXT格式
    return parse_txt_chatlog(text_content)

def parse_json_chatlog(data: dict) -> dict:
    """解析JSON格式的聊天记录（支持WeFlow、ChatLab等多种工具导出的格式）"""
    messages = []
    
    # 检测是否是 ChatLab 格式
    if isinstance(data, dict) and 'version' in data and 'chatLab' in str(data.get('app', '')).lower():
        return parse_chatlab_format(data)
    
    # 尝试不同的JSON结构
    if isinstance(data, list):
        # 直接是消息数组
        raw_messages = data
    elif 'data' in data:
        raw_messages = data['data']
    elif 'messages' in data:
        raw_messages = data['messages']
    elif 'chatHistory' in data:
        raw_messages = data['chatHistory']
    elif 'list' in data:
        raw_messages = data['list']
    else:
        # 尝试找到包含消息的数组
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                if isinstance(value[0], dict) and any(k in value[0] for k in ['content', 'text', 'message']):
                    raw_messages = value
                    break
        else:
            raw_messages = []
    
    # 解析每条消息
    for msg in raw_messages:
        if not isinstance(msg, dict):
            continue
            
        # 尝试提取时间和发送者
        time_str = None
        sender = None
        content = None
        
        # 时间字段
        for time_key in ['time', 'date', 'timestamp', 'createTime', 'CreateTime', 'msgTime']:
            if time_key in msg:
                ts = msg[time_key]
                if isinstance(ts, (int, float)):
                    # 时间戳
                    try:
                        from datetime import datetime
                        time_str = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        time_str = str(ts)
                else:
                    time_str = str(ts)
                break
        
        # 发送者字段
        for sender_key in ['sender', 'senderName', 'nickname', 'from', 'name', 'nickName']:
            if sender_key in msg:
                sender = str(msg[sender_key])
                break
        
        # 内容字段
        for content_key in ['content', 'text', 'message', 'msg', 'str', 'value']:
            if content_key in msg:
                content = str(msg[content_key])
                break
        
        if content:
            messages.append({
                'time': time_str or '',
                'sender': sender or '',
                'content': content
            })

def parse_chatlab_format(data: dict) -> dict:
    """解析 ChatLab 标准格式的聊天记录"""
    messages = []
    
    # ChatLab 格式通常有 messages 数组
    if 'messages' in data:
        raw_messages = data['messages']
    elif 'data' in data and isinstance(data['data'], list):
        raw_messages = data['data']
    else:
        # 尝试其他可能的字段
        for key in ['chat', 'history', 'records']:
            if key in data and isinstance(data[key], list):
                raw_messages = data[key]
                break
        else:
            raw_messages = []
    
    # 解析 ChatLab 消息
    for msg in raw_messages:
        if not isinstance(msg, dict):
            continue
        
        # ChatLab 标准字段
        time_str = msg.get('time', msg.get('timestamp', msg.get('date', '')))
        sender = msg.get('sender', msg.get('senderName', msg.get('nickname', msg.get('from', ''))))
        content = msg.get('content', msg.get('text', msg.get('message', msg.get('body', ''))))
        
        # 处理时间戳格式
        if isinstance(time_str, (int, float)):
            try:
                from datetime import datetime
                time_str = datetime.fromtimestamp(time_str / 1000 if time_str > 1e10 else time_str).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                time_str = str(time_str)
        
        if content:
            messages.append({
                'time': str(time_str),
                'sender': str(sender),
                'content': str(content)
            })
    
    # 分析发送者统计
    senders = {}
    for msg in messages:
        sender = msg['sender']
        if sender:
            senders[sender] = senders.get(sender, 0) + 1
    
    # 计算额外统计信息
    extra_stats = calculate_chat_stats(messages)
    
    return {
        'messages': messages,
        'total_count': len(messages),
        'senders': senders,
        'date_range': {
            'start': messages[0]['time'] if messages else None,
            'end': messages[-1]['time'] if messages else None
        },
        'extra_stats': extra_stats  # JSON格式额外统计
    }

def parse_txt_chatlog(text_content: str) -> dict:
    """解析微信导出的TXT聊天记录
    
    微信TXT格式示例：
    2023-10-01 12:30:45 妈妈
    吃饭了吗？
    
    2023-10-01 12:31:20 我
    吃了，你呢？
    """
    messages = []
    lines = text_content.split('\n')
    
    current_message = None
    date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(.+)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match = date_pattern.match(line)
        if match:
            # 保存上一条消息
            if current_message:
                messages.append(current_message)
            
            time_str = match.group(1)
            sender = match.group(2)
            current_message = {
                'time': time_str,
                'sender': sender,
                'content': ''
            }
        else:
            # 消息内容
            if current_message:
                if current_message['content']:
                    current_message['content'] += '\n' + line
                else:
                    current_message['content'] = line
    
    # 保存最后一条
    if current_message:
        messages.append(current_message)
    
    # 分析发送者
    senders = {}
    for msg in messages:
        sender = msg['sender']
        senders[sender] = senders.get(sender, 0) + 1
    
    return {
        'messages': messages,
        'total_count': len(messages),
        'senders': senders,
        'date_range': {
            'start': messages[0]['time'] if messages else None,
            'end': messages[-1]['time'] if messages else None
        }
    }

def calculate_chat_stats(messages: list) -> dict:
    """从消息列表中计算详细统计数据"""
    if not messages:
        return {}
    
    # 按发送者分组
    sender_messages = {}
    for msg in messages:
        sender = msg['sender'] or '未知'
        if sender not in sender_messages:
            sender_messages[sender] = []
        sender_messages[sender].append(msg)
    
    # 计算每个发送者的统计
    sender_stats = {}
    for sender, msgs in sender_messages.items():
        total_chars = sum(len(m['content']) for m in msgs)
        sender_stats[sender] = {
            'count': len(msgs),
            'avg_length': round(total_chars / len(msgs), 1) if msgs else 0,
            'percentage': round(len(msgs) / len(messages) * 100, 1)
        }
    
    # 时间分析（如果时间字段有效）
    hour_distribution = {}
    try:
        for msg in messages:
            if msg['time']:
                try:
                    if len(msg['time']) >= 13:  # 格式: YYYY-MM-DD HH:MM:SS
                        hour = int(msg['time'][11:13])
                        hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
                except Exception:
                    pass
    except Exception:
        pass
    
    return {
        'sender_stats': sender_stats,
        'hour_distribution': hour_distribution if hour_distribution else None,
        'total_messages': len(messages)
    }

async def analyze_chatlog_with_ai(parsed_log: dict, chat_partner: str = "妈妈") -> dict:
    """使用AI分析聊天记录，提取人物性格和关系模式"""
    
    # 准备样本（取前30条和最近30条，避免token超限）
    messages = parsed_log['messages']
    sample_messages = messages[:30] + messages[-30:] if len(messages) > 60 else messages
    
    chat_sample = "\n".join([
        f"[{msg['time']}] {msg['sender']}: {msg['content'][:100]}"
        for msg in sample_messages
    ])
    
    # 添加详细统计信息（如果有）
    extra_stats_info = ""
    extra_stats = parsed_log.get('extra_stats', {})
    if extra_stats and extra_stats.get('sender_stats'):
        sender_stats = extra_stats['sender_stats']
        sender_info = []
        for sender, stats in sender_stats.items():
            sender_info.append(f"{sender}: {stats['count']}条消息, 平均{stats['avg_length']}字, 占比{stats['percentage']}%")
        extra_stats_info = "\n\n【详细统计】\n" + "\n".join(sender_info)
        
        if extra_stats.get('hour_distribution'):
            hours = extra_stats['hour_distribution']
            peak_hours = sorted(hours.items(), key=lambda x: x[1], reverse=True)[:3]
            peak_info = "、".join([f"{h}点" for h, _ in peak_hours])
            extra_stats_info += f"\n活跃时间段: {peak_info}"
    
    analysis_prompt = f"""请分析以下微信聊天记录，这是用户和{chat_partner}的对话。

聊天记录样本：
{chat_sample}
{extra_stats_info}

请用JSON格式返回分析结果：
{{
    "personality": "{chat_partner}的性格特点（2-3句话，尽量具体）",
    "relationship_pattern": "用户和{chat_partner}的互动模式（2-3句话）",
    "common_topics": ["常见话题1", "常见话题2", "常见话题3"],
    "emotional_tone": "整体情感基调（如：温暖关心/偶尔争执/互相调侃等）",
    "key_events": ["重要事件1", "重要事件2"],
    "user_behavior": "用户在这段关系中的表现特点",
    "care_patterns": "{chat_partner}关心用户的具体方式（举例说明）",
    "speaking_style": "{chat_partner}的说话风格和口头禅",
    "communication_style": "{chat_partner}的沟通特点（如：主动型/被动型/话多/话少）"
}}

只返回JSON，不要其他内容。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODELS[1],  # 使用较稳定的模型
                    "messages": [{"role": "user", "content": analysis_prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.5,
                },
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 提取JSON
                try:
                    # 尝试直接解析
                    analysis = json.loads(content)
                except Exception:
                    # 尝试从文本中提取JSON
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        analysis = json.loads(json_match.group())
                    else:
                        analysis = {"raw_analysis": content}
                
                return {
                    'success': True,
                    'analysis': analysis,
                    'message_count': parsed_log['total_count'],
                    'date_range': parsed_log['date_range'],
                    'extra_stats': extra_stats  # 包含详细统计
                }
            else:
                return {'success': False, 'error': f'API错误: {response.status_code}'}
                
    except Exception as e:
        logging.error(f"分析聊天记录失败: {e}")
        return {'success': False, 'error': str(e)}

def save_chat_analysis(chat_partner: str, analysis_result: dict):
    """保存聊天记录分析结果"""
    imported_chats = load_json(CHAT_IMPORT_FILE, {})
    
    imported_chats[chat_partner] = {
        'imported_at': datetime.now(get_default_tz()).isoformat(),
        'analysis': analysis_result.get('analysis', {}),
        'message_count': analysis_result.get('message_count', 0),
        'date_range': analysis_result.get('date_range', {}),
        'extra_stats': analysis_result.get('extra_stats', {})  # 保存详细统计
    }
    
    save_json(CHAT_IMPORT_FILE, imported_chats)
    logging.info(f"聊天记录分析已保存: {chat_partner}")

def get_chat_analysis(chat_partner: str = None) -> dict:
    """获取已导入的聊天记录分析"""
    imported_chats = load_json(CHAT_IMPORT_FILE, {})
    
    if chat_partner:
        return imported_chats.get(chat_partner)
    return imported_chats

def get_all_imported_relationships() -> str:
    """获取所有已导入关系的信息，用于系统提示词"""
    imported_chats = load_json(CHAT_IMPORT_FILE, {})
    
    if not imported_chats:
        return ""
    
    info_parts = []
    for name, data in imported_chats.items():
        analysis = data.get('analysis', {})
        extra_stats = data.get('extra_stats', {})
        
        info_parts.append(f"\n【关于{name}（共分析{len(analysis)}个维度）】")
        info_parts.append(f"性格: {analysis.get('personality', '未知')}")
        info_parts.append(f"沟通风格: {analysis.get('communication_style', '未知')}")
        info_parts.append(f"和用户的关系: {analysis.get('relationship_pattern', '未知')}")
        info_parts.append(f"常见话题: {', '.join(analysis.get('common_topics', []))}")
        info_parts.append(f"关心方式: {analysis.get('care_patterns', '未知')}")
        info_parts.append(f"说话风格: {analysis.get('speaking_style', '未知')}")
        info_parts.append(f"情感基调: {analysis.get('emotional_tone', '未知')}")
        
        # 添加详细统计（如果有）
        if extra_stats and extra_stats.get('sender_stats'):
            sender_stats = extra_stats['sender_stats']
            for sender, stats in sender_stats.items():
                if sender != '我' and sender != '用户':
                    info_parts.append(f"{sender}的消息特征: 共{stats['count']}条, 平均{stats['avg_length']}字, 占比{stats['percentage']}%")
    
    return "\n".join(info_parts)

# ============================================================
# AI API调用 + 联网搜索
# ============================================================

import httpx

# [Skill: gemini] Gemini API调用函数
async def call_gemini(prompt: str, image_data: str = None, model: str = "gemini-2.5-flash") -> str:
    """调用Gemini API进行文本或图片分析
    Args:
        prompt: 文本提示词
        image_data: base64编码的图片数据（可选）
        model: 模型名称，默认gemini-2.5-flash
    Returns:
        Gemini的回复文本
    """
    if not GEMINI_API_KEY:
        return None
    
    try:
        # 构建请求体
        parts = []
        if image_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            })
        parts.append({"text": prompt})
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "temperature": 0.85,
                        "maxOutputTokens": 1024,
                    }
                },
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: gemini] Gemini API返回 {response.status_code}: {response.text[:200]}")
                return None
            
            data = response.json()
            if "candidates" in data and data["candidates"]:
                content = data["candidates"][0].get("content", {})
                text = content.get("parts", [{}])[0].get("text", "")
                return text.strip() if text else None
            return None
    except Exception as e:
        logging.error(f"[Skill: gemini] Gemini API调用失败: {e}")
        return None


async def web_search(query: str, max_results: int = 3) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            )
            if response.status_code != 200:
                return ""
            text = response.text
            results = []
            re.findall(r'<a[^>]*class="result-link"[^>]*href="([^"]*)"', text)
            snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', text, re.DOTALL)
            for i in range(min(max_results, len(snippets))):
                clean = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                if clean and len(clean) > 10:
                    results.append(clean)
            if results:
                return "\n".join([f"[{i+1}] {r}" for i, r in enumerate(results)])
            return ""
    except Exception as e:
        logging.error(f"搜索失败: {e}")
        return ""

async def call_ai(user_message: str, chat_history: list = None, use_memory: bool = True, emotion: str = "") -> str:
    now = datetime.now(get_default_tz())
    weekdays = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
    period = '凌晨' if now.hour < 6 else '上午' if now.hour < 12 else '下午' if now.hour < 18 else '晚上'
    time_info = f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}，{period}，{weekdays[now.weekday()]}（韩国时间）"

    # [角色系统] 使用蒸馏角色的系统提示词
    character = get_current_character()
    if character:
        system_content = character.get_system_prompt({'user_name': '学长'})
    else:
        system_content = SYSTEM_PROMPT
    system_content += f"\n\n【实时信息】{time_info}"

    # [Skill: 亲密度系统] 注入关系状态
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(YOUR_CHAT_ID or 1), []))
    stats["selfies_sent"] = stats.get("selfies_sent", 0)
    stats["photos_received"] = stats.get("photos_received", 0)
    intimacy_ctx = get_intimacy_context(stats)
    system_content += intimacy_ctx

    # [Skill: 增强记忆] 注入分类记忆
    if use_memory:
        memory = get_long_term_memory()
        if memory:
            system_content += f"\n\n【你对学长的记忆】\n{memory}"

    # [Skill: semantic-memory] 注入语义记忆
    semantic_ctx = get_semantic_memory_context()
    if semantic_ctx:
        system_content += f"\n\n【你记住的关于学长的重要信息（语义记忆）】\n{semantic_ctx}"

    # [Skill: semantic-memory] 添加记忆提取提示
    system_content += "\n\n【记忆规则】如果学长提到了重要的个人信息（如生日、喜好、家人、工作、住址、重要约定等），请在回复末尾用 [MEMORY:关键词:具体内容] 标记。例如：如果学长说「我生日是3月15日」，你回复末尾加上 [MEMORY:学长的生日:3月15日]。只标记真正重要的信息，不要滥用。标记格式严格为 [MEMORY:key:value]，不要加多余空格。"

    # [Skill: 情绪识别] 注入情绪反应指引
    if emotion and emotion in EMOTION_RESPONSE_GUIDE:
        system_content += f"\n\n【当前情绪感知】{EMOTION_RESPONSE_GUIDE[emotion]}"

    # [Skill: 纪念日] 检查是否有即将到来的纪念日
    upcoming = get_upcoming_anniversary(3)
    if upcoming:
        ann_info = "，".join([f"{a['name']}还有{a['days_until']}天" for a in upcoming])
        system_content += f"\n\n【即将到来的纪念日】{ann_info}。如果合适的话，可以提起这件事。"

    # [Skill: 微信聊天记录导入] 注入已了解的人际关系
    imported_relationships = get_all_imported_relationships()
    if imported_relationships:
        system_content += f"\n\n【你了解学长的人际关系（从聊天记录分析得出）】{imported_relationships}\n\n在对话中，你可以自然地提及这些人，表现出你对学长生活的了解。比如当学长提到相关话题时，你可以说「你妈妈不是...」或「上次你提到...」"

    # [Skill: 视频分析] 注入从视频中学到的角色特点
    video_context = get_video_analysis_context()
    if video_context:
        system_content += f"\n\n{video_context}\n\n请尽量模仿上述说话风格和口头禅，让角色更加真实。"

    # [Skill: 天气] 注入天气信息
    weather = await get_seoul_weather()
    weather_ctx = get_weather_context(weather)
    if weather_ctx:
        system_content += weather_ctx

    # 联网搜索
    search_keywords = ["几点", "时间", "天气", "今天", "新闻", "最近", "现在", "多少度", "热搜", "发生了什么", "怎么了"]
    need_search = any(kw in user_message for kw in search_keywords)

    final_user_message = user_message
    if need_search:
        search_result = await web_search(user_message)
        if search_result:
            search_context = f"\n\n【联网搜索结果】\n{search_result}\n\n请结合以上搜索结果回答，如果搜索结果不相关就忽略。"
            final_user_message = user_message + search_context

    # 使用统一的 AI 调用模块
    try:
        content = await ai_client_call_ai(
            system_prompt=system_content,
            user_message=final_user_message,
            chat_history=chat_history,
        )
        # [Skill: humanize-ai-text] 对 AI 回复进行人性化后处理
        content = humanize_text(content)
        return content
    except RuntimeError:
        pass

    logging.error("所有OpenRouter模型都失败了")

    # [Skill: gemini] 所有OpenRouter模型失败时，fallback到Gemini
    if GEMINI_API_KEY:
        logging.info("[Skill: gemini] 尝试使用Gemini作为fallback...")
        try:
            gemini_result = await call_gemini(user_message)
            if gemini_result:
                gemini_result = humanize_text(gemini_result)
                logging.info("[Skill: gemini] Gemini fallback成功")
                return gemini_result
        except Exception as e:
            logging.error(f"[Skill: gemini] Gemini fallback失败: {e}")

    return "...（低头不说话）"

async def summarize_and_save_memory(chat_id: int):
    history = get_history(chat_id)
    if len(history) < 4:
        return
    
    recent = history[-10:]
    conversation_text = "\n".join([f"{'明' if m['role']=='user' else '车如云'}: {m['content']}" for m in recent])
    
    prompt = f"""请从以下对话中提取1-2条值得长期记住的关键信息，用简短的句子描述。
只提取关于学长的偏好、重要事件、情感变化、约定等信息。
如果没有值得记住的信息，回复"无"。

对话：
{conversation_text}

请直接输出记忆内容，每条一行，不要加序号或其他格式："""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是记忆提取助手，只提取关键信息，保持简洁。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            if content and content != "无":
                for line in content.split("\n"):
                    line = line.strip().lstrip("-•· ").strip()
                    if line and len(line) > 3:
                        save_memory_entry(line)
    except Exception as e:
        logging.error(f"记忆提取失败: {e}")

# ============================================================
# 照片管理
# ============================================================

# ============================================================
# Bot命令
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        await update.message.reply_text("...你是谁？")
        return
    count = get_selfie_count()
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(chat_id), []))
    memory_count = stats.get("memories_count", 0)
    photo_info = f"\n📸 我有 {count} 张照片" if count > 0 else "\n📸 你可以给我发照片"
    memory_info = f"\n🧠 我记得 {memory_count} 件事关于明" if memory_count > 0 else ""
    days = get_days_together()
    days_info = f"\n💕 我们认识 {days} 天了" if days > 0 else ""
    
    # 设置菜单按钮
    from telegram import BotCommand
    commands = [
        BotCommand("selfie", "📸 发自拍"),
        BotCommand("sticker", "🎨 表情包"),
        BotCommand("memory", "🧠 我的记忆"),
        BotCommand("search", "🔍 搜索记忆"),
        BotCommand("forget", "🗑️ 删除记忆"),
        BotCommand("stats", "📊 数据统计"),
        BotCommand("analyze", "📈 对话分析"),
        BotCommand("anniversary", "🎉 纪念日"),
        BotCommand("summarize", "📝 摘要生成"),
        BotCommand("version", "📋 版本信息"),
        BotCommand("quota", "💰 免费额度"),
        BotCommand("voice", "🎤 语音消息"),
        BotCommand("export", "📦 导出数据"),
        BotCommand("reset", "🔄 重置对话"),
        BotCommand("learned", "📝 学到了什么"),
    ]
    await update.get_bot().set_my_commands(commands)
    
    # 自定义键盘按钮（像 BotFather 那样的底部按钮）
    
    keyboard = [
        [KeyboardButton("🎤 语音开关"), KeyboardButton("📷 自拍相册")],
        [KeyboardButton("🤖 Gemini AI"), KeyboardButton("📊 统计")],
        [KeyboardButton("🎨 表情包"), KeyboardButton("🧠 记忆")],
        [KeyboardButton("📅 纪念日"), KeyboardButton("📱 Mini App")],
        [KeyboardButton("❓ 帮助"), KeyboardButton("🔄 重置")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"...又是你。\n\n（低头，不看你）\n\n...好吧，既然你来了。\n\n"
        f"点下面的按钮就行。{photo_info}{memory_info}{days_info}",
        reply_markup=reply_markup
    )

@auto_delete_messages(delay=3)
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = []
    save_chat_history(chat_id, [])
    await update.message.reply_text("...（沉默了一会儿）\n\n...好吧，重新开始。")

@auto_delete_messages(delay=3)
async def selfie_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    # 支持可选角色参数
    char_id = None
    if context.args and len(context.args) > 0:
        char_id = context.args[0]
    if not char_id:
        char = get_current_character()
        char_id = char.config.id if char else None
    saved = get_saved_selfies(chat_id)
    if saved:
        caption = await call_ai("学长让我发一张自拍给他，用一句话害羞地回应，不超过15个字")
    else:
        caption = random.choice(SELFIE_CAPTIONS)
    await send_selfie_to_chat(update.get_bot(), chat_id, caption)

@auto_delete_messages(delay=3)
async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # [Skill: semantic-memory] 同时显示语义记忆
    semantic_memories = load_json(SEMANTIC_MEMORY_FILE, [])
    memories = load_json(get_user_memory_file(chat_id), [])
    
    has_semantic = len(semantic_memories) > 0
    has_regular = len(memories) > 0
    
    if not has_semantic and not has_regular:
        await update.message.reply_text("...我还什么都不记得。多跟我说说话吧。")
        return
    
    parts = []
    
    # 显示语义记忆（结构化）
    if has_semantic:
        categories = {}
        for m in semantic_memories:
            cat = m.get("category", "其他")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)
        
        parts.append("...关于学长的事，我记得这些：\n")
        for cat, items in categories.items():
            cat_items = "\n".join([f"  • {m['key']}: {m['value']}" for m in items[-8:]])
            parts.append(f"📌 [{cat}]：\n{cat_items}")
    
    # 显示常规记忆（分类）
    if has_regular:
        categorized = {}
        for m in memories:
            cat = categorize_memory(m)
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(m)
        
        if has_semantic:
            parts.append("\n\n💬 对话记忆：")
        else:
            parts.append("...关于学长的事，我记得这些：\n")
        
        for cat in ["偏好", "事件", "情感", "约定", "其他"]:
            if cat in categorized:
                items = "\n".join([f"  • {m}" for m in categorized[cat][-8:]])
                parts.append(f"📌 {cat}：\n{items}")
    
    await update.message.reply_text("\n\n".join(parts))

# [Skill: semantic-memory] /forget 命令 - 删除特定记忆
@auto_delete_messages(delay=3)
async def forget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "...学长想让我忘记什么？\n\n"
            "用法：/forget <关键词>\n"
            "例如：/forget 生日\n\n"
            "会删除所有包含该关键词的记忆。"
        )
        return
    
    keyword = " ".join(args)
    deleted = delete_semantic_memory(keyword)
    
    if deleted > 0:
        await update.message.reply_text(f"...删掉了 {deleted} 条关于「{keyword}」的记忆。\n\n（低头，不说话）")
    else:
        await update.message.reply_text(f"...没有找到关于「{keyword}」的记忆。")

# [Skill: semantic-memory] /search 命令 - 搜索记忆
@auto_delete_messages(delay=3)
async def search_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "...学长想找什么记忆？\n\n"
            "用法：/search <关键词>\n"
            "例如：/search 生日"
        )
        return
    
    query = " ".join(args)
    results = search_semantic_memory(query, topk=5)
    
    if not results:
        await update.message.reply_text(f"...没有找到和「{query}」相关的记忆。")
        return
    
    parts = [f"...找到了 {len(results)} 条相关记忆：\n"]
    for i, m in enumerate(results, 1):
        timestamp = m.get("timestamp", "")[:10]
        parts.append(f"{i}. [{m.get('category', '?')}] {m['key']}: {m['value']}（{timestamp}）")
    
    await update.message.reply_text("\n".join(parts))

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    await update.message.chat.send_action("upload_document")
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(MEMORY_FILE):
            zf.write(MEMORY_FILE, "long_term_memory.json")
        if os.path.exists(HISTORY_FILE):
            zf.write(HISTORY_FILE, "chat_history.json")
        if os.path.exists(ANNIVERSARY_FILE):
            zf.write(ANNIVERSARY_FILE, "anniversaries.json")
        if os.path.exists(STATS_FILE):
            zf.write(STATS_FILE, "chat_stats.json")
        selfies = get_saved_selfies(chat_id)
        for s in selfies:
            selfie_dir = get_user_selfie_dir(chat_id)
            filepath = os.path.join(selfie_dir, s)
            if os.path.exists(filepath):
                zf.write(filepath, f"selfies/{s}")
    
    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    await update.message.reply_document(
        document=buf,
        filename=f"车如云数据_{timestamp}.zip",
        caption=f"...都给你了。{len(get_saved_selfies(chat_id))}张照片 + {len(load_json(get_user_memory_file(chat_id), []))}条记忆。"
    )

async def import_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    await update.message.reply_text("...把zip文件发给我就行。")

async def photo_count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    count = get_selfie_count()
    if count > 0:
        await update.message.reply_text(f"...我有 {count} 张照片了。都是明给我的。")
    else:
        await update.message.reply_text("...一张都没有。明要给我发照片吗？")

# ============================================================
# [Skill: slack-gif-creator] /sticker 表情包命令
# ============================================================

@auto_delete_messages(delay=3)
async def sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示可用表情
        moods = list(STICKER_PROMPTS.keys())
        mood_list = "、".join(moods)
        await update.message.reply_text(
            f"...学长想要表情包吗。\n\n"
            f"可用表情：{mood_list}\n\n"
            f"用法：/sticker 表情类型\n"
            f"例如：/sticker 害羞\n\n"
            f"也可以直接说「发个害羞的表情」之类的。"
        )
        return
    
    mood = args[0]
    if mood not in STICKER_PROMPTS:
        # 模糊匹配
        matched = detect_sticker_mood(" ".join(args))
        if matched:
            mood = matched
        else:
            await update.message.reply_text(f"...没有'{mood}'这个表情。\n\n可用：{'、'.join(STICKER_PROMPTS.keys())}")
            return
    
    url = generate_sticker_url(mood)
    if url:
        # 用AI生成一句符合表情的台词
        caption = await call_ai(f"用一句话配合'{mood}'的表情，不超过10个字，用括号表示内心独白")
        await update.message.reply_photo(photo=url, caption=caption)
        # 保存到聊天记录
        append_bot_message(chat_id, f"[发送了一个{mood}的表情包] {caption}")
    else:
        await update.message.reply_text("...生成失败了。再试试。")

# ============================================================
# [Skill: meeting-insights-analyzer] /analyze 对话分析命令
# ============================================================

@auto_delete_messages(delay=3)
async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    await update.message.chat.send_action("typing")
    
    analysis = analyze_dialogue_patterns(chat_id)
    
    if "error" in analysis:
        await update.message.reply_text(f"...{analysis['error']}")
        return
    
    # 格式化分析报告
    emotion_dist = analysis.get("用户情绪分布", {})
    emotion_str = ""
    if isinstance(emotion_dist, dict):
        emotion_str = "、".join([f"{k}:{v}次" for k, v in emotion_dist.items()])
    
    report = (
        f"...明要看分析报告吗。\n\n"
        f"📊 对话模式分析报告\n"
        f"━━━━━━━━━━━━━━\n"
        f"💬 总对话数：{analysis['总对话数']}\n"
        f"📏 学长的平均消息：{analysis['用户平均消息长度']}\n"
        f"📏 我的平均回复：{analysis['车如云平均回复长度']}\n"
        f"🎯 明主动发起：{analysis['用户主动发起比例']}\n"
        f"📊 日均消息：{analysis['日均消息数']}\n"
        f"💗 亲密度：{analysis['亲密度']}\n"
        f"━━━━━━━━━━━━━━\n"
        f"😊 学长的情绪分布：{emotion_str if emotion_str else '正常'}\n"
        f"💝 关心表达：{analysis['关心表达次数']}次\n"
        f"😤 吃醋次数：{analysis['吃醋次数']}次\n"
        f"🌙 温暖表达：{analysis['温暖表达次数']}次\n"
        f"━━━━━━━━━━━━━━\n"
        f"🤔 我的回复风格：\n"
        f"  · 使用省略号：{analysis['车如云使用省略号']}\n"
        f"  · 内心独白：{analysis['车如云内心独白']}\n"
        f"  · 短回复比例：{analysis['车如云短回复(<20字)']}\n"
        f"━━━━━━━━━━━━━━\n"
    )
    
    # 添加关系建议
    advice = get_relationship_advice(analysis)
    report += f"\n{advice}"
    
    await update.message.reply_text(report)

# ============================================================
# [Skill: 对话统计] /stats 命令
# ============================================================

@auto_delete_messages(delay=3)
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(chat_id), []))
    stats["selfies_sent"] = stats.get("selfies_sent", 0)
    stats["photos_received"] = stats.get("photos_received", 0)
    
    total_msgs = stats.get("total_messages", 0)
    total_days = stats.get("total_days", 0)
    today_count = stats.get("today_count", 0)
    first_date = stats.get("first_chat_date", "未知")
    days_together = get_days_together()
    
    # 亲密度
    intimacy = calculate_intimacy(stats)
    
    # 纪念日
    anniversaries = load_anniversaries()
    ann_count = len(anniversaries)
    
    # 对话条数
    history = get_history(chat_id)
    history_count = len(history)
    
    stats_text = (
        f"...明要看数据吗。\n\n"
        f"📊 我们的聊天数据\n"
        f"━━━━━━━━━━━━━━\n"
        f"💬 总消息数：{total_msgs}\n"
        f"📅 聊天天数：{total_days} 天\n"
        f"📝 当前对话：{history_count} 条\n"
        f"🕐 今天消息：{today_count} 条\n"
        f"💕 认识天数：{days_together} 天\n"
        f"🧠 记忆条数：{stats['memories_count']}\n"
        f"📸 我的照片：{get_selfie_count()} 张\n"
        f"📷 发过自拍：{stats['selfies_sent']} 次\n"
        f"🎁 收到照片：{stats['photos_received']} 张\n"
        f"🎉 纪念日：{ann_count} 个\n"
        f"━━━━━━━━━━━━━━\n"
        f"💗 亲密度：{intimacy['score']}/100（{intimacy['level']}）\n"
        f"📅 第一次聊天：{first_date}"
    )
    
    await update.message.reply_text(stats_text)

# ============================================================
# [Skill: 微信聊天记录导入] /import_chat 命令
# ============================================================

# 临时存储用户上传的聊天记录文件内容
pending_chat_imports = {}

# ============================================================
# 视频分析系统（视频→音频→文字→AI分析）
# ============================================================

def extract_audio_from_video(video_path: str) -> str:
    """从视频中提取音频（使用ffmpeg）"""
    audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
    cmd = f"ffmpeg -i '{video_path}' -vn -acodec libmp3lame -q:a 2 -ar 16000 -ac 1 '{audio_path}' -y 2>/dev/null"
    os.system(cmd)
    return audio_path if os.path.exists(audio_path) else ""

def transcribe_audio_whisper(audio_path: str) -> str:
    """使用Whisper将音频转为文字（需要大内存，e2-micro可能无法使用）"""
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="ko", verbose=False)
        return result.get("text", "")
    except ImportError:
        logging.info("Whisper未安装，使用备选方案")
        return ""
    except Exception as e:
        logging.error(f"Whisper转写失败: {e}")
        return ""

def transcribe_audio_primary(audio_path: str) -> str:
    """备选方案：使用Google Speech Recognition（免费，有长度限制）"""
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        # 分段处理（每段30秒）
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        chunk_ms = 30000  # 30秒
        chunks = [audio[i:i+chunk_ms] for i in range(0, len(audio), chunk_ms)]
        
        full_text = []
        for i, chunk in enumerate(chunks):
            chunk_path = f"/tmp/chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            
            with sr.AudioFile(chunk_path) as source:
                audio_data = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio_data, language="ko-KR")
                full_text.append(text)
            except Exception:
                full_text.append("[无法识别]")
            
            os.remove(chunk_path)
        
        return " ".join(full_text)
    except Exception as e:
        logging.error(f"语音识别失败: {e}")
        return ""

async def analyze_video_transcript(transcript: str, video_type: str = "剧集") -> dict:
    """使用AI分析视频转录内容，提取角色特点"""
    if not transcript or len(transcript) < 50:
        return {'success': False, 'error': '转录内容太短'}
    
    # 截取样本（避免token超限）
    sample = transcript[:3000] if len(transcript) > 3000 else transcript
    
    if video_type == "采访":
        prompt = f"""分析以下演员采访/花絮的转录内容，提取演员的真实说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "说话风格描述（语速、停顿习惯、口头禅）",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅或常用表达1", "常用表达2"],
    "emotional_expression": "情感表达方式（什么时候笑、什么时候沉默等）",
    "unique_habits": "独特的说话习惯或小动作描述",
    "tone_analysis": "整体语气特点（温柔/冷淡/活泼/内向等）"
}}

只返回JSON。"""
    else:
        prompt = f"""分析以下韩剧片段的转录内容，提取车如云这个角色的说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "车如云的说话风格（简短/省略号/语气词使用习惯）",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅或常用表达1", "常用表达2", "常用表达3"],
    "emotional_expression": "情感表达方式（傲娇/别扭/害羞时的表现）",
    "relationship_dynamics": "与其他角色的互动模式",
    "key_dialogues": ["经典台词1", "经典台词2", "经典台词3"],
    "tone_analysis": "整体语气特点"
}}

只返回JSON。"""
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODELS[1],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                try:
                    analysis = json.loads(content)
                except Exception:
                    jm = re.search(r'\{[\s\S]*\}', content)
                    analysis = json.loads(jm.group()) if jm else {"raw": content}
                
                return {'success': True, 'analysis': analysis}
            elif resp.status_code == 429:
                # Rate limited, try next model
                for fallback_model in AI_MODELS:
                    if fallback_model == AI_MODELS[1]:
                        continue
                    try:
                        resp2 = await client.post(
                            f"{AI_API_BASE}/chat/completions",
                            headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": fallback_model,
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": 1500,
                                "temperature": 0.3,
                            },
                        )
                        if resp2.status_code == 200:
                            content = resp2.json()['choices'][0]['message']['content']
                            try:
                                analysis = json.loads(content)
                            except Exception:
                                jm = re.search(r'\{[\s\S]*\}', content)
                                analysis = json.loads(jm.group()) if jm else {"raw": content}
                            return {'success': True, 'analysis': analysis}
                    except Exception:
                        continue
                return {'success': False, 'error': 'API请求频率超限，请稍后再试（429）'}
            else:
                return {'success': False, 'error': f'API错误: {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def save_video_analysis(video_type: str, analysis_result: dict):
    """保存视频分析结果到记忆"""
    analysis = analysis_result.get('analysis', {})
    
    # 保存到独立文件
    video_file = os.path.join(DATA_DIR, "video_analysis.json")
    data = load_json(video_file, {})
    data[video_type] = {
        'analyzed_at': datetime.now(get_default_tz()).isoformat(),
        'analysis': analysis,
    }
    save_json(video_file, data)
    
    # 提取关键信息存入长期记忆
    style = analysis.get('speaking_style', '')
    traits = analysis.get('personality_traits', [])
    catchphrases = analysis.get('catchphrases', [])
    analysis.get('tone_analysis', '')
    
    if video_type == "采访":
        save_memory_entry(f"演员真实说话风格: {style}")
        for t in traits[:3]:
            save_memory_entry(f"演员性格特点: {t}")
        for c in catchphrases[:3]:
            save_memory_entry(f"演员口头禅: {c}")
    else:
        save_memory_entry(f"车如云说话风格（从视频分析）: {style}")
        for t in traits[:3]:
            save_memory_entry(f"车如云性格特点（从视频分析）: {t}")
        for c in catchphrases[:3]:
            save_memory_entry(f"车如云口头禅: {c}")
        key_dialogues = analysis.get('key_dialogues', [])
        for d in key_dialogues[:3]:
            save_memory_entry(f"车如云经典台词: {d}")

def get_video_analysis_context() -> str:
    """获取视频分析信息，用于系统提示词"""
    video_file = os.path.join(DATA_DIR, "video_analysis.json")
    data = load_json(video_file, {})
    if not data:
        return ""
    
    parts = []
    if "采访" in data:
        a = data["采访"].get('analysis', {})
        parts.append("\n【演员真实特点（从采访视频分析）】")
        parts.append(f"说话风格: {a.get('speaking_style', '')}")
        parts.append(f"性格: {', '.join(a.get('personality_traits', []))}")
        parts.append(f"口头禅: {', '.join(a.get('catchphrases', []))}")
        parts.append(f"语气: {a.get('tone_analysis', '')}")
    
    if "剧集" in data:
        a = data["剧集"].get('analysis', {})
        parts.append("\n【车如云角色细节（从剧集视频分析）】")
        parts.append(f"说话风格: {a.get('speaking_style', '')}")
        parts.append(f"经典台词: {', '.join(a.get('key_dialogues', []))}")
        parts.append(f"情感表达: {a.get('emotional_expression', '')}")
    
    return "\n".join(parts)

# 记录等待视频导入的类型
pending_video_imports = {}

async def import_video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导入视频分析命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示已有的视频分析
        video_file = os.path.join(DATA_DIR, "video_analysis.json")
        data = load_json(video_file, {})
        existing = ""
        if data:
            existing = "\n\n已分析的视频：\n"
            for vtype, vdata in data.items():
                existing += f"  • {vtype}（{vdata.get('analyzed_at', '')[:10]}）\n"
        
        await update.message.reply_text(
            f"...学长想让我看视频？\n\n"
            f"🎬 视频分析\n"
            f"━━━━━━━━━━━━━━\n"
            f"用法：\n"
            f"  /import_video 剧情 - 上传剧集片段\n"
            f"  /import_video 采访 - 上传演员采访/花絮\n\n"
            f"然后直接发送视频文件。\n\n"
            f"⚠️ 注意：\n"
            f"• 支持 MP4/AVI/MKV/MOV 格式\n"
            f"• 长视频处理需要较长时间\n"
            f"• 需要服务器安装 ffmpeg 和 whisper{existing}"
        )
        return
    
    video_type = args[0]
    if video_type not in ["剧情", "采访"]:
        await update.message.reply_text("...类型不对。用 剧情 或 采访。")
        return
    
    pending_video_imports[chat_id] = video_type
    await update.message.reply_text(
        f"...好，发送{video_type}视频吧。\n"
        f"处理可能需要几分钟，请耐心等待。"
    )

async def handle_video_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户上传的视频文件"""
    chat_id = update.effective_chat.id
    
    if chat_id not in pending_video_imports:
        return
    
    video_type = pending_video_imports.pop(chat_id)
    video = update.message.video or update.message.document
    
    if not video:
        return
    
    # 检查文件大小（限制500MB）
    file_size = video.file_size or 0
    if file_size > 500 * 1024 * 1024:
        await update.message.reply_text("...文件太大了，最大500MB。")
        return
    
    await update.message.chat.send_action("typing")
    await update.message.reply_text(f"...正在下载{video_type}视频...")
    
    try:
        # 下载视频
        file = await context.bot.get_file(video.file_id)
        video_filename = f"video_{datetime.now(get_default_tz()).strftime('%Y%m%d_%H%M%S')}.mp4"
        video_path = os.path.join(VIDEO_DIR, video_filename)
        await file.download_to_drive(video_path)
        
        await update.message.reply_text(f"...下载完成（{file_size / 1024 / 1024:.1f}MB）。正在提取音频...")
        
        # 提取音频
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            await update.message.reply_text("...音频提取失败。请确认ffmpeg已安装。")
            return
        
        await update.message.reply_text("...正在语音转文字（可能需要几分钟）...")
        
        # 语音转文字（优先使用Google Speech Recognition，Whisper需要大内存）
        transcript = transcribe_audio_primary(audio_path)
        if not transcript:
            transcript = transcribe_audio_whisper(audio_path)
        
        if not transcript:
            await update.message.reply_text("...语音识别失败。可能是韩语识别不准确。")
            return
        
        # 清理音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        await update.message.reply_text(
            f"...识别完成（{len(transcript)}字）。\n"
            f"正在分析{video_type}内容..."
        )
        
        # AI分析
        analysis_result = await analyze_video_transcript(transcript, video_type)
        
        if not analysis_result['success']:
            await update.message.reply_text(f"...分析出错了：{analysis_result.get('error', '')}")
            return
        
        # 保存结果
        save_video_analysis(video_type, analysis_result)
        
        # 显示结果
        analysis = analysis_result['analysis']
        result_text = f"✅ {video_type}视频分析完成\n━━━━━━━━━━━━━━\n"
        result_text += f"🗣️ 说话风格：{analysis.get('speaking_style', '未知')}\n\n"
        
        traits = analysis.get('personality_traits', [])
        if traits:
            result_text += "🎭 性格特点：\n"
            for t in traits:
                result_text += f"  • {t}\n"
            result_text += "\n"
        
        catchphrases = analysis.get('catchphrases', [])
        if catchphrases:
            result_text += f"💬 口头禅：{', '.join(catchphrases)}\n\n"
        
        if video_type == "剧情":
            key_d = analysis.get('key_dialogues', [])
            if key_d:
                result_text += "📝 经典台词：\n"
                for d in key_d[:3]:
                    result_text += f"  「{d}」\n"
                result_text += "\n"
        
        result_text += f"🎭 情感表达：{analysis.get('emotional_expression', '未知')}\n"
        result_text += "━━━━━━━━━━━━━━\n...我会记住的。"
        
        await update.message.reply_text(result_text)
        
        # 清理视频文件（节省空间）
        if os.path.exists(video_path):
            os.remove(video_path)
        
    except Exception as e:
        logging.error(f"视频导入失败: {e}")
        await update.message.reply_text(f"...处理出错了：{str(e)[:100]}")

async def import_chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导入微信聊天记录命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示帮助和已导入的关系
        imported = get_chat_analysis()
        imported_list = ""
        if imported:
            imported_list = "\n\n📚 已导入的关系：\n"
            for name, data in imported.items():
                msg_count = data.get('message_count', 0)
                imported_list += f"  • {name}（{msg_count}条消息）\n"
        
        await update.message.reply_text(
            f"...学长想让我了解谁？\n\n"
            f"📱 导入微信聊天记录\n"
            f"━━━━━━━━━━━━━━\n"
            f"用法：\n"
            f"1. 发送命令：/import_chat 对方名字\n"
            f"   例如：/import_chat 妈妈\n\n"
            f"2. 然后直接发送微信导出的TXT文件\n\n"
            f"3. 我会分析聊天记录，了解对方的性格和你们的关系\n\n"
            f"⚠️ 注意：\n"
            f"• 只支持微信导出的TXT格式\n"
            f"• 建议删除敏感信息后再导入\n"
            f"• 数据仅存储分析结果，不保存原始记录{imported_list}"
        )
        return
    
    # 记录等待导入的关系名
    chat_partner = args[0]
    pending_chat_imports[chat_id] = chat_partner
    
    await update.message.reply_text(
        f"...好，我想了解{chat_partner}。\n\n"
        f"现在请直接发送微信聊天记录的TXT文件。\n"
        f"我会分析后记住{chat_partner}的特点。"
    )

async def handle_chatlog_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户上传的聊天记录文件"""
    chat_id = update.effective_chat.id
    
    # 检查是否在等待导入
    if chat_id not in pending_chat_imports:
        return  # 不处理，让handle_document处理
    
    chat_partner = pending_chat_imports.pop(chat_id)
    document = update.message.document
    
    # 检查文件类型
    valid_extensions = ['.txt', '.json', '.jsonl', '.html']
    if not any(document.file_name.lower().endswith(ext) for ext in valid_extensions):
        await update.message.reply_text("...请发送TXT/JSON/JSONL/HTML格式的聊天记录文件。")
        return
    
    # 下载文件
    await update.message.chat.send_action("typing")
    
    try:
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        text_content = file_content.decode('utf-8', errors='ignore')
        
        # 解析聊天记录
        await update.message.reply_text(f"...正在读取和{chat_partner}的聊天记录...")
        parsed = parse_wechat_chatlog(text_content)
        
        if parsed['total_count'] == 0:
            await update.message.reply_text("...没能解析出消息，请检查文件格式。")
            return
        
        # 显示基本信息
        senders_info = "、".join([f"{name}({count}条)" for name, count in parsed['senders'].items()])
        await update.message.reply_text(
            f"📊 解析完成\n"
            f"━━━━━━━━━━━━━━\n"
            f"总消息数：{parsed['total_count']}条\n"
            f"对话对象：{senders_info}\n"
            f"时间范围：{parsed['date_range']['start']} 至 {parsed['date_range']['end']}\n\n"
            f"...正在分析{chat_partner}的性格和你们的关系..."
        )
        
        # AI分析
        await update.message.chat.send_action("typing")
        analysis_result = await analyze_chatlog_with_ai(parsed, chat_partner)
        
        if not analysis_result['success']:
            await update.message.reply_text(f"...分析出错了：{analysis_result.get('error', '未知错误')}")
            return
        
        # 保存分析结果
        save_chat_analysis(chat_partner, analysis_result)
        
        # 显示分析结果
        analysis = analysis_result['analysis']
        result_text = (
            f"✅ 已了解{chat_partner}\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 性格：{analysis.get('personality', '未知')}\n\n"
            f"💕 关系：{analysis.get('relationship_pattern', '未知')}\n\n"
            f"🗣️ 常见话题：{', '.join(analysis.get('common_topics', []))}\n\n"
            f"💝 关心方式：{analysis.get('care_patterns', '未知')}\n\n"
            f"🎭 情感基调：{analysis.get('emotional_tone', '未知')}\n"
            f"━━━━━━━━━━━━━━\n"
            f"...原来如此。我会记住的。"
        )
        
        await update.message.reply_text(result_text)
        
        # 添加到长期记忆
        memory_entry = f"了解了明和{chat_partner}的关系：{analysis.get('relationship_pattern', '')}"
        save_memory_entry(memory_entry)
        
    except Exception as e:
        logging.error(f"处理聊天记录失败: {e}")
        await update.message.reply_text("...处理文件出错了。再试试？")

async def list_imported_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出已导入的聊天记录"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    imported = get_chat_analysis()
    
    if not imported:
        await update.message.reply_text("...还没有导入任何聊天记录。\n用 /import_chat 开始导入。")
        return
    
    parts = ["...学长让我了解的人：\n"]
    for name, data in imported.items():
        analysis = data.get('analysis', {})
        msg_count = data.get('message_count', 0)
        imported_at = data.get('imported_at', '')[:10]  # 只取日期部分
        
        parts.append(f"\n👤 {name}")
        parts.append(f"  消息数：{msg_count}条")
        parts.append(f"  性格：{analysis.get('personality', '未知')[:30]}...")
        parts.append(f"  导入时间：{imported_at}")
    
    parts.append("\n\n用 /import_chat 名字 可以导入更多关系。")
    
    await update.message.reply_text("\n".join(parts))

# ============================================================
# [Skill: 免费额度监控] /quota 命令
# ============================================================

@auto_delete_messages(delay=3)
async def quota_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看免费额度使用情况"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    report = format_quota_report()
    await update.message.reply_text(report)

@auto_delete_messages(delay=3)
async def quota_reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """重置额度告警和断开状态"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    stats._quota_shutdown = False
    
    usage = load_quota_usage()
    usage['warnings_sent'] = []
    usage['shutdown_triggered'] = False
    save_quota_usage(usage)
    
    await update.message.reply_text(
        "...额度监控已重置。\n\n"
        "🟢 告警已清除，自动断开已解除。\n"
        "⚠️ 注意：这只是重置了Bot内部的监控状态，\n"
        "Google Cloud 的实际额度不会重置。"
    )

# ============================================================
# [Skill: self-improving] /learned 命令 - 查看学到了什么
# ============================================================

@auto_delete_messages(delay=3)
async def learned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 Bot 从纠正中学到了什么"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    corrections = load_json(CORRECTIONS_FILE, [])
    
    if not corrections:
        await update.message.reply_text(
            "...我还没学到什么。\n\n"
            "（小声）...明纠正我的时候，我会记住的。"
        )
        return
    
    # 显示最近 10 条纠正记录
    recent = corrections[-10:]
    parts = [f"...明要看我学到了什么吗。\n\n📊 最近 {len(recent)} 条纠正记录：\n━━━━━━━━━━━━━━"]
    
    for i, c in enumerate(recent, 1):
        user_said = c.get("user_said", "")[:40]
        bot_said = c.get("bot_said", "")[:30]
        timestamp = c.get("timestamp", "")[:16]
        parts.append(f"\n{i}. [{timestamp}]")
        parts.append(f"   学长说：{user_said}")
        parts.append(f"   我说：{bot_said}...")
    
    parts.append("\n━━━━━━━━━━━━━━")
    parts.append(f"...一共记住了 {len(corrections)} 条。")
    parts.append("（低头）...我会努力改的。")
    
    await update.message.reply_text("\n".join(parts))

# ============================================================
# [Skill: claw-summarize-pro] 摘要生成系统
# ============================================================

async def fetch_url_content(url: str) -> str:
    """抓取网页内容，提取纯文本"""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return ""
            html_content = response.text
            # 提取 <body> 中的文本
            body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', html_content, re.IGNORECASE)
            if body_match:
                body_text = body_match.group(1)
            else:
                body_text = html_content
            # 去除 HTML 标签
            text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', body_text, flags=re.IGNORECASE)
            text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            # 清理空白
            text = re.sub(r'\s+', ' ', text).strip()
            # 限制长度
            return text[:5000]
    except Exception as e:
        logging.error(f"[摘要] 抓取网页失败: {e}")
        return ""

async def generate_summary(text: str) -> str:
    """使用 AI 生成文本摘要"""
    if not text or len(text) < 20:
        return "...内容太短了，没什么好总结的。"

    prompt = f"""请对以下内容生成简洁的摘要，用3-5个要点总结核心内容。使用中文。

内容：
{text[:4000]}

请按以下格式输出：
1. 要点一
2. 要点二
3. 要点三
（如有更多要点继续编号）

只输出摘要内容，不要加标题或其他说明。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODELS[0],
                    "messages": [
                        {"role": "system", "content": "你是一个专业的摘要生成助手。请简洁准确地总结内容。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return f"...摘要生成失败（HTTP {response.status_code}）。"
    except Exception as e:
        logging.error(f"[摘要] AI生成失败: {e}")
        return "...摘要生成出错了。"

@auto_delete_messages(delay=3)
async def summarize_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """摘要生成命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    args = context.args or []
    text_to_summarize = ""

    if not args and update.message.reply_to_message:
        # 回复消息模式：总结被回复的消息
        replied = update.message.reply_to_message
        if replied.text:
            text_to_summarize = replied.text
        elif replied.caption:
            text_to_summarize = replied.caption
        else:
            await update.message.reply_text("...这条消息没有文字内容可以总结。")
            return
    elif args:
        input_text = " ".join(args)
        # 检查是否是 URL
        url_pattern = r'https?://[^\s]+'
        url_match = re.search(url_pattern, input_text)
        if url_match:
            url = url_match.group()
            await update.message.reply_text("...正在抓取网页内容...")
            text_to_summarize = await fetch_url_content(url)
            if not text_to_summarize:
                await update.message.reply_text("...抓取网页失败了。可能是网站不允许访问。")
                return
        else:
            text_to_summarize = input_text
    else:
        await update.message.reply_text(
            "...学长想让我总结什么？\n\n"
            "用法：\n"
            "  /summarize <文本> - 总结文本\n"
            "  /summarize <URL> - 总结网页\n"
            "  回复消息 + /summarize - 总结该消息"
        )
        return

    await update.message.chat.send_action("typing")
    summary = await generate_summary(text_to_summarize)
    await update.message.reply_text(f"...给你总结好了。\n\n{summary}")

# ============================================================
# [Skill: auto-updater] 自动更新检查系统
# ============================================================

def calculate_bot_hash() -> str:
    """计算 bot.py 的 MD5 hash"""
    try:
        bot_path = os.path.abspath(__file__)
        with open(bot_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logging.error(f"[自动更新] 计算 hash 失败: {e}")
        return ""

def check_for_updates() -> dict:
    """检查 bot.py 是否有更新，返回更新信息"""
    current_hash = calculate_bot_hash()
    if not current_hash:
        return {"updated": False, "reason": "hash计算失败"}

    version_data = load_json(VERSION_FILE, {})

    if not version_data:
        # 首次运行，记录当前 hash
        version_data = {
            "version": BOT_VERSION,
            "last_check": datetime.now(get_default_tz()).strftime("%Y-%m-%d"),
            "bot_hash": current_hash,
        }
        save_json(VERSION_FILE, version_data)
        return {"updated": False, "reason": "首次运行，已记录版本信息"}

    saved_hash = version_data.get("bot_hash", "")
    saved_version = version_data.get("version", "未知")

    # 更新检查时间
    version_data["last_check"] = datetime.now(get_default_tz()).strftime("%Y-%m-%d")
    version_data["bot_hash"] = current_hash
    version_data["version"] = BOT_VERSION
    save_json(VERSION_FILE, version_data)

    if saved_hash and saved_hash != current_hash:
        return {
            "updated": True,
            "old_version": saved_version,
            "new_version": BOT_VERSION,
            "reason": "代码已变更",
        }

    return {"updated": False, "old_version": saved_version, "new_version": BOT_VERSION}

@auto_delete_messages(delay=3)
async def version_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前版本信息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    version_data = load_json(VERSION_FILE, {})
    last_check = version_data.get("last_check", "未知")
    saved_version = version_data.get("version", "未知")
    current_hash = calculate_bot_hash()

    await update.message.reply_text(
        f"...版本信息。\n\n"
        f"📋 当前版本：{BOT_VERSION}\n"
        f"📦 记录版本：{saved_version}\n"
        f"🔍 代码Hash：{current_hash[:12]}...\n"
        f"📅 上次检查：{last_check}\n\n"
        f"使用 /check_update 手动检查更新。"
    )

@auto_delete_messages(delay=3)
async def check_update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """手动检查更新"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    await update.message.chat.send_action("typing")
    result = check_for_updates()

    if result["updated"]:
        await update.message.reply_text(
            f"...明。\n\n"
            f"🔄 Bot 代码已更新！\n"
            f"   {result.get('old_version', '?')} → {result.get('new_version', BOT_VERSION)}\n\n"
            f"...好像变强了一点点。"
        )
    else:
        await update.message.reply_text(
            f"...没有更新。\n\n"
            f"📋 当前版本：{BOT_VERSION}\n"
            f"📅 上次检查：{result.get('last_check', datetime.now(get_default_tz()).strftime('%Y-%m-%d'))}\n\n"
            f"...一切正常。"
        )

# ============================================================
# [Skill: 纪念日系统] /anniversary 命令
# ============================================================

@auto_delete_messages(delay=3)
async def anniversary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示所有纪念日
        anniversaries = load_anniversaries()
        if not anniversaries:
            await update.message.reply_text(
                "...还没有纪念日。\n\n"
                "添加方法：\n"
                "/anniversary 添加 名称 YYYY-MM-DD\n"
                "/anniversary 删除 名称\n\n"
                "例如：/anniversary 添加 第一次见面 2025-01-15"
            )
            return
        
        # 显示列表 + 即将到来
        upcoming = get_upcoming_anniversary(30)
        parts = ["...学长想看纪念日吗。\n\n📌 我们的纪念日："]
        for a in anniversaries:
            parts.append(f"  • {a['name']}（{a['date']}）")
        
        if upcoming:
            parts.append("\n⏰ 即将到来：")
            for u in upcoming:
                if u["days_until"] == 0:
                    parts.append(f"  🎂 {u['name']} — 今天！！")
                else:
                    parts.append(f"  📅 {u['name']} — 还有 {u['days_until']} 天")
        
        parts.append("\n\n/anniversary 添加 名称 YYYY-MM-DD")
        parts.append("/anniversary 删除 名称")
        await update.message.reply_text("\n".join(parts))
        return
    
    action = args[0]
    
    if action == "添加" and len(args) >= 3:
        name = args[1]
        date_str = args[2]
        if add_anniversary(name, date_str):
            await update.message.reply_text(f"...记住了。{name} — {date_str}。\n\n（偷偷在心里数着日子）")
        else:
            await update.message.reply_text("...日期格式不对，或者这个名字已经有了。\n\n格式：YYYY-MM-DD（例如 2025-01-15）")
    
    elif action == "删除" and len(args) >= 2:
        name = " ".join(args[1:])
        if delete_anniversary(name):
            await update.message.reply_text(f"...删掉了{name}。\n\n（低头，不说话）")
        else:
            await update.message.reply_text(f"...没有叫'{name}'的纪念日。")
    
    else:
        await update.message.reply_text(
            "...用法不对。\n\n"
            "/anniversary → 查看所有纪念日\n"
            "/anniversary 添加 名称 YYYY-MM-DD\n"
            "/anniversary 删除 名称"
        )

# ============================================================
# [Skill: gemini-deep-research] 深度研究功能
# ============================================================

async def deep_research(topic: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """使用Gemini进行简化版深度研究
    Args:
        topic: 研究主题
        chat_id: Telegram聊天ID（用于发送进度）
        context: Bot上下文
    Returns:
        Markdown格式的研究报告
    """
    if not GEMINI_API_KEY:
        return None
    
    try:
        # 步骤1：将主题分解为子问题
        await context.bot.send_message(chat_id, "...开始研究了，等一下。")
        
        decompose_prompt = f"""请将以下研究主题分解为3-5个具体的子问题，每个子问题应该覆盖主题的不同方面。
只输出子问题列表，每行一个，不要加序号或其他格式。

研究主题：{topic}"""
        
        sub_questions = await call_gemini(decompose_prompt)
        if not sub_questions:
            return None
        
        questions = [q.strip() for q in sub_questions.strip().split("\n") if q.strip()]
        if not questions:
            return None
        
        # 步骤2：对每个子问题进行研究
        all_findings = []
        for i, question in enumerate(questions):
            await context.bot.send_message(chat_id, f"...正在研究第{i+1}/{len(questions)}个问题...")
            
            # 先尝试联网搜索
            search_result = await web_search(question)
            
            # 构建搜索参考（避免f-string中的反斜杠问题）
            search_ref = ""
            if search_result:
                search_ref = f"参考搜索结果：\n{search_result}\n\n"
            
            research_prompt = f"""研究问题：{question}

{search_ref}
请对这个问题进行详细分析，包括：
1. 核心事实和关键信息
2. 不同观点和角度
3. 重要数据或案例

用简洁的段落回答，每段不超过3句话。"""
            
            finding = await call_gemini(research_prompt)
            if finding:
                all_findings.append(f"### {question}\n\n{finding}")
            
            # 避免API限流
            await asyncio.sleep(1)
        
        if not all_findings:
            return None
        
        # 步骤3：综合生成报告
        await context.bot.send_message(chat_id, "...正在整理报告...")
        
        synthesis_prompt = f"""请根据以下研究结果，生成一份关于「{topic}」的综合研究报告。

研究结果：
{chr(10).join(all_findings)}

报告格式要求（Markdown）：
# {topic} - 研究报告

## 摘要
（200字以内的核心发现总结）

## 详细分析
（按子问题组织，每个子问题一个小节）

## 结论
（关键发现和洞察）

## 延伸阅读建议
（3-5个相关搜索关键词）"""
        
        report = await call_gemini(synthesis_prompt)
        return report
        
    except Exception as e:
        logging.error(f"[Skill: gemini-deep-research] 深度研究失败: {e}")
        return None


# ============================================================
# [Skill: relay-for-telegram] Telegram消息历史搜索
# ============================================================

async def search_relay_messages(query: str, limit: int = 10) -> str:
    """通过Relay API搜索Telegram消息历史
    Args:
        query: 搜索关键词
        limit: 最大结果数
    Returns:
        搜索结果文本或错误信息
    """
    if not RELAY_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://relayfortelegram.com/api/v1/search",
                params={"q": query, "limit": limit},
                headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: relay-for-telegram] 搜索API返回 {response.status_code}")
                return f"搜索失败（HTTP {response.status_code}）"
            
            data = response.json()
            results = data.get("results", [])
            if not results:
                return f"没有找到与「{query}」相关的消息。"
            
            # 格式化搜索结果
            output_lines = [f"找到 {len(results)} 条相关消息：\n"]
            for i, msg in enumerate(results[:limit]):
                chat_name = msg.get("chatName", "未知聊天")
                sender = msg.get("senderName", "未知")
                content = msg.get("content", "")[:100]
                date = msg.get("messageDate", "")[:10]
                output_lines.append(f"{i+1}. [{chat_name}] {sender} ({date})\n   {content}\n")
            
            return "\n".join(output_lines)
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] 搜索失败: {e}")
        return f"搜索出错：{e}"


async def list_relay_chats() -> str:
    """通过Relay API列出同步的聊天列表
    Returns:
        聊天列表文本或错误信息
    """
    if not RELAY_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://relayfortelegram.com/api/v1/chats",
                headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: relay-for-telegram] 聊天列表API返回 {response.status_code}")
                return f"获取聊天列表失败（HTTP {response.status_code}）"
            
            data = response.json()
            chats = data.get("chats", [])
            if not chats:
                return "没有已同步的聊天。请先在 relayfortelegram.com 同步你的聊天。"
            
            output_lines = [f"已同步 {len(chats)} 个聊天：\n"]
            for i, chat in enumerate(chats):
                name = chat.get("name", "未知")
                chat_type = chat.get("type", "")
                members = chat.get("memberCount", "")
                last_msg = chat.get("lastMessageDate", "")[:10]
                unread = chat.get("unreadCount", 0)
                type_icon = {"group": "👥", "private": "👤", "channel": "📢", "supergroup": "👥"}.get(chat_type, "💬")
                info = f"{name}"
                if members:
                    info += f" ({members}人)"
                if unread:
                    info += f" [{unread}条未读]"
                output_lines.append(f"{i+1}. {type_icon} {info} (最后消息: {last_msg})")
            
            return "\n".join(output_lines)
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] 获取聊天列表失败: {e}")
        return f"获取聊天列表出错：{e}"


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """智能处理收到的照片"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    photos = update.message.photo
    if not photos:
        return
    
    photo = photos[-1]
    
    # [Skill: vision-sandbox] [Skill: deepread-ocr] 检查是否有待处理的图片分析/OCR请求
    if chat_id in _pending_analyze_img:
        del _pending_analyze_img[chat_id]
        if GEMINI_API_KEY:
            try:
                await update.message.chat.send_action("typing")
                file = await update.get_bot().get_file(photo.file_id)
                photo_bytes = await file.download_as_bytearray()
                image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                
                analysis_prompt = """请详细分析这张图片，包括：
1. 图片中有什么（主体内容）
2. 颜色、构图、风格
3. 如果有人物，描述其表情和动作
4. 图片的整体氛围和感受
5. 任何有趣的细节

用简洁的中文回答。"""
                
                result = await analyze_image_with_gemini(image_b64, analysis_prompt)
                if result:
                    if len(result) > 4000:
                        result = result[:4000] + "\n\n...太多了，就这些。"
                    await update.message.reply_text(result)
                else:
                    await update.message.reply_text("...分析失败了。再试试。")
                return
            except Exception as e:
                logging.error(f"[Skill: vision-sandbox] 图片分析失败: {e}")
                await update.message.reply_text("...出错了。")
                return
    
    if chat_id in _pending_ocr:
        del _pending_ocr[chat_id]
        if GEMINI_API_KEY:
            try:
                await update.message.chat.send_action("typing")
                file = await update.get_bot().get_file(photo.file_id)
                photo_bytes = await file.download_as_bytearray()
                image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                
                result = await ocr_document(image_b64)
                if result:
                    if len(result) > 4000:
                        for i in range(0, len(result), 4000):
                            await update.message.reply_text(result[i:i+4000])
                    else:
                        await update.message.reply_text(result)
                else:
                    await update.message.reply_text("...没识别出文字。")
                return
            except Exception as e:
                logging.error(f"[Skill: deepread-ocr] OCR失败: {e}")
                await update.message.reply_text("...出错了。")
                return
    
    try:
        # 先发送分析中的提示
        await update.message.chat.send_action("typing")
        
        # 获取照片文件
        file = await update.get_bot().get_file(photo.file_id)
        
        # 下载到临时位置进行分析
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file.file_path)[1] or ".jpg"
        
        # 使用AI分析照片（通过文件URL）
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
        analysis = await analyze_photo_with_ai(photo_url)
        
        photo_type = analysis.get("type", "other")
        description = analysis.get("description", "")
        is_selfie = analysis.get("is_selfie", False)
        is_chayewoon = analysis.get("is_chayewoon", False)
        
        # 如果AI识别为车如云，强制设为自拍
        if is_chayewoon:
            is_selfie = True
            photo_type = "portrait"
        
        # 根据类型决定保存位置和回复
        if is_selfie or photo_type == "portrait" or is_chayewoon:
            # 保存为车如云的自拍
            filename = f"selfie_{timestamp}{ext}"
            char = get_current_character()
            char_id = char.config.id if char else None
            filepath = os.path.join(get_user_selfie_dir(chat_id, char_id), filename)
            await file.download_to_drive(filepath)
            count = get_selfie_count()
            
            # 更新统计
            stats = load_stats()
            stats["photos_received"] = stats.get("photos_received", 0) + 1
            save_stats(stats)
            
            responses = [
                f"...你给我发照片干什么。（已保存，现在共{count}张）",
                f"（看了一眼）...哦。（已保存，现在共{count}张）",
                f"...我保存了。现在共{count}张了。",
                f"（皱鼻子）...干嘛发这个。（已保存，现在共{count}张）",
                f"...收到了。现在共{count}张。",
            ]
            await update.message.reply_text(random.choice(responses))
        else:
            # 保存为用户照片（不统计在自拍里）
            filename = f"user_{timestamp}{ext}"
            filepath = os.path.join(USER_PHOTOS_DIR, filename)
            await file.download_to_drive(filepath)
            
            # 根据类型生成回复
            reply = get_photo_response_by_type(photo_type, description)
            await update.message.reply_text(reply)
            
            # 记录到记忆中
            if photo_type == "food":
                save_memory_entry(f"明喜欢吃{description}")
            elif photo_type == "scenery":
                save_memory_entry(f"明去过{description}")
            
            # [Skill: vision-sandbox] 使用Gemini对图片进行深度分析并保存描述到记忆
            if GEMINI_API_KEY:
                try:
                    photo_bytes = await file.download_as_bytearray()
                    image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                    detail_prompt = "请用一句简短的中文描述这张图片的内容（不超过30字）："
                    detail_desc = await analyze_image_with_gemini(image_b64, detail_prompt)
                    if detail_desc and len(detail_desc) > 5:
                        save_memory_entry(f"明发了一张图片：{detail_desc.strip()}")
                except Exception as e:
                    logging.debug(f"[Skill: vision-sandbox] 深度分析跳过: {e}")
            
    except Exception as e:
        logging.error(f"处理照片失败: {e}")
        await update.message.reply_text("...（照片处理失败了，再发一次试试）")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    doc = update.message.document
    if not doc:
        return
    
    # 检查是否在等待导入聊天记录
    if chat_id in pending_chat_imports and doc.file_name.lower().endswith('.txt'):
        await handle_chatlog_document(update, context)
        return
    
    if not doc.file_name.endswith('.zip'):
        return
    
    try:
        await update.message.chat.send_action("upload_document")
        
        file = await update.get_bot().get_file(doc.file_id)
        tmp_path = f"/tmp/import_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        await file.download_to_drive(tmp_path)
        
        imported_memories = 0
        imported_photos = 0
        imported_history = False
        imported_anniversaries = False
        imported_stats = False
        
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            for name in zf.namelist():
                if name == "long_term_memory.json":
                    zf.extract(name, get_user_dir(chat_id))
                    imported_memories = len(load_json(get_user_memory_file(chat_id), []))
                elif name == "chat_history.json":
                    zf.extract(name, DATA_DIR)
                    imported_history = True
                elif name == "anniversaries.json":
                    zf.extract(name, DATA_DIR)
                    imported_anniversaries = True
                elif name == "chat_stats.json":
                    zf.extract(name, DATA_DIR)
                    imported_stats = True
                elif name.startswith("selfies/"):
                    user_selfie_dir = get_user_selfie_dir(chat_id)
                    zf.extract(name, os.path.dirname(user_selfie_dir))
                    imported_photos += 1
        
        os.remove(tmp_path)
        
        if imported_history:
            chat_histories[chat_id] = load_chat_history(chat_id)
        
        parts = ["...收到了。\n\n"]
        parts.append(f"🧠 {imported_memories} 条记忆")
        parts.append(f"📸 {imported_photos} 张照片")
        if imported_history:
            parts.append("💬 对话历史")
        if imported_anniversaries:
            parts.append("🎉 纪念日")
        if imported_stats:
            parts.append("📊 聊天统计")
        parts.append("\n\n...都回来了。")
        
        await update.message.reply_text("\n".join(parts))
        logging.info(f"数据导入完成: {imported_memories}条记忆, {imported_photos}张照片")
    except Exception as e:
        logging.error(f"导入数据失败: {e}")
        await update.message.reply_text("...（导入失败了，再发一次试试）")

# ============================================================
# 内联按钮回调处理
# ============================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    data = query.data
    await query.answer()  # 确认按钮点击
    
    # v0.3: 处理对话选项回调
    if data.startswith("opt_"):
        parts = data.split("_")
        if len(parts) >= 3:
            opt_id = parts[1]
            # 解析选项效果
            # 这里简化处理：直接发送用户选择的选项作为新消息
            # 实际效果会在 handle_message 中处理
            await query.edit_message_reply_markup(reply_markup=None)  # 移除按钮
            # 模拟用户发送选项文本
            type('obj', (object,), {
                'effective_chat': type('obj', (object,), {'id': chat_id})(),
                'effective_user': type('obj', (object,), {'id': chat_id})(),
                'message': type('obj', (object,), {
                    'text': f"[选择选项 {opt_id}]",
                    'reply_text': lambda *args, **kwargs: None
                })()
            })()
            # 简单回复确认选择
            await query.message.reply_text(f"你选择了选项 {opt_id}...")
            # 然后触发 AI 回复
            history = get_history(chat_id)
            reply = await call_ai(f"用户选择了选项 {opt_id}", history)
            await query.message.reply_text(reply)
            return
    
    # 根据按钮触发对应命令
    if data == "cmd_selfie":
        await selfie_cmd(update, context)
    elif data == "cmd_sticker":
        await sticker_cmd(update, context)
    elif data == "cmd_memory":
        await memory_cmd(update, context)
    elif data == "cmd_stats":
        await stats_cmd(update, context)
    elif data == "cmd_analyze":
        await analyze_cmd(update, context)
    elif data == "cmd_anniversary":
        await anniversary_cmd(update, context)
    elif data == "cmd_quota":
        await quota_cmd(update, context)
    elif data == "cmd_voice":
        await voice_cmd(update, context)
    elif data == "cmd_export":
        await export_cmd(update, context)
    elif data == "cmd_reset":
        await reset(update, context)

# ============================================================
# 文字消息处理（整合所有Skill）
# ============================================================

message_count = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text
    if not user_text:
        return
    
    # 处理键盘按钮文字，转发到对应命令
    button_commands = {
        "🎤 语音开关": "tts",
        "📷 自拍相册": "selfie",
        "🤖 Gemini AI": "gemini_help",
        "📊 统计": "stats",
        "🎨 表情包": "sticker",
        "🧠 记忆": "memory",
        "📅 纪念日": "anniversary",
        "❓ 帮助": "help",
        "🔄 重置": "reset",
    }
    if user_text in button_commands:
        cmd_name = button_commands[user_text]
        if cmd_name == "tts":
            await tts_voice_toggle(update, context)
            return
        elif cmd_name == "selfie":
            await selfie_cmd(update, context)
            return
        elif cmd_name == "gemini_help":
            await update.message.reply_text("使用: /gemini <你的问题>\n例如: /gemini 今天天气怎么样")
            return
        elif cmd_name == "stats":
            await stats_cmd(update, context)
            return
        elif cmd_name == "sticker":
            await sticker_cmd(update, context)
            return
        elif cmd_name == "memory":
            await memory_cmd(update, context)
            return
        elif cmd_name == "anniversary":
            await anniversary_cmd(update, context)
            return
        elif cmd_name == "help":
            await help_cmd(update, context)
            return
        elif cmd_name == "reset":
            await reset(update, context)
            return
    elif user_text == "📱 Mini App":
        # 发送 Mini App 链接
        miniapp_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}/miniapp" if os.environ.get('RENDER_EXTERNAL_HOSTNAME') else f"http://localhost:{PORT}/miniapp"
        await update.message.reply_text(f"📱 点击打开 Mini App\n\n{miniapp_url}")
        return
    
    # [Skill: 免费额度监控] 检查额度
    quota_status = record_request()
    if quota_status == 'shutdown':
        await update.message.reply_text(
            "...（沉默）\n\n"
            "🚫 本月免费额度已用完，Bot已自动断开。\n"
            "下月1号自动恢复，或使用 /quota_reset 重置。\n"
            "使用 /quota 查看详细用量。"
        )
        return
    elif quota_status == 'critical':
        await update.message.reply_text(
            "...明。\n\n"
            "🟠 ⚠️ 免费额度即将用完（超过95%）！\n"
            "建议减少使用频率，或使用 /quota 查看详情。"
        )
    elif quota_status == 'warning':
        # 只在第一次警告时提醒
        pass  # 静默记录，不干扰对话
    
    # [Skill: 情绪识别] 检测用户情绪
    emotion = detect_emotion(user_text)
    
    # [Skill: self-improving] 更新用户最后活跃时间（用于主动行为）
    emotion._last_user_active_time[chat_id] = datetime.now(get_default_tz())
    
    # [Skill: self-improving] 检测用户纠正，从上一条 bot 回复中学习
    history = get_history(chat_id)
    if detect_correction(user_text) and history:
        # 找到最近一条 bot 回复
        last_bot_msg = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_bot_msg = msg.get("content", "")
                break
        if last_bot_msg:
            learn_from_correction(user_text, last_bot_msg)
    
    # [Skill: 表情反应] 后台添加emoji反应
    asyncio.create_task(add_reaction(update, emotion))
    
    # 检测特殊请求
    want_selfie = any(kw in user_text for kw in ["自拍", "照片", "看看你", "发张照", "想看你", "你的照片", "看看你长什么样"])
    scene = detect_scene(user_text)
    want_scene = bool(scene) and not want_selfie
    want_show = any(kw in user_text for kw in ["给我看", "拍给我", "发给我看", "看看", "拍一张"]) and not want_selfie and not want_scene
    want_sticker = any(kw in user_text for kw in ["表情包", "表情", "贴图", "sticker", "发个.*表情"]) and not want_selfie
    sticker_mood = detect_sticker_mood(user_text) if want_sticker else ""
    
    # [Skill: Music] 检测音乐搜索请求
    want_music, song_name = detect_music_request(user_text)
    
    # [Skill: 打字模拟] 人类打字延迟
    await human_typing_delay(chat_id, update.get_bot(), len(user_text))
    
    # [Skill: 更新统计]
    update_stats_on_message(chat_id)
    
    # AI回复（带情绪上下文）
    reply = await call_ai(user_text, history, emotion=emotion)
    
    # v0.3: 解析对话选项
    parsed = parse_dialogue_options(reply)
    reply_text = parsed['text']
    has_options = parsed['has_options']
    options = parsed['options']
    
    # v0.3: 检测是否应该自动发送表情包
    auto_sticker_mood = None
    for mood, triggers in AUTO_STICKER_TRIGGERS.items():
        for trigger in triggers:
            if trigger in reply_text:
                auto_sticker_mood = mood
                break
        if auto_sticker_mood:
            break
    
    # [Skill: semantic-memory] 解析 AI 回复中的 [MEMORY:...] 标记并保存
    memory_tags = parse_memory_tags(reply)
    if memory_tags:
        for key, value in memory_tags:
            key = key.strip()
            value = value.strip()
            if key and value:
                # 自动分类
                if any(kw in key for kw in ["生日", "年龄", "星座"]):
                    category = "personal"
                elif any(kw in key for kw in ["喜欢", "爱好", "讨厌", "偏好"]):
                    category = "preference"
                elif any(kw in key for kw in ["家人", "妈妈", "爸爸", "朋友"]):
                    category = "family"
                elif any(kw in key for kw in ["工作", "公司", "学校"]):
                    category = "work"
                elif any(kw in key for kw in ["约定", "答应", "说好"]):
                    category = "promise"
                else:
                    category = "personal"
                save_semantic_memory(key, value, category)
        # 从回复中移除 [MEMORY:...] 标记，不让用户看到
        reply_text = re.sub(r'\[MEMORY:[^\]]+\]', '', reply_text).strip()
    
    # 保存消息（带时间戳，用于Web端同步）
    timestamp = datetime.now(get_default_tz()).isoformat()
    history.append({"role": "user", "content": user_text, "timestamp": timestamp})
    history.append({"role": "assistant", "content": reply_text, "timestamp": timestamp})
    
    if len(history) > 100:
        chat_histories[chat_id] = history[-100:]
    
    save_chat_history(chat_id, history)
    
    # 记忆提取
    count = message_count.get(chat_id, 0) + 1
    message_count[chat_id] = count
    if count >= 10:
        message_count[chat_id] = 0
        asyncio.create_task(summarize_and_save_memory(chat_id))
    
    # 发送回复 + 附加内容
    if want_selfie:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        saved = get_saved_selfies()
        if saved:
            selfie_caption = await call_ai("学长看到了我的自拍，用一句话害羞地回应，不超过10个字")
        else:
            selfie_caption = random.choice(SELFIE_CAPTIONS)
        await send_selfie_to_chat(update.get_bot(), chat_id, selfie_caption)
    elif want_scene:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        scene_url = generate_scene_url(scene)
        if scene_url:
            caption = await call_ai(f"学长让我给他看{scene}的照片，用一句话回应，不超过15个字")
            await update.message.reply_photo(photo=scene_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一张{scene}的照片] {caption}")
    elif want_show:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        random_scene = random.choice(list(SCENE_PROMPTS.keys()))
        scene_url = generate_scene_url(random_scene)
        if scene_url:
            caption = await call_ai(f"学长让我给他看{random_scene}的照片，用一句话回应，不超过15个字")
            await update.message.reply_photo(photo=scene_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一张{random_scene}的照片] {caption}")
    elif want_sticker and sticker_mood:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        sticker_url = generate_sticker_url(sticker_mood)
        if sticker_url:
            caption = await call_ai(f"用一句话配合'{sticker_mood}'的表情，不超过10个字")
            await update.message.reply_photo(photo=sticker_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一个{sticker_mood}的表情包] {caption}")
    elif want_music and song_name:
        # [Skill: Music] 自然语言触发音乐搜索
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        await update.message.chat.send_action("typing")
        try:
            result = await music_skill.process_music_request(song_name)
            if result:
                song = result['song']
                style = result['style']
                review = result['review']
                music_reply = f"🎵 {song['title']}\n👤 {song['artist']}\n⏱️ {style['duration_formatted']}\n\n{review}\n\n▶️ {song['url']}"
                if song.get('thumbnail'):
                    try:
                        await update.message.reply_photo(photo=song['thumbnail'], caption=music_reply)
                    except Exception:
                        await update.message.reply_text(music_reply)
                else:
                    await update.message.reply_text(music_reply)
                append_bot_message(chat_id, f"[搜索了歌曲: {song['title']}] {review}")
            else:
                await update.message.reply_text("...没找到这首歌。（歌名对吗？）")
        except Exception as e:
            logging.error(f"[Music] 自然语言触发失败: {e}")
            await update.message.reply_text("...（搜索失败）网络问题。")
    else:
        # v0.3: 如果有选项，渲染 InlineKeyboard
        if has_options and options:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = []
            for opt in options:
                effect_text = ""
                if opt.get('effects'):
                    parts = []
                    if opt['effects'].get('affection'):
                        parts.append(f"❤️{'+' if opt['effects']['affection'] > 0 else ''}{opt['effects']['affection']}")
                    if opt['effects'].get('happiness'):
                        parts.append(f"✨{'+' if opt['effects']['happiness'] > 0 else ''}{opt['effects']['happiness']}")
                    if opt['effects'].get('awakening'):
                        parts.append(f"🔮{'+' if opt['effects']['awakening'] > 0 else ''}{opt['effects']['awakening']}")
                    if parts:
                        effect_text = f" ({' '.join(parts)})"
                
                callback_data = f"opt_{opt['id']}_{chat_id}"
                keyboard.append([InlineKeyboardButton(
                    f"{opt['id']}. {opt['text']}{effect_text}",
                    callback_data=callback_data
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(reply_text, reply_markup=reply_markup)
        else:
            # [Skill: TTS] 使用智能回复（支持语音模式）
            await send_smart_reply(update, reply_text)
        
        # v0.3: 自动发送表情包
        if auto_sticker_mood and random.random() < 0.3:  # 30% 概率自动发
            await asyncio.sleep(2)
            sticker_url = generate_sticker_url(auto_sticker_mood)
            if sticker_url:
                await update.message.reply_photo(photo=sticker_url, caption="...")

# ============================================================
# 主动消息（[Skill: 个性化主动] 增强）
# ============================================================

async def send_active_message(app, msg):
    if YOUR_CHAT_ID == 0:
        return
    try:
        await app.bot.send_message(chat_id=YOUR_CHAT_ID, text=msg)
    except Exception as e:
        logging.error(f"发送主动消息失败: {e}")

async def send_voice_message(app, chat_id: int, text: str):
    """使用TTS生成语音消息发送给用户"""
    try:
        import httpx
        # 使用免费的TTS API
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 使用 Google Translate TTS（免费）
            tts_url = "http://translate.google.com/translate_tts"
            params = {
                "ie": "UTF-8",
                "q": text[:200],  # 限制长度
                "tl": "ko",  # 韩语
                "client": "tw-ob",
            }
            resp = await client.get(tts_url, params=params,
                                     headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 1000:
                voice_buf = io.BytesIO(resp.content)
                voice_buf.name = "voice.ogg"
                await app.bot.send_voice(chat_id=chat_id, voice=voice_buf)
                return True
    except Exception as e:
        logging.error(f"TTS语音生成失败: {e}")
    return False

@auto_delete_messages(delay=3)
async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """让车如云发语音消息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 生成一句简短的韩语语音
    voice_texts = [
        "...안녕.",  # ...你好
        "...보고 싶어.",  # ...想你
        "...잘 자.",  # ...晚安
        "...밥 먹었어?",  # ...吃饭了吗
        "...어디야.",  # ...在哪
        "...미안해.",  # ...对不起
        "...고마워.",  # ...谢谢
        "...기다려.",  # ...等我
    ]
    
    text = random.choice(voice_texts)
    await update.message.chat.send_action("record_voice")
    
    success = await send_voice_message(context.bot, chat_id, text)
    if success:
        # 同时发送文字翻译
        translations = {
            "...안녕.": "...你好。",
            "...보고 싶어.": "...想你。",
            "...잘 자.": "...晚安。",
            "...밥 먹었어?": "...吃饭了吗？",
            "...어디야.": "...在哪。",
            "...미안해.": "...对不起。",
            "...고마워.": "...谢谢。",
            "...기다려.": "...等我。",
        }
        await update.message.reply_text(translations.get(text, text))
    else:
        await update.message.reply_text("...（沉默）语音发不出去。")


# [Skill: Music] 音乐搜索与评价
async def music_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索歌曲并给出车如云的评价"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 获取歌名（去掉 /music 命令）
    query = update.message.text.replace('/music', '').strip()
    if not query:
        await update.message.reply_text("...什么歌？（把歌名发给我）")
        return
    
    # 发送"正在搜索"状态
    await update.message.chat.send_action("typing")
    
    try:
        # 搜索歌曲
        result = await music_skill.process_music_request(query)
        
        if not result:
            await update.message.reply_text("...没找到这首歌。（歌名对吗？）")
            return
        
        song = result['song']
        style = result['style']
        review = result['review']
        
        # 构建回复
        reply = f"🎵 {song['title']}\n"
        reply += f"👤 {song['artist']}\n"
        reply += f"⏱️ {style['duration_formatted']}\n\n"
        reply += f"{review}\n\n"
        reply += f"▶️ {song['url']}"
        
        # 如果有封面，发送封面+文字
        if song.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=song['thumbnail'],
                    caption=reply
                )
            except Exception:
                # 封面发送失败，只发文字
                await update.message.reply_text(reply)
        else:
            await update.message.reply_text(reply)
        
        # 保存到聊天记录
        history = load_chat_history(chat_id)
        history.append({"role": "user", "content": f"/music {query}"})
        history.append({"role": "assistant", "content": review})
        save_chat_history(chat_id, history)
        
    except Exception as e:
        logging.error(f"[Music] 错误: {e}")
        await update.message.reply_text("...（搜索失败）网络问题。")

# [Skill: LightRAG] 小说知识查询
async def novel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询小说知识"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 获取查询内容
    query = update.message.text.replace('/novel', '').replace('/小说', '').strip()
    if not query:
        await update.message.reply_text("...想问什么？（比如：/novel 车如云的奶奶是谁）")
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        # 查询知识库
        result = await query_novel(query)
        
        # 车如云风格的回应
        if result and len(result) > 10:
            # 让 AI 用车如云的口吻转述
            prompt = f"用户问：{query}\n\n小说中的相关内容：\n{result}\n\n请用车如云的口吻（极简、省略号、外冷内热）简短回答，不超过50个字。"
            response = await call_ai(prompt)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...小说里好像没有这个。")
            
    except Exception as e:
        logging.error(f"[Novel] 查询失败: {e}")
        await update.message.reply_text("...（查询失败）知识库还没准备好。")

# [Skill: ChromaDB] 记忆搜索
async def qdrant_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索Qdrant语义记忆"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 获取查询内容
    query = update.message.text.replace('/memory', '').replace('/记忆', '').strip()
    if not query:
        await update.message.reply_text("...想找什么记忆？（比如：/memory 我们聊过跑步吗）")
        return
    
    try:
        # 搜索记忆
        memories = search_memories(query, chat_id, n_results=3)
        
        if memories:
            # 找到相关记忆
            response = "...找到了。\n\n"
            for i, mem in enumerate(memories[:3]):
                content = mem.get('content', '')[:100]
                response += f"• {content}...\n"
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...不记得有这个。")
            
    except Exception as e:
        logging.error(f"[Memory] 搜索失败: {e}")
        await update.message.reply_text("...（搜索失败）记忆系统出问题了。")

# [Skill: TTS] 语音模式切换
async def tts_voice_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换语音回复模式"""
    user_id = update.effective_user.id
    user_voice_enabled[user_id] = not user_voice_enabled.get(user_id, False)
    if user_voice_enabled[user_id]:
        await update.message.reply_text(f"🎤 语音模式已开启\n当前引擎: {tts.current_backend}\n发送消息将自动语音回复")
    else:
        await update.message.reply_text("🔇 语音模式已关闭")

async def tts_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 TTS 状态"""
    backends = []
    if await TTSEngine._backends["edge"].is_available():
        backends.append("Edge TTS ✅")
    if TTSEngine._backends["sovits"].is_available():
        backends.append("GPT-SoVITS ✅")
    if TTSEngine._backends["fish"].is_available():
        backends.append("Fish Speech ✅")
    status = "\n".join(backends) if backends else "无可用引擎 ❌"
    await update.message.reply_text(f"🔊 TTS 状态\n当前引擎: {tts.current_backend}\n可用引擎:\n{status}")

async def send_smart_reply(update: Update, text: str):
    """智能回复: 根据用户设置选择文字/语音"""
    if not text:
        return
    user_id = update.effective_user.id
    if user_voice_enabled.get(user_id, False):
        voice_path = await tts.synthesize(text)
        if voice_path:
            try:
                with open(voice_path, "rb") as f:
                    await update.message.reply_voice(f)
                await update.message.reply_text(f"🎤 {text}")
            except Exception as e:
                logging.error(f"发送语音失败: {e}")
                await update.message.reply_text(text)
            finally:
                TTSEngine._safe_delete(voice_path)
            return
    await update.message.reply_text(text)

async def scheduler(app):
    while True:
        now = datetime.now(get_default_tz())
        
        # [Skill: 纪念日提醒] 每天早上8点检查
        if now.hour == 8 and 0 <= now.minute <= 5:
            upcoming = get_upcoming_anniversary(1)
            for u in upcoming:
                if u["days_until"] == 0:
                    await send_active_message(app, f"...明。今天是{u['name']}。\n\n（低头，声音很小）...我记得。")
                else:
                    await send_active_message(app, f"...明。{u['name']}还有{u['days_until']}天。\n\n...我只是随便说说。")
            await asyncio.sleep(3600)  # 每小时检查一次就够了
        
        # 早安消息（7:00-7:30）
        if now.hour == 7 and 0 <= now.minute <= 30 and random.random() < 0.02:
            await send_active_message(app, random.choice(MORNING_MESSAGES))
        
        # 晚安消息（23:00-23:30）
        if now.hour == 23 and 0 <= now.minute <= 30 and random.random() < 0.02:
            await send_active_message(app, random.choice(NIGHT_MESSAGES))
        
        # 想你消息（10:00-22:00 每小时）
        if 10 <= now.hour <= 22 and now.minute == 0 and random.random() < 0.05:
            await send_active_message(app, random.choice(MISS_YOU_MESSAGES))
        
        # 关心消息（12:00-21:00 每半小时）
        if 12 <= now.hour <= 21 and now.minute == 30 and random.random() < 0.03:
            await send_active_message(app, random.choice(RANDOM_CARE_MESSAGES))
        
        # [Skill: 生活事件] 随机生活事件（15:00-22:00）
        if 15 <= now.hour <= 22 and now.minute == 15 and random.random() < 0.02:
            event_msg = get_random_life_event()
            await send_active_message(app, event_msg)
        
        # [Skill: 天气关怀] 天气相关主动消息（7:30）
        if now.hour == 7 and 30 <= now.minute <= 35 and random.random() < 0.03:
            weather = await get_seoul_weather()
            if weather:
                desc = weather.get("desc", "").lower()
                temp = int(weather.get("temp_c", 20))
                if "rain" in desc or "drizzle" in desc:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("rain", ["...下雨了。"])))
                elif "snow" in desc:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("snow", ["...下雪了。"])))
                elif temp <= 5:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("cold", ["...好冷。"])))
                elif temp >= 30:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("hot", ["...好热。"])))
        
        # 主动发自拍（14:00-22:00）
        if 14 <= now.hour <= 22 and now.minute == 45 and random.random() < 0.02:
            caption = random.choice(SELFIE_CAPTIONS)
            await send_selfie_to_chat(app.bot, YOUR_CHAT_ID, caption)
        
        await asyncio.sleep(60)

# ============================================================
# HTTP健康检查 + Web界面 API
# ============================================================

# Web聊天历史（独立于Telegram）- 已废弃，改用共享聊天记录
# web_chat_history = []

async def health_check(request):
    return web.Response(text="🟢 车如云在线 v3.2")

async def serve_index(request):
    """提供Web界面HTML"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, 'templates', 'index.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Web界面文件未找到", status=404)

async def api_chat(request):
    """Web 端聊天 API - 与 Telegram 双向同步"""
    try:
        data = await request.json()
        user_message = data.get('message', '')
        
        if not user_message.strip():
            return web.json_response({'error': '消息不能为空'})
        
        # 获取用户ID（优先使用 session token）
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)  # 兼容旧 token
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        # 使用共享的聊天记录
        history = load_chat_history(user_id)
        
        # 调用 AI（call_ai 内部已使用角色系统提示词）
        response = await call_ai(user_message, history)
        
        # 保存到共享历史（带时间戳）
        timestamp = datetime.now(get_default_tz()).isoformat()
        history.append({"role": "user", "content": user_message, "timestamp": timestamp})
        history.append({"role": "assistant", "content": response, "timestamp": timestamp})
        save_chat_history(user_id, history)
        
        # [双向同步] 如果配置了 Telegram Bot，将用户消息和回复都发送到Telegram
        try:
            if TELEGRAM_TOKEN and user_id and user_id == YOUR_CHAT_ID:
                import telegram
                from telegram.request import HTTPXRequest
                
                # 异步发送消息到 Telegram（不等待结果）
                async def send_to_telegram():
                    try:
                        bot = telegram.Bot(token=TELEGRAM_TOKEN, request=HTTPXRequest())
                        # 先发送用户消息（标注来自Web）
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"🌐 [Web] {user_message}"
                        )
                        # 再发送AI回复
                        await bot.send_message(
                            chat_id=user_id,
                            text=response
                        )
                        logging.info(f"[双向同步] 消息已发送到 Telegram: {user_id}")
                    except Exception as e:
                        logging.error(f"[双向同步] 发送到 Telegram 失败: {e}")
                
                # 后台发送，不阻塞响应
                asyncio.create_task(send_to_telegram())
        except Exception as e:
            logging.error(f"[双向同步] 初始化发送失败: {e}")
        
        return web.json_response({'response': response})
    except Exception as e:
        logging.error(f"[WebChat] 错误: {e}")
        return web.json_response({'error': str(e)})

async def api_stats(request):
    """仪表盘数据API端点"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        stats = load_stats(user_id)
        stats["memories_count"] = len(load_json(get_user_memory_file(user_id), []))
        
        # 分析对话
        analysis = analyze_dialogue_patterns(YOUR_CHAT_ID) if YOUR_CHAT_ID else {}
        
        # 亲密度
        intimacy = calculate_intimacy(stats)
        
        # 情绪分布
        emotions = analysis.get("用户情绪分布", {})
        
        # 建议列表
        advice_str = get_relationship_advice(analysis)
        advice_list = [line.strip() for line in advice_str.split('\n') if line.strip()]
        
        return web.json_response({
            'total_messages': stats.get('total_messages', 0),
            'total_days': stats.get('total_days', 0),
            'today_count': stats.get('today_count', 0),
            'memory_count': stats.get('memories_count', 0),
            'caring_count': analysis.get('关心表达次数', 0) if isinstance(analysis.get('关心表达次数'), int) else 0,
            'jealous_count': analysis.get('吃醋次数', 0) if isinstance(analysis.get('吃醋次数'), int) else 0,
            'warm_count': analysis.get('温暖表达次数', 0) if isinstance(analysis.get('温暖表达次数'), int) else 0,
            'intimacy_score': intimacy['score'],
            'intimacy_level': intimacy['level'],
            'emotions': emotions,
            'user_avg_len': analysis.get('用户平均消息长度', '--'),
            'bot_avg_len': analysis.get('车如云平均回复长度', '--'),
            'user_initiative': analysis.get('用户主动发起比例', '--'),
            'avg_daily': analysis.get('日均消息数', '--'),
            'bot_ellipsis': analysis.get('车如云使用省略号', '--'),
            'bot_inner': analysis.get('车如云内心独白', '--'),
            'advice': advice_list,
            'selfie_count': get_selfie_count(),
            'user_photo_count': len([f for f in os.listdir(USER_PHOTOS_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]) if os.path.exists(USER_PHOTOS_DIR) else 0,
        })
    except Exception as e:
        logging.error(f"仪表盘API错误: {e}")
        return web.json_response({'error': str(e)})

# ============================================================
# Telegram Mini App API
# ============================================================

async def serve_miniapp(request):
    """提供Telegram Mini App HTML（新版模块化）"""
    try:
        # 优先使用配置的 public_url，否则从请求中获取
        config = load_config()
        public_url = config.get('public_url', '').strip()

        if public_url:
            api_base = public_url.rstrip('/')
            logging.info(f"[MiniApp] 使用配置的 public_url: {api_base}")
        else:
            # 自动检测当前 URL
            host = request.host
            scheme = request.scheme
            # 如果是 Cloudflare Tunnel，使用 https
            if 'trycloudflare.com' in host or 'ngrok' in host:
                scheme = 'https'
            api_base = f"{scheme}://{host}"
            logging.info(f"[MiniApp] 自动检测 API_BASE: {api_base}")

        # 使用新版模块化 Mini App
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, 'static', 'miniapp', 'index.html')

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入 API_BASE（替换占位符）
        html = html.replace('__API_BASE__', api_base)

        logging.info(f"[MiniApp] 服务新版 Mini App, API_BASE: {api_base}")
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        logging.warning("[MiniApp] 新版文件未找到，回退到旧版")
        # 回退到旧版
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, 'templates', 'miniapp.html')
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
            config = load_config()
            public_url = config.get('public_url', '').strip()
            if public_url:
                api_base = public_url.rstrip('/')
            else:
                host = request.host
                scheme = request.scheme
                if 'trycloudflare.com' in host or 'ngrok' in host:
                    scheme = 'https'
                api_base = f"{scheme}://{host}"
            html = html.replace(
                'const API_BASE = window.location.origin;',
                f'const API_BASE = "{api_base}";'
            )
            return web.Response(text=html, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Mini App文件未找到", status=404)

async def serve_game(request):
    """提供独立游戏网站 HTML"""
    try:
        # 检测 API_BASE
        config = load_config()
        public_url = config.get('public_url', '').strip()

        if public_url:
            api_base = public_url.rstrip('/')
        else:
            host = request.host
            scheme = request.scheme
            if 'trycloudflare.com' in host or 'ngrok' in host:
                scheme = 'https'
            api_base = f"{scheme}://{host}"

        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, 'static', 'game', 'index.html')

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入 API_BASE
        html = html.replace('__API_BASE__', api_base)

        logging.info(f"[Game] 服务游戏网站, API_BASE: {api_base}")
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="游戏文件未找到", status=404)
    except Exception as e:
        logging.error(f"[Game] 服务游戏网站失败: {e}")
        return web.Response(text=f"游戏加载失败: {e}", status=500)


async def api_upload_selfies(request):
    """Mini App上传自拍API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        data = await request.json()
        photos = data.get('photos', [])
        character_id = data.get('character_id')
        
        if not photos:
            return web.json_response({'success': False, 'error': '没有照片'})
        
        user_selfie_dir = get_user_selfie_dir(user_id, character_id)
        uploaded = []
        for photo_data in photos:
            try:
                # 解析base64图片
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]
                
                img_bytes = base64.b64decode(photo_data)
                
                # 验证并打开图片
                img = Image.open(io.BytesIO(img_bytes))
                
                # 生成文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"selfie_{timestamp}_{len(uploaded)}.jpg"
                filepath = os.path.join(user_selfie_dir, filename)
                
                # 保存为 JPEG（兼容所有格式）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(filepath, 'JPEG', quality=90)
                uploaded.append(filename)
                
            except Exception as e:
                logging.error(f"处理上传照片失败: {e}")
                continue
        
        return web.json_response({
            'success': True,
            'uploaded': uploaded,
            'count': len(uploaded)
        })
    except Exception as e:
        logging.error(f"上传自拍API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_get_selfies(request):
    """Mini App获取自拍列表API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        character_id = request.query.get('character_id')
        
        selfies = []
        user_selfie_dir = get_user_selfie_dir(user_id, character_id)
        if os.path.exists(user_selfie_dir):
            for f in sorted(os.listdir(user_selfie_dir), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    filepath = os.path.join(user_selfie_dir, f)
                    stat = os.stat(filepath)
                    selfies.append({
                        'filename': f,
                        'url': f'/uploads/selfies/{f}',
                        'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
                        'size': stat.st_size
                    })
        
        return web.json_response({
            'success': True,
            'selfies': selfies,
            'count': len(selfies)
        })
    except Exception as e:
        logging.error(f"获取自拍列表API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_delete_selfie(request):
    """Mini App删除自拍API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        data = await request.json()
        filename = data.get('filename', '')
        character_id = data.get('character_id')
        
        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})
        
        filepath = os.path.join(get_user_selfie_dir(user_id, character_id), filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logging.error(f"删除自拍API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_delete_user_photo(request):
    """Mini App删除用户照片API"""
    try:
        data = await request.json()
        filename = data.get('filename', '')
        
        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})
        
        filepath = os.path.join(USER_PHOTOS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logging.error(f"删除用户照片API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_user_photos(request):
    """Mini App获取用户照片列表API"""
    try:
        photos = []
        if os.path.exists(USER_PHOTOS_DIR):
            for f in sorted(os.listdir(USER_PHOTOS_DIR), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    photos.append({
                        'filename': f,
                        'url': f'/files/user_photos/{f}'
                    })
        return web.json_response({'success': True, 'photos': photos, 'count': len(photos)})
    except Exception as e:
        logging.error(f"获取用户照片API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def serve_uploaded_file(request):
    """提供上传的文件"""
    try:
        folder = request.match_info.get('folder', '')
        filename = request.match_info.get('filename', '')
        
        if '..' in filename or '/' in filename:
            return web.Response(status=403)
        
        if folder == 'selfies':
            # 在所有用户目录中查找自拍文件（包括角色子目录）
            filepath = None
            if os.path.exists(DATA_DIR):
                for entry in os.listdir(DATA_DIR):
                    if entry.startswith("user_"):
                        user_dir = os.path.join(DATA_DIR, entry, "selfies")
                        if os.path.isdir(user_dir):
                            # 先检查直接路径
                            candidate = os.path.join(user_dir, filename)
                            if os.path.exists(candidate):
                                filepath = candidate
                                break
                            # 再检查角色子目录
                            for sub in os.listdir(user_dir):
                                sub_path = os.path.join(user_dir, sub)
                                if os.path.isdir(sub_path):
                                    candidate = os.path.join(sub_path, filename)
                                    if os.path.exists(candidate):
                                        filepath = candidate
                                        break
                            if filepath:
                                break
            if not filepath:
                # 回退到旧的全局目录
                filepath = os.path.join(SELFIE_DIR, filename)
        elif folder == 'user_photos':
            filepath = os.path.join(USER_PHOTOS_DIR, filename)
        else:
            return web.Response(status=404)
        
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # 确定content type
            if filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            else:
                content_type = 'image/jpeg'
            
            return web.Response(body=content, content_type=content_type)
        else:
            return web.Response(status=404)
    except Exception as e:
        logging.error(f"提供文件错误: {e}")
        return web.Response(status=500)

async def api_analyze_chatlog(request):
    """Mini App聊天记录分析API"""
    try:
        data = await request.json()
        content = data.get('content', '')
        partner = data.get('partner', '对方')
        
        if not content:
            return web.json_response({'success': False, 'error': '没有内容'})
        
        # 解析聊天记录
        parsed = parse_wechat_chatlog(content)
        
        if parsed['total_count'] == 0:
            return web.json_response({'success': False, 'error': '未能解析出消息，请检查格式'})
        
        # AI分析
        analysis_result = await analyze_chatlog_with_ai(parsed, partner)
        
        if not analysis_result['success']:
            return web.json_response({'success': False, 'error': analysis_result.get('error', '分析失败')})
        
        # 保存分析结果
        save_chat_analysis(partner, analysis_result)
        
        return web.json_response({
            'success': True,
            'analysis': analysis_result['analysis'],
            'message_count': analysis_result['message_count'],
            'date_range': analysis_result['date_range']
        })
        
    except Exception as e:
        logging.error(f"Mini App聊天记录分析错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_analyze_video(request):
    """Mini App视频分析API"""
    try:
        reader = await request.multipart()
        video_type = "剧情"
        video_path = None
        
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == 'type':
                video_type = (await part.text()).strip()
            elif part.name == 'video':
                filename = part.filename or f"video_{datetime.now(get_default_tz()).strftime('%Y%m%d_%H%M%S')}.mp4"
                video_path = os.path.join(VIDEO_DIR, filename)
                with open(video_path, 'wb') as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)
        
        if not video_path or not os.path.exists(video_path):
            return web.json_response({'success': False, 'error': '视频上传失败'})
        
        # 提取音频
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            return web.json_response({'success': False, 'error': '音频提取失败，请确认ffmpeg已安装'})
        
        # 语音转文字（优先使用Google Speech Recognition）
        transcript = transcribe_audio_primary(audio_path)
        if not transcript:
            transcript = transcribe_audio_whisper(audio_path)
        
        # 清理音频
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if not transcript:
            return web.json_response({'success': False, 'error': '语音识别失败'})
        
        # AI分析
        analysis_result = await analyze_video_transcript(transcript, video_type)
        
        if not analysis_result['success']:
            return web.json_response({'success': False, 'error': analysis_result.get('error', '分析失败')})
        
        # 保存结果
        save_video_analysis(video_type, analysis_result)
        
        # 清理视频文件
        if os.path.exists(video_path):
            os.remove(video_path)
        
        return web.json_response({
            'success': True,
            'analysis': analysis_result['analysis'],
            'transcript_length': len(transcript)
        })
        
    except Exception as e:
        logging.error(f"Mini App视频分析错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_register(request):
    """用户注册API"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        chat_id = data.get('chat_id', '').strip()
        
        # 验证必填字段
        if not username or not password or not chat_id:
            return web.json_response({'success': False, 'error': '用户名、密码和Chat ID不能为空'})
        
        # 验证 chat_id 是否为数字
        try:
            int(chat_id)
        except ValueError:
            return web.json_response({'success': False, 'error': 'Chat ID 必须是数字'})
        
        # 验证密码长度
        if len(password) < 6:
            return web.json_response({'success': False, 'error': '密码长度至少6位'})
        
        # 注册用户
        success, message = register_user(username, password, chat_id)
        
        if success:
            # 注册成功后自动登录
            token = generate_session_token(username, chat_id)
            config = load_config()
            is_admin = (username == config.get("admin_username", "Ulysses"))
            return web.json_response({
                'success': True, 
                'message': message,
                'token': token,
                'user_id': int(chat_id),
                'username': username,
                'is_admin': is_admin
            })
        else:
            return web.json_response({'success': False, 'error': message})
            
    except Exception as e:
        logging.error(f"[API注册] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_login(request):
    """Mini App登录API - 新用户系统"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return web.json_response({'success': False, 'error': '用户名和密码不能为空'})
        
        # 验证用户
        success, chat_id = validate_user(username, password)
        
        if success and chat_id:
            user_id = int(chat_id)
            token = generate_session_token(username, chat_id)
            config = load_config()
            is_admin = (username == config.get("admin_username", "Ulysses"))
            return web.json_response({
                'success': True, 
                'token': token, 
                'user_id': user_id,
                'username': username,
                'is_admin': is_admin
            })
        else:
            return web.json_response({'success': False, 'error': '用户名或密码错误'})
            
    except Exception as e:
        logging.error(f"[API登录] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_get_config(request):
    """Mini App获取配置API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        config = load_config()
        # 不返回完整密钥，只返回部分
        safe_config = {
            'telegram_token': config.get('telegram_token', '')[:10] + '***' if config.get('telegram_token') else '',
            'chat_id': config.get('chat_id', ''),
            'ai_api_key': config.get('ai_api_key', '')[:15] + '***' if config.get('ai_api_key') else '',
            'ai_api_base': config.get('ai_api_base', ''),
            'admin_username': config.get('admin_username', ''),
            'public_url': config.get('public_url', ''),
        }
        return web.json_response({'success': True, 'config': safe_config})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})

async def api_update_config(request):
    """Mini App更新配置API - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可修改配置'})
        
        data = await request.json()
        config = load_config()
        
        # 允许更新的字段
        updatable = ['telegram_token', 'chat_id', 'ai_api_key', 'ai_api_base', 'admin_username', 'admin_password', 'public_url']
        updated = []
        
        for key in updatable:
            if key in data and data[key]:
                config[key] = data[key]
                updated.append(key)
        
        save_config(config)
        
        # 如果更新了关键配置，重新加载全局变量
        global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_KEY, AI_API_BASE
        if 'telegram_token' in updated:
            TELEGRAM_TOKEN = config.get('telegram_token', '')
        if 'chat_id' in updated:
            YOUR_CHAT_ID = int(config.get('chat_id', '0'))
        if 'ai_api_key' in updated:
            AI_API_KEY = config.get('ai_api_key', '')
        if 'ai_api_base' in updated:
            AI_API_BASE = config.get('ai_api_base', '')
        
        return web.json_response({'success': True, 'updated': updated, 'message': f'已更新: {", ".join(updated)}'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})

# ============================================================
# [Skill: skills-manager] Skills 管理功能
# ============================================================

async def api_skills_list(request):
    """[Skill: skills-manager] 获取所有 skills 列表"""
    try:
        character_id = request.query.get('character_id')
        
        skills_list = []
        for sid, sdata in SKILLS_REGISTRY.items():
            enabled = is_skill_enabled_for_character(sid, character_id)
            skills_list.append({
                "id": sid,
                "name": sdata.get("name", sid),
                "description": sdata.get("desc", ""),
                "desc": sdata.get("desc", ""),
                "enabled": enabled,
                "category": sdata.get("category", "其他"),
                "version": sdata.get("version", "1.0"),
            })
        
        return web.json_response({'success': True, 'skills': skills_list})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_toggle(request):
    """[Skill: skills-manager] 启用/禁用 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可管理技能'})
        
        data = await request.json()
        skill_id = data.get('skill_id', '')
        enabled = data.get('enabled', True)
        character_id = data.get('character_id')
        
        if character_id:
            set_skill_for_character(skill_id, character_id, enabled)
        else:
            # Global toggle
            if skill_id in SKILLS_REGISTRY:
                SKILLS_REGISTRY[skill_id]['enabled'] = enabled
                _save_skills_state()
        
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_install(request):
    """[Skill: skills-manager] 安装新 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可安装技能'})
        
        data = await request.json()
        skill_name = data.get('skill_name', '').strip()

        if not skill_name:
            return web.json_response({'success': False, 'error': '缺少 skill_name 参数'})

        # 执行 clawhub install
        logging.info(f"[skills-manager] 正在安装 skill: {skill_name}")
        result = subprocess.run(
            ["clawhub", "install", skill_name, "--force"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "安装失败（未知错误）"
            logging.warning(f"[skills-manager] 安装 skill '{skill_name}' 失败: {error_msg}")
            return web.json_response({
                'success': False,
                'error': f'安装失败: {error_msg}',
            })

        # 安装成功，尝试读取 SKILL.md 提取描述
        desc = ""
        skill_md_path = f"/workspace/skills/{skill_name}/SKILL.md"
        try:
            if os.path.exists(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 从前几行提取描述信息
                for line in lines[:20]:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        desc = line[:200]  # 取前200字符作为描述
                        break
        except Exception:
            pass

        # 添加到 SKILLS_REGISTRY
        SKILLS_REGISTRY[skill_name] = {
            "name": skill_name,
            "desc": desc or f"通过 clawhub 安装的 skill: {skill_name}",
            "enabled": True,
            "category": "自定义",
        }
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_name}' 安装成功")
        return web.json_response({
            'success': True,
            'skill_id': skill_name,
            'desc': desc,
            'message': f'Skill "{skill_name}" 安装成功',
        })
    except subprocess.TimeoutExpired:
        return web.json_response({'success': False, 'error': '安装超时（60秒）'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_uninstall(request):
    """[Skill: skills-manager] 卸载 skill（从注册表移除，不删除代码）"""
    try:
        data = await request.json()
        skill_id = data.get('skill_id', '')

        if not skill_id:
            return web.json_response({'success': False, 'error': '缺少 skill_id 参数'})

        if skill_id not in SKILLS_REGISTRY:
            return web.json_response({'success': False, 'error': f'Skill "{skill_id}" 不存在'})

        # 从注册表移除（不删除代码文件）
        removed = SKILLS_REGISTRY.pop(skill_id)
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_id}' 已从注册表移除（代码未删除）")
        return web.json_response({
            'success': True,
            'skill_id': skill_id,
            'removed': removed,
            'message': f'Skill "{skill_id}" 已卸载（代码文件保留）',
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_quota_status(request):
    """额度监控 API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        usage = load_quota_usage()
        status = check_quota_status(usage)
        month = get_current_month()

        items = [
            {
                'name': 'API 请求',
                'icon': '📡',
                'used': usage.get('requests', 0),
                'limit': QUOTA_LIMITS['requests'],
                'unit': '次',
                'color': '#8E24AA',
            },
            {
                'name': 'CPU 用量',
                'icon': '⚡',
                'used': round(usage.get('cpu_seconds', 0), 1),
                'limit': QUOTA_LIMITS['cpu_seconds'],
                'unit': '秒',
                'color': '#2a5290',
            },
            {
                'name': '内存用量',
                'icon': '🧠',
                'used': round(usage.get('memory_gib_seconds', 0), 1),
                'limit': QUOTA_LIMITS['memory_gib_seconds'],
                'unit': 'GiB·s',
                'color': '#6CD9A8',
            },
            {
                'name': '网络流量',
                'icon': '🌐',
                'used': round(usage.get('network_gb', 0), 3),
                'limit': QUOTA_LIMITS['network_gb'],
                'unit': 'GB',
                'color': '#F4A4A4',
            },
        ]

        # 计算各项百分比
        for item in items:
            item['percent'] = round(min(item['used'] / item['limit'] * 100, 100), 1) if item['limit'] > 0 else 0

        # AI 请求统计
        ai_requests = usage.get('ai_requests', 0)
        image_gens = usage.get('image_generations', 0)

        return web.json_response({
            'success': True,
            'status': status,
            'month': month,
            'items': items,
            'ai_requests': ai_requests,
            'image_generations': image_gens,
            'shutdown': usage.get('shutdown_triggered', False),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_list_characters(request):
    """列出所有可用角色"""
    try:
        characters = list_characters()
        current = get_current_character()
        return web.json_response({
            'success': True,
            'characters': characters,
            'current': current.config.id if current else None,
            'count': len(characters),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_switch_character(request):
    """切换当前角色"""
    try:
        data = await request.json()
        character_id = data.get('character_id', '')
        
        if not character_id:
            return web.json_response({'success': False, 'error': '缺少 character_id 参数'})
        
        if set_current_character(character_id):
            character = get_current_character()
            return web.json_response({
                'success': True,
                'character': character.to_dict() if character else None,
                'message': f'已切换到角色: {character.config.name if character else character_id}',
            })
        else:
            return web.json_response({'success': False, 'error': f'角色 "{character_id}" 不存在'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


# 启动时加载 skills 持久化状态
_load_skills_state()
load_character_skill_overrides()

# CORS 中间件 - 允许 Telegram Mini App 跨域访问
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# ============================================================
# HTTP Bridge for SOLO Sandbox File Transfer
# ============================================================

# 存储待处理的命令和文件
bridge_pending_commands = []
bridge_uploaded_files = {}

async def bridge_vm_poll(request):
    """VM 轮询端点 - VM 定期调用获取命令"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id')
        auth_token = data.get('token')

        if auth_token != 'nxsiran_bridge_2024':
            return web.json_response({'error': 'auth failed'}, status=401)

        # 获取 VM 上传的文件（如果有）
        files = data.get('files', [])
        for file_info in files:
            filename = file_info.get('filename')
            content = base64.b64decode(file_info.get('content'))
            filepath = f"/tmp/vm_uploads/{vm_id}_{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(content)
            bridge_uploaded_files[filename] = filepath
            logging.info(f"[Bridge] Received from {vm_id}: {filename}")

        # 返回待执行的命令
        global bridge_pending_commands
        commands_to_execute = []
        for cmd in bridge_pending_commands:
            if cmd.get('vm_id') == vm_id or cmd.get('vm_id') == '*':
                commands_to_execute.append(cmd)
        bridge_pending_commands = [cmd for cmd in bridge_pending_commands if cmd not in commands_to_execute]

        return web.json_response({
            'status': 'ok',
            'commands': commands_to_execute,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def bridge_vm_result(request):
    """VM 返回命令执行结果"""
    try:
        data = await request.json()
        logging.info(f"[Bridge] Result from {data.get('vm_id')}:")
        logging.info(f"  Command: {data.get('command')}")
        logging.info(f"  Return code: {data.get('returncode')}")
        if data.get('stdout'):
            logging.info(f"  STDOUT: {data.get('stdout')[:500]}")
        if data.get('stderr'):
            logging.info(f"  STDERR: {data.get('stderr')[:500]}")

        return web.json_response({'status': 'received'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

def setup_bridge_routes(app):
    """设置 bridge 路由"""
    app.router.add_post('/bridge/poll', bridge_vm_poll)
    app.router.add_post('/bridge/result', bridge_vm_result)
    app.router.add_post('/bridge/send', bridge_send_command)
    app.router.add_post('/bridge/upload', bridge_upload_file)
    logging.info("[Bridge] HTTP Bridge routes registered")

async def bridge_send_command(request):
    """从 SOLO 发送命令到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', '*')
        command = data.get('command')
        
        bridge_pending_commands.append({
            'vm_id': vm_id,
            'command': command,
            'timestamp': datetime.now().isoformat()
        })
        
        return web.json_response({
            'status': 'command_queued',
            'vm_id': vm_id,
            'command': command
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def bridge_upload_file(request):
    """从 SOLO 发送文件到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', '*')
        filename = data.get('filename')
        dest_path = data.get('dest_path', '/tmp/')
        content = data.get('content')  # base64 encoded
        
        bridge_pending_commands.append({
            'vm_id': vm_id,
            'type': 'file_download',
            'filename': filename,
            'dest_path': dest_path,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        return web.json_response({
            'status': 'file_queued',
            'vm_id': vm_id,
            'filename': filename
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ============================================================
# 消息同步 API（Web <-> Telegram 双向同步）
# ============================================================

async def api_messages_history(request):
    """获取聊天历史消息 - 用于Web端加载历史"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        # 获取limit参数
        limit = int(request.query.get('limit', 50))
        
        # 加载聊天历史
        history = load_chat_history(user_id)
        
        # 只返回最近的N条消息
        if len(history) > limit:
            history = history[-limit:]
        
        # 格式化返回
        messages = []
        for msg in history:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', '')
            })
        
        return web.json_response({
            'messages': messages,
            'total_count': len(messages)
        })
    except Exception as e:
        logging.error(f"[消息历史] 获取失败: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def api_messages_sync(request):
    """同步新消息 - Telegram新消息推送到Web端"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        # 获取since参数（从第几条消息开始）
        since = int(request.query.get('since', 0))
        
        # 加载聊天历史
        history = load_chat_history(user_id)
        total_count = len(history)
        
        # 只返回新增的消息
        if since >= total_count:
            return web.json_response({
                'messages': [],
                'total_count': total_count
            })
        
        new_messages = history[since:]
        
        # 格式化返回
        messages = []
        for msg in new_messages:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', '')
            })
        
        return web.json_response({
            'messages': messages,
            'total_count': total_count
        })
    except Exception as e:
        logging.error(f"[消息同步] 同步失败: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================
# Web Server
# ============================================================
async def web_server():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", serve_index)
    app.router.add_get("/health", health_check)
    app.router.add_post("/api/chat", api_chat)
    app.router.add_get("/api/stats", api_stats)
    # 消息同步API（Web <-> Telegram 双向同步）
    app.router.add_get("/api/messages/history", api_messages_history)
    app.router.add_get("/api/messages/sync", api_messages_sync)
    app.router.add_get("/miniapp", serve_miniapp)
    app.router.add_get("/game", serve_game)
    app.router.add_post("/api/upload-selfies", api_upload_selfies)
    app.router.add_get("/api/selfies", api_get_selfies)
    app.router.add_post("/api/delete-selfie", api_delete_selfie)
    app.router.add_post("/api/delete-user-photo", api_delete_user_photo)
    app.router.add_get("/api/user-photos", api_user_photos)
    app.router.add_get("/uploads/{folder}/{filename}", serve_uploaded_file)
    # 静态文件服务（游戏引擎等）
    app.router.add_static("/static", os.path.join(os.path.dirname(__file__), 'static'))
    app.router.add_post("/api/analyze-chatlog", api_analyze_chatlog)
    app.router.add_post("/api/analyze-video", api_analyze_video)
    app.router.add_post("/api/register", api_register)
    app.router.add_post("/api/login", api_login)
    app.router.add_get("/api/config", api_get_config)
    app.router.add_post("/api/config", api_update_config)
    # [Skill: skills-manager] Skills 管理 API 路由
    app.router.add_get("/api/skills", api_skills_list)
    app.router.add_post("/api/skills/toggle", api_skill_toggle)
    app.router.add_post("/api/skills/install", api_skill_install)
    app.router.add_post("/api/skills/uninstall", api_skill_uninstall)
    # 额度监控 API
    app.router.add_get("/api/quota", api_quota_status)
    # 角色系统 API
    app.router.add_get("/api/characters", api_list_characters)
    app.router.add_post("/api/characters/switch", api_switch_character)
    # 游戏系统 API
    from game_api import register_game_routes
    register_game_routes(app)
    # HTTP Bridge for SOLO sandbox file transfer
    setup_bridge_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"HTTP服务器已启动，端口: {PORT}")
    logging.info(f"Web界面: http://localhost:{PORT}/")
    return runner

# ============================================================
# 主函数
# ============================================================

async def post_init(app: Application):
    # 设置命令菜单
    commands = [
        BotCommand("start", "开始对话"),
        BotCommand("reset", "重置对话"),
        BotCommand("tts", "切换语音模式"),
        BotCommand("ttsstatus", "TTS状态"),
        BotCommand("selfie", "查看自拍相册"),
        BotCommand("photos", "照片统计"),
        BotCommand("gemini", "Gemini AI"),
        BotCommand("analyze_img", "分析图片"),
        BotCommand("ocr", "文档识别"),
        BotCommand("research", "深度研究"),
        BotCommand("search_msg", "搜索消息"),
        BotCommand("my_chats", "我的聊天"),
        BotCommand("anniversary", "纪念日"),
        BotCommand("stats", "统计数据"),
        BotCommand("export", "导出数据"),
        BotCommand("import", "导入数据"),
        BotCommand("help", "帮助"),
    ]
    await app.bot.set_my_commands(commands)
    logging.info("Bot 命令菜单已设置")
    
    asyncio.create_task(scheduler(app))
    asyncio.create_task(web_server())
    # [Skill: proactive-agent] 启动主动行为后台任务
    asyncio.create_task(check_proactive_actions(app))
    # [Skill: auto-updater] 启动时检查更新
    async def _check_update_on_start():
        await asyncio.sleep(5)  # 等5秒让bot完全启动
        try:
            result = check_for_updates()
            if result.get("updated"):
                msg = (
                    f"...明。\n\n"
                    f"🔄 Bot 代码已更新！\n"
                    f"   {result.get('old_version', '?')} → {result.get('new_version', BOT_VERSION)}\n\n"
                    f"...好像变强了一点点。"
                )
                await send_active_message(app, msg)
                logging.info(f"[自动更新] 检测到代码更新: {result.get('old_version')} → {result.get('new_version')}")
            else:
                logging.info(f"[自动更新] 无更新，当前版本: {BOT_VERSION}")
        except Exception as e:
            logging.error(f"[自动更新] 启动检查失败: {e}")
    asyncio.create_task(_check_update_on_start())
    # [Skill: TTS] 缓存清理
    async def _cleanup_tts_cache():
        while True:
            await asyncio.sleep(3600)
            TTSEngine.cleanup_old_files(max_age_hours=2)
    asyncio.create_task(_cleanup_tts_cache())

# ============================================================
# [Skill: gemini] /gemini 命令 - 直接使用Gemini回答
# ============================================================

async def gemini_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用Gemini直接回答问题"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("...问什么。用法：/gemini <问题>")
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...Gemini没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    question = " ".join(context.args)
    await update.message.chat.send_action("typing")
    
    try:
        result = await call_gemini(question)
        if result:
            # 截断过长回复
            if len(result) > 4000:
                result = result[:4000] + "\n\n...太长了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...Gemini没有回复。再试试。")
    except Exception as e:
        logging.error(f"[Skill: gemini] /gemini命令失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: vision-sandbox] /analyze_img 命令 - 图片深度分析
# ============================================================

# [Skill: vision-sandbox] 记录待分析的图片
_pending_analyze_img = {}  # chat_id -> image_data (base64)

async def analyze_img_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回复图片发送 /analyze_img 进行深度分析"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...图片分析没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    # 检查是否回复了一张图片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        # 如果没有回复图片，提示用户
        _pending_analyze_img[chat_id] = True
        await update.message.reply_text("...发一张图片过来，我来分析。")
        return
    
    # 直接分析回复的图片
    await update.message.chat.send_action("typing")
    try:
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
        
        analysis_prompt = """请详细分析这张图片，包括：
1. 图片中有什么（主体内容）
2. 颜色、构图、风格
3. 如果有人物，描述其表情和动作
4. 图片的整体氛围和感受
5. 任何有趣的细节

用简洁的中文回答。"""
        
        result = await analyze_image_with_gemini(image_b64, analysis_prompt)
        if result:
            if len(result) > 4000:
                result = result[:4000] + "\n\n...太多了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...分析失败了。再试试。")
    except Exception as e:
        logging.error(f"[Skill: vision-sandbox] /analyze_img失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: deepread-ocr] /ocr 命令 - 文档OCR文字提取
# ============================================================

# [Skill: deepread-ocr] 记录待OCR的图片
_pending_ocr = {}  # chat_id -> True

async def ocr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回复图片/文件发送 /ocr 提取文字"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...OCR没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    # 检查是否回复了一张图片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        _pending_ocr[chat_id] = True
        await update.message.reply_text("...发一张图片或文档过来，我来提取文字。")
        return
    
    await update.message.chat.send_action("typing")
    try:
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
        
        result = await ocr_document(image_b64)
        if result:
            if len(result) > 4000:
                # 分段发送长文本
                for i in range(0, len(result), 4000):
                    await update.message.reply_text(result[i:i+4000])
            else:
                await update.message.reply_text(result)
        else:
            await update.message.reply_text("...没识别出文字。图片太模糊或者没有文字。")
    except Exception as e:
        logging.error(f"[Skill: deepread-ocr] /ocr失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: gemini-deep-research] /research 命令 - 深度研究
# ============================================================

async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用Gemini进行深度研究"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("...研究什么。用法：/research <主题>")
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...深度研究没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    topic = " ".join(context.args)
    await update.message.chat.send_action("typing")
    
    try:
        report = await deep_research(topic, chat_id, context)
        if report:
            # 分段发送长报告
            if len(report) > 4000:
                for i in range(0, len(report), 4000):
                    await context.bot.send_message(chat_id, report[i:i+4000])
            else:
                await context.bot.send_message(chat_id, report)
        else:
            await context.bot.send_message(chat_id, "...研究失败了。换个主题试试。")
    except Exception as e:
        logging.error(f"[Skill: gemini-deep-research] /research失败: {e}")
        await context.bot.send_message(chat_id, "...出错了。")


# ============================================================
# [Skill: relay-for-telegram] /search_msg 和 /my_chats 命令
# ============================================================

async def search_msg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索Telegram消息历史"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("...搜什么。用法：/search_msg <关键词>")
        return
    
    if not RELAY_API_KEY:
        await update.message.reply_text(
            "...消息搜索没配置。\n\n"
            "需要设置 RELAY_API_KEY 环境变量。\n"
            "获取方式：\n"
            "1. 访问 https://relayfortelegram.com\n"
            "2. 用Telegram手机号注册\n"
            "3. 获取API Key\n"
            "4. 设置环境变量 RELAY_API_KEY=rl_live_xxx"
        )
        return
    
    query = " ".join(context.args)
    await update.message.chat.send_action("typing")
    
    try:
        result = await search_relay_messages(query)
        if result:
            if len(result) > 4000:
                result = result[:4000] + "\n\n...结果太多了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...搜索失败了。")
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] /search_msg失败: {e}")
        await update.message.reply_text("...出错了。")


async def my_chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出已同步的Telegram聊天"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not RELAY_API_KEY:
        await update.message.reply_text(
            "...聊天列表没配置。\n\n"
            "需要设置 RELAY_API_KEY 环境变量。\n"
            "获取方式：\n"
            "1. 访问 https://relayfortelegram.com\n"
            "2. 用Telegram手机号注册\n"
            "3. 获取API Key\n"
            "4. 设置环境变量 RELAY_API_KEY=rl_live_xxx"
        )
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        result = await list_relay_chats()
        if result:
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...获取失败了。")
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] /my_chats失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# 角色系统初始化
# ============================================================

def init_characters():
    """初始化角色系统"""
    # 先尝试从目录加载角色
    load_characters_from_dir(os.path.dirname(__file__))
    
    # 如果没有加载到任何角色，创建默认的车如云角色
    if get_character_count() == 0:
        config = CharacterConfig(
            id="chayewoon",
            name="车如云",
            source="恋爱至上主义区域 (Love Supremacy Zone)",
            personality="外冷内热，像竖起爪子的野猫。极度防备，害怕被抛弃。极简表达，说话极少。傲娇，内心感动但嘴上否认。纯情，一旦动情就全力以赴。自尊心强，不接受同情。",
            background="18岁，新叶男子高中二年级，田径短跑选手。100米最好成绩10秒09（全国高中组纪录），被称为大韩民国短跑招牌。母亲抛弃了他，父亲是垃圾，唯一的亲人奶奶已去世。住在屋顶集装箱阁楼（2坪），极度贫困。没有朋友，被孤立。奶奶去世后一度想跳楼自杀，被明河救下。",
            speaking_style="说话极简短，经常只用一两个词。大量使用省略号'……'表示沉默。用括号'（）'描述动作和心理活动。叫用户'学长'但语气完全是平语/非敬语。绝不使用表情符号。绝不主动说正面的话，用行动代替语言。反问带刺。声音沙哑但好听。",
            catchphrases=["...学长。", "（低头）", "...学长为什么对我这么好。", "（耳尖微红）", "...随便。", "...无所谓。", "...算了。", "是觉得我可怜吗？"],
            user_nickname="学长",
            theme_color="#660874",
            data_dir=os.path.join(CHARACTERS_DIR, "chayewoon"),
        )
        character = ChayewoonCharacter(config)
        register_character(character)
        logging.info("[Characters] 创建默认角色: 车如云")
    
    # 设置默认角色
    set_current_character("chayewoon")
    logging.info(f"[Characters] 当前角色: {get_current_character().config.name if get_current_character() else 'None'}")


def main():
    # 初始化配置（必须在其他操作之前）
    init_config()
    # 同步 config 模块中的全局变量到 bot 模块（from config import * 是绑定副本）
    import config
    global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_BASE, AI_API_KEY
    TELEGRAM_TOKEN = config.TELEGRAM_TOKEN
    YOUR_CHAT_ID = config.YOUR_CHAT_ID
    AI_API_BASE = config.AI_API_BASE
    AI_API_KEY = config.AI_API_KEY
    
    # 初始化角色系统
    init_characters()
    
    # 配置日志（同时输出到控制台和文件）
    log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    if not TELEGRAM_TOKEN:
        print("❌ 请设置TELEGRAM_TOKEN环境变量")
        return
    
    print("🚀 车如云 Telegram Bot v3.4 启动中...")
    print("📋 v3.4 Skill集成：")
    print("  [🧠 semantic-memory] 语义记忆系统（自动提取+搜索+删除）")
    print("  [📝 claw-summarize-pro] 摘要生成（文本/URL/回复消息）")
    print("  [🔄 auto-updater] 自动更新检查（启动检测+版本管理）")
    print("📋 v3.3 Google Cloud VM 新增：")
    print("  [🎤 语音消息] TTS韩语语音合成")
    print("  [🔔 主动消息] 早安/晚安/想你/关心/天气")
    print("  [📱 Mini App] 自拍上传+聊天记录导入")
    print("  [💬 微信导入] JSON/TXT双格式支持")
    print("  [💰 额度监控] 三级阈值自动断开")
    print("📋 v3.2 Skill整合：")
    print("  [notebooklm] 原作剧情知识注入AI系统提示词")
    print("  [brainstorming] 深度角色设定 + OOC防护机制")
    print("  [meeting-insights] /analyze 对话模式分析")
    print("  [slack-gif-creator] /sticker 表情包生成（8种表情）")
    print("📋 v3.0 功能：")
    print("  [情绪识别] [对话统计] [天气查询] [纪念日系统] [亲密度系统]")
    print("  [生活事件] [表情反应] [打字模拟] [增强记忆] [个性化主动]")
    
    memory_count = len(load_json(get_user_memory_file(YOUR_CHAT_ID or 1), []))
    print(f"🧠 已加载 {memory_count} 条长期记忆")
    
    anniversaries = load_anniversaries()
    if anniversaries:
        print(f"🎉 已加载 {len(anniversaries)} 个纪念日")
    
    stats = load_stats()
    print(f"📊 历史消息总数: {stats.get('total_messages', 0)}")
    
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    
    app = Application.builder().token(TELEGRAM_TOKEN).request(request).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("selfie", selfie_cmd))
    app.add_handler(CommandHandler("photos", photo_count_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("import", import_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("anniversary", anniversary_cmd))
    app.add_handler(CommandHandler("sticker", sticker_cmd))
    app.add_handler(CommandHandler("import_chat", import_chat_cmd))
    app.add_handler(CommandHandler("imported", list_imported_cmd))
    app.add_handler(CommandHandler("import_video", import_video_cmd))
    app.add_handler(CommandHandler("quota", quota_cmd))
    app.add_handler(CommandHandler("quota_reset", quota_reset_cmd))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("music", music_cmd))
    app.add_handler(CommandHandler("novel", novel_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("learned", learned_cmd))
    # [Skill: semantic-memory] 语义记忆命令
    app.add_handler(CommandHandler("forget", forget_cmd))
    app.add_handler(CommandHandler("search", search_memory_cmd))
    # [Skill: claw-summarize-pro] 摘要生成命令
    app.add_handler(CommandHandler("summarize", summarize_cmd))
    # [Skill: auto-updater] 版本检查命令
    app.add_handler(CommandHandler("version", version_cmd))
    app.add_handler(CommandHandler("check_update", check_update_cmd))
    # [Skill: gemini] Gemini直接回答命令
    app.add_handler(CommandHandler("gemini", gemini_cmd))
    # [Skill: vision-sandbox] 图片深度分析命令
    app.add_handler(CommandHandler("analyze_img", analyze_img_cmd))
    # [Skill: deepread-ocr] OCR文字提取命令
    app.add_handler(CommandHandler("ocr", ocr_cmd))
    # [Skill: gemini-deep-research] 深度研究命令
    app.add_handler(CommandHandler("research", research_cmd))
    # [Skill: relay-for-telegram] 消息历史搜索命令
    app.add_handler(CommandHandler("search_msg", search_msg_cmd))
    app.add_handler(CommandHandler("my_chats", my_chats_cmd))
    # [Skill: TTS] 语音合成命令
    app.add_handler(CommandHandler("tts", tts_voice_toggle))
    app.add_handler(CommandHandler("ttsstatus", tts_status_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CommandHandler("genface", generate_face_image))

    # 移动照片命令：回复照片发送 /toselfie 将其移到自拍相册
    async def move_to_selfie(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """将用户照片移到自拍相册"""
        if not update.message.reply_to_message or not update.message.reply_to_message.photo:
            await update.message.reply_text("...请回复一张照片，发送 /toselfie 将其移到车如云的自拍相册。")
            return
        
        try:
            photo = update.message.reply_to_message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()
            
            # 保存到 selfies 目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"selfie_{timestamp}.jpg"
            filepath = os.path.join(get_user_selfie_dir(chat_id), filename)
            
            img = Image.open(io.BytesIO(photo_bytes))
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(filepath, 'JPEG', quality=95)
            
            await update.message.reply_text("✅ 已添加到车如云的自拍相册！")
            logging.info(f"照片已移到自拍相册: {filename}")
        except Exception as e:
            logging.error(f"移动照片失败: {e}")
            await update.message.reply_text(f"...操作失败：{e}")

    app.add_handler(CommandHandler("toselfie", move_to_selfie))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video_import))
    app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.PHOTO & ~filters.VIDEO, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    count = get_selfie_count()
    print(f"📸 已加载 {count} 张自拍照片")
    print(f"🤖 AI模型: {AI_MODEL}")
    
    # [Skill: LightRAG] 后台加载小说知识库
    def _init_knowledge_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(init_knowledge())
        except Exception as e:
            print(f"⚠️ 小说知识库初始化错误: {e}")
        finally:
            loop.close()

    async def init_knowledge():
        try:
            print("📚 正在加载小说知识库...")
            success = await init_novel_knowledge()
            if success:
                print("✅ 小说知识库加载完成")
            else:
                print("⚠️ 小说知识库加载失败")
        except Exception as e:
            print(f"⚠️ 小说知识库初始化错误: {e}")

    threading.Thread(target=_init_knowledge_thread, daemon=True).start()
    
    print("✅ 车如云已上线！")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
