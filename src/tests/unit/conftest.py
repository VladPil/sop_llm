"""Pytest configuration для unit тестов."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client для тестирования."""
    redis = MagicMock()
    redis.hset = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    redis.zadd = AsyncMock()
    redis.zpopmin = AsyncMock(return_value=[])
    redis.zcard = AsyncMock(return_value=0)
    redis.set = AsyncMock()
    redis.expire = AsyncMock()
    redis.setex = AsyncMock()
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.llen = AsyncMock(return_value=0)
    redis.ping = AsyncMock(return_value=True)
    redis.close = AsyncMock()
    return redis
