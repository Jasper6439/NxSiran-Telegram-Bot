// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - Action Page (横版动作页面)
// Full-screen Phaser game with floating React overlay
// ═══════════════════════════════════════════════════════════════════════════
import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorldStore } from '../../../stores/worldStore';
import { useActionGame } from './useActionGame';

export default function ActionPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const isAwakened = useWorldStore((s: any) => s.isAwakened);
  const awakeningLevel = useWorldStore((s: any) => s.awakeningLevel);
  const inventory = useWorldStore((s: any) => s.inventory);

  useActionGame(containerRef);

  const fragmentCount = inventory.filter((i: any) => i.item_type === 'story_fragment')
    .reduce((sum: number, i: any) => sum + i.quantity, 0);

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* Phaser game container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Floating overlay - pointer-events-none so it doesn't block game input */}
      <div className="absolute inset-0 pointer-events-none z-50">
        {/* World indicator - top center */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2">
          <div
            className={`px-3 py-1 rounded-full text-xs font-medium backdrop-blur-sm ${
              isAwakened
                ? 'bg-black/40 text-red-300 border border-red-500/30'
                : 'bg-white/40 text-blue-700 border border-pink-300/50'
            }`}
          >
            {isAwakened ? 'VOID WORLD' : 'SCRIPTED WORLD'}
          </div>
        </div>

        {/* Player stats - top left below awakening bar */}
        <div className="absolute top-10 left-3">
          <div
            className={`px-2 py-1 rounded text-xs backdrop-blur-sm ${
              isAwakened
                ? 'bg-black/30 text-gray-300'
                : 'bg-white/30 text-gray-700'
            }`}
          >
            <div>Awakening: {awakeningLevel}%</div>
            <div>Fragments: {fragmentCount}</div>
          </div>
        </div>

        {/* Back button - top right */}
        <button
          className="absolute top-2 right-14 pointer-events-auto px-3 py-1 rounded-full text-xs font-medium backdrop-blur-sm transition-all hover:scale-105 active:scale-95 cursor-pointer"
          style={{
            background: isAwakened ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.5)',
            color: isAwakened ? '#ccc' : '#333',
            border: isAwakened ? '1px solid rgba(255,0,64,0.3)' : '1px solid rgba(255,182,193,0.5)',
          }}
          onClick={() => navigate('/game')}
        >
          Back
        </button>
      </div>
    </div>
  );
}
