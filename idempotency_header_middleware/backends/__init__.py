from idempotency_header_middleware.backends.memory import MemoryBackend
from idempotency_header_middleware.backends.redis import RedisBackend

# Legacy name of the redis backend for backwards compatibility
AioredisBackend = RedisBackend

__all__ = (
    'AioredisBackend',
    'RedisBackend',
    'MemoryBackend',
)
