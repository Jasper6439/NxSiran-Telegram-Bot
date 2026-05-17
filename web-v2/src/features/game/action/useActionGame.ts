// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - useActionGame Hook
// Creates and manages the Phaser Game instance for the Action Scene
// ═══════════════════════════════════════════════════════════════════════════
import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import ActionScene from './ActionScene';
import { useWorldStore } from '../../../stores/worldStore';

export function useActionGame(containerRef: React.RefObject<HTMLDivElement | null>): void {
  const gameRef = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Prevent duplicate initialization
    if (gameRef.current) return;

    const isAwakened = useWorldStore.getState().isAwakened;
    const inventory = useWorldStore.getState().inventory;

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      parent: container,
      physics: {
        default: 'arcade',
        arcade: {
          gravity: { x: 0, y: 800 },
          debug: false,
        },
      },
      scale: {
        mode: Phaser.Scale.RESIZE,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      scene: [ActionScene],
      backgroundColor: '#87CEEB',
      render: {
        pixelArt: false,
        antialias: true,
      },
      input: {
        activePointers: 3,
      },
    };

    const game = new Phaser.Game(config);
    gameRef.current = game;

    // Pass initial state to scene registry
    game.registry.set('isAwakened', isAwakened);
    game.registry.set('inventory', [...inventory]);

    // Subscribe to world store changes
    const unsubscribe = useWorldStore.subscribe((state: any, prevState: any) => {
      if (state.isAwakened !== prevState.isAwakened && !state.isTransitioning) {
        game.registry.set('isAwakened', state.isAwakened);
        game.registry.set('inventory', [...state.inventory]);
        game.events.emit('worldChanged', state.isAwakened);
      }
    });

    return () => {
      unsubscribe();
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
  }, [containerRef]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (gameRef.current) {
        gameRef.current.scale.resize(
          window.innerWidth,
          window.innerHeight
        );
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
}
