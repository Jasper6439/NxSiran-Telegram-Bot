// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - Farm Page Component
// React wrapper with floating Tailwind overlay over the Phaser canvas
// ═══════════════════════════════════════════════════════════════════════════
import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorldStore } from '../../stores/worldStore';
import { useFarmGame } from './useFarmGame';

export default function FarmPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const isAwakened = useWorldStore((s) => s.isAwakened);
  const inventory = useWorldStore((s) => s.inventory);

  // Initialize Phaser game
  useFarmGame(containerRef);

  // Count relevant inventory items
  const seedCount = inventory.filter(
    (i) => i.item_id === 'tomato_seed' || i.item_id === 'void_seed'
  ).reduce((sum, i) => sum + i.quantity, 0);

  const harvestCount = inventory.filter(
    (i) => i.item_id === 'perfect_tomato' || i.item_id === 'awakening_fragment'
  ).reduce((sum, i) => sum + i.quantity, 0);

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* Phaser canvas container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Floating overlay - pointer-events-none so clicks pass through to Phaser */}
      <div className="absolute inset-0 pointer-events-none z-10 flex flex-col justify-between p-3">
        {/* Top bar */}
        <div className="flex items-center justify-between">
          {/* World indicator */}
          <div
            className={`pointer-events-auto px-3 py-1.5 rounded-full text-xs font-semibold tracking-wide shadow-md backdrop-blur-sm transition-colors duration-500 ${
              isAwakened
                ? 'bg-black/60 text-purple-300 border border-purple-500/40'
                : 'bg-white/70 text-amber-800 border border-amber-300/50'
            }`}
          >
            {isAwakened ? 'Blank Zone' : 'Script Zone'}
          </div>

          {/* Seed / harvest counts */}
          <div className="flex gap-2">
            <div
              className={`pointer-events-auto px-3 py-1.5 rounded-full text-xs font-medium shadow-md backdrop-blur-sm ${
                isAwakened
                  ? 'bg-black/60 text-gray-300 border border-gray-600/40'
                  : 'bg-white/70 text-gray-700 border border-gray-200/50'
              }`}
            >
              Seeds: {seedCount}
            </div>
            <div
              className={`pointer-events-auto px-3 py-1.5 rounded-full text-xs font-medium shadow-md backdrop-blur-sm ${
                isAwakened
                  ? 'bg-black/60 text-purple-300 border border-purple-500/40'
                  : 'bg-white/70 text-green-700 border border-green-200/50'
              }`}
            >
              Harvest: {harvestCount}
            </div>
          </div>

          {/* Back button */}
          <button
            onClick={() => navigate('/game')}
            className={`pointer-events-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shadow-md backdrop-blur-sm transition-colors duration-200 ${
              isAwakened
                ? 'bg-black/60 text-gray-300 border border-gray-600/40 hover:bg-black/80'
                : 'bg-white/70 text-gray-600 border border-gray-200/50 hover:bg-white/90'
            }`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" />
              <path d="M12 19l-7-7 7-7" />
            </svg>
            Back
          </button>
        </div>

        {/* Bottom hint */}
        <div className="flex justify-center">
          <div
            className={`px-4 py-1.5 rounded-full text-xs backdrop-blur-sm ${
              isAwakened
                ? 'bg-black/40 text-gray-500'
                : 'bg-white/40 text-gray-500'
            }`}
          >
            Tap empty plot to plant &middot; Tap crop to water &middot; Tap mature crop to harvest
          </div>
        </div>
      </div>
    </div>
  );
}
