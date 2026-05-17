// ═══════════════════════════════════════════════════════════════════════════
// 农场 Store v1.9.5 - 完全独立状态管理
// 与校园漫游彻底解耦，独立命名空间
// ═══════════════════════════════════════════════════════════════════════════
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CropType, CropData, InventoryItem } from './types';
import { CROP_CONFIG } from './constants';

// ═══════════════════════════════════════════════════════════════════════════
// 类型定义
// ═══════════════════════════════════════════════════════════════════════════
export interface FarmState {
  // 农场数据
  crops: Record<string, CropData>;
  inventory: InventoryItem[];
  money: number;
  totalHarvested: number;
  
  // 游戏配置
  farmLevel: number;
  farmExp: number;
  
  // 操作
  plantCrop: (x: number, y: number, type: CropType) => boolean;
  harvestCrop: (x: number, y: number) => { type: CropType; money: number } | null;
  waterCrop: (x: number, y: number) => boolean;
  buySeed: (type: CropType, quantity: number) => boolean;
  sellCrop: (type: CropType, quantity: number) => boolean;
  tick: () => void;
  
  // 清理
  resetFarm: () => void;
}

// ═══════════════════════════════════════════════════════════════════════════
// 辅助函数
// ═══════════════════════════════════════════════════════════════════════════
export function getCropStageEmoji(type: CropType, stage: number): string {
  if (stage === 0) return '🌱';
  if (stage === 1) return '🌿';
  if (stage === 2) return '🌾';
  return CROP_CONFIG[type]?.emoji || '🌾';
}

// ═══════════════════════════════════════════════════════════════════════════
// Store 实现
// ═══════════════════════════════════════════════════════════════════════════
const initialState = {
  crops: {},
  inventory: [
    { type: 'seed' as const, id: 'wheat', quantity: 5 },
    { type: 'seed' as const, id: 'corn', quantity: 3 },
  ],
  money: 100,
  totalHarvested: 0,
  farmLevel: 1,
  farmExp: 0,
};

export const useFarmStore = create<FarmState>()(
  persist(
    (set, get) => ({
      ...initialState,

      // 种植作物
      plantCrop: (x, y, type) => {
        const key = `${x},${y}`;
        const state = get();
        const seedItem = state.inventory.find(
          item => item.type === 'seed' && item.id === type
        );
        
        if (!seedItem || seedItem.quantity < 1) return false;
        if (state.crops[key]) return false;

        set(state => ({
          crops: {
            ...state.crops,
            [key]: {
              id: `${type}_${Date.now()}`,
              type,
              plantedAt: Date.now(),
              growthStage: 0,
              waterLevel: 0,
            },
          },
          inventory: state.inventory.map(item =>
            item.type === 'seed' && item.id === type
              ? { ...item, quantity: item.quantity - 1 }
              : item
          ),
        }));
        return true;
      },

      // 收获作物
      harvestCrop: (x, y) => {
        const key = `${x},${y}`;
        const state = get();
        const crop = state.crops[key];
        
        if (!crop || crop.growthStage < 3) return null;
        
        const config = CROP_CONFIG[crop.type];
        const earnedMoney = config.sellPrice;
        const expGain = config.growthTime / 10;

        set(state => {
          const newCrops = { ...state.crops };
          delete newCrops[key];
          
          // 升级检查
          let newLevel = state.farmLevel;
          let newExp = state.farmExp + expGain;
          const expNeeded = state.farmLevel * 100;
          if (newExp >= expNeeded) {
            newLevel++;
            newExp -= expNeeded;
          }
          
          return {
            crops: newCrops,
            money: state.money + earnedMoney,
            totalHarvested: state.totalHarvested + 1,
            farmExp: newExp,
            farmLevel: newLevel,
          };
        });
        
        return { type: crop.type, money: earnedMoney };
      },

      // 浇水
      waterCrop: (x, y) => {
        const key = `${x},${y}`;
        const state = get();
        const crop = state.crops[key];
        
        if (!crop || crop.waterLevel >= 3) return false;
        
        set(state => ({
          crops: {
            ...state.crops,
            [key]: { ...crop, waterLevel: crop.waterLevel + 1 },
          },
        }));
        return true;
      },

      // 购买种子
      buySeed: (type, quantity) => {
        const state = get();
        const config = CROP_CONFIG[type];
        const totalPrice = config.seedPrice * quantity;
        
        if (state.money < totalPrice) return false;
        
        set(state => {
          const existingSeed = state.inventory.find(
            item => item.type === 'seed' && item.id === type
          );
          return {
            money: state.money - totalPrice,
            inventory: existingSeed
              ? state.inventory.map(item =>
                  item.type === 'seed' && item.id === type
                    ? { ...item, quantity: item.quantity + quantity }
                    : item
                )
              : [...state.inventory, { type: 'seed', id: type, quantity }],
          };
        });
        return true;
      },

      // 出售作物
      sellCrop: (type, quantity) => {
        const state = get();
        const config = CROP_CONFIG[type];
        const totalPrice = config.sellPrice * quantity;
        const cropItem = state.inventory.find(
          item => item.type === 'crop' && item.id === type
        );
        
        if (!cropItem || cropItem.quantity < quantity) return false;
        
        set(state => ({
          money: state.money + totalPrice,
          inventory: state.inventory
            .map(item =>
              item.type === 'crop' && item.id === type
                ? { ...item, quantity: item.quantity - quantity }
                : item
            )
            .filter(item => item.quantity > 0),
        }));
        return true;
      },

      // 作物生长 tick
      tick: () => {
        const now = Date.now();
        set(state => {
          const newCrops = { ...state.crops };
          let hasChanges = false;
          
          for (const key in newCrops) {
            const crop = newCrops[key];
            const config = CROP_CONFIG[crop.type];
            const elapsed = (now - crop.plantedAt) / 1000;
            const progress = elapsed / config.growthTime;
            
            let newStage: 0 | 1 | 2 | 3 = 0;
            if (progress >= 1) newStage = 3;
            else if (progress >= 0.6) newStage = 2;
            else if (progress >= 0.2) newStage = 1;
            
            if (newStage !== crop.growthStage) {
              newCrops[key] = { ...crop, growthStage: newStage };
              hasChanges = true;
            }
          }
          
          return hasChanges ? { crops: newCrops } : state;
        });
      },

      // 重置农场
      resetFarm: () => set(initialState),
    }),
    {
      name: 'lovesupremacy-farm-storage',
      partialize: state => ({
        crops: state.crops,
        inventory: state.inventory,
        money: state.money,
        totalHarvested: state.totalHarvested,
        farmLevel: state.farmLevel,
        farmExp: state.farmExp,
      }),
    }
  )
);

// 导出类型
export type { CropType, CropData, InventoryItem } from './types';
