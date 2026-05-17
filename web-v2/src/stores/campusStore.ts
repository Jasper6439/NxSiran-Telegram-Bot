// ═══════════════════════════════════════════════════════════════════════════
// 校园 Store v1.9.5 - 完全独立状态管理
// 与农场彻底解耦，独立命名空间
// ═══════════════════════════════════════════════════════════════════════════
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CharacterData, WorldZone, DialogueType } from './types';

// ═══════════════════════════════════════════════════════════════════════════
// 类型定义
// ═══════════════════════════════════════════════════════════════════════════
export interface CampusState {
  // 玩家状态
  player: {
    x: number;
    y: number;
    direction: 'up' | 'down' | 'left' | 'right';
    isMoving: boolean;
  };
  
  // 世界状态
  worldZone: WorldZone;
  collapseEnergy: number;
  
  // NPC
  characters: CharacterData[];
  activeCharacterId: string | null;
  
  // 对话
  showDialogue: boolean;
  selectedDialogueType: DialogueType | null;
  
  // 世界物体
  worldObjects: Array<{
    id: string;
    type: string;
    x: number;
    y: number;
    variant: number;
  }>;
  
  // 操作
  movePlayer: (dx: number, dy: number) => void;
  setPlayerDirection: (direction: 'up' | 'down' | 'left' | 'right') => void;
  setPlayerMoving: (isMoving: boolean) => void;
  shiftWorldZone: () => void;
  interactWithCharacter: (characterId: string) => void;
  closeDialogue: () => void;
  selectDialogueOption: (type: DialogueType) => void;
  updateCharacters: () => void;
  
  // 清理
  resetCampus: () => void;
}

// ═══════════════════════════════════════════════════════════════════════════
// 初始角色数据
// ═══════════════════════════════════════════════════════════════════════════
const initialCharacters: CharacterData[] = [
  {
    id: 'chayewoon',
    name: '车如云',
    fullName: '车如云 (Cha Ye-woon)',
    emoji: '🧑‍🎨',
    title: '傲娇男主角',
    x: 200,
    y: 200,
    targetX: 200,
    targetY: 200,
    heartLevel: 0,
    awakening: 0,
    destiny: 50,
    currentDialogueIndex: 0,
    dialogues: [
      { text: '哼，别靠我太近。', type: 'script', heartGain: 0, awakeningGain: 0 },
      { text: '你...你这个人真是的。', type: 'heart', heartGain: 1, awakeningGain: 0 },
    ],
  },
  {
    id: 'taemyung',
    name: '泰明',
    fullName: '泰明 (Tae Myung)',
    emoji: '🧑‍💼',
    title: '学生会会长',
    x: 400,
    y: 300,
    targetX: 400,
    targetY: 300,
    heartLevel: 0,
    awakening: 0,
    destiny: 50,
    currentDialogueIndex: 0,
    dialogues: [
      { text: '欢迎来到学生会。', type: 'script', heartGain: 0, awakeningGain: 0 },
    ],
  },
];

// ═══════════════════════════════════════════════════════════════════════════
// 初始世界物体
// ═══════════════════════════════════════════════════════════════════════════
const initialWorldObjects = [
  { id: 'tree1', type: 'tree', x: 100, y: 100, variant: 0 },
  { id: 'tree2', type: 'tree', x: 500, y: 150, variant: 1 },
  { id: 'bench1', type: 'bench', x: 300, y: 400, variant: 0 },
  { id: 'lamp1', type: 'lamp', x: 250, y: 250, variant: 0 },
];

// ═══════════════════════════════════════════════════════════════════════════
// Store 实现
// ═══════════════════════════════════════════════════════════════════════════
const initialState = {
  player: {
    x: 300,
    y: 300,
    direction: 'down' as const,
    isMoving: false,
  },
  worldZone: 'script' as WorldZone,
  collapseEnergy: 0,
  characters: initialCharacters,
  activeCharacterId: null,
  showDialogue: false,
  selectedDialogueType: null as DialogueType | null,
  worldObjects: initialWorldObjects,
};

export const useCampusStore = create<CampusState>()(
  persist(
    (set, get) => ({
      ...initialState,

      // 移动玩家
      movePlayer: (dx, dy) => {
        const { player, worldZone } = get();
        const speed = 5;
        const newX = Math.max(20, Math.min(580, player.x + dx * speed));
        const newY = Math.max(20, Math.min(480, player.y + dy * speed));
        
        let newDirection = player.direction;
        if (dx > 0) newDirection = 'right';
        else if (dx < 0) newDirection = 'left';
        else if (dy > 0) newDirection = 'down';
        else if (dy < 0) newDirection = 'up';
        
        set({
          player: {
            ...player,
            x: newX,
            y: newY,
            direction: newDirection,
            isMoving: dx !== 0 || dy !== 0,
          },
        });
      },

      // 设置方向
      setPlayerDirection: (direction) => {
        set(state => ({
          player: { ...state.player, direction },
        }));
      },

      // 设置移动状态
      setPlayerMoving: (isMoving) => {
        set(state => ({
          player: { ...state.player, isMoving },
        }));
      },

      // 切换世界区域
      shiftWorldZone: () => {
        set(state => ({
          worldZone: state.worldZone === 'script' ? 'collapse' : 'script',
        }));
      },

      // 与角色互动
      interactWithCharacter: (characterId) => {
        set({
          activeCharacterId: characterId,
          showDialogue: true,
          selectedDialogueType: null,
        });
      },

      // 关闭对话
      closeDialogue: () => {
        set({
          showDialogue: false,
          activeCharacterId: null,
          selectedDialogueType: null,
        });
      },

      // 选择对话选项
      selectDialogueOption: (type) => {
        const { characters, activeCharacterId } = get();
        if (!activeCharacterId) return;
        
        const charIndex = characters.findIndex(c => c.id === activeCharacterId);
        if (charIndex === -1) return;
        
        const char = characters[charIndex];
        const dialogue = char.dialogues[char.currentDialogueIndex];
        
        if (!dialogue) return;
        
        // 更新角色状态
        const newCharacters = [...characters];
        newCharacters[charIndex] = {
          ...char,
          heartLevel: Math.min(10, char.heartLevel + (dialogue.heartGain || 0)),
          awakening: Math.min(100, char.awakening + (dialogue.awakeningGain || 0)),
          currentDialogueIndex: (char.currentDialogueIndex + 1) % char.dialogues.length,
        };
        
        set({
          characters: newCharacters,
          selectedDialogueType: type,
        });
      },

      // 更新角色位置（闲逛）
      updateCharacters: () => {
        set(state => {
          const newCharacters = state.characters.map(char => {
            // 有目标时向目标移动
            if (char.targetX !== undefined && char.targetY !== undefined) {
              const dx = char.targetX - char.x;
              const dy = char.targetY - char.y;
              const distance = Math.sqrt(dx * dx + dy * dy);
              
              if (distance > 2) {
                const speed = 1;
                return {
                  ...char,
                  x: char.x + (dx / distance) * speed,
                  y: char.y + (dy / distance) * speed,
                };
              } else {
                // 到达目标，设置新目标
                return {
                  ...char,
                  targetX: 50 + Math.random() * 500,
                  targetY: 50 + Math.random() * 400,
                };
              }
            }
            return char;
          });
          
          return { characters: newCharacters };
        });
      },

      // 重置校园
      resetCampus: () => set(initialState),
    }),
    {
      name: 'lovesupremacy-campus-storage',
      partialize: state => ({
        player: state.player,
        worldZone: state.worldZone,
        collapseEnergy: state.collapseEnergy,
        characters: state.characters,
      }),
    }
  )
);

// 导出类型
export type { CharacterData, WorldZone, DialogueType } from './types';
