/**
 * main.js - Phaser 游戏主入口
 * 
 * 配置 Phaser 3 游戏引擎，重点优化移动端适配
 */

// 动态加载 Phaser
const script = document.createElement('script');
script.src = 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js';
script.onload = initGame;
document.head.appendChild(script);

function initGame() {
    // 游戏配置
    const config = {
        type: Phaser.AUTO,
        
        // 画布尺寸
        width: 414,
        height: 896,
        
        // 父容器
        parent: 'game-container',
        
        // 背景色
        backgroundColor: '#6b8e23',
        
        // 场景
        scene: [GameScene],
        
        // 缩放配置 - 关键！
        scale: {
            // FIT 模式：保持宽高比，填满屏幕
            mode: Phaser.Scale.FIT,
            
            // 水平和垂直居中
            autoCenter: Phaser.Scale.CENTER_BOTH,
            
            // 最小/最大缩放
            min: {
                width: 320,
                height: 480
            },
            max: {
                width: 414,
                height: 896
            }
        },
        
        // 渲染配置
        render: {
            // 像素艺术模式（关闭平滑缩放）
            pixelArt: false,
            
            // 抗锯齿
            antialias: true,
            
            // 是否清除画布背景
            clearBeforeRender: true
        },
        
        // 输入配置
        input: {
            // 触摸优先级
            activePointers: 1,
            
            // 防止浏览器默认触摸行为
            touch: {
                capture: true
            }
        }
    };
    
    // 创建游戏实例
    window.game = new Phaser.Game(config);
    
    // 输出日志
    console.log('🎮 WebFarm Game Initialized');
    console.log('Screen:', window.innerWidth, 'x', window.innerHeight);
    
    // 监听窗口大小变化
    window.addEventListener('resize', () => {
        if (window.game) {
            window.game.scale.refresh();
            console.log('Game resized:', window.innerWidth, 'x', window.innerHeight);
        }
    });
}
