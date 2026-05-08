"""
Academic Clarity - Health Check Module
提供详细的系统健康检查端点
"""

import time
import psutil
import os
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from backend.constants import KeyPoolConfig
    from backend.utils.logger import get_logger
except ImportError:
    from constants import KeyPoolConfig
    from utils.logger import get_logger

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class SystemHealth:
    def __init__(self):
        self._start_time = time.time()
        self._checks: Dict[str, ComponentHealth] = {}
        self._logger = get_logger()

    def register_check(self, name: str, health: ComponentHealth):
        self._checks[name] = health

    def get_overall_status(self) -> HealthStatus:
        if not self._checks:
            return HealthStatus.HEALTHY

        statuses = [c.status for c in self._checks.values()]
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def check_database(self) -> ComponentHealth:
        try:
            import sqlite3
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "workspace_default",
                "library.db"
            )
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path, timeout=1)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM documents")
                doc_count = cursor.fetchone()[0]
                conn.close()
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message=f"Database accessible, {doc_count} documents",
                    details={"document_count": doc_count, "path": db_path}
                )
            return ComponentHealth(
                name="database",
                status=HealthStatus.DEGRADED,
                message="Database not initialized yet",
                details={"path": db_path}
            )
        except Exception as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                details={"error": str(e)}
            )

    def check_api_keys(self) -> ComponentHealth:
        try:
            from core.api_key_manager import key_manager

            ocr_pool = key_manager.get_pool("ocr")
            llm_pool = key_manager.get_pool("llm")

            ocr_enabled = ocr_pool.is_enabled() if ocr_pool else False
            llm_enabled = llm_pool.is_enabled() if llm_pool else False

            ocr_keys = ocr_pool.get_stats() if ocr_pool and ocr_enabled else []
            llm_keys = llm_pool.get_stats() if llm_pool and llm_enabled else []

            total_keys = len(ocr_keys) + len(llm_keys)
            healthy_keys = sum(1 for k in ocr_keys if k.get("is_healthy", True))
            healthy_keys += sum(1 for k in llm_keys if k.get("is_healthy", True))

            if total_keys == 0:
                return ComponentHealth(
                    name="api_keys",
                    status=HealthStatus.DEGRADED,
                    message="No API keys configured",
                    details={"ocr_keys": 0, "llm_keys": 0}
                )
            elif healthy_keys < total_keys:
                return ComponentHealth(
                    name="api_keys",
                    status=HealthStatus.DEGRADED,
                    message=f"{healthy_keys}/{total_keys} keys healthy",
                    details={
                        "ocr_keys": len(ocr_keys),
                        "llm_keys": len(llm_keys),
                        "healthy_keys": healthy_keys,
                        "total_keys": total_keys
                    }
                )
            else:
                return ComponentHealth(
                    name="api_keys",
                    status=HealthStatus.HEALTHY,
                    message=f"All {total_keys} keys healthy",
                    details={
                        "ocr_keys": len(ocr_keys),
                        "llm_keys": len(llm_keys),
                        "healthy_keys": healthy_keys,
                        "total_keys": total_keys
                    }
                )
        except Exception as e:
            return ComponentHealth(
                name="api_keys",
                status=HealthStatus.UNHEALTHY,
                message=f"Key manager error: {str(e)}",
                details={"error": str(e)}
            )

    def check_task_queue(self) -> ComponentHealth:
        try:
            from core.task_manager import task_hub

            stats = task_hub.get_stats()
            active = stats.get("active_tasks", 0)
            queued = stats.get("queued_tasks", 0)
            failed = stats.get("failed_tasks", 0)

            if failed > 10:
                return ComponentHealth(
                    name="task_queue",
                    status=HealthStatus.DEGRADED,
                    message=f"High failure count: {failed} failed tasks",
                    details=stats
                )
            return ComponentHealth(
                name="task_queue",
                status=HealthStatus.HEALTHY,
                message=f"Queue healthy: {active} active, {queued} queued",
                details=stats
            )
        except Exception as e:
            return ComponentHealth(
                name="task_queue",
                status=HealthStatus.UNHEALTHY,
                message=f"Task manager error: {str(e)}",
                details={"error": str(e)}
            )

    def check_system_resources(self) -> ComponentHealth:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            memory_percent = memory.percent
            disk_percent = disk.percent

            issues = []
            if cpu_percent > 90:
                issues.append(f"High CPU: {cpu_percent}%")
            if memory_percent > 90:
                issues.append(f"High Memory: {memory_percent}%")
            if disk_percent > 90:
                issues.append(f"High Disk: {disk_percent}%")

            if issues:
                status = HealthStatus.UNHEALTHY if len(issues) > 1 else HealthStatus.DEGRADED
                return ComponentHealth(
                    name="system_resources",
                    status=status,
                    message="; ".join(issues),
                    details={
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "memory_available_mb": memory.available // (1024 * 1024),
                        "disk_percent": disk_percent,
                        "disk_free_gb": disk.free // (1024 * 1024 * 1024)
                    }
                )

            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.HEALTHY,
                message="All resources within limits",
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "memory_available_mb": memory.available // (1024 * 1024),
                    "disk_percent": disk_percent,
                    "disk_free_gb": disk.free // (1024 * 1024 * 1024)
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                message=f"Resource check error: {str(e)}",
                details={"error": str(e)}
            )

    def check_workspace(self) -> ComponentHealth:
        try:
            from server import state

            if not state.workspace_path:
                return ComponentHealth(
                    name="workspace",
                    status=HealthStatus.DEGRADED,
                    message="Workspace not initialized",
                    details={}
                )

            workspace_path = state.workspace_path
            if not os.path.exists(workspace_path):
                return ComponentHealth(
                    name="workspace",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Workspace path missing: {workspace_path}",
                    details={"path": workspace_path}
                )

            pdf_files = [
                f for f in os.listdir(workspace_path)
                if f.lower().endswith('.pdf')
            ]

            return ComponentHealth(
                name="workspace",
                status=HealthStatus.HEALTHY,
                message=f"Workspace accessible with {len(pdf_files)} PDF files",
                details={
                    "path": workspace_path,
                    "pdf_count": len(pdf_files),
                    "total_files": len(os.listdir(workspace_path))
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="workspace",
                status=HealthStatus.UNHEALTHY,
                message=f"Workspace error: {str(e)}",
                details={"error": str(e)}
            )

    def run_all_checks(self) -> Dict[str, Any]:
        checks = [
            self.check_database,
            self.check_api_keys,
            self.check_task_queue,
            self.check_system_resources,
            self.check_workspace
        ]

        results = []
        for check in checks:
            try:
                health = check()
                self._checks[health.name] = health
                results.append(health)
            except Exception as e:
                self._logger.exception(f"Health check failed: {check.__name__}")
                results.append(ComponentHealth(
                    name=check.__name__,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check execution failed: {str(e)}"
                ))

        overall = self.get_overall_status()
        uptime_seconds = time.time() - self._start_time

        return {
            "status": overall.value,
            "uptime_seconds": round(uptime_seconds, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "components": [
                {
                    "name": h.name,
                    "status": h.status.value,
                    "message": h.message,
                    "details": h.details,
                    "timestamp": h.timestamp
                }
                for h in results
            ]
        }

system_health = SystemHealth()

def get_health_status() -> Dict[str, Any]:
    return system_health.run_all_checks()
