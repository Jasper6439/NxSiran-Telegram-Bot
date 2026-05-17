// ═══════════════════════════════════════════════════════════════════════════
// 校园页面 v1.9.5 - 完全独立的校园漫游游戏
// 与农场彻底解耦，独立生命周期
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCampusStore } from '../../stores/campusStore';
import { MAP_AREAS } from '../../stores/constants';
import type { DialogueType } from '../../stores/types';

// 世界物体表情映射
const WORLD_OBJECT_EMOJI: Record<string, string[]> = {
  tree: ['🌳', '🌲', '🎄'],
  bench: ['🪑'],
  lamp: ['🏮'],
  rock: ['🪨', '🗿'],
  mailbox: ['📮'],
  flower: ['🌸', '🌺', '🌻'],
  desk: ['🪑', '📚'],
  bookshelf: ['📚', '📖'],
  flag: ['🚩'],
  fence: ['🏗️'],
};

// 对话选项样式
const DIALOGUE_OPTION_STYLES: Record<DialogueType, { label: string; color: string; icon: string }> = {
  script: { label: '剧本', color: 'bg-gray-500/80 text-white', icon: '📜' },
  heart: { label: '真心', color: 'bg-pink-500/80 text-white', icon: '💗' },
  hidden: { label: '隐藏', color: 'bg-purple-600/80 text-white', icon: '✨' },
};

export default function CampusPage() {
  // 使用独立的 campusStore
  const {
    player,
    characters,
    worldObjects,
    worldZone,
    collapseEnergy,
    showDialogue,
    activeCharacterId,
    selectedDialogueType,
    movePlayer,
    setPlayerMoving,
    shiftWorldZone,
    interactWithCharacter,
    closeDialogue,
    selectDialogueOption,
    updateCharacters,
  } = useCampusStore();

  // 本地状态
  const [keys, setKeys] = useState({ up: false, down: false, left: false, right: false });
  const [currentArea, setCurrentArea] = useState<string>('');
  const [dialogueStep, setDialogueStep] = useState<'choose' | 'result'>('choose');
  
  const containerRef = useRef<HTMLDivElement>(null);
  const moveIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const charUpdateIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 键盘控制
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if (key === 'w' || key === 'arrowup') setKeys(k => ({ ...k, up: true }));
      if (key === 's' || key === 'arrowdown') setKeys(k => ({ ...k, down: true }));
      if (key === 'a' || key === 'arrowleft') setKeys(k => ({ ...k, left: true }));
      if (key === 'd' || key === 'arrowright') setKeys(k => ({ ...k, right: true }));
      if (key === 'e') handleInteract();
      if (key === 'escape' && showDialogue) closeDialogue();
    };
    
    const handleKeyUp = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if (key === 'w' || key === 'arrowup') setKeys(k => ({ ...k, up: false }));
      if (key === 's' || key === 'arrowdown') setKeys(k => ({ ...k, down: false }));
      if (key === 'a' || key === 'arrowleft') setKeys(k => ({ ...k, left: false }));
      if (key === 'd' || key === 'arrowright') setKeys(k => ({ ...k, right: false }));
    };
    
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [showDialogue, closeDialogue]);

  // 移动循环
  useEffect(() => {
    moveIntervalRef.current = setInterval(() => {
      let dx = 0, dy = 0;
      if (keys.up) dy = -1;
      if (keys.down) dy = 1;
      if (keys.left) dx = -1;
      if (keys.right) dx = 1;
      if (dx !== 0 || dy !== 0) {
        movePlayer(dx, dy);
      } else {
        setPlayerMoving(false);
      }
    }, 16);
    
    return () => {
      if (moveIntervalRef.current) {
        clearInterval(moveIntervalRef.current);
      }
    };
  }, [keys, movePlayer, setPlayerMoving]);

  // 角色闲逛更新
  useEffect(() => {
    charUpdateIntervalRef.current = setInterval(updateCharacters, 1000);
    return () => {
      if (charUpdateIntervalRef.current) {
        clearInterval(charUpdateIntervalRef.current);
      }
    };
  }, [updateCharacters]);

  // 检测当前区域
  useEffect(() => {
    for (const area of Object.values(MAP_AREAS)) {
      if (
        player.x >= area.x &&
        player.x <= area.x + area.width &&
        player.y >= area.y &&
        player.y <= area.y + area.height
      ) {
        setCurrentArea(area.label);
        return;
      }
    }
    setCurrentArea('');
  }, [player.x, player.y]);

  // 对话打开时重置步骤
  useEffect(() => {
    if (showDialogue) setDialogueStep('choose');
  }, [showDialogue]);

  // 互动处理
  const handleInteract = useCallback(() => {
    if (showDialogue) return;
    
    // 检查附近角色
    const nearbyChar = characters.find(char => {
      const dx = char.x - player.x;
      const dy = char.y - player.y;
      return Math.sqrt(dx * dx + dy * dy) < 60;
    });
    
    if (nearbyChar) {
      interactWithCharacter(nearbyChar.id);
    }
  }, [player, characters, showDialogue, interactWithCharacter]);

  // 选择对话选项
  const handleSelectOption = (type: DialogueType) => {
    selectDialogueOption(type);
    setDialogueStep('result');
  };

  // 关闭对话
  const handleCloseDialogue = () => {
    closeDialogue();
    setDialogueStep('choose');
  };

  // 当前对话的角色
  const activeChar = activeCharacterId
    ? characters.find(c => c.id === activeCharacterId)
    : undefined;

  // 当前对话
  const currentDialogue = activeChar
    ? activeChar.dialogues[activeChar.currentDialogueIndex]
    : null;

  // 获取可用对话选项
  const availableDialogues = activeChar
    ? activeChar.dialogues.filter(d => d.type !== 'hidden' || activeChar.awakening > 50)
    : [];

  const isCollapse = worldZone === 'collapse';

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-screen overflow-hidden transition-colors duration-700 ${
        isCollapse
          ? 'bg-gradient-to-b from-purple-900 via-indigo-900 to-slate-900'
          : 'bg-gradient-to-b from-brand-200 to-brand-400'
      }`}
    >
      {/* 地图背景 */}
      <div className="absolute inset-0">
        {/* 区域纹理 */}
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: isCollapse
              ? 'radial-gradient(circle at 30% 40%, #7C3AED 0%, transparent 50%), radial-gradient(circle at 70% 60%, #4F46E5 0%, transparent 50%)'
              : 'radial-gradient(circle at 20% 30%, #95D5B2 0%, transparent 50%), radial-gradient(circle at 80% 70%, #B8E0D2 0%, transparent 50%)',
          }}
        />

        {/* 崩坏区特效 */}
        {isCollapse && (
          <div className="absolute inset-0 pointer-events-none">
            {Array.from({ length: 8 }).map((_, i) => (
              <motion.div
                key={i}
                className="absolute w-1 h-1 rounded-full bg-purple-400"
                style={{ left: `${10 + i * 12}%`, top: `${5 + (i % 3) * 30}%` }}
                animate={{ opacity: [0, 1, 0], scale: [0.5, 1.5, 0.5] }}
                transition={{ duration: 2 + i * 0.3, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </div>
        )}

        {/* 区域标签 */}
        {Object.entries(MAP_AREAS).map(([key, area]) => (
          <div
            key={key}
            className={`absolute border-2 border-dashed rounded-lg flex items-center justify-center transition-colors duration-500 ${
              isCollapse ? 'border-purple-400/40' : 'border-white/30'
            }`}
            style={{
              left: area.x,
              top: area.y,
              width: area.width,
              height: area.height,
            }}
          >
            <span className={`text-sm font-medium ${isCollapse ? 'text-purple-300/60' : 'text-white/50'}`}>
              {area.emoji} {area.label}
            </span>
          </div>
        ))}
      </div>

      {/* 世界物体 */}
      {worldObjects.map(obj => {
        const emojis = WORLD_OBJECT_EMOJI[obj.type] || ['❓'];
        const emoji = emojis[obj.variant % emojis.length];
        return (
          <motion.div
            key={obj.id}
            className="absolute text-3xl pointer-events-none"
            style={{ left: obj.x, top: obj.y }}
            animate={obj.type === 'tree' ? { rotate: [0, 2, -2, 0] } : undefined}
            transition={obj.type === 'tree' ? { duration: 4, repeat: Infinity, ease: 'easeInOut' } : undefined}
          >
            {emoji}
          </motion.div>
        );
      })}

      {/* 角色 */}
      {characters.map(char => (
        <motion.div
          key={char.id}
          className="absolute flex flex-col items-center"
          animate={{ x: char.x, y: char.y }}
          transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        >
          <span className="text-3xl">{char.emoji}</span>
          <span className={`text-xs px-1 rounded mt-1 whitespace-nowrap ${
            isCollapse ? 'text-purple-200 bg-purple-900/70' : 'text-white bg-black/50'
          }`}>
            {char.name}
          </span>
          {char.awakening > 0 && (
            <div className="flex gap-0.5 mt-0.5">
              {Array.from({ length: Math.min(5, Math.ceil(char.awakening / 20)) }).map((_, i) => (
                <span key={i} className="text-[8px]">✨</span>
              ))}
            </div>
          )}
        </motion.div>
      ))}

      {/* 玩家 */}
      <motion.div
        className="absolute flex flex-col items-center z-20"
        animate={{ x: player.x, y: player.y }}
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
      >
        <div className="relative">
          <span className="text-4xl">🧑‍🎨</span>
          {player.isMoving && (
            <motion.div
              className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-3 h-1 bg-black/30 rounded-full"
              animate={{ scaleX: [1, 1.3, 1] }}
              transition={{ duration: 0.2, repeat: Infinity }}
            />
          )}
        </div>
      </motion.div>

      {/* HUD - 顶部 */}
      <div className="absolute top-4 left-4 right-4 flex justify-between items-start pointer-events-none z-10">
        <div className={`px-3 py-2 rounded-ios-lg flex items-center gap-3 pointer-events-auto ${
          isCollapse ? 'bg-purple-900/70 backdrop-blur-md' : 'glass-card'
        }`}>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            isCollapse ? 'bg-purple-500/50 text-purple-200' : 'bg-indigo-100 text-indigo-700'
          }`}>
            ⚡ {collapseEnergy}
          </span>
        </div>

        <div className="flex flex-col items-end gap-1">
          {currentArea && (
            <div className={`px-3 py-2 rounded-ios-lg pointer-events-auto ${
              isCollapse ? 'bg-purple-900/70 backdrop-blur-md' : 'glass-card'
            }`}>
              <span className={`text-sm ${isCollapse ? 'text-purple-200' : 'text-gray-700'}`}>
                {currentArea}
              </span>
            </div>
          )}
          <button
            onClick={shiftWorldZone}
            className={`px-3 py-1 rounded-full text-xs font-bold pointer-events-auto transition-all ${
              isCollapse
                ? 'bg-purple-500/80 text-white animate-pulse'
                : 'bg-white/70 text-gray-600 hover:bg-white'
            }`}
          >
            {isCollapse ? '🌀 崩坏区' : '📖 剧本区'}
          </button>
        </div>
      </div>

      {/* 操作提示 */}
      <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end pointer-events-none z-10">
        <div className={`px-3 py-2 rounded-ios-lg text-xs pointer-events-auto ${
          isCollapse ? 'bg-purple-900/70 backdrop-blur-md text-purple-200' : 'glass-card text-gray-600'
        }`}>
          <p>WASD/方向键 移动</p>
          <p>E 互动 | ESC 关闭</p>
        </div>

        {(() => {
          const nearby = characters.find(char => {
            const dx = char.x - player.x;
            const dy = char.y - player.y;
            return Math.sqrt(dx * dx + dy * dy) < 60;
          });
          return nearby ? (
            <div className={`px-3 py-2 rounded-ios-lg text-sm pointer-events-auto ${
              isCollapse ? 'bg-purple-900/70 backdrop-blur-md text-purple-200' : 'glass-card'
            }`}>
              按 E 与 {nearby.emoji} {nearby.name} 对话
            </div>
          ) : null;
        })()}
      </div>

      {/* 对话框 */}
      <AnimatePresence>
        {showDialogue && activeChar && (
          <motion.div
            className="absolute inset-x-4 bottom-20 z-30"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
          >
            <div className={`p-4 rounded-ios-xl backdrop-blur-xl ${
              isCollapse
                ? 'bg-purple-900/90 border border-purple-500/30'
                : 'glass-modal'
            }`}>
              {/* 角色信息头 */}
              <div className="flex items-start gap-3 mb-3">
                <span className="text-4xl">{activeChar.emoji}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className={`font-bold ${isCollapse ? 'text-purple-100' : 'text-gray-800'}`}>
                      {activeChar.fullName}
                    </h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      isCollapse ? 'bg-purple-700/50 text-purple-200' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {activeChar.title}
                    </span>
                  </div>
                  <div className="flex gap-3 mt-1">
                    <span className="text-xs text-pink-400">
                      💗 {activeChar.heartLevel}/10
                    </span>
                    <span className="text-xs text-purple-400">
                      ✨ {activeChar.awakening}/100
                    </span>
                    <span className="text-xs text-gray-400">
                      📜 命运 {activeChar.destiny}%
                    </span>
                  </div>
                </div>
              </div>

              {/* 对话内容 */}
              {dialogueStep === 'choose' ? (
                <>
                  <p className={`text-sm mb-3 ${isCollapse ? 'text-purple-200' : 'text-gray-500'}`}>
                    选择对话方式：
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => handleSelectOption('script')}
                      className={`py-3 px-2 rounded-ios-lg text-center transition-all ${DIALOGUE_OPTION_STYLES.script.color} hover:scale-105 active:scale-95`}
                    >
                      <span className="text-lg">{DIALOGUE_OPTION_STYLES.script.icon}</span>
                      <p className="text-xs mt-1">{DIALOGUE_OPTION_STYLES.script.label}</p>
                    </button>
                    <button
                      onClick={() => handleSelectOption('heart')}
                      className={`py-3 px-2 rounded-ios-lg text-center transition-all ${DIALOGUE_OPTION_STYLES.heart.color} hover:scale-105 active:scale-95`}
                    >
                      <span className="text-lg">{DIALOGUE_OPTION_STYLES.heart.icon}</span>
                      <p className="text-xs mt-1">{DIALOGUE_OPTION_STYLES.heart.label}</p>
                    </button>
                    <button
                      onClick={() => handleSelectOption('hidden')}
                      disabled={activeChar.awakening <= 50}
                      className={`py-3 px-2 rounded-ios-lg text-center transition-all ${
                        activeChar.awakening > 50
                          ? `${DIALOGUE_OPTION_STYLES.hidden.color} hover:scale-105 active:scale-95`
                          : 'bg-gray-300/50 text-gray-400 cursor-not-allowed'
                      }`}
                    >
                      <span className="text-lg">{DIALOGUE_OPTION_STYLES.hidden.icon}</span>
                      <p className="text-xs mt-1">{DIALOGUE_OPTION_STYLES.hidden.label}</p>
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className={`p-3 rounded-ios-lg mb-3 ${
                    selectedDialogueType === 'hidden'
                      ? 'bg-purple-500/20 border border-purple-400/30'
                      : selectedDialogueType === 'heart'
                        ? 'bg-pink-500/20 border border-pink-400/30'
                        : 'bg-gray-500/10 border border-gray-400/20'
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs">{DIALOGUE_OPTION_STYLES[selectedDialogueType || 'script'].icon}</span>
                      <span className={`text-xs font-medium ${
                        selectedDialogueType === 'hidden' ? 'text-purple-300' :
                        selectedDialogueType === 'heart' ? 'text-pink-300' : 'text-gray-400'
                      }`}>
                        {DIALOGUE_OPTION_STYLES[selectedDialogueType || 'script'].label}选项
                      </span>
                    </div>
                    <p className={`text-sm leading-relaxed ${isCollapse ? 'text-purple-100' : 'text-gray-700'}`}>
                      {currentDialogue?.text || '...'}
                    </p>
                  </div>

                  {(currentDialogue?.heartGain || currentDialogue?.awakeningGain) && (
                    <div className="flex gap-2 mb-3 text-xs">
                      {currentDialogue.heartGain && currentDialogue.heartGain > 0 && (
                        <span className="bg-pink-500/20 text-pink-300 px-2 py-1 rounded-full">
                          💗 +{currentDialogue.heartGain}
                        </span>
                      )}
                      {currentDialogue.awakeningGain && currentDialogue.awakeningGain > 0 && (
                        <span className="bg-purple-500/20 text-purple-300 px-2 py-1 rounded-full">
                          ✨ +{currentDialogue.awakeningGain}
                        </span>
                      )}
                    </div>
                  )}

                  <button
                    onClick={handleCloseDialogue}
                    className={`w-full py-2 rounded-ios-lg font-medium transition-all ${
                      isCollapse
                        ? 'bg-purple-600 text-white hover:bg-purple-500'
                        : 'bg-brand-500 text-white hover:bg-brand-600'
                    }`}
                  >
                    继续
                  </button>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
