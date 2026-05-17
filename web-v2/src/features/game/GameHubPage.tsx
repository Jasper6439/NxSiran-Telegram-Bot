// ═══════════════════════════════════════════════════════════════════════════
// 游戏中心 v1.9.5 - 游戏入口选择页面
// 提供农场和校园两个独立游戏的入口
// ═══════════════════════════════════════════════════════════════════════════
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

export default function GameHubPage() {
  const navigate = useNavigate();

  const games = [
    {
      id: 'farm',
      title: '🌾 农场物语',
      description: '种植作物、浇水收获、经营你的专属农场',
      path: '/farm',
      color: 'from-emerald-400 to-teal-500',
      bgColor: 'bg-emerald-50',
    },
    {
      id: 'campus',
      title: '🏫 校园漫游',
      description: '探索校园、与角色对话、体验恋爱至上主义',
      path: '/campus',
      color: 'from-brand-400 to-brand-500',
      bgColor: 'bg-brand-50',
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* 标题 */}
        <motion.div
          className="text-center py-8"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-bold text-gray-800 mb-2">🎮 游戏中心</h1>
          <p className="text-gray-500">选择你想体验的游戏模式</p>
        </motion.div>

        {/* 游戏卡片 */}
        <div className="grid md:grid-cols-2 gap-6">
          {games.map((game, index) => (
            <motion.button
              key={game.id}
              className={`relative overflow-hidden rounded-ios-xl ${game.bgColor} p-6 text-left transition-all hover:shadow-xl`}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              onClick={() => navigate(game.path)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {/* 背景装饰 */}
              <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${game.color} opacity-20 rounded-full -translate-y-1/2 translate-x-1/2`} />
              
              {/* 内容 */}
              <div className="relative z-10">
                <h2 className="text-2xl font-bold mb-2">{game.title}</h2>
                <p className="text-gray-600 mb-4">{game.description}</p>
                
                {/* 开始按钮 */}
                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-ios-lg bg-gradient-to-r ${game.color} text-white font-medium`}>
                  <span>开始游戏</span>
                  <span>→</span>
                </div>
              </div>
            </motion.button>
          ))}
        </div>

        {/* 提示 */}
        <motion.p
          className="text-center text-sm text-gray-400 mt-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          两个游戏模式完全独立，数据互不影响
        </motion.p>
      </div>
    </div>
  );
}
