"""
Academic Clarity - Structured Logging Module
提供统一的结构化日志记录，支持日志级别、上下文追踪、文件轮转
"""

import os
import sys
import json
import time
import traceback
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, Dict, Optional, Union
from enum import IntEnum
from threading import Lock

class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class StructuredLogger:
    _instance = None
    _init_lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._log_level = LogLevel.INFO
        self._log_dir = None
        self._log_file = None
        self._console_output = True
        self._json_format = True
        self._context: Dict[str, Any] = {}
        self._context_lock = Lock()
        self._logger: Optional[logging.Logger] = None
        self._file_handler: Optional[RotatingFileHandler] = None

    def configure(
        self,
        log_level: Union[str, int, LogLevel] = "INFO",
        log_dir: str = None,
        log_file: str = "academic_clarity.log",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        console_output: bool = True,
        json_format: bool = True
    ):
        if isinstance(log_level, str):
            self._log_level = LogLevel[log_level.upper()]
        elif isinstance(log_level, int):
            self._log_level = LogLevel(log_level)
        else:
            self._log_level = log_level

        self._log_dir = log_dir
        self._log_file = log_file
        self._console_output = console_output
        self._json_format = json_format

        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, log_file)
            self._logger = logging.getLogger("AcademicClarity")
            self._logger.setLevel(self._log_level)
            self._logger.handlers.clear()

            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(self._log_level)
            if json_format:
                file_handler.setFormatter(logging.Formatter('%(message)s'))
            else:
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                )
            self._logger.addHandler(file_handler)
            self._file_handler = file_handler

    def set_context(self, **kwargs):
        with self._context_lock:
            self._context.update(kwargs)

    def clear_context(self):
        with self._context_lock:
            self._context.clear()

    def _build_record(self, level: LogLevel, message: str, **kwargs) -> Dict[str, Any]:
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.name,
            "message": message,
        }

        with self._context_lock:
            record["context"] = dict(self._context)

        if kwargs:
            record["extra"] = kwargs

        return record

    def _log(self, level: LogLevel, message: str, **kwargs):
        if level < self._log_level:
            return

        record = self._build_record(level, message, **kwargs)

        if self._json_format:
            log_line = json.dumps(record, ensure_ascii=False, default=str)
        else:
            extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
            context_info = " ".join(f"{k}={v}" for k, v in record["context"].items())
            log_line = f"{record['timestamp']} [{level.name}] {message}"
            if context_info:
                log_line += f" | {context_info}"
            if extra_info:
                log_line += f" | {extra_info}"

        if self._console_output:
            print(log_line, file=sys.stdout if level <= LogLevel.WARNING else sys.stderr)

        if self._logger:
            if level == LogLevel.DEBUG:
                self._logger.debug(log_line)
            elif level == LogLevel.INFO:
                self._logger.info(log_line)
            elif level == LogLevel.WARNING:
                self._logger.warning(log_line)
            elif level == LogLevel.ERROR:
                self._logger.error(log_line)
            elif level == LogLevel.CRITICAL:
                self._logger.critical(log_line)

    def debug(self, message: str, **kwargs):
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def exception(self, message: str, exc: Exception = None, **kwargs):
        exc_info = ""
        if exc:
            exc_info = f" {type(exc).__name__}: {str(exc)}"
        elif sys.exc_info()[0]:
            exc_info = f" {traceback.format_exc()}"
        self._log(LogLevel.ERROR, message + exc_info, **kwargs)

    def log_api_call(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int = None,
        duration_ms: float = None,
        error: str = None,
        **kwargs
    ):
        self.info(
            f"API {method} {endpoint}",
            event="api_call",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            error=error,
            **kwargs
        )

    def log_task(
        self,
        task_id: int,
        action: str,
        status: str = None,
        duration_ms: float = None,
        error: str = None,
        **kwargs
    ):
        level = LogLevel.ERROR if error else LogLevel.INFO
        self._log(
            level,
            f"Task {task_id} {action}",
            event="task",
            task_id=task_id,
            action=action,
            status=status,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            error=error,
            **kwargs
        )

    def log_key_pool(
        self,
        pool_name: str,
        action: str,
        key_id: str = None,
        available: int = None,
        total: int = None,
        error: str = None,
        **kwargs
    ):
        level = LogLevel.ERROR if error else LogLevel.DEBUG
        self._log(
            level,
            f"KeyPool {pool_name}: {action}",
            event="key_pool",
            pool_name=pool_name,
            action=action,
            key_id=key_id[:8] + "..." if key_id else None,
            available=available,
            total=total,
            error=error,
            **kwargs
        )

    def log_db_operation(
        self,
        operation: str,
        table: str = None,
        rows_affected: int = None,
        duration_ms: float = None,
        error: str = None,
        **kwargs
    ):
        level = LogLevel.ERROR if error else LogLevel.DEBUG
        self._log(
            level,
            f"DB {operation}",
            event="database",
            operation=operation,
            table=table,
            rows_affected=rows_affected,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            error=error,
            **kwargs
        )

logger = StructuredLogger()

def get_logger() -> StructuredLogger:
    return logger

def configure_logger(**kwargs):
    logger.configure(**kwargs)
