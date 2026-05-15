# game_api/

游戏 API 模块 — 农场经营 + 角色互动，提供 Web/Mini App 端的游戏数据接口（aiohttp）。

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 路由注册入口, 聚合所有 API handler | `register_game_routes` |
| `auth.py` | 统一认证中间件（session token > api token > config fallback） | `authenticate_request` |
| `awakening_detector.py` | 觉醒条件检测, 阶段判定, 觉醒事件触发 | `AWAKENING_STAGES`, `check_awakening` |
| `character_routes.py` | 角色位置查询, 角色互动, 送礼, 动作同步 | `api_get_character_location`, `api_interact_with_character`, `api_gift_to_character` |
| `cooking_routes.py` | 料理配方查询, 烹饪执行, 每日签到 | `api_get_recipes`, `api_cook`, `api_daily_checkin` |
| `farm_routes.py` | 农场数据 CRUD, 种植/浇水/收获/出售/批量收获 | `api_get_farm`, `api_plant_crop`, `api_harvest_crop`, `api_bulk_harvest` |
| `heart_routes.py` | 心级事件检查与触发 | `api_check_heart_events` |
| `map_routes.py` | 多地图列表, 解锁状态, 地图切换 | `api_get_maps`, `api_unlock_map` |
| `media_routes.py` | 自拍/贴纸/场景 AI 生成 | `api_generate_selfie`, `api_generate_sticker` |
| `sync_routes.py` | 全量状态同步, 游戏事件拉取, SSE 实时推送, 增量 diff | `api_get_full_game_state`, `api_game_state_sse`, `api_game_state_diff`, `api_game_state_version` |
| `game_state.py` | 状态序列化, 版本号管理, 变更通知, 快照缓存 | `serialize_game_state`, `notify_state_change`, `get_state_version` |
| `learning_routes.py` | 角色学习进化 API | `api_character_evolve`, `api_character_learn_novel`, `api_character_learning_status` |
| `upload_routes.py` | 上传处理 API（声音/聊天记录/视频） | `api_upload_voice`, `api_clone_voice`, `api_upload_chatlog`, `api_upload_video` |

## 依赖关系

- 所有 `*_routes.py` → `game_api.auth.authenticate_request`, `database.get_db`
- `character_routes.py` → `characters.get_current_character`
- `media_routes.py` → `prompts.SELFIE_PROMPTS`, `characters.image_gen`
