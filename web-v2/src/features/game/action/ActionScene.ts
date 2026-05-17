// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - Action Scene (横版动作)
// Phaser 3 Side-Scrolling Action Game with Dual-World Mechanics
// ═══════════════════════════════════════════════════════════════════════════
import Phaser from 'phaser';

// ─── Constants ────────────────────────────────────────────────────────────
const PLAYER_SPEED = 200;
const JUMP_FORCE = -420;
const GROUND_Y_OFFSET = 64; // from bottom
const MAX_ENEMIES = 10;
const ENEMY_SPEED = 60;
const ATTACK_DURATION = 200;
const INVINCIBLE_DURATION = 1000;

// ─── Types ────────────────────────────────────────────────────────────────
interface EnemyData {
  sprite: Phaser.Physics.Arcade.Sprite;
  health: number;
  maxHealth: number;
  patrolLeft: number;
  patrolRight: number;
  direction: number;
  healthBar: Phaser.GameObjects.Graphics;
}

interface PlatformData {
  x: number;
  y: number;
  width: number;
  height: number;
}

// ─── Scene ────────────────────────────────────────────────────────────────
export default class ActionScene extends Phaser.Scene {
  private isAwakened = false;
  private player!: Phaser.Physics.Arcade.Sprite;
  private playerGraphics!: Phaser.GameObjects.Graphics;
  private enemies: EnemyData[] = [];
  private platforms: Phaser.Physics.Arcade.StaticGroup | null = null;
  private platformGraphics: Phaser.GameObjects.Graphics | null = null;
  private bgGraphics: Phaser.GameObjects.Graphics | null = null;
  private bgGraphicsFar: Phaser.GameObjects.Graphics | null = null;
  private hudGraphics!: Phaser.GameObjects.Graphics;
  private slashGraphics!: Phaser.GameObjects.Graphics;
  private damageFlash!: Phaser.GameObjects.Graphics;
  private touchControls: Phaser.GameObjects.Graphics | null = null;

  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd!: { W: Phaser.Input.Keyboard.Key; A: Phaser.Input.Keyboard.Key; D: Phaser.Input.Keyboard.Key };
  private spaceKey!: Phaser.Input.Keyboard.Key;

  private playerHealth = 3;
  private maxHealth = 3;
  private score = 0;
  private isAttacking = false;
  private isInvincible = false;
  private facingRight = true;
  private groundY = 0;

  // Touch control tracking
  private touchLeft = false;
  private touchRight = false;
  private touchJump = false;
  private touchAttack = false;
  private isTouchDevice = false;

  constructor() {
    super({ key: 'ActionScene' });
  }

  // ── Lifecycle ───────────────────────────────────────────────────────────

  create(): void {
    const { width, height } = this.scale;
    this.groundY = height - GROUND_Y_OFFSET;
    this.isAwakened = this.registry.get('isAwakened') ?? false;

    // Input
    this.cursors = this.input.keyboard!.createCursorKeys();
    this.wasd = {
      W: this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.W),
      A: this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.A),
      D: this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.D),
    };
    this.spaceKey = this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);

    // Detect touch
    this.isTouchDevice = !this.sys.game.device.os.desktop;
    if (this.isTouchDevice) this.setupTouchControls();

    // Build world
    this.buildBackground();
    this.buildPlatforms();
    this.buildPlayer();
    this.spawnEnemies();
    this.buildHUD();
    this.setupDamageFlash();

    // World change listener
    this.game.events.on('worldChanged', this.handleWorldChanged, this);
  }

  update(_time: number, delta: number): void {
    if (!this.player || !this.player.active) return;
    this.handleMovement(delta);
    this.handleAttack();
    this.updateEnemies();
    this.updateHUD();
    if (this.isTouchDevice) this.updateTouchControls();
  }

  // ── Background ──────────────────────────────────────────────────────────

  private buildBackground(): void {
    if (this.bgGraphics) this.bgGraphics.destroy();
    if (this.bgGraphicsFar) this.bgGraphicsFar.destroy();

    const { width, height } = this.scale;
    this.bgGraphicsFar = this.add.graphics().setScrollFactor(0.1).setDepth(0);
    this.bgGraphics = this.add.graphics().setScrollFactor(0.3).setDepth(1);

    if (!this.isAwakened) {
      // Scripted World: sky gradient + clouds + mountains
      const sky = this.bgGraphicsFar;
      sky.fillGradientStyle(0x87CEEB, 0x87CEEB, 0xE0F0FF, 0xE0F0FF, 1);
      sky.fillRect(0, 0, width * 2, height);

      // Clouds
      sky.fillStyle(0xFFFFFF, 0.8);
      for (let i = 0; i < 5; i++) {
        const cx = (i * width * 0.5) + 50;
        const cy = 40 + (i % 3) * 30;
        sky.fillCircle(cx, cy, 30);
        sky.fillCircle(cx + 25, cy - 10, 25);
        sky.fillCircle(cx + 50, cy, 28);
      }

      // Mountains
      const mtn = this.bgGraphics;
      mtn.fillStyle(0x6B8E6B, 0.6);
      for (let i = 0; i < 4; i++) {
        const mx = i * width * 0.4;
        mtn.fillTriangle(mx, height, mx + 120, height - 200, mx + 240, height);
      }
      mtn.fillStyle(0x5A7D5A, 0.7);
      for (let i = 0; i < 3; i++) {
        const mx = i * width * 0.5 + 80;
        mtn.fillTriangle(mx, height, mx + 90, height - 140, mx + 180, height);
      }
    } else {
      // Void World: dark sky + ruins
      const sky = this.bgGraphicsFar;
      sky.fillGradientStyle(0x1A1A2E, 0x1A1A2E, 0x16213E, 0x16213E, 1);
      sky.fillRect(0, 0, width * 2, height);

      // Distant ruins
      const ruins = this.bgGraphics;
      ruins.fillStyle(0x2A2A3A, 0.5);
      for (let i = 0; i < 6; i++) {
        const rx = i * width * 0.35 + 20;
        const rh = 80 + (i % 3) * 60;
        ruins.fillRect(rx, height - rh, 40, rh);
        if (i % 2 === 0) ruins.fillRect(rx - 10, height - rh - 20, 60, 20);
      }

      // Debris particles
      ruins.fillStyle(0x3A3A4A, 0.3);
      for (let i = 0; i < 15; i++) {
        ruins.fillRect(
          (i * 97 + 30) % (width * 2),
          height - 30 - (i * 43) % 100,
          4 + (i % 3) * 3,
          4 + (i % 2) * 3
        );
      }
    }
  }

  // ── Platforms ───────────────────────────────────────────────────────────

  private getPlatformLayout(): PlatformData[] {
    const { width } = this.scale;
    return [
      { x: 0, y: this.groundY, width, height: 128 }, // ground
      { x: width * 0.1, y: this.groundY - 100, width: 140, height: 20 },
      { x: width * 0.45, y: this.groundY - 170, width: 160, height: 20 },
      { x: width * 0.75, y: this.groundY - 120, width: 130, height: 20 },
      { x: width * 0.3, y: this.groundY - 250, width: 120, height: 20 },
    ];
  }

  private buildPlatforms(): void {
    if (this.platforms) this.platforms.clear(true, true);
    if (this.platformGraphics) this.platformGraphics.destroy();

    this.platforms = this.physics.add.staticGroup();
    this.platformGraphics = this.add.graphics().setDepth(5);

    const layout = this.getPlatformLayout();
    const g = this.platformGraphics;

    for (const p of layout) {
      const rect = this.add.rectangle(p.x + p.width / 2, p.y + p.height / 2, p.width, p.height);
      this.platforms!.add(rect);
      rect.setVisible(false);
      rect.body.updateFromGameObject();

      if (!this.isAwakened) {
        // Scripted: brown earth + green grass
        g.fillStyle(0x8B6914);
        g.fillRect(p.x, p.y, p.width, p.height);
        g.fillStyle(0x4CAF50);
        g.fillRect(p.x, p.y, p.width, 6);
        // Grass tufts
        g.fillStyle(0x66BB6A);
        for (let i = 0; i < p.width; i += 12) {
          g.fillTriangle(p.x + i, p.y, p.x + i + 3, p.y - 6, p.x + i + 6, p.y);
        }
      } else {
        // Void: gray stone with cracks
        g.fillStyle(0x4A4A5A);
        g.fillRect(p.x, p.y, p.width, p.height);
        g.lineStyle(1, 0x3A3A4A, 0.6);
        for (let i = 0; i < p.width; i += 20 + (p.x % 7)) {
          const cy = p.y + 4 + (i % 8);
          g.lineBetween(p.x + i, cy, p.x + i + 10, cy + 4);
        }
        g.lineStyle(0);
      }
    }
  }

  // ── Player ──────────────────────────────────────────────────────────────

  private buildPlayer(): void {
    if (this.player) this.player.destroy();
    if (this.playerGraphics) this.playerGraphics.destroy();

    const { width } = this.scale;
    this.player = this.physics.add.sprite(width / 2, this.groundY - 24, '');
    this.player.setSize(24, 36);
    this.player.setCollideWorldBounds(true);
    this.player.setDepth(10);

    this.playerGraphics = this.add.graphics().setDepth(11);
    this.drawPlayer();

    if (this.platforms) {
      this.physics.add.collider(this.player, this.platforms);
    }
  }

  private drawPlayer(): void {
    const g = this.playerGraphics;
    g.clear();
    const px = this.player.x;
    const py = this.player.y;

    if (!this.isAwakened) {
      // Scripted: blue/white chibi
      // Body
      g.fillStyle(0x4A90D9);
      g.fillRoundedRect(px - 10, py - 8, 20, 22, 4);
      // Head
      g.fillStyle(0xFFD5B8);
      g.fillCircle(px, py - 16, 10);
      // Hair
      g.fillStyle(0x5B3A1A);
      g.fillRoundedRect(px - 10, py - 26, 20, 12, 4);
      // Eyes
      g.fillStyle(0x333333);
      g.fillCircle(px - 4, py - 16, 2);
      g.fillCircle(px + 4, py - 16, 2);
      // Eye shine
      g.fillStyle(0xFFFFFF);
      g.fillCircle(px - 3, py - 17, 1);
      g.fillCircle(px + 5, py - 17, 1);
      // Legs
      g.fillStyle(0x3A3A5A);
      g.fillRect(px - 8, py + 14, 6, 8);
      g.fillRect(px + 2, py + 14, 6, 8);
    } else {
      // Void: black/gray chibi with glitch
      g.fillStyle(0x2A2A3A);
      g.fillRoundedRect(px - 10, py - 8, 20, 22, 4);
      g.fillStyle(0xAAAAAA);
      g.fillCircle(px, py - 16, 10);
      // Dark hair
      g.fillStyle(0x111111);
      g.fillRoundedRect(px - 10, py - 26, 20, 12, 4);
      // Glitch eyes (red)
      g.fillStyle(0xFF3333);
      g.fillRect(px - 5, py - 18, 3, 2);
      g.fillRect(px + 2, py - 18, 3, 2);
      // Glitch scan lines
      g.lineStyle(1, 0xFF0000, 0.15);
      for (let i = -12; i < 18; i += 4) {
        g.lineBetween(px - 10, py + i, px + 10, py + i);
      }
      g.lineStyle(0);
      // Legs
      g.fillStyle(0x1A1A2A);
      g.fillRect(px - 8, py + 14, 6, 8);
      g.fillRect(px + 2, py + 14, 6, 8);
    }
  }

  // ── Enemies ─────────────────────────────────────────────────────────────

  private spawnEnemies(): void {
    this.clearEnemies();
    const { width } = this.scale;
    const count = 3 + Math.floor(Math.random() * 3); // 3-5
    const spots = [
      { x: width * 0.2, left: width * 0.05, right: width * 0.35 },
      { x: width * 0.5, left: width * 0.35, right: width * 0.65 },
      { x: width * 0.8, left: width * 0.65, right: width * 0.95 },
      { x: width * 0.35, left: width * 0.25, right: width * 0.45 },
      { x: width * 0.65, left: width * 0.55, right: width * 0.75 },
    ];

    for (let i = 0; i < count && i < MAX_ENEMIES; i++) {
      const spot = spots[i % spots.length];
      const hp = this.isAwakened ? 2 : 1;
      this.createEnemy(spot.x, this.groundY - 20, spot.left, spot.right, hp);
    }
  }

  private createEnemy(x: number, y: number, left: number, right: number, hp: number): void {
    const sprite = this.physics.add.sprite(x, y, '');
    sprite.setSize(28, 28);
    sprite.setCollideWorldBounds(true);
    sprite.setDepth(8);
    if (this.platforms) this.physics.add.collider(sprite, this.platforms);

    const healthBar = this.add.graphics().setDepth(12);
    const direction = Math.random() > 0.5 ? 1 : -1;

    const enemy: EnemyData = {
      sprite, health: hp, maxHealth: hp,
      patrolLeft: left, patrolRight: right,
      direction, healthBar,
    };
    this.enemies.push(enemy);
    this.drawEnemy(enemy);

    // Collision: player attacks enemy
    this.physics.add.overlap(this.player, sprite, () => {
      if (this.isAttacking) this.damageEnemy(enemy);
    });
    // Collision: enemy damages player
    this.physics.add.overlap(this.player, sprite, () => {
      if (!this.isAttacking && !this.isInvincible) this.damagePlayer();
    });
  }

  private drawEnemy(enemy: EnemyData): void {
    const g = enemy.healthBar;
    g.clear();
    const ex = enemy.sprite.x;
    const ey = enemy.sprite.y;

    if (!this.isAwakened) {
      // Scripted: purple blob monster
      g.fillStyle(0x9B59B6);
      g.fillCircle(ex, ey, 14);
      g.fillStyle(0x8E44AD);
      g.fillCircle(ex - 4, ey + 4, 6);
      g.fillCircle(ex + 4, ey + 4, 6);
      // Eyes
      g.fillStyle(0xFFFFFF);
      g.fillCircle(ex - 5, ey - 3, 4);
      g.fillCircle(ex + 5, ey - 3, 4);
      g.fillStyle(0x333333);
      g.fillCircle(ex - 4, ey - 3, 2);
      g.fillCircle(ex + 6, ey - 3, 2);
    } else {
      // Void: dark glitch monster
      g.fillStyle(0x1A1A2E);
      g.fillRect(ex - 14, ey - 14, 28, 28);
      // Glitch distortion
      g.fillStyle(0xFF0040, 0.3);
      g.fillRect(ex - 14, ey - 4, 28, 3);
      g.fillStyle(0x00FFFF, 0.2);
      g.fillRect(ex - 14, ey + 4, 28, 2);
      // Eyes
      g.fillStyle(0xFF0000);
      g.fillRect(ex - 7, ey - 5, 4, 3);
      g.fillRect(ex + 3, ey - 5, 4, 3);
    }

    // Health bar
    const barW = 24;
    const barH = 3;
    const barX = ex - barW / 2;
    const barY = ey - 22;
    g.fillStyle(0x333333);
    g.fillRect(barX, barY, barW, barH);
    g.fillStyle(0x4CAF50);
    g.fillRect(barX, barY, barW * (enemy.health / enemy.maxHealth), barH);
  }

  private clearEnemies(): void {
    for (const e of this.enemies) {
      e.sprite.destroy();
      e.healthBar.destroy();
    }
    this.enemies = [];
  }

  // ── Combat ──────────────────────────────────────────────────────────────

  private handleAttack(): void {
    const attackPressed = Phaser.Input.Keyboard.JustDown(this.spaceKey) || this.touchAttack;
    if (attackPressed && !this.isAttacking) {
      this.isAttacking = true;
      this.showSlash();
      this.time.delayedCall(ATTACK_DURATION, () => { this.isAttacking = false; });
    }
    this.touchAttack = false;
  }

  private showSlash(): void {
    const g = this.slashGraphics;
    g.clear();
    const px = this.player.x;
    const py = this.player.y;
    const dir = this.facingRight ? 1 : -1;
    const color = this.isAwakened ? 0xFF0040 : 0x66BBFF;

    g.lineStyle(3, color, 0.9);
    g.beginPath();
    g.arc(px + dir * 20, py - 5, 28, dir > 0 ? -Math.PI / 3 : Math.PI - Math.PI / 3, dir > 0 ? Math.PI / 3 : Math.PI + Math.PI / 3, false);
    g.strokePath();
    g.lineStyle(2, 0xFFFFFF, 0.5);
    g.beginPath();
    g.arc(px + dir * 20, py - 5, 22, dir > 0 ? -Math.PI / 4 : Math.PI - Math.PI / 4, dir > 0 ? Math.PI / 4 : Math.PI + Math.PI / 4, false);
    g.strokePath();

    this.time.delayedCall(ATTACK_DURATION, () => g.clear());
  }

  private damageEnemy(enemy: EnemyData): void {
    if (enemy.health <= 0) return;
    enemy.health--;
    this.drawEnemy(enemy);

    if (enemy.health <= 0) {
      this.defeatEnemy(enemy);
    }
  }

  private defeatEnemy(enemy: EnemyData): void {
    const ex = enemy.sprite.x;
    const ey = enemy.sprite.y;

    // Particle burst
    const particles = this.add.graphics().setDepth(15);
    const color = this.isAwakened ? 0xFF0040 : 0x9B59B6;
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * Math.PI * 2;
      const dist = 15 + Math.random() * 10;
      particles.fillStyle(color, 0.8);
      particles.fillCircle(ex + Math.cos(angle) * dist, ey + Math.sin(angle) * dist, 2 + Math.random() * 2);
    }

    // Fade out
    this.tweens.add({
      targets: [enemy.sprite, enemy.healthBar, particles],
      alpha: 0,
      duration: 400,
      onComplete: () => {
        enemy.sprite.destroy();
        enemy.healthBar.destroy();
        particles.destroy();
        this.enemies = this.enemies.filter(e => e !== enemy);
      },
    });

    this.score++;

    // Drop story fragment into inventory via registry
    const inv = this.registry.get('inventory') as Array<{ item_type: string; item_id: string; quantity: number; quality: number }> | undefined;
    if (inv) {
      const fragId = `fragment_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      inv.push({ item_type: 'story_fragment', item_id: fragId, quantity: 1, quality: 1 });
      this.registry.set('inventory', inv);
    }
  }

  private damagePlayer(): void {
    if (this.isInvincible) return;
    this.playerHealth--;
    this.isInvincible = true;

    // Red flash
    this.damageFlash.clear();
    this.damageFlash.fillStyle(0xFF0000, 0.3);
    this.damageFlash.fillRect(0, 0, this.scale.width, this.scale.height);
    this.time.delayedCall(150, () => this.damageFlash.clear());

    // Blink effect
    this.tweens.add({
      targets: this.player,
      alpha: 0.3,
      duration: 100,
      yoyo: true,
      repeat: 4,
      onComplete: () => { this.player.setAlpha(1); },
    });

    this.time.delayedCall(INVINCIBLE_DURATION, () => { this.isInvincible = false; });

    if (this.playerHealth <= 0) {
      this.playerDeath();
    }
  }

  private playerDeath(): void {
    this.player.setTint(0xFF0000);
    this.time.delayedCall(1500, () => {
      this.playerHealth = this.maxHealth;
      this.score = Math.max(0, this.score - 2);
      const { width } = this.scale;
      this.player.setPosition(width / 2, this.groundY - 24);
      this.player.clearTint();
      this.player.setAlpha(1);
    });
  }

  // ── Movement ────────────────────────────────────────────────────────────

  private handleMovement(_delta: number): void {
    const body = this.player.body as Phaser.Physics.Arcade.Body;
    if (!body) return;

    const onGround = body.touching.down || body.blocked.down;
    let moveX = 0;

    if (this.cursors.left.isDown || this.wasd.A.isDown || this.touchLeft) moveX -= 1;
    if (this.cursors.right.isDown || this.wasd.D.isDown || this.touchRight) moveX += 1;

    this.player.setVelocityX(moveX * PLAYER_SPEED);
    if (moveX !== 0) this.facingRight = moveX > 0;

    const jumpPressed = Phaser.Input.Keyboard.JustDown(this.cursors.up) ||
      Phaser.Input.Keyboard.JustDown(this.wasd.W) || this.touchJump;
    if (jumpPressed && onGround) {
      this.player.setVelocityY(JUMP_FORCE);
    }
    this.touchJump = false;

    // Update player graphic position
    this.drawPlayer();
  }

  // ── Enemy AI ────────────────────────────────────────────────────────────

  private updateEnemies(): void {
    for (const enemy of this.enemies) {
      if (enemy.health <= 0) continue;
      const ex = enemy.sprite.x;
      if (ex <= enemy.patrolLeft + 10) enemy.direction = 1;
      if (ex >= enemy.patrolRight - 10) enemy.direction = -1;
      enemy.sprite.setVelocityX(enemy.direction * ENEMY_SPEED);
      this.drawEnemy(enemy);
    }
  }

  // ── HUD ─────────────────────────────────────────────────────────────────

  private buildHUD(): void {
    this.hudGraphics = this.add.graphics().setDepth(50).setScrollFactor(0);
    this.slashGraphics = this.add.graphics().setDepth(9);
  }

  private setupDamageFlash(): void {
    this.damageFlash = this.add.graphics().setDepth(100).setScrollFactor(0);
  }

  private updateHUD(): void {
    const g = this.hudGraphics;
    g.clear();
    const { width } = this.scale;

    // Hearts (top-left)
    for (let i = 0; i < this.maxHealth; i++) {
      const hx = 20 + i * 28;
      const hy = 20;
      if (i < this.playerHealth) {
        g.fillStyle(0xFF4444);
      } else {
        g.fillStyle(0x444444);
      }
      // Simple heart shape
      g.fillCircle(hx - 4, hy - 2, 5);
      g.fillCircle(hx + 4, hy - 2, 5);
      g.fillTriangle(hx - 9, hy, hx + 9, hy, hx, hy + 10);
    }

    // Score (top-right)
    g.fillStyle(0xFFFFFF, 0.9);
    g.fillRect(width - 130, 10, 120, 28);
    g.lineStyle(1, this.isAwakened ? 0xFF0040 : 0x4A90D9, 1);
    g.strokeRect(width - 130, 10, 120, 28);
    g.lineStyle(0);
    // Score text via bitmap-like drawing
    this.drawPixelText(g, `${this.score}`, width - 70, 18, 0x333333, 2);
  }

  private drawPixelText(g: Phaser.GameObjects.Graphics, text: string, x: number, y: number, color: number, size: number): void {
    g.fillStyle(color, 1);
    // Simple digit rendering (0-9 only)
    const patterns: Record<string, number[][]> = {
      '0': [[0,1,1,0],[1,0,0,1],[1,0,0,1],[1,0,0,1],[0,1,1,0]],
      '1': [[0,0,1,0],[0,1,1,0],[0,0,1,0],[0,0,1,0],[0,1,1,1]],
      '2': [[0,1,1,0],[1,0,0,1],[0,0,1,0],[0,1,0,0],[1,1,1,1]],
      '3': [[1,1,1,0],[0,0,0,1],[0,1,1,0],[0,0,0,1],[1,1,1,0]],
      '4': [[1,0,1,0],[1,0,1,0],[1,1,1,1],[0,0,1,0],[0,0,1,0]],
      '5': [[1,1,1,1],[1,0,0,0],[1,1,1,0],[0,0,0,1],[1,1,1,0]],
      '6': [[0,1,1,0],[1,0,0,0],[1,1,1,0],[1,0,0,1],[0,1,1,0]],
      '7': [[1,1,1,1],[0,0,0,1],[0,0,1,0],[0,1,0,0],[0,1,0,0]],
      '8': [[0,1,1,0],[1,0,0,1],[0,1,1,0],[1,0,0,1],[0,1,1,0]],
      '9': [[0,1,1,0],[1,0,0,1],[0,1,1,1],[0,0,0,1],[0,1,1,0]],
    };
    let offsetX = 0;
    for (const ch of text) {
      const pat = patterns[ch];
      if (pat) {
        for (let row = 0; row < pat.length; row++) {
          for (let col = 0; col < pat[row].length; col++) {
            if (pat[row][col]) g.fillRect(x + offsetX + col * size, y + row * size, size, size);
          }
        }
      }
      offsetX += 6 * size;
    }
  }

  // ── Touch Controls ──────────────────────────────────────────────────────

  private setupTouchControls(): void {
    this.touchControls = this.add.graphics().setDepth(60).setScrollFactor(0);
    this.drawTouchControls();

    // D-pad zones (left side)
    const dpadZone = this.add.zone(80, this.scale.height - 100, 120, 120).setInteractive().setScrollFactor(0).setDepth(59);
    dpadZone.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
      const localX = pointer.x - 80;
      if (localX < -15) this.touchLeft = true;
      else if (localX > 15) this.touchRight = true;
      else this.touchJump = true;
    });
    dpadZone.on('pointerup', () => { this.touchLeft = false; this.touchRight = false; });
    dpadZone.on('pointerout', () => { this.touchLeft = false; this.touchRight = false; });

    // Action button (right side)
    const actionZone = this.add.zone(this.scale.width - 80, this.scale.height - 100, 80, 80).setInteractive().setScrollFactor(0).setDepth(59);
    actionZone.on('pointerdown', () => { this.touchAttack = true; });
  }

  private drawTouchControls(): void {
    if (!this.touchControls) return;
    const g = this.touchControls;
    g.clear();
    const { width, height } = this.scale;
    const baseY = height - 100;

    // D-pad background
    g.fillStyle(0xFFFFFF, 0.15);
    g.fillCircle(80, baseY, 50);
    // Arrows
    g.lineStyle(2, 0xFFFFFF, 0.5);
    g.beginPath(); g.moveTo(55, baseY); g.lineTo(70, baseY - 10); g.lineTo(70, baseY + 10); g.closePath(); g.strokePath();
    g.beginPath(); g.moveTo(105, baseY); g.lineTo(90, baseY - 10); g.lineTo(90, baseY + 10); g.closePath(); g.strokePath();
    g.beginPath(); g.moveTo(80, baseY - 25); g.lineTo(70, baseY - 10); g.lineTo(90, baseY - 10); g.closePath(); g.strokePath();
    g.lineStyle(0);

    // Action button
    g.fillStyle(0xFF4444, 0.3);
    g.fillCircle(width - 80, baseY, 32);
    g.lineStyle(2, 0xFF4444, 0.6);
    g.strokeCircle(width - 80, baseY, 32);
    g.lineStyle(0);
    g.fillStyle(0xFFFFFF, 0.6);
    this.drawPixelText(g, 'ATK', width - 92, baseY - 6, 0xFFFFFF, 1.5);
  }

  private updateTouchControls(): void {
    // Redraw touch controls each frame to keep them positioned
    this.drawTouchControls();
  }

  // ── World Switching ─────────────────────────────────────────────────────

  private handleWorldChanged(isAwakened: boolean): void {
    this.isAwakened = isAwakened;
    this.buildBackground();
    this.buildPlatforms();
    if (this.platforms) this.physics.add.collider(this.player, this.platforms);
    this.spawnEnemies();
    this.drawPlayer();
  }

  // ── Cleanup ─────────────────────────────────────────────────────────────

  shutdown(): void {
    this.game.events.off('worldChanged', this.handleWorldChanged, this);
    this.clearEnemies();
  }
}
