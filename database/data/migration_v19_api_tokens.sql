-- v1.9 阶段九：API Token 统一存储到 SQLite
-- ============================================================
-- 将 api_tokens.json 迁移到数据库，实现单一数据源
-- ============================================================

-- 1. 创建 api_tokens 表
CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,  -- SHA256 hash of the token
    created_at TEXT NOT NULL,
    expired_at TEXT,                   -- NULL 表示永不过期
    is_revoked INTEGER DEFAULT 0,      -- 0=有效, 1=已撤销
    last_used_at TEXT,                 -- 最后使用时间
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 2. 创建索引加速查询
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_expired ON api_tokens(expired_at) WHERE expired_at IS NOT NULL;

-- 3. 临时删除依赖的视图（将在最后重建）
DROP VIEW IF EXISTS v_character_location;
DROP VIEW IF EXISTS v_player_game_state;

-- 4. 更新现有外键约束添加 CASCADE（SQLite 需要重新创建表）
-- 注意：以下操作会保留数据，但重新创建表以添加 CASCADE

-- chat_messages 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS chat_messages_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    emotion TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);
INSERT INTO chat_messages_new SELECT * FROM chat_messages WHERE user_id IN (SELECT id FROM users);
DROP TABLE chat_messages;
ALTER TABLE chat_messages_new RENAME TO chat_messages;
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_character ON chat_messages(character_id);
CREATE INDEX IF NOT EXISTS idx_chat_time ON chat_messages(created_at);

-- relationships 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS relationships_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    hearts INTEGER DEFAULT 0,
    talked_today INTEGER DEFAULT 0,
    gifted_today INTEGER DEFAULT 0,
    total_gifts INTEGER DEFAULT 0,
    total_conversations INTEGER DEFAULT 0,
    unlocked_events TEXT,
    current_quest TEXT,
    relationship_status TEXT DEFAULT 'stranger',
    affection INTEGER DEFAULT 0,
    happiness INTEGER DEFAULT 50,
    awakening INTEGER DEFAULT 0,
    current_world_layer TEXT DEFAULT 'stage',
    last_active_time TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    world_layer TEXT DEFAULT 'normal',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    UNIQUE(user_id, character_id)
);
INSERT INTO relationships_new SELECT * FROM relationships WHERE user_id IN (SELECT id FROM users);
DROP TABLE relationships;
ALTER TABLE relationships_new RENAME TO relationships;
CREATE INDEX IF NOT EXISTS idx_relationships_user ON relationships(user_id);
CREATE INDEX IF NOT EXISTS idx_relationships_character ON relationships(character_id);

-- farms 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS farms_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    money INTEGER DEFAULT 500,
    farm_name TEXT DEFAULT '我的农场',
    grid_width INTEGER DEFAULT 12,
    grid_height INTEGER DEFAULT 8,
    unlocked_tiles INTEGER DEFAULT 20,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
INSERT INTO farms_new SELECT * FROM farms WHERE user_id IN (SELECT id FROM users);
DROP TABLE farms;
ALTER TABLE farms_new RENAME TO farms;
CREATE INDEX IF NOT EXISTS idx_farms_user ON farms(user_id);

-- inventory 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS inventory_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    quality INTEGER DEFAULT 1,
    obtained_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, item_type, item_id)
);
INSERT INTO inventory_new SELECT * FROM inventory WHERE user_id IN (SELECT id FROM users);
DROP TABLE inventory;
ALTER TABLE inventory_new RENAME TO inventory;
CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);

-- crops 表：添加 ON DELETE CASCADE（通过 farm_id 间接关联）
-- crops 通过 farm_id -> farms.user_id 关联，farms 已有 CASCADE

-- game_events 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS game_events_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    synced INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
INSERT INTO game_events_new SELECT * FROM game_events WHERE user_id IN (SELECT id FROM users);
DROP TABLE game_events;
ALTER TABLE game_events_new RENAME TO game_events;
CREATE INDEX IF NOT EXISTS idx_events_user ON game_events(user_id);

-- memories 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS memories_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    category TEXT DEFAULT 'personal',
    importance INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    last_referenced TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    UNIQUE(user_id, character_id, memory_key)
);
INSERT INTO memories_new SELECT * FROM memories WHERE user_id IN (SELECT id FROM users);
DROP TABLE memories;
ALTER TABLE memories_new RENAME TO memories;
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);

-- selfies 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS selfies_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    image_url TEXT NOT NULL,
    caption TEXT,
    scene TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);
INSERT INTO selfies_new SELECT * FROM selfies WHERE user_id IN (SELECT id FROM users);
DROP TABLE selfies;
ALTER TABLE selfies_new RENAME TO selfies;
CREATE INDEX IF NOT EXISTS idx_selfies_user ON selfies(user_id);

-- daily_rewards 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS daily_rewards_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reward_date TEXT NOT NULL,
    reward_type TEXT NOT NULL,
    reward_id TEXT NOT NULL,
    reward_qty INTEGER DEFAULT 1,
    claimed INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, reward_date)
);
INSERT INTO daily_rewards_new SELECT * FROM daily_rewards WHERE user_id IN (SELECT id FROM users);
DROP TABLE daily_rewards;
ALTER TABLE daily_rewards_new RENAME TO daily_rewards;
CREATE INDEX IF NOT EXISTS idx_daily_rewards_user ON daily_rewards(user_id);

-- triggered_events 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS triggered_events_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES heart_events(id) ON DELETE CASCADE,
    UNIQUE(user_id, event_id)
);
INSERT INTO triggered_events_new SELECT * FROM triggered_events WHERE user_id IN (SELECT id FROM users);
DROP TABLE triggered_events;
ALTER TABLE triggered_events_new RENAME TO triggered_events;
CREATE INDEX IF NOT EXISTS idx_triggered_events_user ON triggered_events(user_id);

-- gift_history 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS gift_history_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    reaction TEXT,
    hearts_change INTEGER DEFAULT 0,
    gifted_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);
INSERT INTO gift_history_new SELECT * FROM gift_history WHERE user_id IN (SELECT id FROM users);
DROP TABLE gift_history;
ALTER TABLE gift_history_new RENAME TO gift_history;
CREATE INDEX IF NOT EXISTS idx_gift_history_user ON gift_history(user_id);

-- world_shift_history 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS world_shift_history_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    shifted_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
INSERT INTO world_shift_history_new SELECT * FROM world_shift_history WHERE user_id IN (SELECT id FROM users);
DROP TABLE world_shift_history;
ALTER TABLE world_shift_history_new RENAME TO world_shift_history;
CREATE INDEX IF NOT EXISTS idx_world_shift_history_user ON world_shift_history(user_id);

-- player_maps 表：添加 ON DELETE CASCADE
CREATE TABLE IF NOT EXISTS player_maps_new (
    user_id INTEGER PRIMARY KEY,
    current_map TEXT DEFAULT 'home',
    unlocked_maps TEXT DEFAULT '["home","school","cafe"]',
    map_discoveries TEXT DEFAULT '{}',
    last_visit TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
INSERT INTO player_maps_new SELECT * FROM player_maps WHERE user_id IN (SELECT id FROM users);
DROP TABLE player_maps;
ALTER TABLE player_maps_new RENAME TO player_maps;

-- player_positions 表：添加 ON DELETE CASCADE（如果存在）
CREATE TABLE IF NOT EXISTS player_positions (
    user_id INTEGER PRIMARY KEY,
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0,
    direction TEXT DEFAULT 'down',
    updated_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 5. 重新创建视图
-- 当前角色位置视图
CREATE VIEW IF NOT EXISTS v_character_location AS
SELECT 
    cs.character_id,
    c.name as character_name,
    cs.location,
    cs.activity,
    cs.day_of_week,
    cs.start_hour,
    cs.end_hour,
    cs.required_hearts
FROM character_schedules cs
JOIN characters c ON cs.character_id = c.id;

-- 玩家游戏状态视图
CREATE VIEW IF NOT EXISTS v_player_game_state AS
SELECT 
    u.id as user_id,
    u.telegram_id,
    u.username,
    f.level as farm_level,
    f.money,
    f.farm_name,
    r.character_id,
    r.hearts,
    r.relationship_status
FROM users u
LEFT JOIN farms f ON u.id = f.user_id
LEFT JOIN relationships r ON u.id = r.user_id;
