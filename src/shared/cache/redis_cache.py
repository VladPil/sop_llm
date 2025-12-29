"""Redis cache manager for caching results.

Manages Redis connections and caching operations with automatic key generation,
TTL management, and comprehensive statistics tracking.
"""

import hashlib
import json
from typing import Any

from loguru import logger
from redis.asyncio import ConnectionPool, Redis

from src.core.config import settings
from src.shared.errors.domain_errors import ServiceUnavailableError


class RedisCache:
    """Redis cache manager with connection pooling and automatic key generation.

    Provides async operations for get, set, delete, and statistics retrieval
    with automatic cache key generation based on input parameters.

    Attributes:
        pool: Redis connection pool instance.
        client: Redis async client instance.
        ttl: Default time-to-live for cached entries in seconds.

    """

    def __init__(self) -> None:
        """Initialize Redis cache manager.

        Sets up connection pool and client attributes with None values.
        TTL is loaded from application settings.
        """
        self.pool: ConnectionPool | None = None
        self.client: Redis | None = None
        self.ttl: int = settings.cache.ttl

    async def connect(self) -> None:
        """Establish connection to Redis server.

        Creates connection pool and Redis client, then verifies connectivity
        with a ping operation.

        Raises:
            ServiceUnavailableError: If connection to Redis fails.

        """
        try:
            self.pool = ConnectionPool(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                password=settings.redis.password,
                decode_responses=True,
                max_connections=settings.redis.pool_max,
            )

            self.client = Redis(connection_pool=self.pool)

            # Verify connection
            await self.client.ping()

            logger.info(
                f"Connected to Redis at {settings.redis.host}:{settings.redis.port}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ServiceUnavailableError(
                message=f"Failed to connect to Redis: {e}",
                details={"operation": "connect", "error": str(e)},
            )

    async def disconnect(self) -> None:
        """Disconnect from Redis server.

        Closes Redis client and connection pool gracefully.
        Logs errors but does not raise exceptions.
        """
        try:
            if self.client:
                await self.client.close()

            if self.pool:
                await self.pool.disconnect()

            logger.info("Disconnected from Redis")

        except Exception as e:
            logger.error(f"Error while disconnecting from Redis: {e}")

    def _generate_cache_key(
        self,
        text: str,
        model: str,
        task_type: str,
        **kwargs: Any,
    ) -> str:
        """Generate cache key based on input parameters.

        Creates a unique cache key by hashing all input parameters including
        text, model name, task type, and any additional keyword arguments.

        Args:
            text: Input text to be processed.
            model: Name of the model being used.
            task_type: Type of task (e.g., 'classification', 'extraction').
            **kwargs: Additional parameters that affect the result.

        Returns:
            Unique cache key in format: {prefix}cache:{task_type}:{hash}.

        Examples:
            >>> cache._generate_cache_key("hello", "gpt-4", "translate", lang="ru")
            'sop_llm:cache:translate:a1b2c3d4...'

        """
        # Create string from all parameters
        params_str = f"{text}|{model}|{task_type}|{json.dumps(kwargs, sort_keys=True)}"

        # Generate hash
        key_hash = hashlib.sha256(params_str.encode()).hexdigest()

        return f"{settings.cache.prefix}cache:{task_type}:{key_hash}"

    async def get(
        self,
        text: str,
        model: str,
        task_type: str,
        **kwargs: Any,
    ) -> Any | None:
        """Retrieve cached result.

        Attempts to fetch a cached result matching the input parameters.
        Returns None if cache miss or if Redis client is not initialized.

        Args:
            text: Input text to be processed.
            model: Name of the model being used.
            task_type: Type of task (e.g., 'classification', 'extraction').
            **kwargs: Additional parameters that affect the result.

        Returns:
            Cached result if found, None otherwise.

        Examples:
            >>> result = await cache.get("hello", "gpt-4", "translate", lang="ru")
            >>> if result:
            ...     print("Cache hit!")

        """
        if not self.client:
            logger.warning("Redis client is not initialized")
            return None

        try:
            key = self._generate_cache_key(text, model, task_type, **kwargs)

            cached_value = await self.client.get(key)

            if cached_value:
                logger.info(f"Cache hit for key: {key}")
                return json.loads(cached_value)

            logger.debug(f"Cache miss for key: {key}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            # Don't raise exception, just return None
            return None

    async def set(
        self,
        text: str,
        model: str,
        task_type: str,
        result: Any,
        ttl: int | None = None,
        **kwargs: Any,
    ) -> bool:
        """Save result to cache.

        Stores the result in Redis with the specified TTL.
        Uses default TTL if not provided.

        Args:
            text: Input text to be processed.
            model: Name of the model being used.
            task_type: Type of task (e.g., 'classification', 'extraction').
            result: Result to cache (must be JSON serializable).
            ttl: Time to live in seconds (uses default if None).
            **kwargs: Additional parameters that affect the result.

        Returns:
            True if successfully cached, False otherwise.

        Examples:
            >>> success = await cache.set(
            ...     "hello", "gpt-4", "translate",
            ...     {"translation": "привет"}, lang="ru"
            ... )

        """
        if not self.client:
            logger.warning("Redis client is not initialized")
            return False

        try:
            key = self._generate_cache_key(text, model, task_type, **kwargs)

            value = json.dumps(result, ensure_ascii=False)

            await self.client.setex(
                key,
                ttl or self.ttl,
                value,
            )

            logger.debug(f"Result cached for key: {key}")
            return True

        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
            return False

    async def delete(
        self,
        text: str,
        model: str,
        task_type: str,
        **kwargs: Any,
    ) -> bool:
        """Delete cached value.

        Removes a specific cached entry matching the input parameters.

        Args:
            text: Input text to be processed.
            model: Name of the model being used.
            task_type: Type of task (e.g., 'classification', 'extraction').
            **kwargs: Additional parameters that affect the result.

        Returns:
            True if successfully deleted, False otherwise.

        Examples:
            >>> success = await cache.delete("hello", "gpt-4", "translate", lang="ru")

        """
        if not self.client:
            logger.warning("Redis client is not initialized")
            return False

        try:
            key = self._generate_cache_key(text, model, task_type, **kwargs)

            await self.client.delete(key)

            logger.debug(f"Deleted cache key: {key}")
            return True

        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False

    async def clear_all(self) -> bool:
        """Clear all service cache entries.

        Removes all cache entries belonging to this service by matching
        the configured cache prefix pattern.

        Returns:
            True if successfully cleared, False otherwise.

        Examples:
            >>> success = await cache.clear_all()
            >>> if success:
            ...     print("Cache cleared")

        """
        if not self.client:
            logger.warning("Redis client is not initialized")
            return False

        try:
            # Find all service keys
            keys = []
            async for key in self.client.scan_iter(
                match=f"{settings.cache.prefix}cache:*"
            ):
                keys.append(key)

            if keys:
                await self.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")

            return True

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Retrieve cache statistics.

        Gathers statistics about cache usage including number of entries,
        memory usage, and configured TTL.

        Returns:
            Dictionary containing cache statistics:
                - cached_entries: Number of cached entries.
                - used_memory: Human-readable memory usage.
                - ttl_seconds: Configured TTL in seconds.
                - error: Error message if stats retrieval failed.

        Examples:
            >>> stats = await cache.get_stats()
            >>> print(f"Cached entries: {stats['cached_entries']}")

        """
        if not self.client:
            return {"error": "Redis client is not initialized"}

        try:
            # Count keys
            keys_count = 0
            async for _ in self.client.scan_iter(
                match=f"{settings.cache.prefix}cache:*"
            ):
                keys_count += 1

            # Get memory info
            info = await self.client.info("memory")

            return {
                "cached_entries": keys_count,
                "used_memory": info.get("used_memory_human", "unknown"),
                "ttl_seconds": self.ttl,
            }

        except Exception as e:
            logger.error(f"Error retrieving cache stats: {e}")
            return {"error": str(e)}


# Global instance
redis_cache = RedisCache()
