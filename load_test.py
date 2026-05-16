"""
load_test.py - 压力测试脚本 (v1.7 Phase 5)
==========================================
使用 locust 进行 SSE 长连接和普通 API 的压力测试。

运行方式：
    locust -f load_test.py --host http://localhost:8000

然后在浏览器打开 http://localhost:8089 查看测试结果。
"""

import json
import time
from locust import HttpUser, task, events
from locust.runners import MasterRunner, WorkerRunner


class GameAPIUser(HttpUser):
    """模拟普通游戏 API 用户。

    测试目标：
    - 模拟 50 用户
    - 每秒 1 次请求访问 /api/game/state
    """

    # 用户等待时间（秒）
    wait_time = 1

    def on_start(self):
        """用户开始时获取认证 token"""
        # 尝试登录获取 token
        response = self.client.post("/api/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token") or data.get("session_token")
        else:
            # 使用默认 API token（如果配置了）
            self.token = None

    @task(3)
    def get_game_state(self):
        """获取游戏状态"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client.get(
            "/api/game/state",
            headers=headers,
            name="/api/game/state"
        )

    @task(2)
    def get_farm(self):
        """获取农场数据"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client.get(
            "/api/game/farm",
            headers=headers,
            name="/api/game/farm"
        )

    @task(1)
    def get_stats(self):
        """获取统计数据"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client.get(
            "/api/stats",
            headers=headers,
            name="/api/stats"
        )


class SSEChatUser(HttpUser):
    """模拟 SSE 聊天用户。

    测试目标：
    - 模拟 20 用户
    - 建立 SSE 连接并保持 60 秒
    - 验证服务器内存是否持续上涨
    """

    # 用户等待时间
    wait_time = 5

    def on_start(self):
        """用户开始时获取认证 token"""
        response = self.client.post("/api/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token") or data.get("session_token")
        else:
            self.token = None

    @task
    def chat_stream(self):
        """发送聊天消息并接收 SSE 流"""
        if not self.token:
            return

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "text/event-stream",
        }

        # 发送聊天请求（流式）
        start_time = time.time()

        try:
            with self.client.post(
                "/api/chat",
                json={
                    "message": "你好",
                    "character_id": "chayewoon",
                    "stream": True
                },
                headers=headers,
                stream=True,  # 保持连接
                catch_response=True,
                name="/api/chat [SSE]"
            ) as response:
                if response.status_code != 200:
                    response.failure(f"HTTP {response.status_code}")
                    return

                # 读取 SSE 流（最多 60 秒）
                token_count = 0
                for line in response.iter_lines(decode_unicode=True):
                    if time.time() - start_time > 60:
                        # 超过 60 秒，断开连接
                        break

                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                            if event.get("type") == "token":
                                token_count += 1
                            elif event.get("type") == "error":
                                response.failure(event.get("content"))
                                return
                        except json.JSONDecodeError:
                            pass

                response.success()

        except Exception as e:
            # 连接异常
            pass


class HealthCheckUser(HttpUser):
    """健康检查用户。

    测试目标：
    - 持续检查服务健康状态
    - 验证服务稳定性
    """

    wait_time = 10

    @task
    def health_check(self):
        """健康检查"""
        self.client.get("/health", name="/health")

    @task
    def version_check(self):
        """版本检查"""
        self.client.get("/api/version", name="/api/version")


# ============================================================
# 测试事件钩子
# ============================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的回调"""
    print("\n" + "=" * 60)
    print("LoveSupremacy Universe - 压力测试开始")
    print("=" * 60)
    print(f"目标主机: {environment.host}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的回调"""
    print("\n" + "=" * 60)
    print("LoveSupremacy Universe - 压力测试结束")
    print("=" * 60 + "\n")


# ============================================================
# 内存监控（可选）
# ============================================================

def monitor_memory():
    """监控服务器内存使用（需要在服务器端运行）"""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()

    return {
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
    }


# ============================================================
# 运行说明
# ============================================================

"""
## 如何运行压力测试

### 1. 安装依赖

    pip install locust

### 2. 启动测试（Web UI 模式）

    locust -f load_test.py --host http://localhost:8000

然后在浏览器打开 http://localhost:8089，配置：
- Number of users: 50
- Spawn rate: 10
- Host: http://localhost:8000

### 3. 启动测试（无头模式）

    locust -f load_test.py --host http://localhost:8000 \\
        --users 50 --spawn-rate 10 --run-time 5m --headless

### 4. 测试场景

| 场景 | 用户数 | 目标 |
|------|--------|------|
| GameAPIUser | 50 | 普通游戏 API 压力测试 |
| SSEChatUser | 20 | SSE 长连接稳定性测试 |
| HealthCheckUser | 5 | 服务健康监控 |

### 5. 内存泄漏检测

在测试过程中，监控服务器内存使用：

    # 在服务器上运行
    watch -n 5 'ps aux | grep python3 | grep -v grep'

如果内存持续上涨（RSS 超过 500MB），可能存在内存泄漏。

### 6. 测试报告

测试完成后，locust 会生成：
- 请求统计（平均响应时间、RPS、失败率）
- 响应时间分布图
- 错误统计
"""
