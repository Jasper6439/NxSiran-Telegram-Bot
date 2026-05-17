// ═══════════════════════════════════════════════════════════════════════════
// 恋爱至上主义区域 v1.6.0 - 角色 Store Slice
// 角色系统：更新、送礼、附近检测、可用对话
// ═══════════════════════════════════════════════════════════════════════════
import type { CharacterData, DialogueEntry, InventoryItem } from './types';

// ─── 角色 Slice 状态 ───────────────────────────────────────────────────────
export interface CharacterSlice {
  characters: CharacterData[];

  // 角色操作
  updateCharacters: () => void;
  giveGift: (charId: string, giftId: string) => boolean;
}

// ─── 辅助函数 ───────────────────────────────────────────────────────────────
export function getNearbyCharacter(
  player: { x: number; y: number },
  characters: CharacterData[],
  distance = 50
): CharacterData | null {
  for (const char of characters) {
    const dx = Math.abs(player.x - char.x);
    const dy = Math.abs(player.y - char.y);
    if (dx < distance && dy < distance) return char;
  }
  return null;
}

export function getAvailableDialogues(char: CharacterData): DialogueEntry[] {
  return char.dialogues.filter(d => {
    if (!d.condition) return true;
    if (d.condition.includes('觉醒值>30') && char.awakening <= 30) return false;
    if (d.condition.includes('觉醒值>40') && char.awakening <= 40) return false;
    if (d.condition.includes('觉醒值>60') && char.awakening <= 60) return false;
    if (d.condition.includes('所有角色觉醒值>50')) return true; // 简化处理
    return true;
  });
}

// ─── 合并后的完整状态类型（供 slice 内部使用）──────────────────────────────
export interface CharacterFullState extends CharacterSlice {
  inventory: InventoryItem[];
}

export const createCharacterSlice = (
  set: (fn: (s: CharacterFullState) => Partial<CharacterFullState>) => void,
  get: () => CharacterFullState
): CharacterSlice => ({
  characters: [],

  updateCharacters: () => {
    const now = Date.now();
    set(state => ({
      characters: state.characters.map(char => {
        if (!char.lastWanderTime || now - char.lastWanderTime < 5000) return char;
        const area = char.wanderArea;
        const areaX = area?.x ?? 0;
        const areaY = area?.y ?? 0;
        const areaW = area?.width ?? 600;
        const areaH = area?.height ?? 500;
        const newX = Math.max(areaX, Math.min(areaX + areaW, char.x + (Math.random() - 0.5) * 80));
        const newY = Math.max(areaY, Math.min(areaY + areaH, char.y + (Math.random() - 0.5) * 60));
        return { ...char, x: newX, y: newY, lastWanderTime: now };
      }),
    }));
  },

  giveGift: (charId, giftId) => {
    const state = get();
    const char = state.characters.find(c => c.id === charId);
    if (!char) return false;
    const giftItem = state.inventory.find(item => item.id === giftId && (item.type === 'crop' || item.type === 'gift'));
    if (!giftItem || giftItem.quantity < 1) return false;

    const isLiked = (char.likedGifts ?? []).includes(giftId);
    const isDisliked = (char.dislikedGifts ?? []).includes(giftId);
    const heartChange = isLiked ? 3 : isDisliked ? -2 : 1;
    const awakeningChange = isLiked ? 2 : 0;

    set(state => ({
      inventory: state.inventory.map(item =>
        item.id === giftId && (item.type === 'crop' || item.type === 'gift')
          ? { ...item, quantity: item.quantity - 1 }
          : item
      ).filter(item => item.quantity > 0),
      characters: state.characters.map(c =>
        c.id === charId
          ? { ...c, heartLevel: Math.max(0, Math.min(10, c.heartLevel + heartChange)), awakening: Math.min(100, c.awakening + awakeningChange) }
          : c
      ),
    }));
    return true;
  },
});
