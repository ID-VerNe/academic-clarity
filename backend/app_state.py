"""应用全局状态与启动引导（B-SRP-03，拆分自 server.py）。

server.py 只做应用装配；本模块持有唯一 AppState 单例 `state`，
lifespan 与路由层共用（`from server import app, state` 语义保持不变）。
"""
import os
import time

from database import Database
from services import knowledge_service
from services.workspace_service import WorkspaceService
from core.task_manager import task_hub
from utils.cache import init_cache
from utils.logger import core_logger
from utils.metrics import metrics


class AppState:
    def __init__(self):
        self.workspace_path = ""
        self.db = None
        self.workspace_service = None
        self.task_hub = task_hub
        self.start_time = time.time()

    def initialize(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        self.workspace_path = path
        self.db = Database(os.path.join(path, "library.db"))
        self.workspace_service = WorkspaceService(path, self.db)

        init_cache()

        knowledge_service.init_store(path)   # Phase 2：{workspace}/knowledge/index.sqlite

        metrics.set_app_info(
            version="1.0.0",
            workspace=path
        )

        core_logger.info(f"Application initialized", workspace=path)
        print(f"[Core] Active workspace: {path}")


state = AppState()
