import os
import json
from typing import List, Dict, Any, Optional

class ConfigService:
    def __init__(self, db):
        self.db = db
        try:
            import config as local_defaults
            self.defaults = local_defaults
        except ImportError:
            self.defaults = None

    def _get_val(self, db_key, config_attr, literal_default):
        db_val = self.db.get_config(db_key, "")
        if db_val and db_val.strip():
            return db_val
        if self.defaults:
            file_val = getattr(self.defaults, config_attr, None)
            if file_val:
                return file_val
        return literal_default

    def _get_val_int(self, db_key, config_attr, literal_default):
        val = self._get_val(db_key, config_attr, str(literal_default))
        try:
            return int(val)
        except (ValueError, TypeError):
            return literal_default

    def get_ocr_config(self):
        return {
            "api_key": self._get_val("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", ""),
            "api_base": self._get_val("API_BASE", "API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": self._get_val("OCR_MODEL", "OCR_MODEL", "")
        }

    def get_extract_config(self):
        return {
            "api_key": self._get_val("EXTRACT_API_KEY", "LLM_API_KEY", "sk-copilot-sdk-default"),
            "api_base": self._get_val("EXTRACT_API_BASE", "LLM_API_BASE", "http://localhost:37210/v1"),
            "model_name": self._get_val("EXTRACT_MODEL_NAME", "LLM_MODEL", "gpt-4.1")
        }

    def get_chat_config(self):
        return {
            "api_key": self._get_val("CHAT_API_KEY", "LLM_API_KEY", "sk-copilot-sdk-default"),
            "api_base": self._get_val("CHAT_API_BASE", "LLM_API_BASE", "http://localhost:37210/v1"),
            "model_name": self._get_val("CHAT_MODEL_NAME", "LLM_MODEL", "gpt-4.1")
        }

    def get_crossref_config(self):
        """Phase 1：CrossRef 礼貌池参数（mailto 可留空，仅降速不错败）。"""
        return {
            "mailto": self._get_val("CROSSREF_MAILTO", "CROSSREF_MAILTO", ""),
            "timeout": self._get_val_int("CROSSREF_TIMEOUT", "CROSSREF_TIMEOUT", 10),
            "max_retries": self._get_val_int("CROSSREF_MAX_RETRIES", "CROSSREF_MAX_RETRIES", 2),
        }
