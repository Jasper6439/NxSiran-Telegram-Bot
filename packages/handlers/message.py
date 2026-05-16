"""Message handlers for the Telegram bot.

This module serves as the central re-export hub for all handler submodules.
The actual implementations have been split into separate modules to reduce
Git conflicts during parallel SOLO development.

Submodules:
    - photo.py: Photo and document handling (handle_photo, handle_document)
    - callback.py: Inline button callbacks (button_callback)
    - text_message.py: Text message handling (handle_message, send_active_message, send_smart_reply)
    - voice.py: TTS voice cloning system (voice_cmd, music_cmd, novel_cmd, etc.)
"""

from packages.handlers.photo import handle_photo, handle_document
from packages.handlers.callback import button_callback
from packages.handlers.text_message import (
    handle_message,
    send_active_message,
    send_smart_reply,
    message_count,
)
from packages.handlers.voice import (
    voice_cmd,
    voice_sample_cmd,
    voice_train_cmd,
    voice_status_cmd,
    music_cmd,
    novel_cmd,
    semantic_memory_cmd,
    tts_voice_toggle,
    tts_status_cmd,
    send_voice_message,
)

__all__ = [
    "handle_photo",
    "handle_document",
    "button_callback",
    "handle_message",
    "send_active_message",
    "send_voice_message",
    "voice_cmd",
    "voice_sample_cmd",
    "voice_train_cmd",
    "voice_status_cmd",
    "music_cmd",
    "novel_cmd",
    "semantic_memory_cmd",
    "tts_voice_toggle",
    "tts_status_cmd",
    "send_smart_reply",
    "message_count",
]
