// ═══════════════════════════════════════════════════════════════════════════
// 恋爱至上主义区域 v1.6.0 - 类型定义
// 漫画世界觉醒 RPG 架构
// ═══════════════════════════════════════════════════════════════════════════

// ─── 基础类型 ───────────────────────────────────────────────────────────────
export type CropType = 'tomato' | 'carrot' | 'corn' | 'wheat' | 'potato' | 'strawberry';
export type ItemType = 'seed' | 'crop' | 'tool' | 'gift';
export type GameMode = 'manage' | 'roam';
export type WorldZone = 'script' | 'collapse'; // 剧本区 / 崩坏区
export type DialogueType = 'script' | 'heart' | 'hidden'; // 剧本选项 / 真心选项 / 隐藏选项

// ─── 作物数据 ───────────────────────────────────────────────────────────────
export interface CropData {
  id: string;
  type: CropType;
  plantedAt: number;
  growthStage: 0 | 1 | 2 | 3;
  waterLevel: number;
}

// ─── 背包物品 ───────────────────────────────────────────────────────────────
export interface InventoryItem {
  type: ItemType;
  id: string;
  quantity: number;
}

// ─── 玩家数据（漫游模式）───────────────────────────────────────────────────
export interface PlayerData {
  x: number;
  y: number;
  direction: 'up' | 'down' | 'left' | 'right';
  speed: number;
  isMoving: boolean;
}

// ─── 角色数据（GDD 定义）───────────────────────────────────────────────────
export interface CharacterData {
  id: string;
  name: string;
  emoji: string;
  fullName: string;       // 全名
  title: string;          // 头衔/身份
  x: number;
  y: number;
  targetX?: number;       // 移动目标 X（闲逛用）
  targetY?: number;       // 移动目标 Y（闲逛用）
  // 关系系统
  heartLevel: number;     // 心级 0-10
  awakening: number;      // 觉醒值 0-100
  destiny: number;        // 命运力 0-100（剧本控制强度）
  // 对话
  dialogues: DialogueEntry[];
  currentDialogueIndex: number;
  // 行为
  mood: 'happy' | 'neutral' | 'sad' | 'awakening';
  wanderArea: { x: number; y: number; width: number; height: number };
  wanderTarget?: { x: number; y: number };
  lastWanderTime: number;
  // 日程
  schedule: Record<string, { x: number; y: number; activity: string }>;
  // 喜好
  likedGifts: string[];
  dislikedGifts: string[];
}

export interface DialogueEntry {
  text: string;
  type: DialogueType;
  awakeningGain?: number;  // 觉醒值变化
  heartGain?: number;      // 心级变化
  condition?: string;      // 触发条件描述
}

// ─── 世界物体 ───────────────────────────────────────────────────────────────
export interface WorldObject {
  id: string;
  type: 'tree' | 'bench' | 'lamp' | 'rock' | 'mailbox' | 'flower' | 'desk' | 'bookshelf' | 'flag' | 'fence';
  x: number;
  y: number;
  variant: number;
}

// ─── 崩坏事件 ───────────────────────────────────────────────────────────────
export interface CollapseEvent {
  id: string;
  type: 'time_accel' | 'space_fold' | 'memory_surge' | 'emotion_resonance';
  description: string;
  risk: number;           // 风险概率 0-1
  reward: string;         // 奖励描述
}
