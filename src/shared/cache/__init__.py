"""Cache module.

Provides Redis-based caching functionality for the application.
"""

from src.shared.cache.redis_cache import RedisCache, redis_cache

__all__ = ["RedisCache", "redis_cache"]
