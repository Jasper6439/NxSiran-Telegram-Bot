#!/usr/bin/env python3
"""
WebFarm Game Server
基于 aiohttp 的 RESTful API 服务器
设计原则：无状态、纯数据接口、静态文件托管

Author: SOLO
Version: 2.0.0
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import aiohttp
from aiohttp import web
import aiohttp_cors

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置路径
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 作物配置表 (服务器端只存储配置，不存储运行时状态)
CROP_CONFIG = {
    "corn": {
        "id": "corn",
        "name": "玉米",
        "growth_time": 60,  # 生长周期：60秒
        "sell_price": 15,
        "buy_price": 5,
        "stages": 3  # 生长阶段数
    },
    "wheat": {
        "id": "wheat",
        "name": "小麦",
        "growth_time": 45,
        "sell_price": 10,
        "buy_price": 3,
        "stages": 3
    },
    "tomato": {
        "id": "tomato",
        "name": "番茄",
        "growth_time": 90,
        "sell_price": 25,
        "buy_price": 8,
        "stages": 4
    },
    "carrot": {
        "id": "carrot",
        "name": "胡萝卜",
        "growth_time": 30,
        "sell_price": 8,
        "buy_price": 2,
        "stages": 2
    }
}


class FarmDatabase:
    """
    农场数据管理器
    使用 JSON 文件存储，每个用户一个文件
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.cache: Dict[str, Dict] = {}  # 内存缓存，服务器重启后从文件加载
        
    def _get_user_file(self, user_id: str) -> Path:
        """获取用户数据文件路径"""
        return self.data_dir / f"{user_id}.json"
    
    def _load_user_data(self, user_id: str) -> Dict[str, Any]:
        """从文件加载用户数据"""
        if user_id in self.cache:
            return self.cache[user_id]
            
        file_path = self._get_user_file(user_id)
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache[user_id] = data
                    return data
            except Exception as e:
                logger.error(f"加载用户数据失败 {user_id}: {e}")
        
        # 返回默认数据
        return self._create_default_data(user_id)
    
    def _save_user_data(self, user_id: str, data: Dict[str, Any]):
        """保存用户数据到文件"""
        file_path = self._get_user_file(user_id)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.cache[user_id] = data
        except Exception as e:
            logger.error(f"保存用户数据失败 {user_id}: {e}")
            raise
    
    def _create_default_data(self, user_id: str) -> Dict[str, Any]:
        """创建默认农场数据"""
        now = datetime.now().isoformat()
        
        # 创建 5x5 地块网格
        plots = []
        for y in range(5):
            for x in range(5):
                plots.append({
                    "id": y * 5 + x,
                    "x": x,
                    "y": y,
                    "state": "empty",  # empty, tilled, planted, mature
                    "crop_id": None,
                    "planted_at": None,
                    "watered": False
                })
        
        data = {
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "gold": 100,  # 初始金币
            "level": 1,
            "exp": 0,
            "plots": plots,
            "inventory": {
                "seeds": {
                    "corn": 2,
                    "wheat": 3
                },
                "crops": {}
            },
            "stats": {
                "total_planted": 0,
                "total_harvested": 0,
                "total_sold": 0
            }
        }
        
        self._save_user_data(user_id, data)
        return data
    
    def get_farm(self, user_id: str) -> Dict[str, Any]:
        """获取农场完整状态"""
        return self._load_user_data(user_id)
    
    def update_farm(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新农场数据"""
        data = self._load_user_data(user_id)
        data.update(updates)
        data["updated_at"] = datetime.now().isoformat()
        self._save_user_data(user_id, data)
        return data
    
    def update_plot(self, user_id: str, plot_id: int, plot_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新单个地块"""
        data = self._load_user_data(user_id)
        for plot in data["plots"]:
            if plot["id"] == plot_id:
                plot.update(plot_data)
                break
        data["updated_at"] = datetime.now().isoformat()
        self._save_user_data(user_id, data)
        return data
    
    def add_item(self, user_id: str, item_type: str, item_id: str, count: int = 1):
        """添加物品到背包"""
        data = self._load_user_data(user_id)
        if item_type not in data["inventory"]:
            data["inventory"][item_type] = {}
        
        current = data["inventory"][item_type].get(item_id, 0)
        data["inventory"][item_type][item_id] = current + count
        self._save_user_data(user_id, data)
    
    def remove_item(self, user_id: str, item_type: str, item_id: str, count: int = 1) -> bool:
        """从背包移除物品"""
        data = self._load_user_data(user_id)
        if item_type not in data["inventory"]:
            return False
        
        current = data["inventory"][item_type].get(item_id, 0)
        if current < count:
            return False
        
        data["inventory"][item_type][item_id] = current - count
        if data["inventory"][item_type][item_id] <= 0:
            del data["inventory"][item_type][item_id]
        
        self._save_user_data(user_id, data)
        return True


# 全局数据库实例
db = FarmDatabase(DATA_DIR)


# ============== API 处理器 ==============

async def api_get_farm(request: web.Request) -> web.Response:
    """
    GET /api/farm
    获取农场完整状态
    """
    user_id = request.query.get("user_id", "anonymous")
    
    try:
        farm_data = db.get_farm(user_id)
        
        # 返回数据（包含作物配置）
        return web.json_response({
            "success": True,
            "data": {
                "farm": farm_data,
                "crop_config": CROP_CONFIG,
                "server_time": datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"获取农场失败: {e}")
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


async def api_post_action(request: web.Request) -> web.Response:
    """
    POST /api/action
    执行玩家动作
    请求体: {action: string, ...params}
    """
    try:
        body = await request.json()
        user_id = body.get("user_id", "anonymous")
        action = body.get("action")
        
        if not action:
            return web.json_response({
                "success": False,
                "error": "缺少 action 参数"
            }, status=400)
        
        # 获取当前农场状态
        farm_data = db.get_farm(user_id)
        
        result = {"success": False, "error": "未知动作"}
        
        # === 动作处理 ===
        if action == "till":
            # 开垦土地
            plot_id = body.get("plot_id")
            result = await action_till(user_id, plot_id)
            
        elif action == "plant":
            # 种植作物
            plot_id = body.get("plot_id")
            crop_id = body.get("crop_id")
            result = await action_plant(user_id, plot_id, crop_id)
            
        elif action == "harvest":
            # 收获作物
            plot_id = body.get("plot_id")
            result = await action_harvest(user_id, plot_id)
            
        elif action == "water":
            # 浇水
            plot_id = body.get("plot_id")
            result = await action_water(user_id, plot_id)
            
        elif action == "buy_seed":
            # 购买种子
            crop_id = body.get("crop_id")
            count = body.get("count", 1)
            result = await action_buy_seed(user_id, crop_id, count)
            
        elif action == "sell_crop":
            # 出售作物
            crop_id = body.get("crop_id")
            count = body.get("count", 1)
            result = await action_sell_crop(user_id, crop_id, count)
        
        # 返回最新农场状态
        if result.get("success"):
            farm_data = db.get_farm(user_id)
            result["farm"] = farm_data
            result["crop_config"] = CROP_CONFIG
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"执行动作失败: {e}")
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


# ============== 具体动作实现 ==============

async def action_till(user_id: str, plot_id: int) -> Dict:
    """开垦土地"""
    farm_data = db.get_farm(user_id)
    
    # 查找地块
    plot = None
    for p in farm_data["plots"]:
        if p["id"] == plot_id:
            plot = p
            break
    
    if not plot:
        return {"success": False, "error": "地块不存在"}
    
    if plot["state"] != "empty":
        return {"success": False, "error": "该地块已被开垦"}
    
    # 更新地块状态
    db.update_plot(user_id, plot_id, {
        "state": "tilled",
        "crop_id": None,
        "planted_at": None
    })
    
    return {"success": True, "message": "开垦成功"}


async def action_plant(user_id: str, plot_id: int, crop_id: str) -> Dict:
    """种植作物"""
    if crop_id not in CROP_CONFIG:
        return {"success": False, "error": "未知作物类型"}
    
    farm_data = db.get_farm(user_id)
    
    # 检查种子数量
    seeds = farm_data["inventory"].get("seeds", {})
    if seeds.get(crop_id, 0) < 1:
        return {"success": False, "error": "种子不足"}
    
    # 查找地块
    plot = None
    for p in farm_data["plots"]:
        if p["id"] == plot_id:
            plot = p
            break
    
    if not plot:
        return {"success": False, "error": "地块不存在"}
    
    if plot["state"] != "tilled":
        return {"success": False, "error": "请先开垦土地"}
    
    # 扣除种子
    db.remove_item(user_id, "seeds", crop_id, 1)
    
    # 种植
    now = datetime.now().isoformat()
    db.update_plot(user_id, plot_id, {
        "state": "planted",
        "crop_id": crop_id,
        "planted_at": now,
        "watered": False
    })
    
    # 更新统计
    stats = farm_data.get("stats", {})
    stats["total_planted"] = stats.get("total_planted", 0) + 1
    db.update_farm(user_id, {"stats": stats})
    
    return {"success": True, "message": f"种植 {CROP_CONFIG[crop_id]['name']} 成功"}


async def action_harvest(user_id: str, plot_id: int) -> Dict:
    """收获作物"""
    farm_data = db.get_farm(user_id)
    
    # 查找地块
    plot = None
    for p in farm_data["plots"]:
        if p["id"] == plot_id:
            plot = p
            break
    
    if not plot:
        return {"success": False, "error": "地块不存在"}
    
    if plot["state"] != "planted" or not plot.get("crop_id"):
        return {"success": False, "error": "该地块没有作物"}
    
    crop_id = plot["crop_id"]
    
    # 检查是否成熟（客户端计算，服务器只做校验）
    planted_at = plot.get("planted_at")
    if planted_at:
        planted_time = datetime.fromisoformat(planted_at)
        elapsed = (datetime.now() - planted_time).total_seconds()
        growth_time = CROP_CONFIG[crop_id]["growth_time"]
        
        if elapsed < growth_time:
            return {"success": False, "error": "作物尚未成熟"}
    
    # 收获：添加作物到背包
    db.add_item(user_id, "crops", crop_id, 1)
    
    # 清空地块
    db.update_plot(user_id, plot_id, {
        "state": "tilled",  # 收获后保持开垦状态
        "crop_id": None,
        "planted_at": None,
        "watered": False
    })
    
    # 更新统计
    stats = farm_data.get("stats", {})
    stats["total_harvested"] = stats.get("total_harvested", 0) + 1
    db.update_farm(user_id, {"stats": stats})
    
    return {
        "success": True,
        "message": f"收获 {CROP_CONFIG[crop_id]['name']} 成功",
        "harvested": {"crop_id": crop_id, "count": 1}
    }


async def action_water(user_id: str, plot_id: int) -> Dict:
    """浇水"""
    farm_data = db.get_farm(user_id)
    
    plot = None
    for p in farm_data["plots"]:
        if p["id"] == plot_id:
            plot = p
            break
    
    if not plot:
        return {"success": False, "error": "地块不存在"}
    
    if plot["state"] != "planted":
        return {"success": False, "error": "该地块没有作物"}
    
    db.update_plot(user_id, plot_id, {"watered": True})
    
    return {"success": True, "message": "浇水成功"}


async def action_buy_seed(user_id: str, crop_id: str, count: int) -> Dict:
    """购买种子"""
    if crop_id not in CROP_CONFIG:
        return {"success": False, "error": "未知作物类型"}
    
    farm_data = db.get_farm(user_id)
    config = CROP_CONFIG[crop_id]
    total_cost = config["buy_price"] * count
    
    # 检查金币
    if farm_data["gold"] < total_cost:
        return {"success": False, "error": "金币不足"}
    
    # 扣除金币
    farm_data["gold"] -= total_cost
    db.update_farm(user_id, {"gold": farm_data["gold"]})
    
    # 添加种子
    db.add_item(user_id, "seeds", crop_id, count)
    
    return {
        "success": True,
        "message": f"购买 {config['name']} 种子 x{count} 成功",
        "cost": total_cost
    }


async def action_sell_crop(user_id: str, crop_id: str, count: int) -> Dict:
    """出售作物"""
    if crop_id not in CROP_CONFIG:
        return {"success": False, "error": "未知作物类型"}
    
    farm_data = db.get_farm(user_id)
    
    # 检查作物数量
    crops = farm_data["inventory"].get("crops", {})
    if crops.get(crop_id, 0) < count:
        return {"success": False, "error": "作物数量不足"}
    
    config = CROP_CONFIG[crop_id]
    total_earn = config["sell_price"] * count
    
    # 扣除作物
    db.remove_item(user_id, "crops", crop_id, count)
    
    # 增加金币
    farm_data["gold"] += total_earn
    db.update_farm(user_id, {"gold": farm_data["gold"]})
    
    # 更新统计
    stats = farm_data.get("stats", {})
    stats["total_sold"] = stats.get("total_sold", 0) + count
    db.update_farm(user_id, {"stats": stats})
    
    return {
        "success": True,
        "message": f"出售 {config['name']} x{count} 成功",
        "earn": total_earn
    }


# ============== 应用初始化 ==============

def create_app() -> web.Application:
    """创建 aiohttp 应用"""
    app = web.Application()
    
    # 配置 CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    # API 路由
    api_routes = [
        web.get("/api/farm", api_get_farm),
        web.post("/api/action", api_post_action),
    ]
    
    for route in api_routes:
        cors.add(app.router.add_route(route.method, route.path, route.handler))
    
    # 静态文件服务 (前端 dist 目录)
    dist_path = BASE_DIR / "dist"
    if dist_path.exists():
        app.router.add_static("/", dist_path, name="static")
        logger.info(f"静态文件服务: {dist_path}")
    else:
        logger.warning(f"dist 目录不存在: {dist_path}")
    
    return app


async def main():
    """主入口"""
    app = create_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    logger.info(f"🌾 WebFarm Server starting on port {port}")
    logger.info(f"📁 Data directory: {DATA_DIR}")
    
    await site.start()
    
    # 保持运行
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())