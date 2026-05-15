# 游戏 API 模块 - 农场经营 + 角色互动
# 提供 Web/Mini App 端的游戏数据接口

from game_api.farm_routes import (
    api_get_farm, api_plant_crop, api_harvest_crop,
    api_sell_crop, api_buy_seed, api_water_crop, api_move_player,
    api_bulk_harvest,
)
from game_api.character_routes import (
    api_get_character_location,
    api_interact_with_character,
    api_gift_to_character,
    api_sync_actions,
)
from game_api.cooking_routes import (
    api_get_recipes, api_cook, api_daily_reward, api_check_daily,
)
from game_api.sync_routes import (
    api_get_game_events, api_mark_synced,
    api_get_full_game_state, api_get_emotion_values,
    api_check_awakening, api_trigger_awakening,
    api_switch_world_layer, api_get_world_state,
    api_game_state_sse, api_game_state_diff, api_game_state_version,
)
from game_api.media_routes import (
    api_generate_selfie, api_generate_sticker,
    api_generate_scene, api_tts,
)
from game_api.heart_routes import (
    api_check_heart_events, api_trigger_heart_event,
)
from game_api.map_routes import (
    api_get_maps, api_switch_map, api_get_map_state,
    api_discover_map, api_get_map_discoveries,
)
from game_api.learning_routes import (
    api_character_evolve, api_character_learn_novel,
    api_character_learn_chat, api_character_learn_qdrant,
    api_character_learning_status,
)
from game_api.upload_routes import (
    api_upload_voice, api_clone_voice,
    api_upload_chatlog, api_upload_video,
    api_upload_status,
)


def register_game_routes(app):
    """注册游戏 API 路由"""
    # DOM-based 游戏引擎
    app.router.add_get("/api/game/state", api_get_full_game_state)
    app.router.add_post("/api/game/water", api_water_crop)
    app.router.add_post("/api/game/move", api_move_player)
    app.router.add_post("/api/game/sync", api_sync_actions)

    # 农场
    app.router.add_get("/api/game/farm", api_get_farm)
    app.router.add_post("/api/game/plant", api_plant_crop)
    app.router.add_post("/api/game/harvest", api_harvest_crop)
    app.router.add_post("/api/game/sell", api_sell_crop)
    app.router.add_post("/api/game/buy-seed", api_buy_seed)
    app.router.add_post("/api/game/bulk-harvest", api_bulk_harvest)

    # 角色互动
    app.router.add_get("/api/game/character/location", api_get_character_location)
    app.router.add_post("/api/game/character/interact", api_interact_with_character)
    app.router.add_post("/api/game/gift", api_gift_to_character)

    # 心级事件
    app.router.add_get("/api/game/events/heart", api_check_heart_events)
    app.router.add_post("/api/game/events/trigger", api_trigger_heart_event)

    # 烹饪
    app.router.add_get("/api/game/recipes", api_get_recipes)
    app.router.add_post("/api/game/cook", api_cook)

    # 每日签到
    app.router.add_get("/api/game/daily/check", api_check_daily)
    app.router.add_post("/api/game/daily/claim", api_daily_reward)

    # 同步
    app.router.add_get("/api/game/events", api_get_game_events)
    app.router.add_post("/api/game/events/sync", api_mark_synced)

    # 情感值与觉醒系统（恋爱至上主义区域）
    app.router.add_get("/api/game/emotions", api_get_emotion_values)
    app.router.add_get("/api/game/awakening/check", api_check_awakening)
    app.router.add_post("/api/game/awakening/trigger", api_trigger_awakening)
    app.router.add_get("/api/game/world/state", api_get_world_state)
    app.router.add_post("/api/game/world/switch", api_switch_world_layer)

    # 多媒体生成 API（v0.3）
    app.router.add_post("/api/game/generate/selfie", api_generate_selfie)
    app.router.add_post("/api/game/generate/sticker", api_generate_sticker)
    app.router.add_post("/api/game/generate/scene", api_generate_scene)
    app.router.add_post("/api/game/tts", api_tts)

    # 多地图系统 API（v1.4.10.2）
    app.router.add_get("/api/game/maps", api_get_maps)
    app.router.add_post("/api/game/maps/switch", api_switch_map)
    app.router.add_get("/api/game/maps/state", api_get_map_state)
    app.router.add_post("/api/game/maps/discover", api_discover_map)
    app.router.add_get("/api/game/maps/discoveries", api_get_map_discoveries)

    # v1.6.3 — 前后端状态同步
    app.router.add_get("/api/game/state/sse", api_game_state_sse)
    app.router.add_get("/api/game/state/diff", api_game_state_diff)
    app.router.add_get("/api/game/state/version", api_game_state_version)

    # v1.6.4.1 — 角色学习进化 API
    app.router.add_post("/api/characters/evolve", api_character_evolve)
    app.router.add_post("/api/characters/learn/novel", api_character_learn_novel)
    app.router.add_post("/api/characters/learn/chat", api_character_learn_chat)
    app.router.add_post("/api/characters/learn/qdrant", api_character_learn_qdrant)
    app.router.add_get("/api/characters/learning/status", api_character_learning_status)

    # v1.6.4.2 — 上传处理 API
    app.router.add_post("/api/upload/voice", api_upload_voice)
    app.router.add_post("/api/upload/voice/clone", api_clone_voice)
    app.router.add_post("/api/upload/chatlog", api_upload_chatlog)
    app.router.add_post("/api/upload/video", api_upload_video)
    app.router.add_get("/api/upload/status", api_upload_status)
