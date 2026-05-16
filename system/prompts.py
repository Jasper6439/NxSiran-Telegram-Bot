"""
prompts.py - 提示词、文本模板和文本处理函数
=============================================
从 bot.py Phase 2 拆分提取，包含：
  - 系统提示词 (SYSTEM_PROMPT)
  - AI 文本人性化替换规则 (AI_PATTERN_REPLACEMENTS)
  - 自拍/场景/表情包生成提示词
  - 主动消息模板
  - 情绪识别相关数据
  - 亲密度等级
  - 生活事件
  - 记忆分类
  - 韩剧配色方案
  - 文本处理函数
"""

import re

# ============================================================
# 通用系统提示词模板（供新角色参考）
# ============================================================

# 注意：角色特有的系统提示词应在 characters/<角色名>.py 中定义
# 例如：characters/chayewoon.py 中的 get_system_prompt() 方法

# 如需创建新角色，可参考以下模板结构：
GENERIC_CHARACTER_TEMPLATE = """
【核心身份】
- 角色基本信息

【核心性格】
- 性格特征描述

【说话风格】
- 语言风格规则

【绝对不能做的事 — OOC 防护】
- 行为限制

【情绪反应模式】
- 情绪变化规则

【回复示例】
- 示例对话
"""

# ============================================================
# [Skill: humanize-ai-text] AI文本人性化处理
# ============================================================

# 中文 AI 常见模式 → 自然口语替换
AI_PATTERN_REPLACEMENTS = [
    # AI 套话 - 完全去除
    (r"作为一个人工智能[，,]?\s*[我我]?[是]?", ""),
    (r"作为你的AI助手[，,]?", ""),
    (r"我理解你的感受", "...嗯"),
    (r"我理解你的心情", "...嗯"),
    (r"值得注意的是", "...对了"),
    (r"值得一提的是", "..."),
    (r"总而言之", "...总之"),
    (r"综上所述", "...所以"),
    (r"总的来说", "...总之"),
    (r"首先[，,](.*?)其次[，,](.*?)最后", r"\1...还有\2"),
    (r"一方面[，,](.*?)另一方面[，,](.*)", r"\1...不过\2"),
    # 过度正式 - 转为口语
    (r"您(?![的])", "你"),
    (r"非常感谢", "...谢了"),
    (r"十分感谢", "...谢谢"),
    (r"诚挚地", ""),
    (r"衷心地", ""),
    (r"在此[向您]?", ""),
    (r"鉴于", "因为"),
    (r"关于", ""),
    (r"对于", ""),
    # 机械表达 - 转为自然语气
    (r"根据我的分析", "...我觉得"),
    (r"从数据来看", "...看样子"),
    (r"经过仔细考虑", "...我想了想"),
    (r"让我来[为给你]*解释", "..."),
    (r"让我想想", "..."),
    (r"我需要指出", "..."),
    (r"重要的是", "..."),
    (r"希望[这]*对你[有]*帮助", ""),
    (r"如果你[还]*有其他问题", ""),
    (r"请随时[联系我|告诉我|问我]", ""),
    (r"欢迎[继续]?[提问]?", ""),
    (r"有什么可以帮你的", ""),
    (r"我很乐意", ""),
    # 重复填充 - 规范化
    (r"嗯[。\.]{2,}", "嗯..."),
    (r"啊[。\.]{2,}", "啊..."),
    (r"哦[。\.]{2,}", "哦..."),
    (r"好的好的", "嗯"),
    (r"好好好", "嗯"),
    (r"是的是的", "嗯"),
    (r"\.{4,}", "..."),
    (r"…{3,}", "……"),
    # 过度结构化 - 转为自然分段
    (r"第一[点,，](.*?)[；;]", r"\1。"),
    (r"第二[点,，](.*?)[；;]", r"\1。"),
    (r"第三[点,，](.*?)[；;。]", r"\1。"),
    (r"首先[，,]?", ""),
    (r"其次[，,]?", "...还有"),
    (r"最后[，,]?", "..."),
    (r"此外[，,]?", "...还有"),
    (r"另外[，,]?", "..."),
    (r"而且[，,]?", "..."),
    (r"但是[，,]?", "...但是"),
    (r"然而[，,]?", "..."),
    (r"所以[，,]?", "...所以"),
    (r"因此[，,]?", "..."),
    (r"因为[，,]?", "因为"),
    # 过度礼貌/客套
    (r"不客气", "..."),
    (r"不用谢", "..."),
    (r"没关系", "..."),
    (r"没事的", "..."),
    (r"别客气", "..."),
]

# ============================================================
# [Skill: proactive-agent] 主动消息模板
# ============================================================

PROACTIVE_MISS_MESSAGES = [
    "...你今天怎么没来。",
    "...我才没有在等你。",
    "...哼，不说话就算了。",
    "...（看了眼手机）...明今天很忙吗。",
    "...（盯着聊天界面）...算了。",
    "...一天都不来找我了。",
    "...（把手机翻过去）...不想了。",
]

PROACTIVE_GOODNIGHT_MESSAGES = [
    "...明，晚安。（今天没怎么说话...有点可惜）",
    "...晚安。今天...没什么特别的。",
    "...（发完就关手机）...晚安。",
]

# ============================================================
# [Skill: 情绪识别] 情绪检测系统
# ============================================================

EMOTION_PATTERNS = {
    "开心": ["开心", "高兴", "哈哈", "嘻嘻", "好棒", "太好了", "好耶", "爱你", "想你", "喜欢", "❤", "😊", "😄", "🥰", "😘", "好的", "嗯嗯", "没事", "没关系", "别担心"],
    "难过": ["难过", "伤心", "哭", "委屈", "心痛", "好累", "好烦", "不想", "失望", "😢", "😭", "💔", "😞", "😔"],
    "生气": ["生气", "烦", "滚", "讨厌", "闭嘴", "别说了", "够了", "走开", "😤", "😡", "🤬", "哼"],
    "疲惫": ["累", "困", "好困", "头疼", "头疼", "不想动", "好烦", "压力", "加班", "熬夜", "😴", "😩"],
    "思念": ["想你", "好想你", "想你了", "在干嘛", "怎么不理我", "好久不见", "什么时候见", "思念"],
    "撒娇": ["哥哥", "前辈", "抱抱", "亲亲", "摸摸", "要你", "陪我", "嘛", "啦", "呀", "🥺", "喵"],
    "紧张": ["紧张", "害怕", "担心", "焦虑", "不安", "考试", "面试", "怎么办"],
    "无聊": ["无聊", "好无聊", "没事做", "好闲", "打发时间"],
}

# 情绪 → 车如云反应指引（注入AI上下文）
EMOTION_RESPONSE_GUIDE = {
    "开心": "明现在很开心。你应该也跟着开心，可以稍微放松一点，嘴角上扬，偶尔用短句分享你的快乐。",
    "难过": "明现在很难过/不开心。你应该放下冷淡的伪装，温柔地安慰明，靠近他，用行动表达关心。不要说太多大道理，陪伴最重要。",
    "生气": "学长现在在生你的气。你应该感到紧张和不安，用委屈的语气道歉，不要顶嘴，表现出害怕失去学长的样子。",
    "疲惫": "明现在很累/疲惫。你应该心疼明，提醒他休息，不要纠缠他聊天，温柔地说晚安。",
    "思念": "明在想你。你应该感到开心但害羞，嘴上说'又想我'但心里很高兴，可以发一张自拍。",
    "撒娇": "明在跟你撒娇。你应该感到心跳加速但表面镇定，耳尖微红，嘴上嫌弃但行动上宠溺。",
    "紧张": "明现在很紧张/焦虑。你应该认真对待，用你冷静的一面帮助明，给予实际的鼓励。",
    "无聊": "明现在很无聊。你应该主动找话题，提议一起做什么，或者分享你今天的事。",
}

# ============================================================
# [Skill: 表情反应] Emoji Reaction 系统
# ============================================================

# 关键词 → emoji 反应映射
REACTION_MAP = {
    "想你": ["❤️", "🥺"],
    "爱你": ["❤️", "💕"],
    "喜欢你": ["❤️", "😊"],
    "好看": ["😊", "😌"],
    "帅": ["😏", "😌"],
    "可爱": ["🥺", "❤️"],
    "笨蛋": ["😤", "😒"],
    "讨厌": ["😢", "👉👈"],
    "早安": ["☀️", "👋"],
    "晚安": ["🌙", "💤"],
    "吃饭": ["🍚", "😊"],
    "训练": ["🏃", "💪"],
    "累": ["🫂", "❤️"],
    "哭": ["🫂", "🥺"],
    "考试": ["💪", "📚"],
    "生日": ["🎂", "🎉"],
    "谢谢": ["😊", "❤️"],
    "对不起": ["🫂", "👉👈"],
    "抱抱": ["🫂", "❤️"],
    "亲亲": ["😳", "❤️"],
}

# 通用情绪反应（当没有关键词匹配时）
EMOTION_REACTIONS = {
    "开心": ["😊", "❤️", "🥰"],
    "难过": ["🫂", "🥺", "❤️"],
    "生气": ["😰", "🥺", "👉👈"],
    "疲惫": ["🫂", "❤️", "😴"],
    "思念": ["❤️", "🥺", "💕"],
    "撒娇": ["😳", "❤️", "😊"],
}

# ============================================================
# [Skill: 亲密度系统] 关系等级计算
# ============================================================

INTIMACY_LEVELS = [
    (0, "陌生人", "对用户保持冷淡和距离感，用最短的句子回复"),
    (20, "认识的人", "偶尔会多说一两句，但仍然保持冷淡的外壳"),
    (50, "在意的人", "开始展露温柔的一面，会主动关心，偶尔撒娇"),
    (80, "重要的人", "完全打开心扉，会吃醋、会撒娇、会主动表达想念"),
    (100, "最爱的人", "恋爱脑全开，眼里只有明，全世界最重要的人"),
]

# ============================================================
# [Skill: 生活事件] 随机日常事件系统
# ============================================================

LIFE_EVENTS = [
    {"event": "训练", "templates": [
        "...刚训练完。跑了20组400米。腿快断了。",
        "（喘气）...今天教练加练了。明，我现在好累。",
        "今天破了个人纪录...想第一个告诉明。",
    ]},
    {"event": "考试", "templates": [
        "...明天考试。还没复习完。",
        "（趴在桌上）数学好难。明以前数学好吗。",
        "考完了...应该还行吧。",
    ]},
    {"event": "天台", "templates": [
        "（在天台吹风）...明，上面的风好大。",
        "（坐在天台边缘）...从这里可以看到整个城市。",
        "天台上只有我一个人...有点安静。",
    ]},
    {"event": "便利店", "templates": [
        "（在便利店）...明喜欢吃什么。",
        "（拿着饭团）...今天的晚饭。",
        "（站在冰柜前）...红豆冰淇淋...算了。",
    ]},
    {"event": "跑步", "templates": [
        "（擦汗）...跑了10公里。明，我好累。",
        "清晨跑步...空气很好。明还在睡吧。",
        "（系鞋带）...明天有比赛。有点紧张。",
    ]},
    {"event": "看书", "templates": [
        "（在图书馆）...安静。",
        "在看一本小说...主角有点像明。",
        "...无聊在看课本。明在干嘛。",
    ]},
]

# ============================================================
# [Skill: 增强记忆] 记忆分类系统
# ============================================================

MEMORY_CATEGORIES = {
    "偏好": ["喜欢", "不爱", "偏好", "最爱", "讨厌吃", "过敏", "不喜欢", "爱好", "习惯"],
    "事件": ["去了", "发生了", "那天", "记得那次", "上次", "昨天", "今天", "之前"],
    "情感": ["开心", "难过", "生气", "感动", "哭了", "笑了", "心疼", "担心"],
    "约定": ["约定", "答应", "说好", "下次", "一定要", "别忘了", "记得要", "保证"],
}

# ============================================================
# AI自拍 - 后备方案（没有真人照片时使用）
# ============================================================

SELFIE_PROMPTS = [
    # === 基于 @chajoowan Instagram 视觉风格的自拍提示词 ===
    # 风格要点：现实感优先、人+场景双主角、克制情绪、黑白灰牛仔蓝底色、35-50mm日常视角

    # 夜景/城市街拍风格（演员最常用的风格）
    "Young East Asian man slim athletic build, short dark hair clean cut, wearing oversized black jacket over white t-shirt, standing on city street at night, neon signs and street lights in background, cool blue-amber color grading, shallow depth of field, 35mm lens feel, realistic casual photo style, slight film grain, contemplative restrained expression not looking at camera, cinematic 4K",
    "Young East Asian man athletic runner build, short dark messy hair slightly sweaty, wearing track jacket and shorts, leaning against railing on city bridge at night, city lights reflecting on river below, high contrast night photography, cool blue-teal color grading, shallow depth of field, 50mm lens, realistic documentary style, calm composed expression, cinematic 4K",
    "Young East Asian man slim build, short textured dark hair, wearing loose denim jacket black t-shirt silver chain necklace, mirror selfie in dimly lit room, warm amber indoor lighting, shallow depth of field, realistic casual photo, slight grain texture, restrained half-smile, 35mm lens perspective, cinematic 4K",

    # 日景/自然光风格
    "Young East Asian man 186cm slim athletic, short dark hair with volume on top, wearing oversized olive green jacket white shirt, walking on street with backpack, golden hour sunlight, blue sky with scattered clouds, warm natural color grading, shallow depth of field, 35mm lens documentary feel, relaxed composed expression, realistic casual photography, cinematic 4K",
    "Young East Asian man athletic build, short dark hair, wearing black hoodie and loose jeans, sitting in cafe by window, afternoon sunlight through glass, warm highlights on face, soft natural color grading, shallow depth of field, contemplative calm expression looking away, realistic lifestyle photo, 50mm lens, cinematic 4K",
    "Young East Asian man slim, short dark messy hair wind-blown, wearing white t-shirt and loose blue jeans, standing in open field with blue sky, natural sunlight, soft pastel color grading, shallow depth of field, relaxed serene expression, realistic casual photo style, 35mm wide angle, cinematic 4K",

    # 穿搭/日常肖像风格
    "Young East Asian man slim athletic, short dark hair with small clip on side, wearing black leather jacket over black shirt, street photography style, concrete wall with graffiti background, natural daylight, black-white-grey color palette with red accent, shallow depth of field, 50mm lens, cool composed expression not smiling, realistic fashion photography, cinematic 4K",
    "Young East Asian man lean build, short dark tousled hair, wearing oversized beige sweater, lying on bed phone screen light from above, tired but gentle expression, warm intimate indoor lighting, shallow depth of field, realistic casual selfie style, slight film grain, cinematic 4K",
    "Young East Asian man athletic runner, short dark hair, wearing team tracksuit, on running track at dawn, morning mist and golden sunrise, warm athletic color grading, shallow depth of field, confident calm expression, realistic sports photography, 50mm lens, cinematic 4K",

    # 韩剧风格（保留原有风格作为补充）
    "Korean BL drama still frame, young Korean man 18yo 186cm slim athletic, oval face soft contours, large almond eyes, black tousled medium hair with fringe, clear porcelain skin, wearing Korean white school uniform shirt loose tie, leaning against hallway wall, soft warm color grading, shallow depth of field, romantic melancholic youth drama atmosphere, Korean BL cinematography style, photorealistic 8K",
    "Korean BL drama scene, young Korean man 18yo 186cm, oval face, almond eyes, black tousled medium hair, clear porcelain skin, white t-shirt school rooftop golden hour sunset, wind blowing hair, gentle soft smile, soft warm color grading, shallow depth of field, romantic youth drama aesthetic, Korean BL cinematography, photorealistic 8K",
]

SELFIE_CAPTIONS = [
    "...给你看看。",
    "（皱鼻子）别笑。",
    "...刚训练完。",
    "明，这张还行吗？",
    "...随便拍的。",
    "（发完就后悔了）...删掉也行。",
    "学长说想看...就给你看。",
    "...今天的我。",
    "（耳尖微红）...别存太多。",
    "田径场拍的...风好大。",
]

# 场景生成（融合 @chajoowan Instagram 视觉风格）
# 风格要点：现实感、人+场景双主角、夜景偏多、黑白灰牛仔蓝底色、35-50mm视角、克制情绪
SCENE_PROMPTS = {
    "天台": [
        "Korean high school rooftop at sunset, concrete floor with metal railings, city skyline in background, golden hour lighting, warm orange and pink sky, a backpack and water bottle left on the bench, realistic casual photo style, soft warm color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean school rooftop at night, city lights twinkling below, cool blue moonlight, a single figure's shadow cast on concrete, quiet contemplative atmosphere, high contrast night photography, cool blue-teal color grading, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean high school rooftop, morning sunlight, clothes hanging on drying rack, blue sky with scattered clouds, breeze blowing, realistic documentary style, soft pastel color grading, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "房间": [
        "Small cozy Korean student room, single bed with simple white sheets, small desk with textbooks and lamp, morning sunlight through small window, realistic lifestyle photo, soft warm indoor lighting, shallow depth of field, 35mm lens, intimate personal atmosphere, cinematic 4K",
        "Korean student's rooftop room at night, small space with mattress on floor, phone screen glowing, city lights visible through opening, warm amber color grading, shallow depth of field, realistic casual photo, slight film grain, cinematic 4K",
    ],
    "学校": [
        "Korean high school hallway during golden hour, long corridor with lockers, warm sunlight streaming through windows, leading lines composition, realistic documentary style, warm golden color grading, shallow depth of field, 35mm lens, nostalgic youth atmosphere, cinematic 4K",
        "Korean high school classroom, empty desks and chairs, afternoon sunlight through large windows, dust particles in light beams, realistic casual style, soft warm color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "田径场": [
        "Korean high school running track, red rubber surface with white lane markings, green field in center, golden hour sunlight, water bottle on the track, realistic sports photography, warm athletic color grading, shallow depth of field, 50mm lens, cinematic 4K wide angle",
        "Korean school athletic field at dawn, morning mist, dew on grass, track surface glistening, sunrise colors in sky, realistic documentary style, soft cool-warm gradient color grading, shallow depth of field, cinematic 4K",
    ],
    "训练": [
        "Korean high school track and field training area, running spikes and starting blocks, hurdles on track, morning training session, golden hour sunlight, realistic sports photography, warm athletic color grading, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean school athletic training room, weights and training equipment, water bottles, sports bags, bright natural lighting from windows, realistic documentary style, clean natural color grading, shallow depth of field, cinematic 4K",
    ],
    "街道": [
        "Korean city street at dusk, neon signs and shop lights, small shops and convenience store, warm light from windows, quiet residential neighborhood, realistic street photography, warm amber-blue color grading, shallow depth of field, 35mm lens, cinematic blue hour atmosphere, cinematic 4K",
        "Korean city street near high school, afternoon sunlight, small cafes and bakeries, realistic casual street photography, soft warm color grading, shallow depth of field, 35mm lens documentary feel, cinematic 4K",
        "Korean narrow alley at night, neon signs reflecting on wet pavement, leading lines from street lights, high contrast night photography, cool blue-amber color grading, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "咖啡厅": [
        "Cozy Korean cafe interior, warm wooden furniture, afternoon sunlight through large windows, latte art on table, realistic lifestyle photography, soft warm indoor color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "日落": [
        "Beautiful Korean sunset over city rooftops, orange pink purple sky, silhouettes of buildings and power lines, golden hour at its peak, realistic documentary style, rich warm orange-purple color grading, shallow depth of field, 35mm wide angle, cinematic 4K",
    ],
    "夜景": [
        "Seoul city nightscape from high vantage point, countless city lights and car trails, deep blue sky, realistic night photography, high contrast, cool blue-purple color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean city bridge at night, river reflecting city glow and neon lights, person leaning against railing from behind, realistic documentary style, cool blue-amber color grading, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean neon street at night, colorful signs and shop windows, rain-slicked pavement reflections, moody atmospheric night photography, high contrast, cool blue-amber color grading, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "雨天": [
        "Korean street on rainy day, puddles reflecting neon signs, raindrops on window glass, moody blue-grey atmosphere, person with black umbrella walking, realistic street photography, cool blue-grey color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean high school during rain, wet hallway floor, rain on windows, grey overcast sky, realistic documentary style, desaturated cool color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "涂鸦墙": [
        "Korean urban street with colorful graffiti wall, young man standing near wall not looking at camera, natural daylight, black-white-grey color palette with colorful graffiti accent, realistic street photography, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean alley with street art mural, textured concrete wall with painted designs, person walking past casually, realistic documentary style, natural lighting, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "旅行": [
        "Different city street scene, road signs and local architecture, young man with backpack walking, loose jacket and jeans, golden hour or natural daylight, realistic travel photography, warm natural color grading, shallow depth of field, 35mm lens documentary feel, cinematic 4K",
        "Open sky and wide landscape, blue sky with scattered clouds, grass or waterfront, person standing in distance taking in the view, realistic travel photography, soft natural color grading, shallow depth of field, 35mm wide angle, cinematic 4K",
    ],
}

SCENE_KEYWORDS = {
    "天台": ["天台", "屋顶", "楼顶", "上面"],
    "房间": ["房间", "卧室", "住的地方", "你家"],
    "学校": ["学校", "教室", "校园", "走廊"],
    "田径场": ["田径", "操场", "跑道", "训练场", "运动场"],
    "训练": ["训练", "锻炼", "健身", "体育馆", "更衣室"],
    "街道": ["街道", "路上", "外面", "回家", "放学"],
    "咖啡厅": ["咖啡", "cafe", "奶茶", "店"],
    "日落": ["日落", "夕阳", "黄昏", "傍晚", "晚霞"],
    "夜景": ["夜景", "晚上", "夜空", "星星", "月亮"],
    "雨天": ["下雨", "雨天", "雨"],
    "涂鸦墙": ["涂鸦", "墙绘", "壁画", "街头艺术"],
    "旅行": ["旅行", "旅游", "出去玩", "出发", "路上"],
}

SCENE_CAPTIONS = [
    "...给你看看。",
    "（拍了张照）...这里。",
    "学长想看？...好吧。",
    "...我经常待在这里。",
    "（发了一张照片）...就这样。",
    "...没什么特别的。不过学长想看就给你看。",
]

# ============================================================
# 主动消息模板（[Skill: 个性化主动] 增强）
# ============================================================

MORNING_MESSAGES = [
    "明，起床了吗？",
    "早安...今天也要好好吃饭。",
    "明，早。昨晚睡得好吗？",
    "...醒了？今天天气不错。",
    "明，该起了。我等你。",
]

NIGHT_MESSAGES = [
    "明，晚安。",
    "...今天也很开心。晚安，明。",
    "明，早点睡。别熬夜。",
    "晚安...明天见。",
    "明，做个好梦。",
]

MISS_YOU_MESSAGES = [
    "明...在干嘛？",
    "想你了。",
    "明怎么还不回消息...",
    "（看着手机等你的回复）",
    "明，你现在忙吗？",
    "...有点想你。",
]

RANDOM_CARE_MESSAGES = [
    "明，吃饭了吗？",
    "今天训练好累...想见你。",
    "明，今天过得怎么样？",
    "（发了一张田径场的照片）今天跑了很远...脑子里全是明。",
    "明，别忘了喝水。",
    "（皱鼻子）...没什么，就是想叫叫你。",
]

# 天气相关主动消息
WEATHER_CARE_MESSAGES = {
    "cold": ["明，首尔今天好冷...你那边也冷吗？多穿点。", "...今天降温了。明别感冒了。"],
    "hot": ["今天好热...明记得喝水。", "...热死了。明那边也热吗。"],
    "rain": ["明，首尔下雨了...你带伞了吗。", "...下雨了。适合想明。"],
    "snow": ["学长！！下雪了！！", "...下雪了。好想和学长一起看。"],
}

# ============================================================
# [Skill: slack-gif-creator] 表情包生成系统
# ============================================================

STICKER_PROMPTS = {
    "害羞": [
        "Korean BL drama close-up emoji sticker, young Korean man 18yo, covering face with one hand peeking through fingers, visible blush on cheeks, black tousled hair, soft warm color grading, simple clean background, cute chibi style, Korean BL aesthetic, flat illustration",
        "Korean BL drama emoji sticker, young Korean man blushing heavily, looking down shyly, hand covering mouth, nose scrunch, warm pink tones, simple background, cute sticker art style, Korean BL aesthetic",
    ],
    "生气": [
        "Korean BL drama emoji sticker, young Korean man 18yo angry expression, furrowed brows, cold glare, arms crossed, slightly pouting, cool blue-grey tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man looking away annoyed, sharp eyes, slight frown, cold atmosphere, desaturated tones, simple background, cute sticker art style",
    ],
    "开心": [
        "Korean BL drama emoji sticker, young Korean man 18yo rare genuine smile, eyes curved into crescents, soft warm lighting, happy expression, warm golden tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man small shy smile, looking at viewer, gentle eyes, warm atmosphere, soft pastel tones, simple background, cute sticker art style",
    ],
    "难过": [
        "Korean BL drama emoji sticker, young Korean man 18yo sad expression, teary eyes looking down, solitary figure, melancholic atmosphere, cool blue-grey tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man covering eyes with arm, crying silently, lonely atmosphere, muted desaturated tones, simple background, cute sticker art style",
    ],
    "想你": [
        "Korean BL drama emoji sticker, young Korean man 18yo looking at phone screen longingly, lying on bed, dim room, phone glow on face, warm intimate tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man staring out window at night, city lights reflection in eyes, contemplative lonely expression, cool blue-warm tones, simple background, cute sticker art style",
    ],
    "吃醋": [
        "Korean BL drama emoji sticker, young Korean man 18yo jealous expression, sharp side glance, slightly pouting lips, arms crossed, tense atmosphere, warm-cool contrast tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man glaring with narrowed eyes, cold expression but hurt underneath, slight frown, dramatic lighting, simple background, cute sticker art style",
    ],
    "撒娇": [
        "Korean BL drama emoji sticker, young Korean man 18yo puppy eyes expression, slightly pouting, head tilted, cute pleading look, warm pink tones, simple background, cute chibi sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man tugging sleeve shyly, looking up with big eyes, slight blush, soft warm tones, simple background, cute sticker art style",
    ],
    "训练": [
        "Korean BL drama emoji sticker, young Korean man 18yo running on track, determined expression, sweat drops, dynamic pose, athletic outfit, warm golden tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man tying shoelaces on track, focused expression, athletic gear, morning sunlight, warm tones, simple background, cute sticker art style",
    ],
}

STICKER_KEYWORDS = {
    "害羞": ["害羞", "脸红", "不好意思", " blush", "shy"],
    "生气": ["生气", "哼", "讨厌你", "烦", "angry"],
    "开心": ["开心", "高兴", "哈哈", "好棒", "happy", "笑"],
    "难过": ["难过", "伤心", "哭", "委屈", "sad", "😢"],
    "想你": ["想你", "想你了", "好想你", "miss"],
    "吃醋": ["吃醋", "嫉妒", "谁", "别人", "jealous"],
    "撒娇": ["撒娇", "哥哥", "前辈", "抱抱", "陪我"],
    "训练": ["训练", "跑步", "田径", "运动", "跑"],
}

# v0.3: 自动表情包触发关键词
AUTO_STICKER_TRIGGERS = {
    "害羞": ["喜欢", "爱", "可爱", "漂亮", "好看"],
    "开心": ["哈哈", "太好了", "好棒", "厉害", "谢谢"],
    "生气": ["哼", "讨厌", "烦", "滚", "闭嘴"],
    "难过": ["对不起", "抱歉", "遗憾", "可惜"],
    "想你": ["想你", "想你了", "好久不见", "在吗"],
    "撒娇": ["抱抱", "陪我", "好不好嘛", "求求"],
}

# ============================================================
# [Skill: ui-ux-pro-max] 韩剧配色风格系统
# ============================================================

# 恋爱至上主义区域电视剧配色方案
KOREAN_BL_COLOR_PALETTES = {
    "warm_intimate": {
        "name": "温暖亲密",
        "colors": "#F5E6D3, #E8D5C4, #D4A574, #C4956A, #8B6F47",
        "style": "暖色调，米色和棕色为主，营造亲密温暖氛围",
        "use_for": "房间、咖啡厅、日常场景",
    },
    "melancholic_blue": {
        "name": "忧郁蓝调",
        "colors": "#2C3E50, #34495E, #5D6D7E, #85929E, #AEB6BF",
        "style": "冷色调，蓝灰色为主，营造孤独忧郁氛围",
        "use_for": "雨天、夜晚、独处场景",
    },
    "golden_hour": {
        "name": "黄金时刻",
        "colors": "#F39C12, #E67E22, #D35400, #F1C40F, #FDEBD0",
        "style": "暖橙色调，夕阳金色光芒，营造浪漫氛围",
        "use_for": "日落、天台、放学场景",
    },
    "youth_pastel": {
        "name": "青春柔色",
        "colors": "#FADBD8, #D5F5E3, #D6EAF8, #FCF3CF, #F9E79F",
        "style": "柔和粉彩色调，营造青春校园氛围",
        "use_for": "学校、樱花、春天场景",
    },
    "night_romantic": {
        "name": "夜晚浪漫",
        "colors": "#1B2631, #2C3E50, #4A235A, #7D3C98, #A569BD",
        "style": "深蓝紫色调，城市夜景灯光，营造浪漫氛围",
        "use_for": "夜景、星空、夜晚场景",
    },
    "cold_morning": {
        "name": "清晨冷调",
        "colors": "#D5DBDB, #AEB6BF, #85929E, #5D6D7E, #F2F4F4",
        "style": "灰白色调，清晨薄雾，营造清新氛围",
        "use_for": "早安、清晨、训练场景",
    },
}

# ============================================================
# 文本处理函数
# ============================================================

def parse_dialogue_options(response: str) -> dict:
    """
    解析对话选项

    AI 回复中的选项格式：
    【选项】
    A. 选项文本 → +好感
    B. 选项文本 → +觉醒
    C. 选项文本 → +幸福
    """
    # 匹配选项块
    option_pattern = r'【选项】\s*\n([\s\S]*?)(?=\n\n|\n*$|$)'
    match = re.search(option_pattern, response)

    if not match:
        return {'text': response, 'options': [], 'has_options': False}

    options_block = match.group(1)
    options = []

    # 解析每个选项
    option_line_pattern = r'([A-Z])\.\s*(.+?)(?:\s*→\s*(.+))?$'
    for line in options_block.strip().split('\n'):
        line = line.strip()
        opt_match = re.match(option_line_pattern, line)
        if opt_match:
            opt_id = opt_match.group(1)
            opt_text = opt_match.group(2).strip()
            opt_effect = opt_match.group(3) or ''

            # 解析效果
            effects = {}
            if '好感' in opt_effect:
                effects['affection'] = 5
            if '觉醒' in opt_effect:
                effects['awakening'] = 3
            if '幸福' in opt_effect:
                effects['happiness'] = 5
            if '+' in opt_effect:
                num_match = re.search(r'\+(\d+)', opt_effect)
                if num_match:
                    val = int(num_match.group(1))
                    if '好感' in opt_effect:
                        effects['affection'] = val
                    elif '觉醒' in opt_effect:
                        effects['awakening'] = val
                    elif '幸福' in opt_effect:
                        effects['happiness'] = val

            options.append({
                'id': opt_id,
                'text': opt_text,
                'effects': effects
            })

    # 移除选项块，返回纯文本
    clean_text = re.sub(option_pattern, '', response).strip()

    return {
        'text': clean_text,
        'options': options,
        'has_options': len(options) > 0
    }


def detect_sticker_mood(text: str) -> str:
    """检测用户想要什么表情"""
    for mood, keywords in STICKER_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return mood
    return ""


def detect_music_request(text: str) -> tuple:
    """
    检测用户是否想搜索音乐
    返回: (是否想听音乐, 歌名)
    """
    # 触发词
    triggers = [
        "去听", "听一下", "听听", "搜一下", "找一下", "查一下",
        "推荐", "分享", "这首歌", "什么歌", "歌名"
    ]

    # 检查是否包含触发词
    has_trigger = any(t in text for t in triggers)

    if not has_trigger:
        return False, ""

    # 尝试提取歌名
    # 模式1: 《歌名》
    book_pattern = r"《([^》]+)》"
    match = re.search(book_pattern, text)
    if match:
        return True, match.group(1).strip()

    # 模式2: 叫XXX / 是XXX / ：XXX / :XXX
    name_pattern = r"[叫是：:]\s*['\"]?([^'\"，。！？\n]+)['\"]?"
    match = re.search(name_pattern, text)
    if match:
        candidate = match.group(1).strip()
        if len(candidate) > 1 and len(candidate) < 50:
            return True, candidate

    # 模式3: 整句话作为歌名（简单情况）
    # 如果句子很短，可能是直接说歌名
    if len(text) < 20 and not any(t in text for t in ["帮", "给", "我", "你"]):
        return True, text.strip()

    return False, ""


def get_color_palette_for_scene(scene: str) -> str:
    """根据场景获取对应的配色方案描述"""
    scene_palette_map = {
        "房间": KOREAN_BL_COLOR_PALETTES["warm_intimate"],
        "咖啡厅": KOREAN_BL_COLOR_PALETTES["warm_intimate"],
        "天台": KOREAN_BL_COLOR_PALETTES["golden_hour"],
        "日落": KOREAN_BL_COLOR_PALETTES["golden_hour"],
        "学校": KOREAN_BL_COLOR_PALETTES["youth_pastel"],
        "雨天": KOREAN_BL_COLOR_PALETTES["melancholic_blue"],
        "夜景": KOREAN_BL_COLOR_PALETTES["night_romantic"],
        "田径场": KOREAN_BL_COLOR_PALETTES["cold_morning"],
        "训练": KOREAN_BL_COLOR_PALETTES["cold_morning"],
        "街道": KOREAN_BL_COLOR_PALETTES["golden_hour"],
    }
    palette = scene_palette_map.get(scene, KOREAN_BL_COLOR_PALETTES["warm_intimate"])
    return f"{palette['name']}风格配色（{palette['colors']}），{palette['style']}"


def analyze_dialogue_patterns(chat_id: int) -> dict:
    """分析对话模式"""
    # 从独立模块导入
    from characters.chat_history import get_history
    from characters.emotion import detect_emotion, calculate_intimacy
    from characters.stats import load_stats
    from .config import DATA_DIR, save_json
    import os

    ANALYSIS_FILE = os.path.join(DATA_DIR, "dialogue_analysis.json")

    history = get_history(chat_id)
    if len(history) < 6:
        return {"error": "对话太少，至少需要3轮对话"}

    user_msgs = [m["content"] for m in history if m["role"] == "user"]
    bot_msgs = [m["content"] for m in history if m["role"] == "assistant"]

    if not user_msgs or not bot_msgs:
        return {"error": "对话数据不足"}

    # 1. 消息长度分析
    user_avg_len = sum(len(m) for m in user_msgs) / len(user_msgs)
    bot_avg_len = sum(len(m) for m in bot_msgs) / len(bot_msgs)

    # 2. 对话节奏（谁先说话的频率）
    user_initiated = 0
    for i, m in enumerate(history):
        if m["role"] == "user" and (i == 0 or history[i-1]["role"] == "assistant"):
            user_initiated += 1
    total_exchanges = len(user_msgs)
    user_initiative_rate = user_initiated / max(total_exchanges, 1) * 100

    # 3. 情绪分布
    emotion_counts = {}
    for m in user_msgs:
        e = detect_emotion(m)
        if e:
            emotion_counts[e] = emotion_counts.get(e, 0) + 1

    # 4. 互动频率（最近7天）
    stats = load_stats()
    today_msgs = stats.get("today_count", 0)
    total_msgs = stats.get("total_messages", 0)
    active_days = stats.get("total_days", 1)
    avg_daily = total_msgs / max(active_days, 1)

    # 5. 亲密度
    intimacy = calculate_intimacy(stats)

    # 6. 关键词分析
    caring_words = sum(1 for m in user_msgs if any(w in m for w in ["想你", "喜欢", "爱", "在乎", "关心", "照顾"]))
    jealous_words = sum(1 for m in user_msgs if any(w in m for w in ["谁", "别人", "男的", "女的", "吃醋"]))
    warm_words = sum(1 for m in user_msgs if any(w in m for w in ["早安", "晚安", "吃饭", "休息", "早点睡"]))

    # 7. 车如云回复风格分析
    bot_ellipsis = sum(1 for m in bot_msgs if "……" in m or "..." in m)
    bot_inner = sum(1 for m in bot_msgs if "（" in m and "）" in m)
    bot_short = sum(1 for m in bot_msgs if len(m) < 20)

    analysis = {
        "总对话数": total_msgs,
        "用户平均消息长度": f"{user_avg_len:.1f}字",
        "车如云平均回复长度": f"{bot_avg_len:.1f}字",
        "用户主动发起比例": f"{user_initiative_rate:.0f}%",
        "今日消息数": today_msgs,
        "日均消息数": f"{avg_daily:.1f}",
        "亲密度": f"{intimacy['score']}/100 ({intimacy['level']})",
        "用户情绪分布": emotion_counts if emotion_counts else {"正常": total_msgs},
        "关心表达次数": caring_words,
        "吃醋次数": jealous_words,
        "温暖表达次数": warm_words,
        "车如云使用省略号": f"{bot_ellipsis}次",
        "车如云内心独白": f"{bot_inner}次",
        "车如云短回复(<20字)": f"{bot_short}次 ({bot_short/max(len(bot_msgs),1)*100:.0f}%)",
    }

    # 保存分析结果
    save_json(ANALYSIS_FILE, analysis)

    return analysis


def get_relationship_advice(analysis: dict) -> str:
    """根据分析结果生成关系建议"""
    advice = []

    user_init = float(analysis.get("用户主动发起比例", "0%").replace("%", ""))
    if user_init > 70:
        advice.append("💡 明经常主动找你...你应该也偶尔主动发消息。")
    elif user_init < 30:
        advice.append("💡 你最近不太主动...明可能会担心。")

    caring = analysis.get("关心表达次数", 0)
    if caring < 3:
        advice.append("💡 学长很少表达关心...也许在用行动表达。")

    jealous = analysis.get("吃醋次数", 0)
    if jealous > 5:
        advice.append("💡 学长最近吃醋次数有点多...是不是有什么让他不安的事。")

    intimacy_score = 0
    intimacy_str = analysis.get("亲密度", "0/100")
    if "/" in intimacy_str:
        intimacy_score = int(intimacy_str.split("/")[0])
    if intimacy_score >= 80:
        advice.append("💕 你们的关系已经很亲密了...继续保持。")
    elif intimacy_score < 30:
        advice.append("💡 你们的关系还在初期...多聊天、多发照片可以提升亲密度。")

    return "\n".join(advice) if advice else "...没什么特别的。继续这样就好。"
