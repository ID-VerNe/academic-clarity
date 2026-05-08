"""
Academic Clarity - System Constants and Defaults
统一管理所有魔法数字和配置常量
注意：此文件为代码常量模块，不存储用户配置
"""

# ==== Logging Config ====
class LoggingConfig:
    DEFAULT_LEVEL = "INFO"
    LOG_DIR = "logs"
    LOG_FILE = "academic_clarity.log"
    MAX_BYTES = 10 * 1024 * 1024
    BACKUP_COUNT = 5
    JSON_FORMAT = True

# ==== Cache Config ====
class CacheConfig:
    DEFAULT_TTL = 3600
    DOCUMENT_TTL = 7200
    OCR_RESULT_TTL = 86400
    SESSION_TTL = 3600
    MAX_SIZE = 1000
    REDIS_URL = "redis://localhost:6379/0"

# ==== OCR Service ====
class OCRConfig:
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    DEFAULT_RPM_LIMIT = 60
    DEFAULT_TPM_LIMIT = 100000
    DEFAULT_MAX_CONCURRENT = 5
    PAGE_RETRY_BACKOFF = [1, 2, 4]

# ==== API Key Pool ====
class KeyPoolConfig:
    UNHEALTHY_THRESHOLD = 5
    HEALTH_CHECK_COOLDOWN = 60
    ACQUIRE_TIMEOUT = 5.0
    RETRY_INTERVAL = 0.1

# ==== Task Manager ====
class TaskConfig:
    DEFAULT_CONCURRENCY = 10
    MAX_RETRIES = 3
    RETRY_BACKOFF = [1, 5, 30]
    MAX_FAILED_TASKS = 100

# ==== API Call ====
class APIConfig:
    REQUEST_TIMEOUT = 30.0
    CONNECT_TIMEOUT = 5.0
    MAX_RETRIES = 3
    DEFAULT_TEMPERATURE = 0.1
    RETRY_INTERVAL = 0.1

# ==== Metadata Extraction ====
class MetadataConfig:
    DEFAULT_LABEL = "Basic Insight"
    REQUIRED_FIELDS = ["title", "authors", "abstract"]

# ==== Security ====
class SecurityConfig:
    ALLOWED_ORIGINS = [
        "http://localhost:30517",
        "http://127.0.0.1:30517",
    ]
    ALLOWED_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"

# ==== Database ====
class DBConfig:
    TIMEOUT = 30.0
    WAL_MODE = True
    BUSY_TIMEOUT = 30000

# ==== Server ====
class ServerConfig:
    DEFAULT_PORT = 38391
    MAX_PORT_RANGE = 5
