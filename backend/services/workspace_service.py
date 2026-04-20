import os
from database import Database

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
        
        sync_results = {"added": 0, "removed": 0}

        # 3. 同步新文件 (物理有，DB无)
        for filename in physical_files:
            if filename not in db_filenames:
                full_path = os.path.join(self.workspace_path, filename)
                # 自动将物理文件导入索引 (OCR 状态为 pending)
                self.db.add_document(filename, full_path, full_path)
                sync_results["added"] += 1
                print(f"  [Sync] New file detected and indexed: {filename}")

        # 4. 清理已丢失文件 (DB有，物理无 - 可选，目前建议保留记录但标记)
        # 暂时只做增量同步，不做硬删除，防止用户移动文件夹导致元数据丢失

        return sync_results
