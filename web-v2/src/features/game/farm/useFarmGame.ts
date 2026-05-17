// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - useFarmGame Hook
// Bridges React state (Zustand) with the Phaser FarmScene
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useRef, useCallback } from 'react';
import Phaser from 'phaser';
import FarmScene from './FarmScene';
import { useWorldStore } from '../../../stores/worldStore';

/**
 * Initializes a Phaser.Game instance targeting the given container ref.
 * Syncs `isAwakened` from worldStore into the Phaser registry and emits
 * a `worldChanged` event whenever it flips so the scene can rebuild visuals.
 */
export function useFarmGame(containerRef: React.RefObject<HTMLDivElement | null>): void {
  const gameRef = useRef<Phaser.Game | null>(null);
  const isAwakened = useWorldStore((s: any) => s.isAwakened);
  const addToInventory = useWorldStore((s: any) => s.addToInventory);
  const updateFarmPlot = useWorldStore((s: any) => s.updateFarmPlot);
  const farmPlots = useWorldStore((s: any) => s.farmPlots);

  const prevAwakenedRef = useRef(isAwakened);

  // ── Initialize Phaser ────────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container || gameRef.current) return;

    const game = new Phaser.Game({
      type: Phaser.AUTO,
      backgroundColor: '#FDFBF7',
      parent: container,
      scale: {
        mode: Phaser.Scale.RESIZE,
        width: '100%',
        height: '100%',
      },
      scene: [FarmScene],
      // Keep it lightweight: no physics, no audio
      physics: { default: undefined as unknown as never },
      audio: { noAudio: true },
      render: {
        antialias: true,
        pixelArt: false,
        roundPixels: true,
      },
    });

    gameRef.current = game;

    // Inject store callbacks into registry so the scene can call them
    game.registry.set('onAddToInventory', addToInventory);
    game.registry.set('onUpdateFarmPlot', updateFarmPlot);
    game.registry.set('onGetFarmPlots', () => useWorldStore.getState().farmPlots);
    game.registry.set('isAwakened', isAwakened);

    return () => {
      game.destroy(true);
      gameRef.current = null;
    };
    // Only run on mount/unmount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Sync isAwakened into Phaser registry ─────────────────────────────
  useEffect(() => {
    const game = gameRef.current;
    if (!game) return;

    const prev = prevAwakenedRef.current;
    prevAwakenedRef.current = isAwakened;

    // Always update registry value
    game.registry.set('isAwakened', isAwakened);

    // Also update callback references (they may change on re-render)
    game.registry.set('onAddToInventory', addToInventory);
    game.registry.set('onUpdateFarmPlot', updateFarmPlot);
    game.registry.set('onGetFarmPlots', () => useWorldStore.getState().farmPlots);

    // Emit worldChanged only when the value actually flips
    if (prev !== isAwakened) {
      game.events.emit('worldChanged');
    }
  }, [isAwakened, addToInventory, updateFarmPlot, farmPlots]);

  // ── Handle window resize (Phaser.Scale.RESIZE handles most of it) ────
  const handleResize = useCallback(() => {
    gameRef.current?.scale.resize(window.innerWidth, window.innerHeight);
  }, []);

  useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);
}

export default useFarmGame;
