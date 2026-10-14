"""
Academic Clarity - 统一日志系统
提供结构化日志、多个日志级别、按模块分类输出
"""
import os
import sys
import logging
import json
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from backend.constants import ServerConfig
except ImportError:
    from constants import ServerConfig

class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data)

class ColoredFormatter(logging.Formatter):
    """带颜色的控制台格式化器"""
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return f"[{self.formatTime(record)}] [{record.levelname}] [{record.name}] {record.getMessage()}"

class StructuredLogger:
    """结构化日志记录器"""
    _instances: Dict[str, logging.Logger] = {}

    def __init__(self, name: str, log_dir: Optional[str] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        if log_dir:
            self._setup_file_handler(log_dir)
        self._setup_console_handler()

    def _setup_console_handler(self):
        """设置控制台处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter())
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self, log_dir: str):
        """设置文件处理器"""
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path / f"{self.name}.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)

        error_handler = RotatingFileHandler(
            log_path / f"{self.name}_error.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(error_handler)

    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, extra=kwargs if kwargs else None)

    def info(self, msg: str, **kwargs):
        self.logger.info(msg, extra=kwargs if kwargs else None)

    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, extra=kwargs if kwargs else None)

    def error(self, msg: str, **kwargs):
        self.logger.error(msg, extra=kwargs if kwargs else None)

    def critical(self, msg: str, **kwargs):
        self.logger.critical(msg, extra=kwargs if kwargs else None)

    def log_api_call(self, endpoint: str, method: str, status_code: int, duration_ms: float):
        """记录API调用"""
        self.info(
            f"API {method} {endpoint} -> {status_code}",
            event="api_call",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms
        )

    def log_task(self, action: str, doc_id: int, worker_id: Optional[int] = None, **kwargs):
        """记录任务相关事件"""
        extra = {"event": "task", "doc_id": doc_id, "action": action}
        if worker_id is not None:
            extra["worker_id"] = worker_id
        extra.update(kwargs)

        if action in ["started", "completed"]:
            self.info(f"Task {action} for Doc {doc_id}", **extra)
        else:
            self.warning(f"Task {action} for Doc {doc_id}", **extra)

    def log_key_pool(self, action: str, service: str, key_prefix: str = "", **kwargs):
        """记录密钥池操作"""
        extra = {"event": "key_pool", "service": service, "action": action}
        if key_prefix:
            extra["key"] = f"{key_prefix}..."
        extra.update(kwargs)
        self.info(f"KeyPool [{service}] {action}", **extra)

    def log_database(self, operation: str, duration_ms: float, rows_affected: int = 0, **kwargs):
        """记录数据库操作"""
        extra = {
            "event": "database",
            "operation": operation,
            "duration_ms": duration_ms,
            "rows_affected": rows_affected
        }
        extra.update(kwargs)
        self.debug(f"DB {operation} ({duration_ms:.2f}ms, {rows_affected} rows)", **extra)

def get_logger(name: str, log_dir: Optional[str] = None) -> StructuredLogger:
    """获取或创建日志记录器"""
    if name not in StructuredLogger._instances:
        StructuredLogger._instances[name] = StructuredLogger(name, log_dir)
    return StructuredLogger._instances[name]

core_logger = get_logger("academic_clarity")
api_logger = get_logger("api")
task_logger = get_logger("task")
db_logger = get_logger("database")
key_logger = get_logger("keypool")
