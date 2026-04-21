import os

class ConfigService:
    def __init__(self, db):
        self.db = db
        # 尝试从本地 config.py 导入默认值
        try:
            import config as local_defaults
            self.defaults = local_defaults
        except ImportError:
            self.defaults = None

    def _get_fallback(self, db_key, config_attr, literal_default):
        """数据库优先 -> config.py 次之 -> 硬编码字面量保底"""
        db_val = self.db.get_config(db_key, "")
        if db_val:
            return db_val
        return getattr(self.defaults, config_attr, literal_default) if self.defaults else literal_default

    def get_ocr_config(self):
        return {
            "api_key": self._get_fallback("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", ""),
            "api_base": self._get_fallback("API_BASE", "API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": self._get_fallback("MODEL_NAME", "DEFAULT_MODEL", "openai/deepseek-ai/DeepSeek-OCR")
        }

    def get_extract_config(self):
        # 默认提取服务共享 OCR 配置，除非库中有特殊覆盖
        return {
            "api_key": self._get_fallback("EXTRACT_API_KEY", "DEEPSEEK_API_KEY", "sk-copilot-sdk-default"),
            "api_base": self._get_fallback("EXTRACT_API_BASE", "API_BASE", "http://localhost:37210/v1"),
            "model_name": self._get_fallback("EXTRACT_MODEL_NAME", "DEFAULT_MODEL", "gpt-4.1")
        }

    def get_chat_config(self):
        return {
            "api_key": self._get_fallback("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", ""),
            "api_base": self._get_fallback("API_BASE", "API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": "deepseek-ai/DeepSeek-V3"
        }
