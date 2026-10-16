"""
Academic Clarity - 健康检查项实现（系统资源 / 各服务探测）

纯检查函数：每个函数返回 HealthCheckResult，不做编排（编排见 health.py）。
- DB 探测走传入 db 对象的公开 API（不再裸写 SQL 查 documents 表）；
- API 配置检查在函数内延迟 import services.config_service，避免
  utils → services 的模块级反向依赖。
"""
import os
import time
import psutil
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: str
    message: str = ""
    latency_ms: float = 0
    details: Optional[Dict] = None


def check_system_resources() -> HealthCheckResult:
    """检查系统资源（CPU / 内存 / 磁盘）"""
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


async def check_database(db) -> HealthCheckResult:
    """检查数据库连接（走 Database 公开 API，不裸写 SQL）"""
    start = time.time()
    try:
        if db is None:
            return HealthCheckResult("database", "unhealthy", "Database not initialized", 0)

        doc_count = len(db.get_all_documents())

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


async def check_workspace(workspace_path: str) -> HealthCheckResult:
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


async def check_api_config(db) -> HealthCheckResult:
    """检查 API 配置（单 Key 模式；多 Key 轮询由本地代理承担）"""
    start = time.time()
    try:
        if db is None:
            return HealthCheckResult("api_config", "degraded", "Database not ready", 0)

        # 延迟 import：utils 层不在模块级反向依赖 services（B-SRP-05）
        from services.config_service import ConfigService
        cs = ConfigService(db)
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


async def check_task_queue(task_hub) -> HealthCheckResult:
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


async def check_redis(cache_manager) -> HealthCheckResult:
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


async def check_websocket(ws_manager) -> HealthCheckResult:
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
