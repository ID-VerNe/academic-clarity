"""配置读取与写入的统一入口（B-SRP-15 / B-SRP-24 / B-DRY-09）。

读取回退链：DB → config.py（可选本地覆盖层）→ 字面默认值。
三个 LLM 配置（OCR / 提取 / 对话）经 _api_config 统一工厂构造，
{"api_key", "api_base", "model_name"} 键名只在此处定义。
"""


class ConfigService:
    # POST /configs 白名单：SettingsModal FIELDS（DEEPSEEK_API_KEY/API_BASE/OCR_MODEL）
    # + TABLE_STYLE（设置弹窗同批保存）+ GET /configs 键（WORKSPACE_PATH）
    # + EXTRACT_*（E2E 测试注入、get_extract_config 消费）
    CONFIG_WHITELIST = frozenset({
        "DEEPSEEK_API_KEY", "API_BASE", "OCR_MODEL", "TABLE_STYLE", "WORKSPACE_PATH",
        "EXTRACT_API_KEY", "EXTRACT_API_BASE", "EXTRACT_MODEL_NAME",
    })

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

    def _api_config(self, db_keys, cfg_keys, defaults):
        """统一工厂（B-DRY-09）：db 键 / config.py 属性 / 字面默认值三元组一一对应。"""
        return dict(zip(
            ("api_key", "api_base", "model_name"),
            (self._get_val(d, c, l) for d, c, l in zip(db_keys, cfg_keys, defaults)),
        ))

    def get_ocr_config(self):
        return self._api_config(
            ("DEEPSEEK_API_KEY", "API_BASE", "OCR_MODEL"),
            ("DEEPSEEK_API_KEY", "API_BASE", "OCR_MODEL"),
            ("", "https://api.siliconflow.cn/v1", ""),
        )

    def get_extract_config(self):
        return self._api_config(
            ("EXTRACT_API_KEY", "EXTRACT_API_BASE", "EXTRACT_MODEL_NAME"),
            ("LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"),
            ("sk-copilot-sdk-default", "http://localhost:37210/v1", "gpt-4.1"),
        )

    def get_chat_config(self):
        return self._api_config(
            ("CHAT_API_KEY", "CHAT_API_BASE", "CHAT_MODEL_NAME"),
            ("LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"),
            ("sk-copilot-sdk-default", "http://localhost:37210/v1", "gpt-4.1"),
        )

    def get_crossref_config(self):
        """Phase 1：CrossRef 礼貌池参数（mailto 可留空，仅降速不错败）。"""
        return {
            "mailto": self._get_val("CROSSREF_MAILTO", "CROSSREF_MAILTO", ""),
            "timeout": self._get_val_int("CROSSREF_TIMEOUT", "CROSSREF_TIMEOUT", 10),
            "max_retries": self._get_val_int("CROSSREF_MAX_RETRIES", "CROSSREF_MAX_RETRIES", 2),
        }

    def get_ui_config(self, workspace_path):
        """聚合 GET /configs 返回的全部键（响应结构逐字不变，B-SRP-15）。"""
        ocr = self.get_ocr_config()
        return {
            "DEEPSEEK_API_KEY": ocr["api_key"],
            "API_BASE": ocr["api_base"],
            "OCR_MODEL": ocr["model_name"],
            "WORKSPACE_PATH": workspace_path,
            "TABLE_STYLE": self.db.get_config("TABLE_STYLE", "three-line"),
        }

    def set_config(self, key, value):
        """白名单写入（B-SRP-15）；非白名单键不落库并返回 False。"""
        if key not in self.CONFIG_WHITELIST:
            return False
        self.db.set_config(key, value)
        return True
