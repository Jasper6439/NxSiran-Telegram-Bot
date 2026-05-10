/* ============================================================
 * NxSiRan Farm Game Engine
 * HTML5 Canvas 2D - Q版 Cute Style
 * Inspired by Stardew Valley & Animal Crossing
 *
 * All graphics drawn with Canvas 2D API (no external images).
 * Pure JavaScript, no frameworks, no ES modules.
 * Target: mobile phones (320-414px width), portrait orientation.
 * ============================================================ */

/* ============================================================
 * SECTION 1: CONSTANTS & CONFIGURATION
 * ============================================================ */

var TILE = 32;
var PLAYER_SPEED = 2.5;
var NPC_SPEED = 1.0;
var INTERACT_DIST = 48;
var FPS_TARGET = 30;
var FRAME_TIME = 1000 / FPS_TARGET;
var CROP_GROW_TIME = 30000; /* 30 seconds to fully grow */

var COLORS = {
    grass: '#7BC67E',
    grassDark: '#5DAF60',
    grassLight: '#9AD89D',
    soil: '#8B6914',
    soilDark: '#6B4F0E',
    soilWet: '#5A3E0A',
    path: '#D4A574',
    pathDark: '#B8895C',
    fence: '#A0724A',
    fencePost: '#7A5535',
    wood: '#D4A574',
    woodDark: '#B8895C',
    woodLight: '#E8C9A0',
    roof: '#C0392B',
    roofDark: '#96281B',
    wall: '#F5E6CC',
    wallDark: '#E0CDB0',
    concrete: '#B0B0B0',
    concreteDark: '#909090',
    railing: '#707070',
    purple: '#7B3FA0',
    purpleDark: '#5E2D7A',
    purpleLight: '#A86BC8',
    white: '#FFFFFF',
    black: '#1A1A2E',
    skin: '#FFE0BD',
    skinShadow: '#F0C8A0',
    hair: '#2C1810',
    hairDark: '#1A0E08',
    eye: '#1A1A2E',
    eyeWhite: '#FFFFFF',
    mouth: '#E07070',
    cheek: '#FFB0B0',
    hat: '#C0392B',
    hatBand: '#D4A574',
    shirt: '#5B8BD4',
    shirtDark: '#3A6BC5',
    pants: '#4A6FA5',
    pantsDark: '#3A5585',
    shoe: '#5A3A2A',
    flower1: '#FF6B8A',
    flower2: '#FFD93D',
    flower3: '#A86BC8',
    flower4: '#FF9F43',
    leaf: '#5DAF60',
    trunk: '#8B6914',
    water: '#5B8BD4',
    waterLight: '#7AADE8',
    cafeFloor: '#D4A574',
    cafeFloorDark: '#C09060',
    counter: '#8B6914',
    counterTop: '#A07830',
    menu: '#3A2A1A',
    menuText: '#FFD93D',
    bench: '#A0724A',
    benchDark: '#7A5535',
    pot: '#D4764A',
    potGreen: '#5DAF60',
    clothesline: '#A0A0A0',
    cloth1: '#FF6B8A',
    cloth2: '#5B8BD4',
    cloth3: '#FFD93D',
    cloth4: '#A86BC8',
    npcHair: '#2C1810',
    npcOutfit: '#7B3FA0',
    npcOutfitLight: '#FFFFFF',
    npcSkin: '#FFE0BD',
    shadow: 'rgba(0,0,0,0.18)',
    bubble: 'rgba(255,255,255,0.92)',
    bubbleBorder: '#7B3FA0',
    dialogueBg: 'rgba(30,20,40,0.92)',
    dialogueName: '#A86BC8',
    dialogueText: '#F0E8F8',
    warmLight: 'rgba(255,200,100,0.08)',
    nightOverlay: 'rgba(10,10,40,',
    rainDrop: 'rgba(180,200,255,0.5)',
    sunRay: 'rgba(255,240,180,0.06)',
    cloudShadow: 'rgba(0,0,0,0.07)',
    barn: '#8B4513',
    barnDark: '#6B3410',
    barnRoof: '#A0522D',
    barnDoor: '#5C3317'
};

/* ============================================================
 * SECTION 2: UTILITY FUNCTIONS
 * ============================================================ */

function clamp(v, min, max) {
    return v < min ? min : v > max ? max : v;
}

function lerp(a, b, t) {
    return a + (b - a) * t;
}

function dist(x1, y1, x2, y2) {
    var dx = x2 - x1;
    var dy = y2 - y1;
    return Math.sqrt(dx * dx + dy * dy);
}

function rectOverlap(ax, ay, aw, ah, bx, by, bw, bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

function isTouchDevice() {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
}

/* ============================================================
 * SECTION 3: TILE MAP DATA
 * ============================================================ */

/*
 * Tile legend:
 * 0 = grass, 1 = path, 2 = soil, 3 = fence-top, 4 = fence-bottom,
 * 5 = fence-left, 6 = fence-right, 7 = house-wall, 8 = house-door,
 * 9 = fence-corner-tl, 10 = fence-corner-tr, 11 = fence-corner-bl, 12 = fence-corner-br,
 * 13 = flower-red, 14 = flower-yellow, 15 = tree, 16 = water,
 * 17 = concrete, 18 = railing, 19 = bench, 20 = potted-plant,
 * 21 = clothesline, 22 = building-bg, 23 = cafe-floor, 24 = counter,
 * 25 = table, 26 = chair, 27 = menu-board, 28 = barista,
 * 29 = exit-zone, 30 = flower-purple, 31 = flower-orange,
 * 33 = fence-post-top, 34 = fence-post-bottom, 35 = fence-post-left, 36 = fence-post-right,
 * 37 = lamp, 38 = sky-bg, 39 = rooftop-edge,
 * 40 = farm-soil (plantable), 41 = barn-wall, 42 = barn-door, 43 = barn-roof
 */

/* Scene 1: Farm (24x18 tiles) */
var FARM_MAP = [
    [3,33,3,33,3,33,3,33,3,33,3,33,3,33,3,33,3,33,3,33,3,33,3,10],
    [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0,15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,13, 0,14, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 7, 8, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,41,41,41, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,41,42,41, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,41,41,41, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0,40,40,40,40,40,40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0,40,40,40,40,40,40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0,40,40,40,40,40,40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0,40,40,40,40,40,40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [5, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,29, 6],
    [5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    [9,34,4,34,4,34,4,34,4,34,4,34,4,34,4,34,4,34,4,34,4,34,4,12]
];

/* Scene 2: Rooftop (16x14 tiles) */
var ROOFTOP_MAP = [
    [38,38,38,38,38,38,38,38,38,38,38,38,38,38,38,38],
    [22,22,22,22,22,22,22,22,22,22,22,22,22,22,22,22],
    [39,39,39,39,39,39,39,39,39,39,39,39,39,39,39,39],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,17,17,17,17,17,17,17,17,17,17,17,17,17,18,18],
    [18,18,18,18,18,18,18,18,18,18,18,18,18,18,18,18]
];

/* Scene 3: Cafe (16x14 tiles) */
var CAFE_MAP = [
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,27,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23],
    [23,23,23,23,23,23,23,23,23,23,23,23,23,23,23,23]
];

/* Seed data for the seed selection bar */
var SEEDS = [
    { id: 'tomato', name: '番茄', emoji: '🍅' },
    { id: 'corn', name: '玉米', emoji: '🌽' },
    { id: 'strawberry', name: '草莓', emoji: '🍓' },
    { id: 'carrot', name: '胡萝卜', emoji: '🥕' },
    { id: 'watermelon', name: '西瓜', emoji: '🍉' },
    { id: 'sunflower', name: '向日葵', emoji: '🌻' }
];

/* Scene configurations */
var SCENES = {
    farm: {
        name: '农场',
        map: FARM_MAP,
        width: 24,
        height: 18,
        playerStart: { x: 5 * TILE, y: 14 * TILE },
        npcStart: { x: 16 * TILE, y: 10 * TILE },
        exits: [
            { x: 22, y: 15, w: 1, h: 2, target: 'rooftop', spawnX: 7, spawnY: 11 },
            { x: 22, y: 15, w: 1, h: 2, target: 'cafe', spawnX: 7, spawnY: 11 }
        ],
        solidTiles: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 33, 34, 35, 36, 39, 41, 42, 43]
    },
    rooftop: {
        name: '天台',
        map: ROOFTOP_MAP,
        width: 16,
        height: 14,
        playerStart: { x: 7 * TILE, y: 11 * TILE },
        npcStart: { x: 10 * TILE, y: 6 * TILE },
        exits: [
            { x: 7, y: 13, w: 2, h: 1, target: 'farm', spawnX: 22, spawnY: 14 }
        ],
        solidTiles: [18, 22, 38, 39]
    },
    cafe: {
        name: '咖啡厅',
        map: CAFE_MAP,
        width: 16,
        height: 14,
        playerStart: { x: 7 * TILE, y: 11 * TILE },
        npcStart: { x: 3 * TILE, y: 4 * TILE },
        exits: [
            { x: 7, y: 13, w: 2, h: 1, target: 'farm', spawnX: 22, spawnY: 14 }
        ],
        solidTiles: [24, 27, 28]
    }
};

/* ============================================================
 * SECTION 4: INPUT SYSTEM
 * ============================================================ */

var Input = {
    keys: {},
    dirX: 0,
    dirY: 0,
    actionPressed: false,
    actionJustPressed: false,
    _prevAction: false,
    _touchId: null,
    _joystickActive: false,
    _joystickStartX: 0,
    _joystickStartY: 0,
    _joystickX: 0,
    _joystickY: 0,
    _actionTouchId: null,

    init: function(canvas) {
        var self = this;

        document.addEventListener('keydown', function(e) {
            self.keys[e.key] = true;
            if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' '].indexOf(e.key) !== -1) {
                e.preventDefault();
            }
        });

        document.addEventListener('keyup', function(e) {
            self.keys[e.key] = false;
        });

        canvas.addEventListener('touchstart', function(e) {
            e.preventDefault();
            for (var i = 0; i < e.changedTouches.length; i++) {
                var t = e.changedTouches[i];
                var rect = canvas.getBoundingClientRect();
                var tx = t.clientX - rect.left;
                var ty = t.clientY - rect.top;
                var cw = rect.width;
                var ch = rect.height;

                /* Seed bar area: full width, bottom 50px */
                if (ty > ch - 50) {
                    continue;
                }

                /* Joystick: bottom-left area, above seed bar */
                if (tx < cw * 0.4 && ty > ch * 0.55 && ty < ch - 50) {
                    self._touchId = t.identifier;
                    self._joystickActive = true;
                    self._joystickStartX = tx;
                    self._joystickStartY = ty;
                    self._joystickX = tx;
                    self._joystickY = ty;
                } else if (tx > cw * 0.6 && ty > ch * 0.55 && ty < ch - 50) {
                    /* Action button: bottom-right area, above seed bar */
                    self._actionTouchId = t.identifier;
                    self.actionPressed = true;
                }
            }
        }, { passive: false });

        canvas.addEventListener('touchmove', function(e) {
            e.preventDefault();
            for (var i = 0; i < e.changedTouches.length; i++) {
                var t = e.changedTouches[i];
                if (t.identifier === self._touchId) {
                    self._joystickX = t.clientX - canvas.getBoundingClientRect().left;
                    self._joystickY = t.clientY - canvas.getBoundingClientRect().top;
                }
            }
        }, { passive: false });

        canvas.addEventListener('touchend', function(e) {
            e.preventDefault();
            for (var i = 0; i < e.changedTouches.length; i++) {
                var t = e.changedTouches[i];
                if (t.identifier === self._touchId) {
                    self._touchId = null;
                    self._joystickActive = false;
                    self._joystickX = 0;
                    self._joystickY = 0;
                    self.dirX = 0;
                    self.dirY = 0;
                }
                if (t.identifier === self._actionTouchId) {
                    self._actionTouchId = null;
                    self.actionPressed = false;
                }
            }
        }, { passive: false });

        canvas.addEventListener('touchcancel', function(e) {
            self._touchId = null;
            self._joystickActive = false;
            self._joystickX = 0;
            self._joystickY = 0;
            self.dirX = 0;
            self.dirY = 0;
            self._actionTouchId = null;
            self.actionPressed = false;
        });
    },

    update: function() {
        this._prevAction = this.actionJustPressed;
        this.actionJustPressed = false;

        if (this._joystickActive) {
            var dx = this._joystickX - this._joystickStartX;
            var dy = this._joystickY - this._joystickStartY;
            var d = Math.sqrt(dx * dx + dy * dy);
            var maxR = 40;
            if (d > maxR) {
                dx = (dx / d) * maxR;
                dy = (dy / d) * maxR;
            }
            if (d > 8) {
                this.dirX = dx / maxR;
                this.dirY = dy / maxR;
            } else {
                this.dirX = 0;
                this.dirY = 0;
            }
        } else {
            this.dirX = 0;
            this.dirY = 0;
            if (this.keys['ArrowLeft'] || this.keys['a'] || this.keys['A']) this.dirX -= 1;
            if (this.keys['ArrowRight'] || this.keys['d'] || this.keys['D']) this.dirX += 1;
            if (this.keys['ArrowUp'] || this.keys['w'] || this.keys['W']) this.dirY -= 1;
            if (this.keys['ArrowDown'] || this.keys['s'] || this.keys['S']) this.dirY += 1;

            if (this.dirX !== 0 && this.dirY !== 0) {
                var inv = 1 / Math.sqrt(2);
                this.dirX *= inv;
                this.dirY *= inv;
            }
        }

        if ((this.keys[' '] || this.keys['e'] || this.keys['E'] || this.keys['Enter']) && !this._prevAction) {
            this.actionJustPressed = true;
        }
        if (this.actionPressed && !this._prevAction) {
            this.actionJustPressed = true;
        }
    },

    isJoystickActive: function() {
        return this._joystickActive;
    },

    getJoystickPos: function() {
        return {
            baseX: this._joystickStartX,
            baseY: this._joystickStartY,
            stickX: this._joystickX,
            stickY: this._joystickY
        };
    }
};

/* ============================================================
 * SECTION 5: CAMERA
 * ============================================================ */

var Camera = {
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0,
    viewW: 0,
    viewH: 0,
    mapW: 0,
    mapH: 0,

    init: function(viewW, viewH, mapW, mapH) {
        this.viewW = viewW;
        this.viewH = viewH;
        this.mapW = mapW;
        this.mapH = mapH;
    },

    follow: function(x, y) {
        this.targetX = x - this.viewW / 2;
        this.targetY = y - this.viewH / 2;
    },

    update: function() {
        this.x = lerp(this.x, this.targetX, 0.1);
        this.y = lerp(this.y, this.targetY, 0.1);
        this.x = clamp(this.x, 0, Math.max(0, this.mapW - this.viewW));
        this.y = clamp(this.y, 0, Math.max(0, this.mapH - this.viewH));
    },

    screenX: function(worldX) {
        return worldX - this.x;
    },

    screenY: function(worldY) {
        return worldY - this.y;
    },

    setBounds: function(mapW, mapH) {
        this.mapW = mapW;
        this.mapH = mapH;
    }
};

/* ============================================================
 * SECTION 6: SPRITE DRAWING FUNCTIONS
 * ============================================================ */

/* Pre-allocated temp objects to avoid GC in game loop */
var _spriteTemp = { frame: 0, dir: 0, x: 0, y: 0, time: 0 };

function drawShadow(ctx, x, y, w, h) {
    ctx.fillStyle = COLORS.shadow;
    ctx.beginPath();
    ctx.ellipse(x, y, w, h, 0, 0, Math.PI * 2);
    ctx.fill();
}

function drawPlayerSprite(ctx, x, y, dir, frame, time) {
    /* dir: 0=down, 1=left, 2=right, 3=up */
    /* frame: 0=stand, 1=walk-left, 2=walk-right */

    var bob = 0;
    if (frame === 1) bob = -1;
    else if (frame === 2) bob = 1;

    var sy = y + bob;

    /* Shadow */
    drawShadow(ctx, x, y + 2, 8, 3);

    /* Body (small) */
    ctx.fillStyle = COLORS.shirt;
    ctx.fillRect(x - 5, sy - 10, 10, 8);

    /* Shirt detail */
    ctx.fillStyle = COLORS.shirtDark;
    ctx.fillRect(x - 5, sy - 10, 10, 2);

    /* Pants */
    ctx.fillStyle = COLORS.pants;
    ctx.fillRect(x - 5, sy - 2, 10, 4);

    /* Legs */
    if (frame === 0) {
        ctx.fillStyle = COLORS.shoe;
        ctx.fillRect(x - 4, sy + 2, 3, 2);
        ctx.fillRect(x + 1, sy + 2, 3, 2);
    } else if (frame === 1) {
        ctx.fillStyle = COLORS.shoe;
        ctx.fillRect(x - 5, sy + 2, 3, 2);
        ctx.fillRect(x + 2, sy + 1, 3, 2);
    } else {
        ctx.fillStyle = COLORS.shoe;
        ctx.fillRect(x - 3, sy + 1, 3, 2);
        ctx.fillRect(x, sy + 2, 3, 2);
    }

    /* Head (big - Q版 style) */
    ctx.fillStyle = COLORS.skin;
    ctx.beginPath();
    ctx.arc(x, sy - 18, 10, 0, Math.PI * 2);
    ctx.fill();

    /* Face details based on direction */
    if (dir === 0) {
        /* Facing down */
        /* Eyes */
        ctx.fillStyle = COLORS.eye;
        ctx.fillRect(x - 4, sy - 20, 2, 3);
        ctx.fillRect(x + 2, sy - 20, 2, 3);
        /* Eye shine */
        ctx.fillStyle = COLORS.eyeWhite;
        ctx.fillRect(x - 4, sy - 20, 1, 1);
        ctx.fillRect(x + 2, sy - 20, 1, 1);
        /* Mouth */
        ctx.fillStyle = COLORS.mouth;
        ctx.fillRect(x - 1, sy - 15, 2, 1);
        /* Cheeks */
        ctx.fillStyle = COLORS.cheek;
        ctx.globalAlpha = 0.4;
        ctx.fillRect(x - 7, sy - 17, 3, 2);
        ctx.fillRect(x + 4, sy - 17, 3, 2);
        ctx.globalAlpha = 1.0;
        /* Hat */
        ctx.fillStyle = COLORS.hat;
        ctx.beginPath();
        ctx.arc(x, sy - 22, 11, Math.PI, 0);
        ctx.fill();
        ctx.fillRect(x - 13, sy - 22, 26, 3);
        /* Hat band */
        ctx.fillStyle = COLORS.hatBand;
        ctx.fillRect(x - 11, sy - 20, 22, 2);
    } else if (dir === 3) {
        /* Facing up */
        ctx.fillStyle = COLORS.hat;
        ctx.beginPath();
        ctx.arc(x, sy - 22, 11, Math.PI, 0);
        ctx.fill();
        ctx.fillRect(x - 13, sy - 22, 26, 3);
        ctx.fillStyle = COLORS.hatBand;
        ctx.fillRect(x - 11, sy - 20, 22, 2);
        /* Back of hair */
        ctx.fillStyle = COLORS.hair;
        ctx.beginPath();
        ctx.arc(x, sy - 18, 10, 0.3, Math.PI - 0.3);
        ctx.fill();
    } else {
        /* Facing left or right */
        var flip = (dir === 2) ? -1 : 1;
        /* Eye */
        ctx.fillStyle = COLORS.eye;
        ctx.fillRect(x + flip * 2, sy - 20, 2, 3);
        ctx.fillStyle = COLORS.eyeWhite;
        ctx.fillRect(x + flip * 2, sy - 20, 1, 1);
        /* Mouth */
        ctx.fillStyle = COLORS.mouth;
        ctx.fillRect(x + flip * 1, sy - 15, 2, 1);
        /* Cheek */
        ctx.fillStyle = COLORS.cheek;
        ctx.globalAlpha = 0.4;
        ctx.fillRect(x + flip * 4, sy - 17, 3, 2);
        ctx.globalAlpha = 1.0;
        /* Hat */
        ctx.fillStyle = COLORS.hat;
        ctx.beginPath();
        ctx.arc(x, sy - 22, 11, Math.PI, 0);
        ctx.fill();
        ctx.fillRect(x - 13, sy - 22, 26, 3);
        ctx.fillStyle = COLORS.hatBand;
        ctx.fillRect(x - 11, sy - 20, 22, 2);
    }
}

function drawNPCSprite(ctx, x, y, dir, frame, time) {
    /* NPC: 车如云 - Q版 female character */
    /* dir: 0=down, 1=left, 2=right, 3=up */
    /* frame: 0=stand, 1=walk-left, 2=walk-right */

    var bob = 0;
    if (frame === 1) bob = -1;
    else if (frame === 2) bob = 1;

    /* Idle breathing animation */
    var breathOffset = Math.sin(time * 0.003) * 0.8;

    var sy = y + bob + breathOffset;

    /* Shadow */
    drawShadow(ctx, x, y + 2, 8, 3);

    /* Long hair (behind body) */
    ctx.fillStyle = COLORS.npcHair;
    if (dir === 1 || dir === 0) {
        /* Hair flows to the left / behind */
        ctx.fillRect(x - 8, sy - 16, 4, 16);
        ctx.fillRect(x - 7, sy - 2, 3, 6);
    }
    if (dir === 2 || dir === 0) {
        ctx.fillRect(x + 4, sy - 16, 4, 16);
        ctx.fillRect(x + 4, sy - 2, 3, 6);
    }
    if (dir === 3) {
        ctx.fillRect(x - 8, sy - 16, 4, 18);
        ctx.fillRect(x + 4, sy - 16, 4, 18);
    }

    /* Body - purple/white outfit */
    ctx.fillStyle = COLORS.npcOutfit;
    ctx.fillRect(x - 5, sy - 10, 10, 8);

    /* White collar/trim */
    ctx.fillStyle = COLORS.npcOutfitLight;
    ctx.fillRect(x - 4, sy - 10, 8, 2);

    /* Skirt/lower */
    ctx.fillStyle = COLORS.npcOutfitDark;
    ctx.fillRect(x - 5, sy - 2, 10, 4);

    /* Legs */
    if (frame === 0) {
        ctx.fillStyle = COLORS.skin;
        ctx.fillRect(x - 3, sy + 2, 2, 2);
        ctx.fillRect(x + 1, sy + 2, 2, 2);
        ctx.fillStyle = COLORS.shoe;
        ctx.fillRect(x - 4, sy + 3, 3, 2);
        ctx.fillRect(x + 1, sy + 3, 3, 2);
    } else if (frame === 1) {
        ctx.fillStyle = COLORS.skin;
        ctx.fillRect(x - 4, sy + 2, 2, 2);
        ctx.fillRect(x + 2, sy + 1, 2, 2);
        ctx.fillStyle = COLORS.shoe;
        ctx.fillRect(x - 5, sy + 3, 3, 2);
        ctx.fillRect(x + 2, sy + 2, 3, 2);
    } else {
        ctx.fillStyle = COLORS.skin;
        ctx.fillRect(x - 2, sy + 1, 2, 2);
        ctx.fillRect(x, sy + 2, 2, 2);
        ctx.fillStyle = COLORS.shoe;
        ctx.fillRect(x - 3, sy + 2, 3, 2);
        ctx.fillRect(x, sy + 3, 3, 2);
    }

    /* Head (big - Q版) */
    ctx.fillStyle = COLORS.npcSkin;
    ctx.beginPath();
    ctx.arc(x, sy - 18, 10, 0, Math.PI * 2);
    ctx.fill();

    /* Hair on top */
    ctx.fillStyle = COLORS.npcHair;
    ctx.beginPath();
    ctx.arc(x, sy - 20, 11, Math.PI + 0.3, -0.3);
    ctx.fill();
    /* Bangs */
    ctx.fillRect(x - 9, sy - 22, 18, 5);
    /* Side hair */
    ctx.fillRect(x - 10, sy - 18, 3, 8);
    ctx.fillRect(x + 7, sy - 18, 3, 8);

    if (dir === 0) {
        /* Facing down - calm expression */
        /* Eyes - slightly narrower, calm */
        ctx.fillStyle = COLORS.eye;
        ctx.fillRect(x - 4, sy - 19, 2, 2);
        ctx.fillRect(x + 2, sy - 19, 2, 2);
        /* Eye shine */
        ctx.fillStyle = COLORS.eyeWhite;
        ctx.fillRect(x - 4, sy - 19, 1, 1);
        ctx.fillRect(x + 2, sy - 19, 1, 1);
        /* Subtle mouth */
        ctx.fillStyle = COLORS.mouth;
        ctx.fillRect(x - 1, sy - 14, 2, 1);
        /* Cheeks */
        ctx.fillStyle = COLORS.cheek;
        ctx.globalAlpha = 0.3;
        ctx.fillRect(x - 7, sy - 16, 3, 2);
        ctx.fillRect(x + 4, sy - 16, 3, 2);
        ctx.globalAlpha = 1.0;
    } else if (dir === 3) {
        /* Facing up - hair covers face mostly */
        ctx.fillStyle = COLORS.npcHair;
        ctx.fillRect(x - 8, sy - 20, 16, 6);
    } else {
        /* Facing left or right */
        var flip = (dir === 2) ? -1 : 1;
        ctx.fillStyle = COLORS.eye;
        ctx.fillRect(x + flip * 2, sy - 19, 2, 2);
        ctx.fillStyle = COLORS.eyeWhite;
        ctx.fillRect(x + flip * 2, sy - 19, 1, 1);
        ctx.fillStyle = COLORS.mouth;
        ctx.fillRect(x + flip * 1, sy - 14, 1, 1);
        ctx.fillStyle = COLORS.cheek;
        ctx.globalAlpha = 0.3;
        ctx.fillRect(x + flip * 4, sy - 16, 3, 2);
        ctx.globalAlpha = 1.0;
    }
}

/* ============================================================
 * SECTION 7: TILE RENDERING
 * ============================================================ */

function drawTile(ctx, tileType, sx, sy, time) {
    switch (tileType) {
        case 0: /* grass */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            /* Grass detail */
            ctx.fillStyle = COLORS.grassLight;
            ctx.fillRect(sx + 4, sy + 8, 2, 3);
            ctx.fillRect(sx + 20, sy + 4, 2, 3);
            ctx.fillRect(sx + 12, sy + 22, 2, 3);
            break;

        case 1: /* path */
            ctx.fillStyle = COLORS.path;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.pathDark;
            ctx.fillRect(sx + 2, sy + 2, 4, 4);
            ctx.fillRect(sx + 18, sy + 14, 4, 4);
            ctx.fillRect(sx + 10, sy + 24, 3, 3);
            break;

        case 2: /* soil */
            ctx.fillStyle = COLORS.soil;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.soilDark;
            for (var i = 0; i < 3; i++) {
                ctx.fillRect(sx + 4 + i * 10, sy + 6 + (i % 2) * 10, 6, 2);
                ctx.fillRect(sx + 8 + (i % 2) * 8, sy + 14 + i * 5, 4, 2);
            }
            break;

        case 3: /* fence-top */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 4, sy + 2, 24, 6);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 4, sy, 4, 10);
            ctx.fillRect(sx + 24, sy, 4, 10);
            break;

        case 4: /* fence-bottom */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 4, sy + 24, 24, 6);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 4, sy + 22, 4, 10);
            ctx.fillRect(sx + 24, sy + 22, 4, 10);
            break;

        case 5: /* fence-left */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 2, sy + 4, 6, 24);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx, sy + 4, 10, 4);
            ctx.fillRect(sx, sy + 24, 10, 4);
            break;

        case 6: /* fence-right */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 24, sy + 4, 6, 24);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 22, sy + 4, 10, 4);
            ctx.fillRect(sx + 22, sy + 24, 10, 4);
            break;

        case 7: /* house-wall */
            ctx.fillStyle = COLORS.wall;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.wallDark;
            ctx.fillRect(sx, sy + 30, TILE, 2);
            ctx.fillRect(sx + 15, sy, 2, TILE);
            break;

        case 8: /* house-door */
            ctx.fillStyle = COLORS.wall;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.woodDark;
            ctx.fillRect(sx + 8, sy + 4, 16, 28);
            ctx.fillStyle = COLORS.wood;
            ctx.fillRect(sx + 10, sy + 6, 12, 24);
            /* Door knob */
            ctx.fillStyle = COLORS.purple;
            ctx.fillRect(sx + 18, sy + 16, 3, 3);
            break;

        case 9: /* fence-corner-tl */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 4, sy + 2, 28, 6);
            ctx.fillRect(sx + 2, sy + 4, 6, 28);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 2, sy + 2, 6, 6);
            break;

        case 10: /* fence-corner-tr */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx, sy + 2, 28, 6);
            ctx.fillRect(sx + 24, sy + 4, 6, 28);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 24, sy + 2, 6, 6);
            break;

        case 11: /* fence-corner-bl */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 4, sy + 24, 28, 6);
            ctx.fillRect(sx + 2, sy, 6, 28);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 2, sy + 24, 6, 6);
            break;

        case 12: /* fence-corner-br */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx, sy + 24, 28, 6);
            ctx.fillRect(sx + 24, sy, 6, 28);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 24, sy + 24, 6, 6);
            break;

        case 13: /* flower-red */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            drawFlower(ctx, sx + 16, sy + 16, COLORS.flower1, time);
            break;

        case 14: /* flower-yellow */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            drawFlower(ctx, sx + 16, sy + 16, COLORS.flower2, time);
            break;

        case 15: /* tree */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            /* Trunk */
            ctx.fillStyle = COLORS.trunk;
            ctx.fillRect(sx + 13, sy + 16, 6, 16);
            /* Leaves */
            ctx.fillStyle = COLORS.leaf;
            ctx.beginPath();
            ctx.arc(sx + 16, sy + 12, 12, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = COLORS.grassLight;
            ctx.beginPath();
            ctx.arc(sx + 12, sy + 10, 6, 0, Math.PI * 2);
            ctx.fill();
            break;

        case 17: /* concrete */
            ctx.fillStyle = COLORS.concrete;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.concreteDark;
            ctx.fillRect(sx, sy, TILE, 1);
            ctx.fillRect(sx, sy, 1, TILE);
            break;

        case 18: /* railing */
            ctx.fillStyle = COLORS.concrete;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.railing;
            ctx.fillRect(sx + 14, sy + 2, 4, 28);
            ctx.fillRect(sx + 2, sy + 8, 28, 3);
            ctx.fillRect(sx + 2, sy + 22, 28, 3);
            break;

        case 19: /* bench */
            ctx.fillStyle = COLORS.concrete;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.bench;
            ctx.fillRect(sx + 2, sy + 10, 28, 4);
            ctx.fillRect(sx + 2, sy + 18, 28, 4);
            ctx.fillStyle = COLORS.benchDark;
            ctx.fillRect(sx + 4, sy + 14, 3, 10);
            ctx.fillRect(sx + 25, sy + 14, 3, 10);
            break;

        case 20: /* potted-plant */
            ctx.fillStyle = COLORS.concrete;
            ctx.fillRect(sx, sy, TILE, TILE);
            /* Pot */
            ctx.fillStyle = COLORS.pot;
            ctx.fillRect(sx + 10, sy + 18, 12, 12);
            ctx.fillRect(sx + 8, sy + 16, 16, 4);
            /* Plant */
            ctx.fillStyle = COLORS.potGreen;
            ctx.beginPath();
            ctx.arc(sx + 16, sy + 12, 8, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = COLORS.grassLight;
            ctx.beginPath();
            ctx.arc(sx + 14, sy + 10, 4, 0, Math.PI * 2);
            ctx.fill();
            break;

        case 21: /* clothesline */
            ctx.fillStyle = COLORS.concrete;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.clothesline;
            ctx.fillRect(sx, sy + 6, TILE, 2);
            /* Hanging items */
            var colors = [COLORS.cloth1, COLORS.cloth2, COLORS.cloth3, COLORS.cloth4];
            for (var ci = 0; ci < 4; ci++) {
                ctx.fillStyle = colors[ci];
                var swing = Math.sin(time * 0.002 + ci * 1.5) * 2;
                ctx.fillRect(sx + 2 + ci * 8 + swing, sy + 8, 5, 10);
            }
            break;

        case 22: /* building-bg (skyline) */
            ctx.fillStyle = '#87CEEB';
            ctx.fillRect(sx, sy, TILE, TILE);
            /* Simple building rectangles */
            ctx.fillStyle = '#607080';
            ctx.fillRect(sx + 2, sy + 8, 12, 24);
            ctx.fillStyle = '#506070';
            ctx.fillRect(sx + 16, sy + 14, 12, 18);
            /* Windows */
            ctx.fillStyle = '#FFE88C';
            ctx.fillRect(sx + 4, sy + 12, 3, 3);
            ctx.fillRect(sx + 9, sy + 12, 3, 3);
            ctx.fillRect(sx + 4, sy + 20, 3, 3);
            ctx.fillRect(sx + 9, sy + 20, 3, 3);
            ctx.fillRect(sx + 18, sy + 18, 3, 3);
            ctx.fillRect(sx + 23, sy + 18, 3, 3);
            break;

        case 23: /* cafe-floor */
            ctx.fillStyle = COLORS.cafeFloor;
            ctx.fillRect(sx, sy, TILE, TILE);
            /* Wood plank lines */
            ctx.fillStyle = COLORS.cafeFloorDark;
            ctx.fillRect(sx, sy + 15, TILE, 1);
            ctx.fillRect(sx + 15, sy, 1, TILE);
            break;

        case 24: /* counter */
            ctx.fillStyle = COLORS.cafeFloor;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.counter;
            ctx.fillRect(sx, sy + 4, TILE, 24);
            ctx.fillStyle = COLORS.counterTop;
            ctx.fillRect(sx, sy + 2, TILE, 6);
            break;

        case 25: /* table */
            ctx.fillStyle = COLORS.cafeFloor;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.wood;
            ctx.fillRect(sx + 4, sy + 10, 24, 14);
            ctx.fillStyle = COLORS.woodDark;
            ctx.fillRect(sx + 4, sy + 10, 24, 2);
            ctx.fillRect(sx + 12, sy + 24, 8, 6);
            break;

        case 26: /* chair */
            ctx.fillStyle = COLORS.cafeFloor;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.wood;
            ctx.fillRect(sx + 8, sy + 12, 16, 12);
            ctx.fillStyle = COLORS.woodDark;
            ctx.fillRect(sx + 8, sy + 4, 3, 20);
            break;

        case 27: /* menu-board */
            ctx.fillStyle = COLORS.cafeFloor;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.menu;
            ctx.fillRect(sx + 4, sy + 2, 24, 28);
            ctx.fillStyle = COLORS.menuText;
            ctx.font = '6px monospace';
            ctx.fillText('MENU', sx + 8, sy + 10);
            ctx.fillRect(sx + 8, sy + 14, 16, 1);
            ctx.fillRect(sx + 8, sy + 18, 12, 1);
            ctx.fillRect(sx + 8, sy + 22, 14, 1);
            break;

        case 28: /* barista area */
            ctx.fillStyle = COLORS.cafeFloor;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.counter;
            ctx.fillRect(sx, sy + 8, TILE, 20);
            ctx.fillStyle = COLORS.counterTop;
            ctx.fillRect(sx, sy + 6, TILE, 6);
            /* Coffee machine */
            ctx.fillStyle = '#555';
            ctx.fillRect(sx + 4, sy + 2, 10, 8);
            ctx.fillStyle = '#777';
            ctx.fillRect(sx + 6, sy, 6, 4);
            break;

        case 29: /* exit zone (drawn as subtle arrow) */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.path;
            ctx.fillRect(sx + 8, sy + 4, 16, 24);
            /* Arrow indicator */
            ctx.fillStyle = COLORS.purpleLight;
            ctx.globalAlpha = 0.4 + Math.sin(time * 0.004) * 0.2;
            ctx.beginPath();
            ctx.moveTo(sx + 16, sy + 2);
            ctx.lineTo(sx + 24, sy + 14);
            ctx.lineTo(sx + 16, sy + 10);
            ctx.fill();
            ctx.globalAlpha = 1.0;
            break;

        case 30: /* flower-purple */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            drawFlower(ctx, sx + 16, sy + 16, COLORS.flower3, time);
            break;

        case 31: /* flower-orange */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            drawFlower(ctx, sx + 16, sy + 16, COLORS.flower4, time);
            break;

        case 33: /* fence-post-top */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 4, sy + 2, 24, 6);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 13, sy, 6, 10);
            break;

        case 34: /* fence-post-bottom */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 4, sy + 24, 24, 6);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 13, sy + 22, 6, 10);
            break;

        case 35: /* fence-post-left */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 2, sy + 4, 6, 24);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx, sy + 13, 10, 6);
            break;

        case 36: /* fence-post-right */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.fence;
            ctx.fillRect(sx + 24, sy + 4, 6, 24);
            ctx.fillStyle = COLORS.fencePost;
            ctx.fillRect(sx + 22, sy + 13, 10, 6);
            break;

        case 37: /* lamp */
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = '#555';
            ctx.fillRect(sx + 14, sy + 8, 4, 22);
            ctx.fillStyle = '#FFE88C';
            ctx.beginPath();
            ctx.arc(sx + 16, sy + 8, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = 'rgba(255,232,140,0.15)';
            ctx.beginPath();
            ctx.arc(sx + 16, sy + 8, 16, 0, Math.PI * 2);
            ctx.fill();
            break;

        case 38: /* sky background */
            var grad = ctx.createLinearGradient(sx, sy, sx, sy + TILE);
            grad.addColorStop(0, '#4A90D9');
            grad.addColorStop(1, '#87CEEB');
            ctx.fillStyle = grad;
            ctx.fillRect(sx, sy, TILE, TILE);
            break;

        case 39: /* rooftop edge */
            ctx.fillStyle = COLORS.concrete;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.railing;
            ctx.fillRect(sx, sy, TILE, 4);
            ctx.fillStyle = COLORS.concreteDark;
            ctx.fillRect(sx, sy + 28, TILE, 4);
            break;

        case 40: /* farm-soil (plantable) - darker brown with furrow lines */
            ctx.fillStyle = '#5C3D1A';
            ctx.fillRect(sx, sy, TILE, TILE);
            /* Furrow lines */
            ctx.fillStyle = '#4A2E12';
            ctx.fillRect(sx + 2, sy + 8, 28, 2);
            ctx.fillRect(sx + 2, sy + 16, 28, 2);
            ctx.fillRect(sx + 2, sy + 24, 28, 2);
            /* Soil texture dots */
            ctx.fillStyle = '#6B4F22';
            ctx.fillRect(sx + 6, sy + 4, 2, 2);
            ctx.fillRect(sx + 18, sy + 12, 2, 2);
            ctx.fillRect(sx + 10, sy + 20, 2, 2);
            ctx.fillRect(sx + 24, sy + 4, 2, 2);
            /* Border highlight */
            ctx.strokeStyle = '#7A5A30';
            ctx.lineWidth = 1;
            ctx.strokeRect(sx + 0.5, sy + 0.5, TILE - 1, TILE - 1);
            break;

        case 41: /* barn-wall */
            ctx.fillStyle = COLORS.barn;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.barnDark;
            ctx.fillRect(sx, sy + 30, TILE, 2);
            ctx.fillRect(sx + 15, sy, 2, TILE);
            /* Wood plank detail */
            ctx.fillStyle = '#7A3B10';
            ctx.fillRect(sx, sy + 10, TILE, 1);
            ctx.fillRect(sx, sy + 20, TILE, 1);
            break;

        case 42: /* barn-door */
            ctx.fillStyle = COLORS.barn;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = COLORS.barnDoor;
            ctx.fillRect(sx + 4, sy + 2, 12, 30);
            ctx.fillRect(sx + 16, sy + 2, 12, 30);
            /* Door handles */
            ctx.fillStyle = '#D4A574';
            ctx.fillRect(sx + 13, sy + 16, 3, 3);
            ctx.fillRect(sx + 16, sy + 16, 3, 3);
            /* Cross beam */
            ctx.fillStyle = '#8B4513';
            ctx.fillRect(sx + 4, sy + 14, 24, 3);
            break;

        case 43: /* barn-roof */
            ctx.fillStyle = COLORS.barnRoof;
            ctx.fillRect(sx, sy, TILE, TILE);
            ctx.fillStyle = '#8B4513';
            ctx.fillRect(sx, sy + 28, TILE, 4);
            /* Shingle pattern */
            ctx.fillStyle = '#955530';
            ctx.fillRect(sx + 4, sy + 4, 10, 8);
            ctx.fillRect(sx + 18, sy + 4, 10, 8);
            ctx.fillRect(sx + 12, sy + 14, 10, 8);
            break;

        default:
            ctx.fillStyle = COLORS.grass;
            ctx.fillRect(sx, sy, TILE, TILE);
            break;
    }
}

function drawFlower(ctx, cx, cy, color, time) {
    /* Stem */
    ctx.fillStyle = COLORS.leaf;
    ctx.fillRect(cx - 1, cy, 2, 10);
    /* Petals */
    var sway = Math.sin(time * 0.003) * 1;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(cx + sway, cy - 2, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = COLORS.flower2;
    ctx.beginPath();
    ctx.arc(cx + sway, cy - 2, 2, 0, Math.PI * 2);
    ctx.fill();
}

/* ============================================================
 * SECTION 8: WEATHER SYSTEM
 * ============================================================ */

var Weather = {
    type: 'sunny',
    rainDrops: [],
    clouds: [],
    sunAngle: 0,

    init: function() {
        /* Pre-allocate rain drops */
        this.rainDrops = [];
        for (var i = 0; i < 80; i++) {
            this.rainDrops.push({ x: 0, y: 0, speed: 0, len: 0 });
        }
        this._resetRain();

        /* Pre-allocate clouds */
        this.clouds = [];
        for (var j = 0; j < 5; j++) {
            this.clouds.push({ x: 0, y: 0, w: 0, speed: 0 });
        }
        this._resetClouds();
    },

    _resetRain: function() {
        for (var i = 0; i < this.rainDrops.length; i++) {
            this.rainDrops[i].x = Math.random() * 500;
            this.rainDrops[i].y = Math.random() * 800;
            this.rainDrops[i].speed = 4 + Math.random() * 4;
            this.rainDrops[i].len = 8 + Math.random() * 12;
        }
    },

    _resetClouds: function() {
        for (var i = 0; i < this.clouds.length; i++) {
            this.clouds[i].x = Math.random() * 500 - 100;
            this.clouds[i].y = 20 + Math.random() * 100;
            this.clouds[i].w = 60 + Math.random() * 80;
            this.clouds[i].speed = 0.2 + Math.random() * 0.3;
        }
    },

    update: function(dt) {
        this.sunAngle += 0.001 * dt;

        if (this.type === 'rainy') {
            for (var i = 0; i < this.rainDrops.length; i++) {
                var drop = this.rainDrops[i];
                drop.y += drop.speed * dt * 0.06;
                drop.x -= 0.5 * dt * 0.06;
                if (drop.y > 800) {
                    drop.y = -20;
                    drop.x = Math.random() * 500;
                }
            }
        }

        if (this.type === 'cloudy' || this.type === 'rainy') {
            for (var j = 0; j < this.clouds.length; j++) {
                var c = this.clouds[j];
                c.x += c.speed * dt * 0.06;
                if (c.x > 500) {
                    c.x = -c.w - 20;
                    c.y = 20 + Math.random() * 100;
                }
            }
        }
    },

    draw: function(ctx, w, h) {
        if (this.type === 'sunny') {
            this._drawSunny(ctx, w, h);
        } else if (this.type === 'rainy') {
            this._drawRainy(ctx, w, h);
        } else if (this.type === 'cloudy') {
            this._drawCloudy(ctx, w, h);
        }
    },

    _drawSunny: function(ctx, w, h) {
        ctx.save();
        ctx.globalAlpha = 0.06;
        ctx.fillStyle = '#FFF8DC';
        for (var i = 0; i < 5; i++) {
            var angle = this.sunAngle + i * 0.4;
            var rx = w * 0.8;
            var ry = 0;
            ctx.save();
            ctx.translate(rx, ry);
            ctx.rotate(angle);
            ctx.fillRect(-15, 0, 30, h * 1.2);
            ctx.restore();
        }
        ctx.restore();
    },

    _drawRainy: function(ctx, w, h) {
        /* Dark overlay */
        ctx.fillStyle = 'rgba(40,50,70,0.15)';
        ctx.fillRect(0, 0, w, h);

        /* Clouds */
        this._drawCloudShapes(ctx, w, 'rgba(80,85,95,0.5)');

        /* Rain drops */
        ctx.strokeStyle = COLORS.rainDrop;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (var i = 0; i < this.rainDrops.length; i++) {
            var d = this.rainDrops[i];
            ctx.moveTo(d.x, d.y);
            ctx.lineTo(d.x - 2, d.y + d.len);
        }
        ctx.stroke();
    },

    _drawCloudy: function(ctx, w, h) {
        this._drawCloudShapes(ctx, w, COLORS.cloudShadow);
    },

    _drawCloudShapes: function(ctx, w, color) {
        ctx.fillStyle = color;
        for (var i = 0; i < this.clouds.length; i++) {
            var c = this.clouds[i];
            ctx.beginPath();
            ctx.ellipse(c.x, c.y, c.w * 0.5, 16, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.ellipse(c.x - c.w * 0.2, c.y + 5, c.w * 0.3, 12, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.ellipse(c.x + c.w * 0.25, c.y + 3, c.w * 0.35, 14, 0, 0, Math.PI * 2);
            ctx.fill();
        }
    }
};

/* ============================================================
 * SECTION 9: DAY/NIGHT CYCLE
 * ============================================================ */

var DayNight = {
    hour: 10,
    overlayAlpha: 0,

    update: function() {
        /* Calculate overlay alpha based on hour */
        /* 6-8: dawn (0.15 -> 0), 8-17: day (0), 17-20: dusk (0 -> 0.3), 20-5: night (0.3-0.4) */
        var h = this.hour;
        if (h >= 8 && h < 17) {
            this.overlayAlpha = 0;
        } else if (h >= 6 && h < 8) {
            this.overlayAlpha = lerp(0.15, 0, (h - 6) / 2);
        } else if (h >= 17 && h < 20) {
            this.overlayAlpha = lerp(0, 0.3, (h - 17) / 3);
        } else if (h >= 20 || h < 5) {
            this.overlayAlpha = 0.35;
        } else {
            /* 5-6 */
            this.overlayAlpha = lerp(0.35, 0.15, (h - 5));
        }
    },

    draw: function(ctx, w, h) {
        if (this.overlayAlpha > 0.01) {
            ctx.fillStyle = COLORS.nightOverlay + this.overlayAlpha + ')';
            ctx.fillRect(0, 0, w, h);
        }
    }
};

/* ============================================================
 * SECTION 10: DIALOGUE SYSTEM
 * ============================================================ */

var Dialogue = {
    active: false,
    name: '',
    text: '',
    displayedText: '',
    charIndex: 0,
    charTimer: 0,
    charSpeed: 40,
    portrait: null,
    onDismiss: null,

    show: function(name, text, portrait, onDismiss) {
        this.active = true;
        this.name = name;
        this.text = text;
        this.displayedText = '';
        this.charIndex = 0;
        this.charTimer = 0;
        this.portrait = portrait || null;
        this.onDismiss = onDismiss || null;
    },

    dismiss: function() {
        if (this.active && this.onDismiss) {
            this.onDismiss();
        }
        this.active = false;
    },

    update: function(dt) {
        if (!this.active) return;
        if (this.charIndex < this.text.length) {
            this.charTimer += dt;
            while (this.charTimer >= this.charSpeed && this.charIndex < this.text.length) {
                this.charTimer -= this.charSpeed;
                this.charIndex++;
                this.displayedText = this.text.substring(0, this.charIndex);
            }
        }
    },

    advance: function() {
        if (!this.active) return;
        if (this.charIndex < this.text.length) {
            this.charIndex = this.text.length;
            this.displayedText = this.text;
        } else {
            this.dismiss();
        }
    },

    draw: function(ctx, w, h) {
        if (!this.active) return;

        var boxH = 100;
        var boxY = h - boxH - 60; /* Above seed bar */
        var boxX = 10;
        var boxW = w - 20;

        /* Background */
        ctx.fillStyle = COLORS.dialogueBg;
        ctx.beginPath();
        ctx.roundRect(boxX, boxY, boxW, boxH, 12);
        ctx.fill();

        /* Border */
        ctx.strokeStyle = COLORS.purple;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(boxX, boxY, boxW, boxH, 12);
        ctx.stroke();

        /* Portrait area */
        var portraitX = boxX + 12;
        var portraitY = boxY + 12;
        var portraitSize = 60;

        if (this.portrait) {
            /* Draw portrait */
            ctx.save();
            ctx.beginPath();
            ctx.arc(portraitX + portraitSize / 2, portraitY + portraitSize / 2, portraitSize / 2, 0, Math.PI * 2);
            ctx.clip();
            ctx.drawImage(this.portrait, portraitX, portraitY, portraitSize, portraitSize);
            ctx.restore();
            /* Portrait border */
            ctx.strokeStyle = COLORS.purpleLight;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(portraitX + portraitSize / 2, portraitY + portraitSize / 2, portraitSize / 2, 0, Math.PI * 2);
            ctx.stroke();
        } else {
            /* Draw NPC mini portrait */
            ctx.fillStyle = COLORS.purpleDark;
            ctx.beginPath();
            ctx.arc(portraitX + portraitSize / 2, portraitY + portraitSize / 2, portraitSize / 2, 0, Math.PI * 2);
            ctx.fill();
            drawNPCSprite(ctx, portraitX + portraitSize / 2, portraitY + portraitSize / 2 + 10, 0, 0, 0);
        }

        /* Name */
        var textX = portraitX + portraitSize + 12;
        ctx.fillStyle = COLORS.dialogueName;
        ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(this.name, textX, boxY + 24);

        /* Text */
        ctx.fillStyle = COLORS.dialogueText;
        ctx.font = '13px -apple-system, BlinkMacSystemFont, sans-serif';
        /* Word wrap */
        var maxW = boxW - (portraitSize + 48);
        var lines = this._wrapText(ctx, this.displayedText, maxW);
        for (var i = 0; i < lines.length; i++) {
            ctx.fillText(lines[i], textX, boxY + 46 + i * 18);
        }

        /* Advance indicator */
        if (this.charIndex >= this.text.length) {
            var blink = Math.sin(Date.now() * 0.005) > 0;
            if (blink) {
                ctx.fillStyle = COLORS.dialogueText;
                ctx.font = '10px -apple-system, sans-serif';
                ctx.fillText('▼', boxX + boxW - 24, boxY + boxH - 12);
            }
        }
    },

    _wrapText: function(ctx, text, maxW) {
        var lines = [];
        var line = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text[i];
            var test = line + ch;
            if (ctx.measureText(test).width > maxW && line.length > 0) {
                lines.push(line);
                line = ch;
            } else {
                line = test;
            }
        }
        if (line) lines.push(line);
        return lines;
    }
};

/* ============================================================
 * SECTION 11: SCENE TRANSITION
 * ============================================================ */

var Transition = {
    active: false,
    phase: 'none',
    alpha: 0,
    speed: 0.04,
    callback: null,

    start: function(callback) {
        this.active = true;
        this.phase = 'fadeOut';
        this.alpha = 0;
        this.callback = callback;
    },

    update: function(dt) {
        if (!this.active) return;

        if (this.phase === 'fadeOut') {
            this.alpha += this.speed * dt * 0.06;
            if (this.alpha >= 1) {
                this.alpha = 1;
                this.phase = 'fadeIn';
                if (this.callback) {
                    this.callback();
                    this.callback = null;
                }
            }
        } else if (this.phase === 'fadeIn') {
            this.alpha -= this.speed * dt * 0.06;
            if (this.alpha <= 0) {
                this.alpha = 0;
                this.active = false;
                this.phase = 'none';
            }
        }
    },

    draw: function(ctx, w, h) {
        if (!this.active) return;
        ctx.fillStyle = 'rgba(0,0,0,' + this.alpha + ')';
        ctx.fillRect(0, 0, w, h);
    }
};

/* ============================================================
 * SECTION 12: VIRTUAL JOYSTICK RENDERER
 * ============================================================ */

var JoystickRenderer = {
    draw: function(ctx, canvasW, canvasH) {
        if (!isTouchDevice()) return;

        /* Position joystick and action button above the seed bar (50px tall) */
        var baseX = 70;
        var baseY = canvasH - 60 - 50; /* 60px from bottom of seed bar */
        var baseR = 45;

        /* Base circle */
        ctx.fillStyle = 'rgba(123,63,160,0.15)';
        ctx.beginPath();
        ctx.arc(baseX, baseY, baseR, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(123,63,160,0.3)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(baseX, baseY, baseR, 0, Math.PI * 2);
        ctx.stroke();

        /* Stick */
        var pos = Input.getJoystickPos();
        var stickX = baseX;
        var stickY = baseY;
        if (Input.isJoystickActive()) {
            var dx = pos.stickX - pos.baseX;
            var dy = pos.stickY - pos.baseY;
            var d = Math.sqrt(dx * dx + dy * dy);
            var maxR = 30;
            if (d > maxR) {
                stickX = baseX + (dx / d) * maxR;
                stickY = baseY + (dy / d) * maxR;
            } else {
                stickX = baseX + dx;
                stickY = baseY + dy;
            }
        }

        ctx.fillStyle = 'rgba(123,63,160,0.4)';
        ctx.beginPath();
        ctx.arc(stickX, stickY, 20, 0, Math.PI * 2);
        ctx.fill();

        /* Action button */
        var btnX = canvasW - 70;
        var btnY = canvasH - 60 - 50; /* 60px from bottom of seed bar */
        var btnR = 28;

        ctx.fillStyle = 'rgba(123,63,160,0.2)';
        ctx.beginPath();
        ctx.arc(btnX, btnY, btnR, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(123,63,160,0.4)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(btnX, btnY, btnR, 0, Math.PI * 2);
        ctx.stroke();

        /* Action icon */
        ctx.fillStyle = 'rgba(123,63,160,0.6)';
        ctx.font = 'bold 16px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('A', btnX, btnY);
        ctx.textAlign = 'start';
        ctx.textBaseline = 'alphabetic';
    }
};

/* ============================================================
 * SECTION 13: SEED SELECTION BAR
 * ============================================================ */

var SeedBar = {
    selectedSeedId: null,
    seedCounts: {},

    init: function() {
        this.selectedSeedId = null;
        this.seedCounts = {};
        for (var i = 0; i < SEEDS.length; i++) {
            this.seedCounts[SEEDS[i].id] = 99;
        }
    },

    getSelectedSeedId: function() {
        return this.selectedSeedId;
    },

    setSelectedSeedId: function(seedId) {
        this.selectedSeedId = seedId;
    },

    getSeedData: function(seedId) {
        for (var i = 0; i < SEEDS.length; i++) {
            if (SEEDS[i].id === seedId) return SEEDS[i];
        }
        return null;
    },

    getCount: function(seedId) {
        return this.seedCounts[seedId] || 0;
    },

    addCount: function(seedId, amount) {
        if (this.seedCounts[seedId] === undefined) this.seedCounts[seedId] = 0;
        this.seedCounts[seedId] += (amount || 1);
    },

    consumeSeed: function(seedId) {
        if (this.seedCounts[seedId] && this.seedCounts[seedId] > 0) {
            this.seedCounts[seedId]--;
            return true;
        }
        return false;
    },

    handleClick: function(canvasX, canvasY, canvasW, canvasH) {
        var barY = canvasH - 50;
        if (canvasY < barY) return false;

        var slotW = canvasW / SEEDS.length;
        var slotIndex = Math.floor(canvasX / slotW);
        if (slotIndex < 0 || slotIndex >= SEEDS.length) return false;

        this.selectedSeedId = SEEDS[slotIndex].id;
        return true;
    },

    draw: function(ctx, canvasW, canvasH) {
        var barY = canvasH - 50;
        var barH = 50;
        var slotW = canvasW / SEEDS.length;

        /* Semi-transparent dark background */
        ctx.fillStyle = 'rgba(20,10,30,0.85)';
        ctx.fillRect(0, barY, canvasW, barH);

        /* Top border line */
        ctx.fillStyle = 'rgba(123,63,160,0.4)';
        ctx.fillRect(0, barY, canvasW, 2);

        /* Draw each seed slot */
        for (var i = 0; i < SEEDS.length; i++) {
            var seed = SEEDS[i];
            var sx = i * slotW;
            var isSelected = (this.selectedSeedId === seed.id);

            /* Selected highlight */
            if (isSelected) {
                ctx.fillStyle = 'rgba(123,63,160,0.5)';
                ctx.fillRect(sx + 2, barY + 4, slotW - 4, barH - 6);
                ctx.strokeStyle = '#A86BC8';
                ctx.lineWidth = 2;
                ctx.strokeRect(sx + 2, barY + 4, slotW - 4, barH - 6);
            }

            /* Emoji */
            ctx.font = '18px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(seed.emoji, sx + slotW / 2, barY + 18);

            /* Name */
            ctx.fillStyle = isSelected ? '#FFFFFF' : '#CCCCCC';
            ctx.font = '9px -apple-system, BlinkMacSystemFont, sans-serif';
            ctx.fillText(seed.name, sx + slotW / 2, barY + 34);

            /* Count */
            ctx.fillStyle = isSelected ? '#FFD93D' : '#999999';
            ctx.font = '8px -apple-system, sans-serif';
            ctx.fillText('x' + (this.seedCounts[seed.id] || 0), sx + slotW / 2, barY + 45);

            ctx.textAlign = 'start';
            ctx.textBaseline = 'alphabetic';
        }
    }
};

/* ============================================================
 * SECTION 14: CROP SYSTEM
 * ============================================================ */

var CropSystem = {
    crops: {}, /* key: "col,row" -> { seedId, plantedAt, growthStage } */

    init: function() {
        this.crops = {};
    },

    _key: function(col, row) {
        return col + ',' + row;
    },

    plantCrop: function(col, row, seedId) {
        this.crops[this._key(col, row)] = {
            seedId: seedId,
            plantedAt: Date.now(),
            growthStage: 0
        };
    },

    getCrop: function(col, row) {
        return this.crops[this._key(col, row)] || null;
    },

    removeCrop: function(col, row) {
        delete this.crops[this._key(col, row)];
    },

    hasCrop: function(col, row) {
        return !!this.crops[this._key(col, row)];
    },

    updateGrowth: function() {
        var now = Date.now();
        var keys = Object.keys(this.crops);
        for (var i = 0; i < keys.length; i++) {
            var crop = this.crops[keys[i]];
            var elapsed = now - crop.plantedAt;
            var progress = elapsed / CROP_GROW_TIME;
            if (progress < 0.25) {
                crop.growthStage = 0;
            } else if (progress < 0.5) {
                crop.growthStage = 1;
            } else if (progress < 1.0) {
                crop.growthStage = 2;
            } else {
                crop.growthStage = 3;
            }
        }
    },

    isReady: function(col, row) {
        var crop = this.crops[this._key(col, row)];
        if (!crop) return false;
        return crop.growthStage >= 3;
    },

    getTimeRemaining: function(col, row) {
        var crop = this.crops[this._key(col, row)];
        if (!crop) return 0;
        var elapsed = Date.now() - crop.plantedAt;
        var remaining = CROP_GROW_TIME - elapsed;
        return remaining > 0 ? Math.ceil(remaining / 1000) : 0;
    },

    drawCropOnTile: function(ctx, sx, sy, col, row) {
        var crop = this.getCrop(col, row);
        if (!crop) return;

        var seedData = SeedBar.getSeedData(crop.seedId);
        if (!seedData) return;

        var cx = sx + TILE / 2;
        var cy = sy + TILE / 2;

        if (crop.growthStage === 0) {
            /* Just planted: small dot */
            ctx.fillStyle = '#4A7A3A';
            ctx.beginPath();
            ctx.arc(cx, cy, 3, 0, Math.PI * 2);
            ctx.fill();
        } else if (crop.growthStage === 1) {
            /* Sprouting */
            ctx.font = '14px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('🌱', cx, cy);
            ctx.textAlign = 'start';
            ctx.textBaseline = 'alphabetic';
        } else if (crop.growthStage === 2) {
            /* Growing */
            ctx.font = '16px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('🌿', cx, cy);
            ctx.textAlign = 'start';
            ctx.textBaseline = 'alphabetic';
        } else if (crop.growthStage >= 3) {
            /* Ready to harvest - show crop emoji */
            ctx.font = '18px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(seedData.emoji, cx, cy);
            /* Sparkle effect */
            var sparkle = Math.sin(Date.now() * 0.005) * 0.3 + 0.7;
            ctx.globalAlpha = sparkle;
            ctx.font = '10px -apple-system, sans-serif';
            ctx.fillText('✨', cx + 8, cy - 8);
            ctx.globalAlpha = 1.0;
            ctx.textAlign = 'start';
            ctx.textBaseline = 'alphabetic';
        }
    }
};

/* ============================================================
 * SECTION 15: PLAYER
 * ============================================================ */

var Player = {
    x: 0,
    y: 0,
    dir: 0,
    frame: 0,
    animTimer: 0,
    animInterval: 180,
    moving: false,
    width: 16,
    height: 24,

    init: function(x, y) {
        this.x = x;
        this.y = y;
        this.dir = 0;
        this.frame = 0;
    },

    update: function(dt, solidCheck) {
        var ix = Input.dirX;
        var iy = Input.dirY;

        this.moving = (ix !== 0 || iy !== 0);

        if (this.moving) {
            /* Determine direction */
            if (Math.abs(ix) > Math.abs(iy)) {
                this.dir = ix < 0 ? 1 : 2;
            } else {
                this.dir = iy < 0 ? 3 : 0;
            }

            /* Calculate new position */
            var nx = this.x + ix * PLAYER_SPEED * dt * 0.06;
            var ny = this.y + iy * PLAYER_SPEED * dt * 0.06;

            /* Collision check */
            var canMoveX = !solidCheck(nx, this.y, this.width, this.height);
            var canMoveY = !solidCheck(this.x, ny, this.width, this.height);

            if (canMoveX) this.x = nx;
            if (canMoveY) this.y = ny;

            /* Pixel snapping */
            this.x = Math.round(this.x);
            this.y = Math.round(this.y);

            /* Animation */
            this.animTimer += dt;
            if (this.animTimer >= this.animInterval) {
                this.animTimer -= this.animInterval;
                this.frame = (this.frame + 1) % 3;
            }
        } else {
            this.frame = 0;
            this.animTimer = 0;
        }
    },

    draw: function(ctx, camX, camY) {
        var sx = this.x - camX;
        var sy = this.y - camY;
        drawPlayerSprite(ctx, sx, sy, this.dir, this.frame, Date.now());
    },

    getCenterX: function() { return this.x; },
    getCenterY: function() { return this.y - 10; }
};

/* ============================================================
 * SECTION 16: NPC SYSTEM
 * ============================================================ */

var NPC = {
    x: 0,
    y: 0,
    dir: 0,
    frame: 0,
    animTimer: 0,
    moving: false,
    showBubble: false,
    bubbleTimer: 0,
    width: 16,
    height: 24,
    waypoints: [],
    waypointIndex: 0,
    waitTimer: 0,
    waitDuration: 0,
    state: 'idle',
    name: '车如云',

    init: function(x, y) {
        this.x = x;
        this.y = y;
        this.dir = 0;
        this.frame = 0;
        this.waypoints = [];
        this.waypointIndex = 0;
        this.waitTimer = 0;
        this.waitDuration = 2000;
        this.state = 'idle';
    },

    setWaypoints: function(points) {
        this.waypoints = points;
        this.waypointIndex = 0;
        this.state = 'patrol';
    },

    update: function(dt, solidCheck, playerX, playerY) {
        /* Check proximity to player for interaction bubble */
        var d = dist(this.x, this.y, playerX, playerY);
        this.showBubble = d < INTERACT_DIST * 1.5;

        if (this.state === 'patrol' && this.waypoints.length > 0) {
            if (this.waitTimer > 0) {
                this.waitTimer -= dt;
                this.moving = false;
                this.frame = 0;
                if (this.waitTimer <= 0) {
                    this.waypointIndex = (this.waypointIndex + 1) % this.waypoints.length;
                }
                return;
            }

            var target = this.waypoints[this.waypointIndex];
            var tx = target.x * TILE + TILE / 2;
            var ty = target.y * TILE + TILE / 2;
            var dx = tx - this.x;
            var dy = ty - this.y;
            var dd = Math.sqrt(dx * dx + dy * dy);

            if (dd < 4) {
                this.waitTimer = this.waitDuration;
                this.moving = false;
                this.frame = 0;
                return;
            }

            this.moving = true;
            var speed = NPC_SPEED * dt * 0.06;
            var mx = (dx / dd) * speed;
            var my = (dy / dd) * speed;

            /* Direction */
            if (Math.abs(dx) > Math.abs(dy)) {
                this.dir = dx < 0 ? 1 : 2;
            } else {
                this.dir = dy < 0 ? 3 : 0;
            }

            var nx = this.x + mx;
            var ny = this.y + my;

            if (!solidCheck(nx, this.y, this.width, this.height)) this.x = nx;
            if (!solidCheck(this.x, ny, this.width, this.height)) this.y = ny;

            this.x = Math.round(this.x);
            this.y = Math.round(this.y);

            this.animTimer += dt;
            if (this.animTimer >= 200) {
                this.animTimer -= 200;
                this.frame = (this.frame + 1) % 3;
            }
        } else {
            this.moving = false;
            this.frame = 0;
        }
    },

    draw: function(ctx, camX, camY) {
        var sx = this.x - camX;
        var sy = this.y - camY;
        drawNPCSprite(ctx, sx, sy, this.dir, this.frame, Date.now());

        /* Interaction bubble */
        if (this.showBubble) {
            var bx = sx;
            var by = sy - 36;
            var bw = 22;
            var bh = 16;

            ctx.fillStyle = COLORS.bubble;
            ctx.beginPath();
            ctx.roundRect(bx - bw / 2, by - bh, bw, bh, 6);
            ctx.fill();
            ctx.strokeStyle = COLORS.bubbleBorder;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(bx - bw / 2, by - bh, bw, bh, 6);
            ctx.stroke();

            /* Triangle pointer */
            ctx.fillStyle = COLORS.bubble;
            ctx.beginPath();
            ctx.moveTo(bx - 4, by);
            ctx.lineTo(bx + 4, by);
            ctx.lineTo(bx, by + 5);
            ctx.closePath();
            ctx.fill();

            /* "!" icon */
            ctx.fillStyle = COLORS.purple;
            ctx.font = 'bold 11px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('!', bx, by - bh / 2);
            ctx.textAlign = 'start';
            ctx.textBaseline = 'alphabetic';
        }
    },

    getCenterX: function() { return this.x; },
    getCenterY: function() { return this.y - 10; }
};

/* ============================================================
 * SECTION 17: SCENE DECORATIONS (non-tile overlays)
 * ============================================================ */

var Decorations = {
    drawFarmDecorations: function(ctx, camX, camY, time) {
        /* House roof (above house tiles) */
        var hx = 3 * TILE - camX;
        var hy = 4 * TILE - camY;
        ctx.fillStyle = COLORS.roof;
        ctx.beginPath();
        ctx.moveTo(hx - 8, hy + 4);
        ctx.lineTo(hx + TILE * 3 + 8, hy + 4);
        ctx.lineTo(hx + TILE * 1.5, hy - 20);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = COLORS.roofDark;
        ctx.beginPath();
        ctx.moveTo(hx - 8, hy + 4);
        ctx.lineTo(hx + TILE * 1.5, hy - 20);
        ctx.lineTo(hx + TILE * 1.5, hy + 4);
        ctx.closePath();
        ctx.fill();

        /* Barn roof (above barn tiles) */
        var bx = 17 * TILE - camX;
        var by = 9 * TILE - camY;
        ctx.fillStyle = COLORS.barnRoof;
        ctx.beginPath();
        ctx.moveTo(bx - 8, by + 4);
        ctx.lineTo(bx + TILE * 3 + 8, by + 4);
        ctx.lineTo(bx + TILE * 1.5, by - 24);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = '#7A3B10';
        ctx.beginPath();
        ctx.moveTo(bx - 8, by + 4);
        ctx.lineTo(bx + TILE * 1.5, by - 24);
        ctx.lineTo(bx + TILE * 1.5, by + 4);
        ctx.closePath();
        ctx.fill();

        /* Path from player start to farm plots */
        /* The path tiles handle this, but add some decorative stones */
        var pathStones = [
            { x: 3, y: 14 }, { x: 5, y: 14 }, { x: 7, y: 14 },
            { x: 9, y: 14 }, { x: 11, y: 14 }, { x: 13, y: 14 }
        ];
        for (var pi = 0; pi < pathStones.length; pi++) {
            var ps = pathStones[pi];
            var psx = ps.x * TILE - camX;
            var psy = ps.y * TILE - camY;
            ctx.fillStyle = COLORS.pathDark;
            ctx.fillRect(psx + 10, psy + 12, 4, 3);
            ctx.fillRect(psx + 20, psy + 22, 3, 3);
        }

        /* Draw crops on farm soil tiles */
        if (typeof CropSystem !== 'undefined') {
            var sc = SCENES.farm;
            for (var row = 0; row < sc.height; row++) {
                for (var col = 0; col < sc.width; col++) {
                    if (sc.map[row][col] === 40 && CropSystem.hasCrop(col, row)) {
                        var csx = col * TILE - camX;
                        var csy = row * TILE - camY;
                        CropSystem.drawCropOnTile(ctx, csx, csy, col, row);
                    }
                }
            }
        }
    },

    drawRooftopDecorations: function(ctx, camX, camY, time) {
        /* Bench at specific position */
        /* Potted plants */
        /* Clothesline - already in tiles */

        /* City skyline is in the background tiles (row 0-1) */
    },

    drawCafeDecorations: function(ctx, camX, camY, time) {
        /* Warm lighting overlay */
        ctx.fillStyle = COLORS.warmLight;
        ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

        /* Counter area with items */
        var counterX = 2 * TILE - camX;
        var counterY = 5 * TILE - camY;

        /* Cups on counter */
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(counterX + TILE + 8, counterY + 4, 6, 8);
        ctx.fillStyle = '#D4764A';
        ctx.fillRect(counterX + TILE + 8, counterY + 4, 6, 3);

        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(counterX + TILE + 20, counterY + 6, 6, 6);
        ctx.fillStyle = '#8B6914';
        ctx.fillRect(counterX + TILE + 20, counterY + 6, 6, 2);

        /* Tables and chairs (additional detail) */
        /* Table 1 */
        var t1x = 5 * TILE - camX;
        var t1y = 7 * TILE - camY;
        ctx.fillStyle = COLORS.wood;
        ctx.fillRect(t1x + 4, t1y + 10, 24, 14);
        ctx.fillStyle = COLORS.woodDark;
        ctx.fillRect(t1x + 4, t1y + 10, 24, 2);
        ctx.fillRect(t1x + 12, t1y + 24, 8, 6);
        /* Chairs */
        ctx.fillStyle = COLORS.wood;
        ctx.fillRect(t1x - 4, t1y + 12, 6, 12);
        ctx.fillRect(t1x + 30, t1y + 12, 6, 12);

        /* Table 2 */
        var t2x = 10 * TILE - camX;
        var t2y = 7 * TILE - camY;
        ctx.fillStyle = COLORS.wood;
        ctx.fillRect(t2x + 4, t2y + 10, 24, 14);
        ctx.fillStyle = COLORS.woodDark;
        ctx.fillRect(t2x + 4, t2y + 10, 24, 2);
        ctx.fillRect(t2x + 12, t2y + 24, 8, 6);
        ctx.fillStyle = COLORS.wood;
        ctx.fillRect(t2x - 4, t2y + 12, 6, 12);
        ctx.fillRect(t2x + 30, t2y + 12, 6, 12);

        /* Table 3 */
        var t3x = 5 * TILE - camX;
        var t3y = 10 * TILE - camY;
        ctx.fillStyle = COLORS.wood;
        ctx.fillRect(t3x + 4, t3y + 10, 24, 14);
        ctx.fillStyle = COLORS.woodDark;
        ctx.fillRect(t3x + 4, t3y + 10, 24, 2);
        ctx.fillRect(t3x + 12, t3y + 24, 8, 6);
        ctx.fillStyle = COLORS.wood;
        ctx.fillRect(t3x - 4, t3y + 12, 6, 12);
        ctx.fillRect(t3x + 30, t3y + 12, 6, 12);

        /* Pendant lights */
        var lights = [
            { x: 6 * TILE, y: 3 * TILE },
            { x: 11 * TILE, y: 3 * TILE },
            { x: 8 * TILE, y: 6 * TILE }
        ];
        for (var li = 0; li < lights.length; li++) {
            var lx = lights[li].x - camX;
            var ly = lights[li].y - camY;
            /* Wire */
            ctx.fillStyle = '#888';
            ctx.fillRect(lx, ly - 20, 1, 20);
            /* Shade */
            ctx.fillStyle = '#D4A574';
            ctx.beginPath();
            ctx.moveTo(lx - 8, ly);
            ctx.lineTo(lx + 8, ly);
            ctx.lineTo(lx + 5, ly + 8);
            ctx.lineTo(lx - 5, ly + 8);
            ctx.closePath();
            ctx.fill();
            /* Glow */
            ctx.fillStyle = 'rgba(255,220,150,0.08)';
            ctx.beginPath();
            ctx.arc(lx, ly + 10, 30, 0, Math.PI * 2);
            ctx.fill();
        }
    }
};

/* ============================================================
 * SECTION 18: MAIN GAME CLASS
 * ============================================================ */

function Game(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
        /* Create canvas if not found */
        this.canvas = document.createElement('canvas');
        this.canvas.id = canvasId || 'gameCanvas';
        document.body.appendChild(this.canvas);
    }

    this.ctx = this.canvas.getContext('2d');
    this.dpr = window.devicePixelRatio || 1;
    this.canvasW = 0;
    this.canvasH = 0;
    this.running = false;
    this.lastTime = 0;
    this.accumulator = 0;
    this.currentScene = 'farm';
    this.sceneConfig = null;

    /* Callbacks */
    this._onInteract = null;
    this._onSceneChange = null;
    this._onPlant = null;
    this._onHarvest = null;

    /* Pre-allocated render bounds */
    this._startCol = 0;
    this._endCol = 0;
    this._startRow = 0;
    this._endRow = 0;

    /* Seed bar touch tracking */
    this._seedBarTouchId = null;

    this._init();
}

Game.prototype._init = function() {
    var self = this;

    SeedBar.init();
    CropSystem.init();

    this._resize();
    window.addEventListener('resize', function() {
        self._resize();
    });

    Input.init(this.canvas);
    Weather.init();
    DayNight.update();

    /* Seed bar touch handling */
    this.canvas.addEventListener('touchstart', function(e) {
        for (var i = 0; i < e.changedTouches.length; i++) {
            var t = e.changedTouches[i];
            var rect = self.canvas.getBoundingClientRect();
            var tx = t.clientX - rect.left;
            var ty = t.clientY - rect.top;
            var cw = rect.width;
            var ch = rect.height;

            /* Check if touch is in seed bar area */
            if (ty > ch - 50) {
                self._seedBarTouchId = t.identifier;
                SeedBar.handleClick(tx * (self.canvasW / cw), ty * (self.canvasH / ch), self.canvasW, self.canvasH);
            }
        }
    }, { passive: true });

    this.canvas.addEventListener('touchend', function(e) {
        for (var i = 0; i < e.changedTouches.length; i++) {
            if (e.changedTouches[i].identifier === self._seedBarTouchId) {
                self._seedBarTouchId = null;
            }
        }
    }, { passive: true });

    this.canvas.addEventListener('touchcancel', function() {
        self._seedBarTouchId = null;
    }, { passive: true });

    /* Mouse click for seed bar (desktop) */
    this.canvas.addEventListener('click', function(e) {
        var rect = self.canvas.getBoundingClientRect();
        var mx = (e.clientX - rect.left) * (self.canvasW / rect.width);
        var my = (e.clientY - rect.top) * (self.canvasH / rect.height);
        SeedBar.handleClick(mx, my, self.canvasW, self.canvasH);
    });

    this._loadScene('farm');
    this.start();
};

Game.prototype._resize = function() {
    var container = this.canvas.parentElement;
    var w = 0;
    var h = 0;

    if (container) {
        w = container.clientWidth;
        h = container.clientHeight;
    }

    /* Fallback if container is hidden or has 0 dimensions */
    if (!w || w === 0) w = window.innerWidth;
    if (!h || h === 0) h = window.innerHeight - 110;

    this.canvasW = w;
    this.canvasH = h;

    this.canvas.width = Math.round(w * this.dpr);
    this.canvas.height = Math.round(h * this.dpr);
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';

    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

    if (this.sceneConfig) {
        Camera.viewW = w;
        Camera.viewH = h;
    }
};

Game.prototype._loadScene = function(sceneId) {
    this.currentScene = sceneId;
    this.sceneConfig = SCENES[sceneId];
    var sc = this.sceneConfig;

    Player.init(sc.playerStart.x, sc.playerStart.y);
    NPC.init(sc.npcStart.x, sc.npcStart.y);

    /* Set NPC patrol waypoints based on scene */
    if (sceneId === 'farm') {
        NPC.setWaypoints([
            { x: 16, y: 10 }, { x: 12, y: 12 }, { x: 8, y: 10 }, { x: 12, y: 8 }
        ]);
    } else if (sceneId === 'rooftop') {
        NPC.setWaypoints([
            { x: 10, y: 6 }, { x: 5, y: 6 }, { x: 5, y: 10 }, { x: 10, y: 10 }
        ]);
    } else if (sceneId === 'cafe') {
        NPC.setWaypoints([
            { x: 3, y: 4 }, { x: 7, y: 4 }, { x: 7, y: 8 }, { x: 3, y: 8 }
        ]);
    }

    Camera.init(this.canvasW, this.canvasH, sc.width * TILE, sc.height * TILE);
    Camera.x = Player.x - this.canvasW / 2;
    Camera.y = Player.y - this.canvasH / 2;
    Camera.x = clamp(Camera.x, 0, Math.max(0, sc.width * TILE - this.canvasW));
    Camera.y = clamp(Camera.y, 0, Math.max(0, sc.height * TILE - this.canvasH));
};

Game.prototype._solidCheck = function(x, y, w, h) {
    var sc = this.sceneConfig;
    if (!sc) return false;

    /* Check map bounds */
    if (x < 0 || y < 0 || x + w > sc.width * TILE || y + h > sc.height * TILE) {
        return true;
    }

    /* Check corners of the entity bounding box */
    var halfW = w / 2;
    var halfH = h / 2;
    var points = [
        { x: x - halfW + 2, y: y - halfH + 2 },
        { x: x + halfW - 2, y: y - halfH + 2 },
        { x: x - halfW + 2, y: y + halfH - 2 },
        { x: x + halfW - 2, y: y + halfH - 2 }
    ];

    for (var i = 0; i < points.length; i++) {
        var col = Math.floor(points[i].x / TILE);
        var row = Math.floor(points[i].y / TILE);
        if (col < 0 || row < 0 || col >= sc.width || row >= sc.height) return true;
        var tile = sc.map[row][col];
        if (sc.solidTiles.indexOf(tile) !== -1) return true;
    }

    return false;
};

Game.prototype._checkExits = function() {
    var sc = this.sceneConfig;
    if (!sc) return;

    var px = Player.x / TILE;
    var py = Player.y / TILE;

    for (var i = 0; i < sc.exits.length; i++) {
        var exit = sc.exits[i];
        if (px >= exit.x && px < exit.x + exit.w && py >= exit.y && py < exit.y + exit.h) {
            this._transitionToScene(exit.target, exit.spawnX, exit.spawnY);
            return;
        }
    }
};

Game.prototype._transitionToScene = function(targetScene, spawnX, spawnY) {
    var self = this;
    var prevScene = this.currentScene;

    Transition.start(function() {
        self._loadScene(targetScene);
        Player.x = spawnX * TILE + TILE / 2;
        Player.y = spawnY * TILE + TILE / 2;

        if (self._onSceneChange) {
            self._onSceneChange(prevScene, targetScene);
        }
    });
};

Game.prototype._getFacingTile = function() {
    /* Get the tile the player is facing */
    var px = Player.x;
    var py = Player.y;
    var offset = 16; /* Half a tile ahead */

    var tx = px;
    var ty = py;

    if (Player.dir === 0) ty += offset;       /* facing down */
    else if (Player.dir === 3) ty -= offset;   /* facing up */
    else if (Player.dir === 1) tx -= offset;   /* facing left */
    else if (Player.dir === 2) tx += offset;   /* facing right */

    var col = Math.floor(tx / TILE);
    var row = Math.floor(ty / TILE);

    var sc = this.sceneConfig;
    if (!sc) return null;
    if (col < 0 || row < 0 || col >= sc.width || row >= sc.height) return null;

    return { col: col, row: row, tile: sc.map[row][col] };
};

Game.prototype._checkFarmInteraction = function() {
    /* Only check farm plot interaction on the farm scene */
    if (this.currentScene !== 'farm') return false;

    var facing = this._getFacingTile();
    if (!facing) return false;

    /* Check if facing a farm soil tile (type 40) */
    if (facing.tile === 40) {
        var selectedSeedId = SeedBar.getSelectedSeedId();

        if (!selectedSeedId) {
            /* No seed selected */
            Dialogue.show('系统', '选择种子后再种植吧');
            return true;
        }

        /* Check if player has seeds */
        if (SeedBar.getCount(selectedSeedId) <= 0) {
            Dialogue.show('系统', '没有足够的种子了！');
            return true;
        }

        /* Check if already planted */
        if (CropSystem.hasCrop(facing.col, facing.row)) {
            var crop = CropSystem.getCrop(facing.col, facing.row);
            var seedData = SeedBar.getSeedData(crop.seedId);
            if (CropSystem.isReady(facing.col, facing.row)) {
                /* Harvest! */
                CropSystem.removeCrop(facing.col, facing.row);
                SeedBar.addCount(crop.seedId, 1); /* Return seed + crop */
                Dialogue.show('系统', '收获了' + (seedData ? seedData.name : '作物') + '！');

                if (this._onHarvest) {
                    this._onHarvest({
                        cropType: crop.seedId,
                        x: facing.col,
                        y: facing.row
                    });
                }
            } else {
                /* Not ready yet */
                var remaining = CropSystem.getTimeRemaining(facing.col, facing.row);
                Dialogue.show('系统', '还要等' + remaining + '秒才能收获');
            }
        } else {
            /* Plant the seed */
            SeedBar.consumeSeed(selectedSeedId);
            CropSystem.plantCrop(facing.col, facing.row, selectedSeedId);
            var seedInfo = SeedBar.getSeedData(selectedSeedId);
            Dialogue.show('系统', '种下了' + (seedInfo ? seedInfo.name : '种子') + '！');

            if (this._onPlant) {
                this._onPlant({
                    seedId: selectedSeedId,
                    x: facing.col,
                    y: facing.row
                });
            }
        }

        return true;
    }

    return false;
};

Game.prototype._checkInteraction = function() {
    if (Dialogue.active) {
        Dialogue.advance();
        return;
    }

    if (!Input.actionJustPressed) return;

    /* First check farm plot interaction */
    if (this._checkFarmInteraction()) return;

    /* Then check NPC interaction */
    var d = dist(Player.x, Player.y, NPC.x, NPC.y);
    if (d < INTERACT_DIST) {
        if (this._onInteract) {
            this._onInteract(NPC.name, Player.x, Player.y, NPC.x, NPC.y);
        }
    }
};

Game.prototype._renderMap = function(ctx) {
    var sc = this.sceneConfig;
    if (!sc) return;

    /* Calculate visible tile range */
    this._startCol = Math.max(0, Math.floor(Camera.x / TILE));
    this._endCol = Math.min(sc.width, Math.ceil((Camera.x + this.canvasW) / TILE) + 1);
    this._startRow = Math.max(0, Math.floor(Camera.y / TILE));
    this._endRow = Math.min(sc.height, Math.ceil((Camera.y + this.canvasH) / TILE) + 1);

    var now = Date.now();

    for (var row = this._startRow; row < this._endRow; row++) {
        for (var col = this._startCol; col < this._endCol; col++) {
            var tile = sc.map[row][col];
            var sx = col * TILE - Camera.x;
            var sy = row * TILE - Camera.y;
            drawTile(ctx, tile, sx, sy, now);
        }
    }
};

Game.prototype._renderSceneDecorations = function(ctx) {
    if (this.currentScene === 'farm') {
        Decorations.drawFarmDecorations(ctx, Camera.x, Camera.y, Date.now());
    } else if (this.currentScene === 'rooftop') {
        Decorations.drawRooftopDecorations(ctx, Camera.x, Camera.y, Date.now());
    } else if (this.currentScene === 'cafe') {
        Decorations.drawCafeDecorations(ctx, Camera.x, Camera.y, Date.now());
    }
};

Game.prototype._renderEntities = function(ctx) {
    /* Sort entities by Y position for proper overlap */
    var entities = [
        { type: 'player', y: Player.y },
        { type: 'npc', y: NPC.y }
    ];
    entities.sort(function(a, b) { return a.y - b.y; });

    for (var i = 0; i < entities.length; i++) {
        if (entities[i].type === 'player') {
            Player.draw(ctx, Camera.x, Camera.y);
        } else {
            NPC.draw(ctx, Camera.x, Camera.y);
        }
    }
};

Game.prototype._renderUI = function(ctx) {
    /* Scene name */
    ctx.fillStyle = 'rgba(30,20,40,0.5)';
    ctx.beginPath();
    ctx.roundRect(this.canvasW / 2 - 40, 8, 80, 24, 12);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(this.sceneConfig.name, this.canvasW / 2, 24);
    ctx.textAlign = 'start';

    /* Time indicator */
    var timeStr = DayNight.hour.toString().padStart(2, '0') + ':00';
    ctx.fillStyle = 'rgba(30,20,40,0.5)';
    ctx.beginPath();
    ctx.roundRect(this.canvasW - 60, 8, 52, 24, 12);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(timeStr, this.canvasW - 34, 24);
    ctx.textAlign = 'start';

    /* Weather indicator */
    var weatherIcons = { sunny: '☀', rainy: '☂', cloudy: '☁' };
    var wIcon = weatherIcons[Weather.type] || '☀';
    ctx.fillStyle = 'rgba(30,20,40,0.5)';
    ctx.beginPath();
    ctx.roundRect(8, 8, 30, 24, 12);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '14px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(wIcon, 23, 25);
    ctx.textAlign = 'start';
};

/* ============================================================
 * SECTION 19: GAME LOOP
 * ============================================================ */

Game.prototype.start = function() {
    if (this.running) return;
    this.running = true;
    this.lastTime = performance.now();
    var self = this;
    requestAnimationFrame(function(t) { self._loop(t); });
};

Game.prototype.stop = function() {
    this.running = false;
};

Game.prototype._loop = function(timestamp) {
    if (!this.running) return;

    var dt = timestamp - this.lastTime;
    this.lastTime = timestamp;

    /* Cap delta to avoid spiral of death */
    if (dt > 100) dt = FRAME_TIME;

    this.accumulator += dt;

    /* Fixed timestep updates */
    while (this.accumulator >= FRAME_TIME) {
        this._update(FRAME_TIME);
        this.accumulator -= FRAME_TIME;
    }

    this._render();

    var self = this;
    requestAnimationFrame(function(t) { self._loop(t); });
};

Game.prototype._update = function(dt) {
    Input.update();

    if (Transition.active) {
        Transition.update(dt);
        return;
    }

    if (Dialogue.active) {
        Dialogue.update(dt);
        this._checkInteraction();
        return;
    }

    Player.update(dt, this._solidCheck.bind(this));
    NPC.update(dt, this._solidCheck.bind(this), Player.x, Player.y);

    Camera.follow(Player.x, Player.y);
    Camera.update();

    Weather.update(dt);
    DayNight.update();

    /* Update crop growth */
    CropSystem.updateGrowth();

    this._checkExits();
    this._checkInteraction();
};

Game.prototype._render = function() {
    var ctx = this.ctx;
    var w = this.canvasW;
    var h = this.canvasH;

    /* Clear */
    ctx.clearRect(0, 0, w, h);

    /* Disable smoothing for pixel art */
    ctx.imageSmoothingEnabled = false;

    /* Map */
    this._renderMap(ctx);

    /* Scene decorations (behind entities) */
    this._renderSceneDecorations(ctx);

    /* Entities */
    this._renderEntities(ctx);

    /* Weather overlay */
    Weather.draw(ctx, w, h);

    /* Day/night overlay */
    DayNight.draw(ctx, w, h);

    /* UI */
    this._renderUI(ctx);

    /* Dialogue */
    Dialogue.draw(ctx, w, h);

    /* Transition */
    Transition.draw(ctx, w, h);

    /* Seed bar (above joystick) */
    SeedBar.draw(ctx, w, h);

    /* Virtual joystick (on top of everything) */
    JoystickRenderer.draw(ctx, w, h);
};

/* ============================================================
 * SECTION 20: PUBLIC API
 * ============================================================ */

Game.prototype.onInteract = function(callback) {
    this._onInteract = callback;
};

Game.prototype.onSceneChange = function(callback) {
    this._onSceneChange = callback;
};

Game.prototype.onPlant = function(callback) {
    this._onPlant = callback;
};

Game.prototype.onHarvest = function(callback) {
    this._onHarvest = callback;
};

Game.prototype.getSelectedSeed = function() {
    return SeedBar.getSelectedSeedId();
};

Game.prototype.setSelectedSeed = function(seedId) {
    SeedBar.setSelectedSeedId(seedId);
};

Game.prototype.getPlayerPosition = function() {
    return {
        x: Player.x,
        y: Player.y,
        scene: this.currentScene
    };
};

Game.prototype.setNPCPosition = function(x, y) {
    NPC.x = x;
    NPC.y = y;
};

Game.prototype.showDialogue = function(name, text, portrait) {
    Dialogue.show(name, text, portrait);
};

Game.prototype.setWeather = function(type) {
    if (type === 'sunny' || type === 'rainy' || type === 'cloudy') {
        Weather.type = type;
        if (type === 'rainy') {
            Weather._resetRain();
        }
    }
};

Game.prototype.setTimeOfDay = function(hour) {
    DayNight.hour = clamp(Math.floor(hour), 0, 23);
    DayNight.update();
};

Game.prototype.changeScene = function(sceneId) {
    if (SCENES[sceneId]) {
        var sc = SCENES[sceneId];
        this._transitionToScene(sceneId, sc.playerStart.x / TILE, sc.playerStart.y / TILE);
    }
};

Game.prototype.getCurrentScene = function() {
    return this.currentScene;
};

Game.prototype.getSceneName = function() {
    return this.sceneConfig ? this.sceneConfig.name : '';
};

Game.prototype.getNPCPosition = function() {
    return { x: NPC.x, y: NPC.y };
};

Game.prototype.isNearNPC = function() {
    return dist(Player.x, Player.y, NPC.x, NPC.y) < INTERACT_DIST;
};

Game.prototype.resize = function() {
    this._resize();
};

/* ============================================================
 * SECTION 21: CANVAS ROUNDRECT POLYFILL
 * ============================================================ */

if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, radii) {
        var r = typeof radii === 'number' ? radii : (radii && radii[0]) || 0;
        r = Math.min(r, w / 2, h / 2);
        this.moveTo(x + r, y);
        this.lineTo(x + w - r, y);
        this.arcTo(x + w, y, x + w, y + r, r);
        this.lineTo(x + w, y + h - r);
        this.arcTo(x + w, y + h, x + w - r, y + h, r);
        this.lineTo(x + r, y + h);
        this.arcTo(x, y + h, x, y + h - r, r);
        this.lineTo(x, y + r);
        this.arcTo(x, y, x + r, y, r);
        this.closePath();
        return this;
    };
}

/* ============================================================
 * SECTION 22: AUTO-INIT ON DOM READY
 * ============================================================ */

var _gameInstance = null;

function initGame(canvasId) {
    if (_gameInstance) return _gameInstance;
    _gameInstance = new Game(canvasId || 'gameCanvas');
    _gameInstance.start();
    return _gameInstance;
}

function getGame() {
    return _gameInstance;
}

/* Expose globally */
window.Game = Game;
window.initGame = initGame;
window.getGame = getGame;
