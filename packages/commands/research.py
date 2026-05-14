import asyncio
import logging

from telegram.ext import ContextTypes

from system.config import GEMINI_API_KEY
from packages.commands.utils import call_gemini, web_search


# ============================================================
# 深度研究功能
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
        logging.error(f"深度研究失败: {e}")
        return None
