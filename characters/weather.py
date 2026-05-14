"""
天气查询模块
============
从 bot.py 提取的天气相关函数：
  - get_seoul_weather: 获取首尔天气（wttr.in 免费 API）
  - get_weather_context: 生成天气上下文字符串
"""

import logging

import httpx


async def get_seoul_weather() -> dict:
    """获取首尔天气（使用wttr.in免费API）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://wttr.in/Seoul?format=j1",
                headers={"User-Agent": "curl/7.0"},
            )
            if response.status_code != 200:
                return {}
            data = response.json()
            current = data.get("current_condition", [{}])[0]
            return {
                "temp_c": current.get("temp_C", "?"),
                "feels_like": current.get("FeelsLikeC", "?"),
                "desc": current.get("weatherDesc", [{}])[0].get("value", "未知"),
                "humidity": current.get("humidity", "?"),
                "wind": current.get("windspeedKmph", "?"),
            }
    except Exception as e:
        logging.debug(f"天气查询失败: {e}")
        return {}


def get_weather_context(weather: dict) -> str:
    """生成天气上下文"""
    if not weather:
        return ""
    return f"\n【首尔现在天气】{weather['desc']}，{weather['temp_c']}°C（体感{weather['feels_like']}°C），湿度{weather['humidity']}%"
