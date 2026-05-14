/**
 * main.js - Phaser 游戏主入口
 * 
 * v1.5.6 矢量扁平插画风
 * - Nunito 圆润字体
 * - 莫兰迪色系
 * - 矢量图形绘制
 */

const script = document.createElement('script');
script.src = 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js';
script.onload = initGame;
document.head.appendChild(script);

function initGame() {
    const config = {
        // Canvas 渲染（矢量图形更适合）
        type: Phaser.CANVAS,
        
        // 9:16 竖屏比例（移动端友好）
        width: 360,
        height: 640,
        
        parent: 'game-container',
        
        // 背景透明（HTML 已有渐变）
        backgroundColor: 'transparent',
        
        scene: [GameScene],
        
        scale: {
            mode: Phaser.Scale.ENVELOP,
            autoCenter: Phaser.Scale.CENTER_BOTH,
        },
        
        render: {
            // 矢量风格：抗锯齿开启
            antialias: true,
            roundPixels: false,
            clearBeforeRender: true,
        },
        
        input: {
            activePointers: 2,
            touch: { capture: true }
        }
    };
    
    window.game = new Phaser.Game(config);
    
    console.log('🎮 WebFarm v1.5.6 Initialized - Vector Flat Style');
}
