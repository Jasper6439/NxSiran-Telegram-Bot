import json
import logging
import re
from datetime import datetime

from system.config import CHAT_IMPORT_FILE, load_json, save_json, get_default_tz, AI_API_BASE, AI_API_KEY, AI_MODELS


__all__ = [
    "parse_wechat_chatlog",
    "parse_json_chatlog",
    "parse_chatlab_format",
    "parse_txt_chatlog",
    "calculate_chat_stats",
    "analyze_chatlog_with_ai",
    "save_chat_analysis",
    "get_chat_analysis",
    "get_all_imported_relationships",
]


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
        import httpx
        from characters.ai_client import _get_http_client
        client = _get_http_client()
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
