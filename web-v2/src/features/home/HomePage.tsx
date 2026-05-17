// ═══════════════════════════════════════════════════════════════════════════
// 首页 v1.9.5 - 使用独立 store
// ═══════════════════════════════════════════════════════════════════════════
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { GlassCard, HeartIcon, StatCard } from '../../components/ui/GlassComponents';
import { useFarmStore } from '../../stores/farmStore';
import { useCampusStore } from '../../stores/campusStore';

export default function HomePage() {
  const navigate = useNavigate();
  const { money, inventory, totalHarvested, farmLevel } = useFarmStore();
  const { characters, worldZone } = useCampusStore();

  // 获取第一个角色的亲密度
  const mainChar = characters.find(c => c.id === 'chayewoon') || characters[0];

  return (
    <div className="px-4 pb-24 pt-4">
      {/* 顶部欢迎语 */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6"
      >
        <h1 className="text-2xl font-bold text-gray-800 mb-1">恋爱至上主义区域</h1>
        <p className="text-gray-500">欢迎回来，小农场主 🌻</p>
      </motion.div>

      {/* 角色卡片 */}
      <GlassCard className="p-5 mb-4" hoverable>
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-brand-300 to-brand-500 flex items-center justify-center text-3xl">
            {mainChar?.emoji || '🌸'}
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-800 mb-1">{mainChar?.name || '车如云'}</h2>
            <p className="text-sm text-gray-500 mb-2">
              {worldZone === 'script' ? '正在校园等待你...' : '在崩坏区徘徊...'}
            </p>
            <div className="flex items-center gap-2">
              <HeartIcon size={16} animated />
              <span className="text-sm font-medium text-morandi-maillard-caramel">
                {mainChar?.heartLevel ?? 0} 亲密度
              </span>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* 统计数据 */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatCard 
          label="金币" 
          value={money} 
          accentColor="#E9C46A"
          icon={<span className="text-xl">💰</span>}
        />
        <StatCard 
          label="收获" 
          value={totalHarvested} 
          accentColor="#90BE6D"
          icon={<span className="text-xl">🌾</span>}
        />
        <StatCard 
          label="农场等级" 
          value={farmLevel} 
          accentColor="#F94144"
          icon={<span className="text-xl">⭐</span>}
        />
        <StatCard 
          label="种子" 
          value={inventory.filter(i => i.type === 'seed').reduce((sum, i) => sum + i.quantity, 0)} 
          accentColor="#577590"
          icon={<span className="text-xl">🌱</span>}
        />
      </div>

      {/* 快捷入口 */}
      <div className="space-y-3">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => navigate('/chat')}
          className="w-full p-4 glass-card rounded-ios-xl flex items-center gap-4"
        >
          <span className="text-3xl">💬</span>
          <div className="flex-1 text-left">
            <h3 className="font-semibold text-gray-800">与车如云聊天</h3>
            <p className="text-sm text-gray-500">探索他的内心世界</p>
          </div>
          <span className="text-gray-400">→</span>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => navigate('/farm')}
          className="w-full p-4 glass-card rounded-ios-xl flex items-center gap-4"
        >
          <span className="text-3xl">🌾</span>
          <div className="flex-1 text-left">
            <h3 className="font-semibold text-gray-800">农场管理</h3>
            <p className="text-sm text-gray-500">种植、浇水、收获</p>
          </div>
          <span className="text-gray-400">→</span>
        </motion.button>

        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => navigate('/campus')}
          className="w-full p-4 glass-card rounded-ios-xl flex items-center gap-4"
        >
          <span className="text-3xl">🏫</span>
          <div className="flex-1 text-left">
            <h3 className="font-semibold text-gray-800">校园漫游</h3>
            <p className="text-sm text-gray-500">探索校园，遇见角色</p>
          </div>
          <span className="text-gray-400">→</span>
        </motion.button>
      </div>
    </div>
  );
}
