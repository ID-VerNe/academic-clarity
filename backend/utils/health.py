"""
Academic Clarity - 综合健康检查端点
提供系统各组件的健康状态检查
"""
import os
import time
import asyncio
import psutil
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

try:
    from backend.constants import ServerConfig
except ImportError:
    class ServerConfig:
        DEFAULT_PORT = 38391

@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: str
    message: str = ""
    latency_ms: float = 0
    details: Optional[Dict] = None

class HealthChecker:
    """系统健康检查器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._start_time = time.time()
        return cls._instance

    def __init__(self):
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

    async def check_database(self, db) -> HealthCheckResult:
        """检查数据库连接"""
        start = time.time()
        try:
            if db is None:
                return HealthCheckResult("database", "unhealthy", "Database not initialized", 0)

            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.execute("SELECT COUNT(*) FROM documents")
            doc_count = cursor.fetchone()[0]
            conn.close()

            return HealthCheckResult(
                "database",
                "healthy",
                f"Connected, {doc_count} documents",
                (time.time() - start) * 1000,
                {"document_count": doc_count}
            )
        except Exception as e:
            return HealthCheckResult(
                "database",
                "unhealthy",
                str(e),
                (time.time() - start) * 1000
            )

    async def check_workspace(self, workspace_path: str) -> HealthCheckResult:
        """检查工作区目录"""
        start = time.time()
        try:
            if not workspace_path:
                return HealthCheckResult("workspace", "unhealthy", "Workspace path not set", 0)

            if not os.path.exists(workspace_path):
                return HealthCheckResult("workspace", "unhealthy", "Workspace directory not found", 0)

            pdf_files = [f for f in os.listdir(workspace_path) if f.lower().endswith('.pdf')]

            return HealthCheckResult(
                "workspace",
                "healthy",
                f"{len(pdf_files)} PDF files",
                (time.time() - start) * 1000,
                {"pdf_count": len(pdf_files), "path": workspace_path}
            )
        except Exception as e:
            return HealthCheckResult("workspace", "unhealthy", str(e), (time.time() - start) * 1000)

    async def check_api_config(self, state) -> HealthCheckResult:
        """检查 API 配置（单 Key 模式；多 Key 轮询由本地代理承担）"""
        start = time.time()
        try:
            if state is None or not getattr(state, 'db', None):
                return HealthCheckResult("api_config", "degraded", "Database not ready", 0)

            from services.config_service import ConfigService
            cs = ConfigService(state.db)
            ocr = cs.get_ocr_config()
            llm = cs.get_chat_config()

            missing = []
            if not ocr.get("api_key"):
                missing.append("OCR API Key")
            if not ocr.get("model_name"):
                missing.append("OCR Model")
            if not llm.get("model_name"):
                missing.append("LLM Model")

            if missing:
                return HealthCheckResult(
                    "api_config", "degraded",
                    "Missing: " + ", ".join(missing),
                    (time.time() - start) * 1000,
                    {"missing": missing}
                )

            return HealthCheckResult(
                "api_config", "healthy", "OCR & LLM configured",
                (time.time() - start) * 1000
            )
        except Exception as e:
            return HealthCheckResult("api_config", "unhealthy", str(e), (time.time() - start) * 1000)

    async def check_task_queue(self, task_hub) -> HealthCheckResult:
        """检查任务队列"""
        start = time.time()
        try:
            if task_hub is None:
                return HealthCheckResult("task_queue", "unhealthy", "Task hub not initialized", 0)

            stats = task_hub.get_stats()
            queue_size = stats.get("queued_tasks", 0)
            active = stats.get("active_tasks", 0)
            failed = stats.get("failed_tasks", 0)

            status = "healthy"
            if failed > 10:
                status = "degraded"
            if active > 50:
                status = "busy"

            return HealthCheckResult(
                "task_queue",
                status,
                f"Queue: {queue_size}, Active: {active}, Failed: {failed}",
                (time.time() - start) * 1000,
                stats
            )
        except Exception as e:
            return HealthCheckResult("task_queue", "unhealthy", str(e), (time.time() - start) * 1000)

    def check_system_resources(self) -> HealthCheckResult:
        """检查系统资源"""
        start = time.time()
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            warnings = []
            status = "healthy"

            if cpu_percent > 80:
                warnings.append(f"High CPU: {cpu_percent}%")
                status = "degraded"

            if memory.percent > 85:
                warnings.append(f"High Memory: {memory.percent}%")
                status = "degraded"

            if disk.percent > 90:
                warnings.append(f"Low Disk: {disk.percent}% used")
                status = "unhealthy"

            message = f"CPU: {cpu_percent:.1f}%, Memory: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%"
            if warnings:
                message += " | " + ", ".join(warnings)

            return HealthCheckResult(
                "system",
                status,
                message,
                (time.time() - start) * 1000,
                {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free / (1024**3)
                }
            )
        except Exception as e:
            return HealthCheckResult("system", "unhealthy", str(e), (time.time() - start) * 1000)

    async def check_redis(self, cache_manager) -> HealthCheckResult:
        """检查Redis连接"""
        start = time.time()
        try:
            if cache_manager is None:
                return HealthCheckResult("redis", "skipped", "Cache not enabled", 0)

            stats = cache_manager.cache.get_stats()
            backend = stats.get("backend", "unknown")

            if backend == "redis" and stats.get("connected"):
                return HealthCheckResult(
                    "redis",
                    "healthy",
                    f"Connected ({stats.get('memory_used', 'unknown')})",
                    (time.time() - start) * 1000,
                    stats
                )
            else:
                return HealthCheckResult(
                    "redis",
                    "healthy",
                    f"Using in-memory cache ({stats.get('size', 0)} items)",
                    (time.time() - start) * 1000,
                    stats
                )
        except Exception as e:
            return HealthCheckResult("redis", "unhealthy", str(e), (time.time() - start) * 1000)

    async def check_websocket(self, ws_manager) -> HealthCheckResult:
        """检查WebSocket服务"""
        start = time.time()
        try:
            if ws_manager is None:
                return HealthCheckResult("websocket", "skipped", "WebSocket not enabled", 0)

            connections = ws_manager.get_connection_count()

            return HealthCheckResult(
                "websocket",
                "healthy",
                f"{connections} active connections",
                (time.time() - start) * 1000,
                {"connections": connections}
            )
        except Exception as e:
            return HealthCheckResult("websocket", "unhealthy", str(e), (time.time() - start) * 1000)

    async def run_all_checks(self, state) -> Dict:
        """运行所有健康检查"""
        checks = []

        checks.append(self.check_system_resources())

        if state.db:
            checks.append(await self.check_database(state.db))

        if state.workspace_path:
            checks.append(await self.check_workspace(state.workspace_path))

        checks.append(await self.check_api_config(state))

        if hasattr(state, 'task_hub'):
            checks.append(await self.check_task_queue(state.task_hub))

        try:
            from utils.cache import get_cache
            cache = get_cache()
            checks.append(await self.check_redis(cache))
        except:
            pass

        try:
            from utils.websocket import ws_manager as ws
            checks.append(await self.check_websocket(ws))
        except:
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
            "timestamp": datetime.utcnow().isoformat() + "Z",
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
