"""
Academic Clarity - 健康检查编排与响应

HealthChecker 单例负责：运行时间统计、依次执行 health_checks 中的检查项、
汇总整体状态并生成 /health/detailed 的响应结构（run_all_checks 返回结构与
latency_ms 字段保持不变）。
"""
import time
from typing import Dict

from .singleton import SingletonMeta
from .time_utils import utc_now_iso
from .health_checks import (
    HealthCheckResult,
    check_system_resources,
    check_database,
    check_workspace,
    check_api_config,
    check_task_queue,
    check_redis,
    check_websocket,
)

__all__ = ["HealthCheckResult", "HealthChecker", "health_checker"]


class HealthChecker(metaclass=SingletonMeta):
    """系统健康检查器（单例；_start_time 在首次实例化时记录）"""

    def __init__(self):
        self._start_time = time.time()
        self._checks = {}
        self._last_results = {}

    def get_uptime(self) -> float:
        """获取运行时间（秒）"""
        return time.time() - self._start_time

    def get_uptime_human(self) -> str:
        """获取可读运行时间"""
        uptime = self.get_uptime()
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"

    async def run_all_checks(self, state) -> Dict:
        """运行所有健康检查"""
        checks = []

        checks.append(check_system_resources())

        if state.db:
            checks.append(await check_database(state.db))

        if state.workspace_path:
            checks.append(await check_workspace(state.workspace_path))

        checks.append(await check_api_config(state.db))

        if hasattr(state, 'task_hub'):
            checks.append(await check_task_queue(state.task_hub))

        try:
            from .cache import get_cache
            cache = get_cache()
            checks.append(await check_redis(cache))
        except Exception:
            pass

        try:
            from .websocket import ws_manager as ws
            checks.append(await check_websocket(ws))
        except Exception:
            pass

        overall_status = "healthy"
        unhealthy_count = sum(1 for c in checks if c.status == "unhealthy")
        degraded_count = sum(1 for c in checks if c.status == "degraded")

        if unhealthy_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "uptime": self.get_uptime(),
            "uptime_human": self.get_uptime_human(),
            "timestamp": utc_now_iso(),
            "checks": [
                {
                    "component": c.component,
                    "status": c.status,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2),
                    "details": c.details
                }
                for c in checks
            ]
        }


health_checker = HealthChecker()
