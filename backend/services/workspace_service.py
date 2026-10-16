import os
import asyncio

from database import Database
from utils.logger import core_logger

try:
    from backend.constants import FileConfig
except ImportError:
    from constants import FileConfig


class WorkspaceService:
    def __init__(self, workspace_path, db: Database):
        self.workspace_path = workspace_path
        self.db = db

    def scan_and_sync(self):
        """
        同步扫描工作区目录
        Returns: list of (doc_id, full_path) for NEW files.
        """
        core_logger.info(f"[Workspace] Scanning: {self.workspace_path}")
        physical_files = [f for f in os.listdir(self.workspace_path)
                          if f.lower().endswith(FileConfig.SUPPORTED_EXTS)]
        db_docs = self.db.get_all_documents()
        db_filenames = {d['filename'] for d in db_docs}

        new_tasks = []
        for filename in physical_files:
            if filename not in db_filenames:
                full_path = os.path.join(self.workspace_path, filename)
                doc_id = self.db.add_document(filename, full_path, full_path)
                new_tasks.append((doc_id, full_path))
                core_logger.info(f"  [Sync] New document indexed: {filename}")

        return new_tasks

    async def async_scan_and_sync(self):
        """
        异步扫描工作区目录，避免阻塞事件循环（B-DRY-01：to_thread 单行包装）
        Returns: list of (doc_id, full_path) for NEW files.
        """
        return await asyncio.to_thread(self.scan_and_sync)
