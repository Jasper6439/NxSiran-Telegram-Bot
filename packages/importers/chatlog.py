"""聊天记录导入模块：微信聊天记录导入与分析"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from system.config import YOUR_CHAT_ID
from packages.analysis.chatlog import (
    get_chat_analysis, parse_wechat_chatlog, analyze_chatlog_with_ai, save_chat_analysis,
)
from characters.memory_legacy import save_memory_entry

__all__ = [
    'pending_chat_imports',
    'import_chat_cmd',
    'handle_chatlog_document',
    'list_imported_cmd',
]

# 临时存储用户上传的聊天记录文件内容
pending_chat_imports = {}

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
