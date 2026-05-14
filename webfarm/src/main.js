/**
 * main.js - Phaser 游戏主入口
 * 
 * v1.5.5 优化：
 * - WEBGL 渲染 + pixelArt 像素锐利
 * - 16:9 宽高比，消灭黑边
 * - ENVELOP 模式：画布填满屏幕，内容自适应
 */

const script = document.createElement('script');
script.src = 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js';
script.onload = initGame;
document.head.appendChild(script);

function initGame() {
    const config = {
        // WEBGL 渲染，性能更好
        type: Phaser.WEBGL,
        
        // 16:9 宽高比基准分辨率
        width: 720,
        height: 405,
        
        parent: 'game-container',
        
        // 背景色与 body 一致，消灭黑边
        backgroundColor: '#4a7a2e',
        
        scene: [GameScene],
        
        // 缩放配置
        scale: {
            // ENVELOP：画布填满屏幕，内容等比缩放（无黑边）
            mode: Phaser.Scale.ENVELOP,
            autoCenter: Phaser.Scale.CENTER_BOTH,
        },
        
        // 渲染配置
        render: {
            // 像素艺术模式：关闭平滑缩放，像素锐利
            pixelArt: true,
            antialias: false,
            roundPixels: true,
            clearBeforeRender: true,
            // 批处理优化（e2-micro 友好）
            batchDraw: true,
        },
        
        // 输入配置
        input: {
            activePointers: 2,
            touch: { capture: true }
        },
        
        // 物理引擎（预留）
        physics: {
            default: 'arcade',
            arcade: { debug: false }
        }
    };
    
    window.game = new Phaser.Game(config);
    
    console.log('🎮 WebFarm v1.5.5 Initialized');
    console.log('Screen:', window.innerWidth, 'x', window.innerHeight);
    
    window.addEventListener('resize', () => {
        if (window.game) window.game.scale.refresh();
    });
}
