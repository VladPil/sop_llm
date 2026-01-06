"""Константы для SOP LLM Executor.

Централизованное хранилище всех магических чисел и строк.
"""

# === HTTP и API ===
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_DOCS_URL = "/docs"
DEFAULT_REDOC_URL = "/redoc"
DEFAULT_OPENAPI_URL = "/openapi.json"

# === Таймауты (в секундах) ===
DEFAULT_HTTP_TIMEOUT = 60
DEFAULT_WEBHOOK_TIMEOUT = 30
DEFAULT_JSON_FIXER_TIMEOUT = 30

# === Повторы (retries) ===
DEFAULT_HTTP_MAX_RETRIES = 2
DEFAULT_WEBHOOK_MAX_RETRIES = 3
DEFAULT_LITELLM_MAX_RETRIES = 3

# === TTL (Time To Live в секундах) ===
DEFAULT_SESSION_TTL = 3600  # 1 час
DEFAULT_IDEMPOTENCY_TTL = 86400  # 24 часа

# === Лимиты логов и очередей ===
DEFAULT_LOGS_MAX_RECENT = 100

# === LLM параметры ===
DEFAULT_CONTEXT_WINDOW = 4096
DEFAULT_MAX_TOKENS = 2048

# === GPU настройки ===
DEFAULT_GPU_INDEX = 0
DEFAULT_MAX_VRAM_USAGE_PERCENT = 90.0
DEFAULT_VRAM_RESERVE_MB = 512

# === Models ===
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
DEFAULT_MODELS_DIR = "./models"

# === Redis ===
DEFAULT_REDIS_HOST = "redis"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 1  # DB 1 для sop_llm

# === Kafka ===
DEFAULT_KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"

# === Langfuse ===
DEFAULT_LANGFUSE_HOST = "http://langfuse:3000"

# === CORS ===
DEFAULT_CORS_ORIGINS = ["*"]

# === Server ===
DEFAULT_SERVER_HOST = "0.0.0.0"
DEFAULT_SERVER_PORT = 8000

# === Названия приложений ===
DEFAULT_APP_NAME = "SOP LLM Executor"

# === Форматы ===
ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# === Redis Keys Prefixes ===
REDIS_SESSION_PREFIX = "session:"
REDIS_IDEMPOTENCY_PREFIX = "idempotency:"
REDIS_QUEUE_KEY = "queue:tasks"
REDIS_PROCESSING_KEY = "queue:processing"
REDIS_LOGS_PREFIX = "logs:"
REDIS_LOGS_RECENT_KEY = "logs:recent"

# === Default values для requests (если не переопределены) ===
DEFAULT_TOP_P = 1.0
DEFAULT_TOP_K = 40
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_PRIORITY = 0.0
DEFAULT_STREAM = False
DEFAULT_CLEANUP = True
