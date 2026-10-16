import os
import sys

# 路径引导必须先于任何 backend 内 import：python_embed 的 ._pth 隔离模式
# 不会把脚本目录加入 sys.path，`python backend/server.py` 直接启动时
# `from backend.constants import ...` 与 `from constants import ...` 均会失败。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(BASE_DIR)
for _p in (BASE_DIR, _ROOT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.constants import SecurityConfig, ServerConfig
except ImportError:
    from constants import SecurityConfig, ServerConfig

from app_state import state
from core.priority_queue import priority_task_hub
from core.task_manager import task_hub
from routes import documents, extraction, knowledge, system, tasks
from utils.logger import api_logger, core_logger
from utils.metrics import metrics
from utils.middleware import PrometheusMetricsMiddleware, RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    initial_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_ROOT_DIR, "workspace_default")
    state.initialize(initial_path)

    await task_hub.start_workers(state)
    if priority_task_hub:
        await priority_task_hub.start(state)

    core_logger.info("Application startup complete", uptime_start=state.start_time)

    yield

    await task_hub.shutdown()
    if priority_task_hub:
        await priority_task_hub.stop()
    core_logger.info("Application shutdown complete")


app = FastAPI(title="Academic Clarity Backend", lifespan=lifespan)

app.add_middleware(PrometheusMetricsMiddleware, metrics_collector=metrics)
app.add_middleware(RequestLoggingMiddleware, logger=api_logger)

app.add_middleware(
    CORSMiddleware,
    allow_origins=SecurityConfig.ALLOWED_ORIGINS,
    allow_origin_regex=SecurityConfig.ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册顺序保持拆分前原序：system（/ws、/files、/health、/metrics、/configs）
# → tasks → documents（含 /workspace/sync）→ knowledge（/chat、/knowledge）
# → extraction（/extraction/*、/documents/export）
app.include_router(system.router)
app.include_router(tasks.router)
app.include_router(documents.router)
app.include_router(knowledge.router)
app.include_router(extraction.router)


if __name__ == "__main__":
    initial_port = int(sys.argv[1]) if len(sys.argv) > 1 else ServerConfig.DEFAULT_PORT
    for port in range(initial_port, initial_port + ServerConfig.MAX_PORT_RANGE):
        try:
            print(f"[Core] Starting server on port {port}...")
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            uvicorn.run(app, host="127.0.0.1", port=port)
            break
        except OSError:
            continue
