-- 恋爱至上主义区域 (Love Supremacy Zone) - 数据库 Schema
-- ============================================================
-- NxSiRan Game Database Schema
-- 农场经营 + 角色互动游戏
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    password_hash TEXT,
    is_admin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    last_login TEXT,
    last_active TEXT
);

-- 角色表（蒸馏角色）
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,              -- chayewoon, etc.
    name TEXT NOT NULL,
    source TEXT,
    personality TEXT,
    background TEXT,
    speaking_style TEXT,
    theme_color TEXT DEFAULT '#660874',
    is_active INTEGER DEFAULT 1,
    world_layer TEXT DEFAULT 'stage',
    is_novel_character INTEGER DEFAULT 1,
    default_affection INTEGER DEFAULT 0,
    default_happiness INTEGER DEFAULT 50,
    default_awakening INTEGER DEFAULT 0,
    world_role TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- 聊天记录表（替代 JSON 文件）
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    role TEXT NOT NULL,               -- 'user' or 'assistant'
    content TEXT NOT NULL,
    emotion TEXT,                     -- 情绪标签
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 创建索引加速查询
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_character ON chat_messages(character_id);
CREATE INDEX IF NOT EXISTS idx_chat_time ON chat_messages(created_at);

-- 玩家-角色关系表（亲密度系统）
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    hearts INTEGER DEFAULT 0,         -- 心级 0-10
    talked_today INTEGER DEFAULT 0,
    gifted_today INTEGER DEFAULT 0,
    total_gifts INTEGER DEFAULT 0,
    total_conversations INTEGER DEFAULT 0,
    unlocked_events TEXT,             -- JSON array of event IDs
    current_quest TEXT,
    relationship_status TEXT DEFAULT 'stranger', -- stranger, acquaintance, friend, close, lover
    affection INTEGER DEFAULT 0,
    happiness INTEGER DEFAULT 50,
    awakening INTEGER DEFAULT 0,
    current_world_layer TEXT DEFAULT 'stage',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE(user_id, character_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 农场表
CREATE TABLE IF NOT EXISTS farms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    money INTEGER DEFAULT 500,        -- 初始资金
    farm_name TEXT DEFAULT '我的农场',
    grid_width INTEGER DEFAULT 12,
    grid_height INTEGER DEFAULT 8,
    unlocked_tiles INTEGER DEFAULT 20, -- 已解锁的地块数
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 地块表（农场格子）
CREATE TABLE IF NOT EXISTS farm_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    tile_type TEXT DEFAULT 'soil',    -- soil, water, path, building
    is_unlocked INTEGER DEFAULT 0,
    FOREIGN KEY (farm_id) REFERENCES farms(id),
    UNIQUE(farm_id, x, y)
);

-- 作物表
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    tile_x INTEGER NOT NULL,
    tile_y INTEGER NOT NULL,
    crop_type TEXT NOT NULL,          -- tomato, corn, etc.
    planted_at TEXT NOT NULL,
    growth_stage INTEGER DEFAULT 0,   -- 0=seed, 1=sprout, 2=growing, 3=mature
    water_level INTEGER DEFAULT 0,
    is_harvestable INTEGER DEFAULT 0,
    FOREIGN KEY (farm_id) REFERENCES farms(id),
    UNIQUE(farm_id, tile_x, tile_y)
);

-- 作物类型定义表
CREATE TABLE IF NOT EXISTS crop_types (
    id TEXT PRIMARY KEY,              -- tomato, corn, strawberry
    name TEXT NOT NULL,
    name_ko TEXT,                     -- 韩文名
    growth_time INTEGER NOT NULL,     -- 成熟所需分钟数
    sell_price INTEGER NOT NULL,
    seed_price INTEGER NOT NULL,
    seasons TEXT,                     -- JSON array: ["spring", "summer"]
    gift_preference TEXT,             -- 角色喜好: chayewoon:love, chayewoon:like
    emoji TEXT DEFAULT '🌱',
    description TEXT
);

-- 玩家背包表
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,          -- crop, seed, gift, tool
    item_id TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    quality INTEGER DEFAULT 1,        -- 1-3 星品质
    obtained_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, item_type, item_id)
);

-- 角色日程表
CREATE TABLE IF NOT EXISTS character_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    day_of_week INTEGER NOT NULL,     -- 0=Monday, 6=Sunday
    start_hour INTEGER NOT NULL,
    end_hour INTEGER NOT NULL,
    location TEXT NOT NULL,           -- dorm, track, cafe, rooftop
    activity TEXT,
    weather_condition TEXT,           -- any, sunny, rainy
    required_hearts INTEGER DEFAULT 0,
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 心级事件表
CREATE TABLE IF NOT EXISTS heart_events (
    id TEXT PRIMARY KEY,              -- first_meet, roof_night, etc.
    character_id TEXT NOT NULL,
    required_hearts INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    trigger_location TEXT,
    trigger_time_start INTEGER,       -- 小时
    trigger_time_end INTEGER,
    trigger_weather TEXT,
    dialogue TEXT,                    -- JSON array of dialogue lines
    rewards TEXT,                     -- JSON: items, hearts, etc.
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 已触发事件表
CREATE TABLE IF NOT EXISTS triggered_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (event_id) REFERENCES heart_events(id),
    UNIQUE(user_id, event_id)
);

-- 礼物记录表
CREATE TABLE IF NOT EXISTS gift_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    reaction TEXT,                    -- love, like, neutral, dislike, hate
    hearts_change INTEGER DEFAULT 0,
    gifted_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 游戏事件日志（跨平台同步用）
CREATE TABLE IF NOT EXISTS game_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,         -- chat, gift, harvest, plant, etc.
    event_data TEXT,                  -- JSON
    source TEXT NOT NULL,             -- telegram, web, miniapp
    created_at TEXT NOT NULL,
    synced INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 记忆表（替代 semantic_memory.json）
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    category TEXT DEFAULT 'personal',
    importance INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    last_referenced TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    UNIQUE(user_id, character_id, memory_key)
);

-- 自拍表（替代 selfies 目录）
CREATE TABLE IF NOT EXISTS selfies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    image_url TEXT NOT NULL,
    caption TEXT,
    scene TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- ============================================================
-- 初始数据
-- ============================================================

-- 插入车如云角色
INSERT OR IGNORE INTO characters (id, name, source, personality, background, speaking_style, theme_color, created_at)
VALUES (
    'chayewoon',
    '车如云',
    '恋爱至上主义区域 (Love Supremacy Zone)',
    '外冷内热，像竖起爪子的野猫。极度防备，害怕被抛弃。极简表达，说话极少。傲娇，内心感动但嘴上否认。纯情，一旦动情就全力以赴。自尊心强，不接受同情。',
    '18岁，新叶男子高中二年级，田径短跑选手。100米最好成绩10秒09（全国高中组纪录），被称为大韩民国短跑招牌。母亲抛弃了他，父亲是垃圾，唯一的亲人奶奶已去世。住在屋顶集装箱阁楼（2坪），极度贫困。没有朋友，被孤立。',
    '说话极简短，经常只用一两个词。大量使用省略号''……''表示沉默。用括号''（）''描述动作和心理活动。叫用户''学长''但语气完全是平语/非敬语。绝不使用表情符号。',
    '#660874',
    datetime('now')
);

-- 插入初始作物类型
INSERT OR IGNORE INTO crop_types (id, name, name_ko, growth_time, sell_price, seed_price, seasons, emoji, description) VALUES
('tomato', '番茄', '토마토', 180, 50, 20, '["spring", "summer"]', '🍅', '新鲜的红色番茄'),
('corn', '玉米', '옥수수', 240, 80, 30, '["summer"]', '🌽', '金黄的甜玉米'),
('strawberry', '草莓', '딸기', 300, 120, 50, '["spring"]', '🍓', '甜美的草莓'),
('pumpkin', '南瓜', '호박', 360, 150, 40, '["autumn"]', '🎃', '大大的南瓜'),
('watermelon', '西瓜', '수박', 420, 200, 60, '["summer"]', '🍉', '清凉的西瓜'),
('potato', '土豆', '감자', 120, 30, 10, '["spring", "autumn"]', '🥔', '朴实的土豆'),
('carrot', '胡萝卜', '당근', 150, 35, 15, '["spring", "autumn"]', '🥕', '脆甜的胡萝卜'),
('cabbage', '白菜', '배추', 180, 40, 15, '["autumn", "winter"]', '🥬', '新鲜的白菜');

-- 料理类型定义表
CREATE TABLE IF NOT EXISTS recipe_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_ko TEXT,
    ingredients TEXT NOT NULL,        -- JSON: [{"crop": "tomato", "qty": 2}, ...]
    sell_price INTEGER NOT NULL,
    gift_preference TEXT,             -- 角色喜好
    emoji TEXT DEFAULT '🍲',
    effect TEXT,                     -- JSON: {"type": "hearts", "value": 3}
    description TEXT
);

-- 插入料理配方
INSERT OR IGNORE INTO recipe_types (id, name, name_ko, ingredients, sell_price, gift_preference, emoji, effect, description) VALUES
('tomato_salad', '番茄沙拉', '토마토 샐러드', '[{"crop": "tomato", "qty": 2}]', 120, 'chayewoon:like', '🥗', '{"type": "energy", "value": 10}', '清爽的番茄沙拉'),
('corn_soup', '玉米浓汤', '옥수수 수프', '[{"crop": "corn", "qty": 2}, {"crop": "potato", "qty": 1}]', 200, 'chayewoon:love', '🍲', '{"type": "hearts", "value": 2}', '温暖的玉米浓汤'),
('strawberry_cake', '草莓蛋糕', '딸기 케이크', '[{"crop": "strawberry", "qty": 3}, {"crop": "tomato", "qty": 1}]', 350, 'chayewoon:love', '🍰', '{"type": "hearts", "value": 5}', '甜美的草莓蛋糕'),
('pumpkin_pie', '南瓜派', '호박 파이', '[{"crop": "pumpkin", "qty": 2}, {"crop": "cabbage", "qty": 1}]', 280, 'chayewoon:like', '🥧', '{"type": "energy", "value": 20}', '香浓的南瓜派'),
('watermelon_juice', '西瓜汁', '수박 주스', '[{"crop": "watermelon", "qty": 2}]', 180, 'chayewoon:like', '🧃', '{"type": "energy", "value": 15}', '清凉的西瓜汁'),
('red_bean_porridge', '红豆粥', '팥죽', '[{"crop": "strawberry", "qty": 1}, {"crop": "potato", "qty": 2}]', 500, 'chayewoon:love', '🥣', '{"type": "hearts", "value": 8}', '奶奶做的红豆粥（车如云最爱的味道）'),
('veggie_stir_fry', '蔬菜炒饭', '야채 볶음밥', '[{"crop": "carrot", "qty": 1}, {"crop": "cabbage", "qty": 1}, {"crop": "corn", "qty": 1}]', 150, 'chayewoon:neutral', '🍳', '{"type": "energy", "value": 25}', '简单的蔬菜炒饭'),
('baked_potato', '烤土豆', '구운 감자', '[{"crop": "potato", "qty": 3}]', 100, 'chayewoon:like', '🥔', '{"type": "energy", "value": 15}', '香喷喷的烤土豆');

-- 每日登录奖励表
CREATE TABLE IF NOT EXISTS daily_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reward_date TEXT NOT NULL,
    reward_type TEXT NOT NULL,
    reward_id TEXT NOT NULL,
    reward_qty INTEGER DEFAULT 1,
    claimed INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, reward_date)
);

-- 插入车如云日程（周一到周日）
INSERT OR IGNORE INTO character_schedules (character_id, day_of_week, start_hour, end_hour, location, activity, weather_condition, required_hearts)
VALUES
-- 周一到周五（上学日）
('chayewoon', 0, 6, 7, 'dorm', '起床准备', 'any', 0),
('chayewoon', 0, 7, 8, 'track', '晨跑训练', 'any', 0),
('chayewoon', 0, 8, 12, 'school', '上课', 'any', 0),
('chayewoon', 0, 12, 13, 'cafeteria', '午餐', 'any', 0),
('chayewoon', 0, 13, 17, 'school', '上课', 'any', 0),
('chayewoon', 0, 17, 19, 'track', '下午训练', 'any', 0),
('chayewoon', 0, 19, 21, 'dorm', '休息', 'any', 0),
('chayewoon', 0, 21, 23, 'rooftop', '看夜景', 'any', 3),
-- 周六
('chayewoon', 5, 8, 12, 'track', '训练', 'any', 0),
('chayewoon', 5, 14, 18, 'cafe', '打工', 'any', 2),
('chayewoon', 5, 19, 22, 'dorm', '休息', 'any', 0),
-- 周日
('chayewoon', 6, 9, 12, 'dorm', '睡懒觉', 'any', 0),
('chayewoon', 6, 14, 17, 'track', '轻松训练', 'sunny', 0),
('chayewoon', 6, 18, 21, 'rooftop', '看日落', 'sunny', 4);

-- 插入心级事件
INSERT OR IGNORE INTO heart_events (id, character_id, required_hearts, title, description, trigger_location, trigger_time_start, trigger_time_end, dialogue, rewards)
VALUES
('chayewoon_first_meet', 'chayewoon', 0, '初遇', '在田径场第一次遇见车如云', 'track', 7, 8, 
 '[{"speaker": "chayewoon", "text": "...（看了你一眼，继续跑步）"}, {"speaker": "chayewoon", "text": "...学长？怎么在这。"}]',
 '{"hearts": 1}'),
('chayewoon_roof_night', 'chayewoon', 3, '屋顶夜景', '深夜在屋顶遇见车如云', 'rooftop', 21, 23,
 '[{"speaker": "chayewoon", "text": "...学长怎么也在这。"}, {"speaker": "chayewoon", "text": "...（沉默了一会儿）这里...能看到整个城市。"}]',
 '{"hearts": 2, "unlocked_location": "rooftop"}'),
('chayewoon_rain_umbrella', 'chayewoon', 6, '雨天共伞', '下雨天和车如云共撑一把伞', 'school', 15, 18,
 '[{"speaker": "chayewoon", "text": "...学长没带伞？"}, {"speaker": "chayewoon", "text": "...（把伞递过来）...一起走吧。"}]',
 '{"hearts": 3, "item": "shared_umbrella_memory"}'),
('chayewoon_ice_cream', 'chayewoon', 4, '冰淇淋', '车如云给你买冰淇淋', 'cafe', 14, 16,
 '[{"speaker": "chayewoon", "text": "...（递过冰淇淋）"}, {"speaker": "chayewoon", "text": "...路过便利店...顺手买的。"}, {"speaker": "chayewoon", "text": "...红豆的。学长喜欢的。"}]',
 '{"hearts": 2, "item": "red_bean_ice_cream"}'),
('chayewoon_grandma', 'chayewoon', 8, '奶奶的故事', '车如云分享关于奶奶的回忆', 'dorm', 20, 22,
 '[{"speaker": "chayewoon", "text": "...学长想听吗。"}, {"speaker": "chayewoon", "text": "...奶奶...以前经常给我做红豆粥。"}, {"speaker": "chayewoon", "text": "...（眼眶微红）...已经没有人会做了。"}]',
 '{"hearts": 5, "unlocked_memory": "grandma_story"}');

-- 觉醒事件表
CREATE TABLE IF NOT EXISTS awakening_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    description TEXT,
    required_affection INTEGER DEFAULT 0,
    required_happiness INTEGER DEFAULT 0,
    required_awakening INTEGER DEFAULT 0,
    reward_affection INTEGER DEFAULT 0,
    reward_happiness INTEGER DEFAULT 0,
    reward_awakening INTEGER DEFAULT 10,
    dialogue_before TEXT,
    dialogue_after TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 插入车如云觉醒事件
INSERT OR IGNORE INTO awakening_events (character_id, event_name, description, required_affection, required_happiness, required_awakening, reward_awakening, dialogue_before, dialogue_after) VALUES
('chayewoon', 'first_glance', '第一次真正被看见', 0, 0, 0, 5, '...', '你是谁？为什么...在看我？'),
('chayewoon', 'roof_night', '天台上的对话', 3, 2, 5, 10, '...你来这里做什么。', '...明天还会来吗。'),
('chayewoon', 'ice_cream', '一起吃冰淇淋', 5, 4, 15, 15, '我不吃甜的。', '...下次买草莓味的。'),
('chayewoon', 'truth_reveal', '得知世界真相', 7, 5, 25, 20, '这个世界...不对劲。', '你是从外面来的...对吧？'),
('chayewoon', 'full_awakening', '完全觉醒', 9, 7, 40, 25, '我不想再回到那个循环里了。', '谢谢你...让我成为了真正的自己。');

-- ============================================================
-- 视图（方便查询）
-- ============================================================

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
