import os
from database import Database

from services.ocr_service import run_full_ocr_workflow
import asyncio

class WorkspaceService:
    def __init__(self, workspace_path, db: Database):
        self.workspace_path = workspace_path
        self.db = db

    def scan_and_sync(self):
        """
        Scans the physical workspace directory and synchronizes it with the database.
        Returns a summary of changes.
        """
        print(f"[Workspace] Syncing: {self.workspace_path}")

        # 1. 获取物理文件列表
        physical_files = [f for f in os.listdir(self.workspace_path) if f.lower().endswith('.pdf')]

        # 2. 获取数据库中已有的记录
        db_docs = self.db.get_all_documents()
        db_filenames = {d['filename'] for d in db_docs}

        sync_results = {"added": 0, "triggered_ocr": 0}

        # 3. 同步新文件 (物理有，DB无)
        for filename in physical_files:
            if filename not in db_filenames:
                full_path = os.path.join(self.workspace_path, filename)
                # 自动将物理文件导入索引 (OCR 状态为 pending)
                doc_id = self.db.add_document(filename, full_path, full_path)
                sync_results["added"] += 1
                print(f"  [Sync] New file detected: {filename}")

                # 4. 自动触发 OCR 全链路 (异步执行)
                try:
                    # 获取事件循环并启动任务
                    loop = asyncio.get_event_loop()
                    loop.create_task(run_full_ocr_workflow(doc_id, full_path, self.db))
                    sync_results["triggered_ocr"] += 1
                except Exception as e:
                    print(f"  [Sync] Failed to trigger OCR for {filename}: {e}")

        return sync_results
