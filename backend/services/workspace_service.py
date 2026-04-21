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
        Scans physical directory. Returns list of (doc_id, full_path) for NEW files.
        """
        print(f"[Workspace] Scanning: {self.workspace_path}")
        physical_files = [f for f in os.listdir(self.workspace_path) if f.lower().endswith('.pdf')]
        db_docs = self.db.get_all_documents()
        db_filenames = {d['filename'] for d in db_docs}

        new_tasks = []
        for filename in physical_files:
            if filename not in db_filenames:
                full_path = os.path.join(self.workspace_path, filename)
                doc_id = self.db.add_document(filename, full_path, full_path)
                new_tasks.append((doc_id, full_path))
                print(f"  [Sync] New document indexed: {filename}")
        
        return new_tasks
