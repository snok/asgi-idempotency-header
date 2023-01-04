import time
import json
from dataclasses import dataclass
from typing import Optional, Tuple

from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from idempotency_header_middleware.backends.base import Backend


@dataclass()
class RedisBackend(Backend):
    def __init__(
        self,
        redis: Redis,
        keys_key: str = 'idempotency-key-keys',
        response_key: str = 'idempotency-key-responses',
        expiry: int = 60 * 60 * 24,
    ):
        self.redis = redis
        self.KEYS_KEY = keys_key
        self.RESPONSE_KEY = response_key
        self.expiry = expiry

    def _get_keys(self, idempotency_key: str) -> Tuple[str, str]:
        payload_key = self.RESPONSE_KEY + idempotency_key
        status_code_key = self.RESPONSE_KEY + idempotency_key + 'status-code'
        return payload_key, status_code_key

    async def get_stored_response(self, idempotency_key: str) -> Optional[JSONResponse]:
        """
        Return a stored response if it exists, otherwise return None.
        """
        payload_key, status_code_key = self._get_keys(idempotency_key)

        if not (payload := await self.redis.get(payload_key)):
            return None
        else:
            status_code = await self.redis.get(status_code_key)

        return JSONResponse(json.loads(payload), status_code=int(status_code))  # type: ignore[arg-type]

    async def store_response_data(self, idempotency_key: str, payload: dict, status_code: int) -> None:
        """
        Store a response in redis.
        """
        payload_key, status_code_key = self._get_keys(idempotency_key)

        await self.redis.set(payload_key, json.dumps(payload))
        await self.redis.set(status_code_key, status_code)

        if self.expiry:
            await self.redis.expire(payload_key, self.expiry)
            await self.redis.expire(status_code_key, self.expiry)

    async def store_idempotency_key(self, idempotency_key: str) -> bool:
        """
        Store an idempotency key header value in a sortedset.
        """
        return not bool(await self.redis.zadd(self.KEYS_KEY, {idempotency_key: time.time() + self.expiry},))

    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the set.
        """
        await self.redis.zrem(self.KEYS_KEY, idempotency_key)

    async def expire_idempotency_keys(self) -> None:
        """
        Remove any expired idempotency keys to avoid returning 409s
        after the response expires.
        """
        if self.expiry:
            await self.redis.zremrangebyscore(self.KEYS_KEY, '-inf', time.time())
