"""
Academic Clarity - System Constants and Defaults
统一管理所有魔法数字和配置常量
注意：此文件为代码常量模块，不存储用户配置
"""

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

# ==== Logging ====
class LoggingConfig:
    LOG_DIR = "logs"
    MAX_LOG_SIZE = 10 * 1024 * 1024
    BACKUP_COUNT = 5
    JSON_FORMAT = True
    LOG_LEVEL = "INFO"

# ==== Metrics (Prometheus) ====
class MetricsConfig:
    ENABLED = True
    EXPORT_INTERVAL = 60
    RETENTION_HOURS = 24

# ==== Cache ====
class CacheConfig:
    ENABLED = False
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    DEFAULT_TTL = 300
    DOCUMENT_TTL = 600
    KEYPOOL_TTL = 30
    MAX_IN_MEMORY_SIZE = 1000

# ==== WebSocket ====
class WebSocketConfig:
    ENABLED = True
    HEARTBEAT_INTERVAL = 30
    MAX_CONNECTIONS = 100
    MESSAGE_QUEUE_SIZE = 1000

# ==== Priority Queue ====
class PriorityConfig:
    DEFAULT_PRIORITY = 2
    CRITICAL_RETRY_INTERVAL = 0.5
    HIGH_RETRY_INTERVAL = 1.0
    NORMAL_RETRY_INTERVAL = 5.0
    DEAD_LETTER_RETENTION_HOURS = 24
