# WebFarm - Web 种田模拟游戏

基于 Phaser 3 + Python aiohttp 的轻量级种田模拟游戏。

## 架构特点

- **前端**: Phaser 3 (Canvas 渲染) + 客户端计算生长进度
- **后端**: Python aiohttp (RESTful API，无状态设计)
- **数据**: JSON 文件存储 + localStorage 缓存
- **部署**: Docker + Google Cloud e2-micro 优化

## 快速开始

### 本地开发

```bash
cd webfarm

# 安装依赖
pip install -r requirements.txt

# 启动后端
python server/server.py

# 访问 http://localhost:8080
```

### Docker 部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## API 文档

### GET /api/farm
获取农场状态

### POST /api/action
执行动作
- `action`: till, plant, harvest, water, buy_seed, sell_crop

## 目录结构

```
webfarm/
├── server/
│   └── server.py          # 后端 API
├── src/
│   ├── model/
│   │   └── FarmModel.js   # 数据管理层
│   ├── scene/
│   │   └── GameScene.js   # Phaser 场景
│   ├── index.html         # 入口
│   └── main.js            # 游戏启动
├── data/                  # 用户数据 (JSON)
├── Dockerfile
└── docker-compose.yml
```
