from packages.commands.basic import (
    start,
    reset,
    selfie_cmd,
    memory_cmd,
    forget_cmd,
    search_memory_cmd,
    export_cmd,
    import_cmd,
    photo_count_cmd,
)

from packages.commands.skills import (
    sticker_cmd,
    analyze_cmd,
    stats_cmd,
)

from packages.commands.misc import (
    quota_cmd,
    quota_reset_cmd,
    learned_cmd,
    fetch_url_content,
    generate_summary,
    summarize_cmd,
    calculate_bot_hash,
    check_for_updates,
    version_cmd,
    check_update_cmd,
    anniversary_cmd,
    deep_research,
    search_relay_messages,
    list_relay_chats,
    call_gemini,
    web_search,
    auto_delete_messages,
)

from packages.commands.extra import (
    gemini_cmd,
    analyze_img_cmd,
    ocr_cmd,
    research_cmd,
    search_msg_cmd,
    my_chats_cmd,
)

__all__ = [
    # basic
    "start", "reset", "selfie_cmd", "memory_cmd", "forget_cmd",
    "search_memory_cmd", "export_cmd", "import_cmd", "photo_count_cmd",
    # skills
    "sticker_cmd", "analyze_cmd", "stats_cmd",
    # misc
    "quota_cmd", "quota_reset_cmd", "learned_cmd", "fetch_url_content",
    "generate_summary", "summarize_cmd", "calculate_bot_hash", "check_for_updates",
    "version_cmd", "check_update_cmd", "anniversary_cmd", "deep_research",
    "search_relay_messages", "list_relay_chats", "call_gemini", "web_search",
    "auto_delete_messages",
    # extra
    "gemini_cmd", "analyze_img_cmd", "ocr_cmd", "research_cmd",
    "search_msg_cmd", "my_chats_cmd",
]
