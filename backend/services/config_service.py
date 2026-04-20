class ConfigService:
    def __init__(self, db):
        self.db = db

    def get_ocr_config(self):
        return {
            "api_key": self.db.get_config("DEEPSEEK_API_KEY", ""),
            "api_base": self.db.get_config("API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": self.db.get_config("MODEL_NAME", "openai/deepseek-ai/DeepSeek-OCR")
        }

    def get_extract_config(self):
        return {
            "api_key": self.db.get_config("EXTRACT_API_KEY", "sk-copilot-sdk-default"),
            "api_base": self.db.get_config("EXTRACT_API_BASE", "http://localhost:37210/v1"),
            "model_name": self.db.get_config("EXTRACT_MODEL_NAME", "gpt-4.1")
        }

    def get_chat_config(self):
        return {
            "api_key": self.db.get_config("DEEPSEEK_API_KEY", ""),
            "api_base": self.db.get_config("API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": "deepseek-ai/DeepSeek-V3"
        }
