import os

class ConfigService:
    def __init__(self, db):
        self.db = db
        try:
            import config as local_defaults
            self.defaults = local_defaults
        except ImportError:
            self.defaults = None

    def _get_val(self, db_key, config_attr, literal_default):
        """
        优先级：数据库设置 > config.py 本地文件 > 硬编码保底值
        """
        # 1. 尝试从数据库读取
        db_val = self.db.get_config(db_key, "")
        if db_val and db_val.strip():
            return db_val
            
        # 2. 尝试从 config.py 读取
        if self.defaults:
            file_val = getattr(self.defaults, config_attr, None)
            if file_val:
                return file_val
                
        # 3. 返回保底值
        return literal_default

    def get_ocr_config(self):
        """获取 OCR 配置 (默认使用硅基流动 + DeepSeek Key)"""
        return {
            "api_key": self._get_val("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", ""),
            "api_base": self._get_val("API_BASE", "API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": self._get_val("OCR_MODEL", "OCR_MODEL", "openai/deepseek-ai/DeepSeek-OCR")
        }

    def get_extract_config(self):
        """获取提取配置 (默认使用本地 LLM 中转)"""
        return {
            "api_key": self._get_val("EXTRACT_API_KEY", "LLM_API_KEY", "sk-copilot-sdk-default"),
            "api_base": self._get_val("EXTRACT_API_BASE", "LLM_API_BASE", "http://localhost:37210/v1"),
            "model_name": self._get_val("EXTRACT_MODEL_NAME", "LLM_MODEL", "gpt-4.1")
        }

    def get_chat_config(self):
        """获取对话配置 (默认与提取服务共享本地 LLM 中转)"""
        return {
            "api_key": self._get_val("CHAT_API_KEY", "LLM_API_KEY", "sk-copilot-sdk-default"),
            "api_base": self._get_val("CHAT_API_BASE", "LLM_API_BASE", "http://localhost:37210/v1"),
            "model_name": self._get_val("CHAT_MODEL_NAME", "LLM_MODEL", "gpt-4.1")
        }
