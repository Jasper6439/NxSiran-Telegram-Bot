// ═══════════════════════════════════════════════════════════════════════════
// 农场页面 v1.9.5 - 完全独立的农场游戏
// 与校园漫游彻底解耦，独立生命周期
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useFarmStore, getCropStageEmoji } from '../../stores/farmStore';
import { CROP_CONFIG } from '../../stores/constants';
import type { CropType } from '../../stores/types';

// 农场网格配置
const GRID_SIZE = 6;
const CELL_SIZE = 60;
const FARM_WIDTH = GRID_SIZE * CELL_SIZE;
const FARM_HEIGHT = GRID_SIZE * CELL_SIZE;

export default function FarmPage() {
  // 使用独立的 farmStore
  const {
    crops,
    inventory,
    money,
    totalHarvested,
    farmLevel,
    farmExp,
    plantCrop,
    harvestCrop,
    waterCrop,
    buySeed,
    tick,
  } = useFarmStore();

  // 本地状态
  const [selectedSeed, setSelectedSeed] = useState<CropType>('wheat');
  const [selectedPlot, setSelectedPlot] = useState<{ x: number; y: number } | null>(null);
  const [floatingTexts, setFloatingTexts] = useState<Array<{
    id: number;
    x: number;
    y: number;
    text: string;
    color: string;
  }>>([]);
  const [showShop, setShowShop] = useState(false);
  
  const floatingIdRef = useRef(0);
  const tickIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 添加飘字效果
  const addFloatingText = useCallback((x: number, y: number, text: string, color: string) => {
    const id = floatingIdRef.current++;
    setFloatingTexts(prev => [...prev, { id, x, y, text, color }]);
    setTimeout(() => {
      setFloatingTexts(prev => prev.filter(t => t.id !== id));
    }, 1000);
  }, []);

  // 作物生长 tick - 组件挂载时启动
  useEffect(() => {
    tickIntervalRef.current = setInterval(tick, 1000);
    return () => {
      if (tickIntervalRef.current) {
        clearInterval(tickIntervalRef.current);
      }
    };
  }, [tick]);

  // 获取种子数量
  const getSeedCount = (type: CropType) => {
    const seed = inventory.find(item => item.type === 'seed' && item.id === type);
    return seed?.quantity || 0;
  };

  // 处理地块点击
  const handlePlotClick = (x: number, y: number) => {
    const key = `${x},${y}`;
    const crop = crops[key];
    
    if (crop) {
      // 有作物，尝试收获
      if (crop.growthStage >= 3) {
        const result = harvestCrop(x, y);
        if (result) {
          addFloatingText(
            x * CELL_SIZE + CELL_SIZE / 2,
            y * CELL_SIZE + CELL_SIZE / 2,
            `+💰${result.money}`,
            '#C68E17'
          );
        }
      } else {
        // 浇水
        const success = waterCrop(x, y);
        if (success) {
          addFloatingText(
            x * CELL_SIZE + CELL_SIZE / 2,
            y * CELL_SIZE + CELL_SIZE / 2,
            '💧',
            '#3B82F6'
          );
        }
      }
    } else {
      // 空地，种植
      const success = plantCrop(x, y, selectedSeed);
      if (success) {
        addFloatingText(
          x * CELL_SIZE + CELL_SIZE / 2,
          y * CELL_SIZE + CELL_SIZE / 2,
          '🌱',
          '#22C55E'
        );
      } else {
        // 种子不足，显示提示
        addFloatingText(
          x * CELL_SIZE + CELL_SIZE / 2,
          y * CELL_SIZE + CELL_SIZE / 2,
          '种子不足!',
          '#EF4444'
        );
      }
    }
    setSelectedPlot({ x, y });
  };

  // 计算升级所需经验
  const expNeeded = farmLevel * 100;
  const expProgress = (farmExp / expNeeded) * 100;

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-100 to-emerald-100 p-4">
      {/* 顶部状态栏 */}
      <div className="max-w-4xl mx-auto mb-4">
        <div className="glass-card rounded-ios-xl p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="text-2xl">💰 {money}</div>
            <div className="text-sm text-gray-600">
              等级 {farmLevel} ({Math.floor(expProgress)}%)
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span>🌾 收获: {totalHarvested}</span>
            <button
              onClick={() => setShowShop(true)}
              className="px-4 py-2 bg-brand-500 text-white rounded-ios-lg hover:bg-brand-600 transition-colors"
            >
              🛒 商店
            </button>
          </div>
        </div>
      </div>

      {/* 种子选择器 */}
      <div className="max-w-4xl mx-auto mb-4">
        <div className="glass-card rounded-ios-xl p-3 flex gap-2 overflow-x-auto">
          {(Object.keys(CROP_CONFIG) as CropType[]).map(type => {
            const config = CROP_CONFIG[type];
            const count = getSeedCount(type);
            const isSelected = selectedSeed === type;
            
            return (
              <button
                key={type}
                onClick={() => setSelectedSeed(type)}
                className={`flex-shrink-0 px-4 py-2 rounded-ios-lg border-2 transition-all ${
                  isSelected
                    ? 'border-brand-500 bg-brand-50'
                    : 'border-transparent hover:bg-white/50'
                }`}
              >
                <div className="text-2xl">{config.emoji}</div>
                <div className="text-xs text-gray-600">{config.name}</div>
                <div className="text-xs text-brand-600">×{count}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 农场网格 */}
      <div className="max-w-4xl mx-auto">
        <div 
          className="relative mx-auto rounded-ios-xl overflow-hidden shadow-2xl"
          style={{
            width: FARM_WIDTH,
            height: FARM_HEIGHT,
            background: 'linear-gradient(135deg, #8B4513 0%, #A0522D 100%)',
          }}
        >
          {/* 网格线 */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => (
              <line
                key={`h-${i}`}
                x1="0"
                y1={i * CELL_SIZE}
                x2={FARM_WIDTH}
                y2={i * CELL_SIZE}
                stroke="rgba(0,0,0,0.2)"
                strokeWidth="1"
              />
            ))}
            {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => (
              <line
                key={`v-${i}`}
                x1={i * CELL_SIZE}
                y1="0"
                x2={i * CELL_SIZE}
                y2={FARM_HEIGHT}
                stroke="rgba(0,0,0,0.2)"
                strokeWidth="1"
              />
            ))}
          </svg>

          {/* 地块 */}
          {Array.from({ length: GRID_SIZE }).map((_, y) =>
            Array.from({ length: GRID_SIZE }).map((_, x) => {
              const key = `${x},${y}`;
              const crop = crops[key];
              const isSelected = selectedPlot?.x === x && selectedPlot?.y === y;
              
              return (
                <motion.button
                  key={key}
                  className={`absolute flex items-center justify-center transition-all ${
                    isSelected ? 'ring-4 ring-brand-400 ring-opacity-50' : ''
                  }`}
                  style={{
                    left: x * CELL_SIZE,
                    top: y * CELL_SIZE,
                    width: CELL_SIZE,
                    height: CELL_SIZE,
                  }}
                  onClick={() => handlePlotClick(x, y)}
                  whileHover={{ scale: 0.95 }}
                  whileTap={{ scale: 0.9 }}
                >
                  {/* 土壤背景 */}
                  <div 
                    className="absolute inset-2 rounded-lg"
                    style={{
                      background: crop
                        ? `linear-gradient(135deg, ${
                            crop.waterLevel > 0 ? '#4A3728' : '#6B4423'
                          } 0%, ${
                            crop.waterLevel > 0 ? '#5A4738' : '#8B6543'
                          } 100%)`
                        : 'linear-gradient(135deg, #8B7355 0%, #A08565 100%)',
                      boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.3)',
                    }}
                  />
                  
                  {/* 作物 */}
                  {crop && (
                    <motion.span 
                      className="relative text-3xl z-10"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: 'spring', stiffness: 300 }}
                    >
                      {getCropStageEmoji(crop.type, crop.growthStage)}
                    </motion.span>
                  )}
                  
                  {/* 水分指示器 */}
                  {crop && crop.waterLevel > 0 && (
                    <div className="absolute bottom-1 right-1 flex gap-0.5">
                      {Array.from({ length: crop.waterLevel }).map((_, i) => (
                        <span key={i} className="text-xs">💧</span>
                      ))}
                    </div>
                  )}
                  
                  {/* 可收获标记 */}
                  {crop && crop.growthStage >= 3 && (
                    <motion.div
                      className="absolute -top-1 -right-1 w-4 h-4 bg-yellow-400 rounded-full flex items-center justify-center"
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    >
                      <span className="text-xs">✨</span>
                    </motion.div>
                  )}
                </motion.button>
              );
            })
          )}

          {/* 飘字效果 */}
          <AnimatePresence>
            {floatingTexts.map(ft => (
              <motion.div
                key={ft.id}
                className="absolute text-lg font-bold pointer-events-none z-20"
                style={{
                  left: ft.x,
                  top: ft.y,
                  color: ft.color,
                }}
                initial={{ opacity: 1, y: 0 }}
                animate={{ opacity: 0, y: -40 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1 }}
              >
                {ft.text}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      {/* 操作提示 */}
      <div className="max-w-4xl mx-auto mt-4 text-center text-sm text-gray-600">
        <p>点击空地种植 {CROP_CONFIG[selectedSeed].emoji} {CROP_CONFIG[selectedSeed].name}</p>
        <p>点击作物浇水 💧 | 成熟后点击收获 💰</p>
      </div>

      {/* 商店弹窗 */}
      <AnimatePresence>
        {showShop && (
          <motion.div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowShop(false)}
          >
            <motion.div
              className="glass-modal rounded-ios-xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={e => e.stopPropagation()}
            >
              <h2 className="text-xl font-bold mb-4">🛒 种子商店</h2>
              <div className="space-y-3">
                {(Object.keys(CROP_CONFIG) as CropType[]).map(type => {
                  const config = CROP_CONFIG[type];
                  return (
                    <div
                      key={type}
                      className="flex items-center justify-between p-3 bg-white/50 rounded-ios-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{config.emoji}</span>
                        <div>
                          <div className="font-medium">{config.name}</div>
                          <div className="text-xs text-gray-500">
                            生长时间: {config.growthTime}秒 | 售价: 💰{config.sellPrice}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => buySeed(type, 1)}
                        disabled={money < config.seedPrice}
                        className="px-3 py-1 bg-brand-500 text-white rounded-ios-lg text-sm disabled:opacity-50"
                      >
                        💰{config.seedPrice}
                      </button>
                    </div>
                  );
                })}
              </div>
              <button
                onClick={() => setShowShop(false)}
                className="w-full mt-4 py-2 bg-gray-200 rounded-ios-lg hover:bg-gray-300 transition-colors"
              >
                关闭
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
