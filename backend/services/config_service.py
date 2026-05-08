import os
import json
from typing import List, Dict, Any, Optional
from core.api_key_manager import KeyConfig, key_manager

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

    def _parse_key_configs(self, keys_json: str, default_api_base: str, default_model: str) -> List[KeyConfig]:
        configs = []
        if not keys_json:
            return configs
        
        try:
            keys_data = json.loads(keys_json)
            if isinstance(keys_data, list):
                for key_data in keys_data:
                    if isinstance(key_data, dict) and key_data.get("api_key"):
                        config = KeyConfig(
                            api_key=key_data["api_key"],
                            api_base=key_data.get("api_base", default_api_base),
                            model_name=key_data.get("model_name", default_model),
                            max_concurrent=key_data.get("max_concurrent", 5),
                            rpm_limit=key_data.get("rpm_limit", 60),
                            tpm_limit=key_data.get("tpm_limit", 100000),
                            enabled=key_data.get("enabled", True)
                        )
                        configs.append(config)
        except json.JSONDecodeError:
            pass
        return configs

    def get_ocr_key_configs(self) -> List[KeyConfig]:
        default_base = self._get_val("API_BASE", "API_BASE", "https://api.siliconflow.cn/v1")
        default_model = self._get_val("OCR_MODEL", "OCR_MODEL", "")
        keys_json = self.db.get_config("OCR_API_KEYS", "")
        return self._parse_key_configs(keys_json, default_base, default_model)
    
    def get_llm_key_configs(self) -> List[KeyConfig]:
        default_base = self._get_val("LLM_API_BASE", "LLM_API_BASE", "http://localhost:37210/v1")
        default_model = self._get_val("LLM_MODEL", "LLM_MODEL", "gpt-4.1")
        keys_json = self.db.get_config("LLM_API_KEYS", "")
        return self._parse_key_configs(keys_json, default_base, default_model)

    def initialize_key_pools(self) -> Dict[str, bool]:
        results = {}
        
        ocr_configs = self.get_ocr_key_configs()
        if ocr_configs:
            key_manager.initialize_pool("ocr", ocr_configs)
            results["ocr"] = True
        else:
            results["ocr"] = False
        
        llm_configs = self.get_llm_key_configs()
        if llm_configs:
            key_manager.initialize_pool("llm", llm_configs)
            results["llm"] = True
        else:
            results["llm"] = False
        
        return results

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
