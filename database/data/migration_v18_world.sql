-- v1.8 阶段八：双域救赎系统 - 数据库迁移
-- ============================================================

-- 1. crops 表新增字段
ALTER TABLE crops ADD COLUMN source_type TEXT DEFAULT 'NORMAL';
ALTER TABLE crops ADD COLUMN color_hex TEXT DEFAULT NULL;

-- 2. recipe_types 表新增字段
ALTER TABLE recipe_types ADD COLUMN awakening_boost INTEGER DEFAULT 0;
ALTER TABLE recipe_types ADD COLUMN effect_type TEXT DEFAULT 'STABILIZE';

-- 3. 空白区作物类型
INSERT OR IGNORE INTO crop_types (id, name, name_ko, growth_time, sell_price, seed_price, seasons, emoji, description, tier) VALUES
('void_pumpkin', '逆重力南瓜', '반중력 호박', 480, 300, 80, '["autumn"]', '🎃', '漂浮在空中的南瓜，带有微弱的暖光', 3),
('void_strawberry', '记忆草莓', '기억 딸기', 360, 250, 70, '["spring"]', '🍓', '每一颗都封存着一段被遗忘的记忆', 3),
('void_tomato', '真实番茄', '진실 토마토', 300, 200, 60, '["spring", "summer"]', '🍅', '褪去伪装后的番茄，散发着泥土的芬芳', 2),
('void_corn', '低语玉米', '속삭임 옥수수', 420, 280, 75, '["summer"]', '🌽', '风吹过时会发出温柔的低语声', 3),
('void_rose', '纸玫瑰', '종이 장미', 600, 400, 100, '["spring"]', '🌹', '用空白区的纸张折叠的玫瑰，永不凋零', 4),
('void_starfruit', '星尘果', '별빛 과일', 720, 500, 150, '["summer"]', '⭐', '果实内部闪烁着微弱的星光', 5);

-- 4. 觉醒料理配方
INSERT OR IGNORE INTO recipe_types (id, name, name_ko, ingredients, sell_price, gift_preference, emoji, effect, effect_type, awakening_boost, description) VALUES
('truth_salad', '真实沙拉', '진실 샐러드', '[{"crop": "void_tomato", "qty": 2}, {"crop": "tomato", "qty": 1}]', 300, 'chayewoon:love', '🥗', '{"type": "hearts", "value": 3}', 'AWAKEN', 8, '混合了真实与虚假的番茄，味道令人困惑'),
('gravity_pie', '失重南瓜派', '무중력 호박 파이', '[{"crop": "void_pumpkin", "qty": 2}, {"crop": "pumpkin", "qty": 1}]', 400, 'chayewoon:love', '🥧', '{"type": "hearts", "value": 5}', 'AWAKEN', 12, '吃下去会感觉身体变轻，仿佛要飘起来'),
('memory_cake', '记忆蛋糕', '기억 케이크', '[{"crop": "void_strawberry", "qty": 3}, {"crop": "strawberry", "qty": 1}]', 500, 'chayewoon:love', '🍰', '{"type": "hearts", "value": 8}', 'AWAKEN', 15, '每一口都唤起一段温暖的回忆'),
('whisper_soup', '低语浓汤', '속삭임 수프', '[{"crop": "void_corn", "qty": 2}, {"crop": "potato", "qty": 1}]', 350, 'chayewoon:love', '🍲', '{"type": "hearts", "value": 4}', 'AWAKEN', 10, '喝下去耳边会响起温柔的声音'),
('paper_rose_tea', '纸玫瑰茶', '종이 장미 차', '[{"crop": "void_rose", "qty": 1}, {"crop": "strawberry", "qty": 2}]', 600, 'chayewoon:love', '🍵', '{"type": "hearts", "value": 10}', 'AWAKEN', 20, '茶水中漂浮着纸玫瑰的花瓣，苦涩中带着甘甜'),
('stardust_dessert', '星尘甜品', '별빛 디저트', '[{"crop": "void_starfruit", "qty": 2}, {"crop": "void_strawberry", "qty": 1}]', 800, 'chayewoon:love', '✨', '{"type": "hearts", "value": 15}', 'AWAKEN', 25, '散发着星光的甜品，吃下后眼前会出现微弱的极光');

-- 5. 世界状态历史表
CREATE TABLE IF NOT EXISTS world_shift_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    shifted_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
