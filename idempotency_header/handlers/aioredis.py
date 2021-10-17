import json
from typing import Optional

from aioredis.client import Redis
from fastapi.responses import JSONResponse

from idempotency_header.handlers.base import Handler


class RedisHandler(Handler):
    """
    Redis handler class.
    """

    def __init__(self, redis: Redis):
        self.redis = redis
        self.KEYS_KEY = 'idempotency-key-keys'
        self.RESPONSE_STORE = 'idempotency-key-responses'

    def get_keys(self, idempotency_key: str) -> tuple[str, str]:
        payload_key = self.RESPONSE_STORE + idempotency_key
        status_code_key = self.RESPONSE_STORE + idempotency_key + 'status-code'
        return payload_key, status_code_key

    async def get_stored_response(self, idempotency_key: str) -> Optional[JSONResponse]:
        """
        Return a stored response if it exists, otherwise return None.
        """
        payload_key, status_code_key = self.get_keys(idempotency_key)

        if not (payload := await self.redis.get(payload_key)):
            return None
        else:
            status_code = await self.redis.get(status_code_key)

        return JSONResponse(json.loads(payload), status_code=int(status_code))

    async def store_response_data(
        self, idempotency_key: str, payload: dict, status_code: int, expiry: Optional[int] = None
    ) -> None:
        """
        Store a response in redis.
        """
        payload_key, status_code_key = self.get_keys(idempotency_key)

        await self.redis.set(payload_key, json.dumps(payload))
        await self.redis.set(status_code_key, status_code)

        if expiry:
            await self.redis.expire(payload_key, expiry)
            await self.redis.expire(status_code_key, expiry)

    async def store_idempotency_key(self, idempotency_key: str) -> None:
        """
        Store an idempotency key header value in a set.
        """
        await self.redis.sadd(self.KEYS_KEY, idempotency_key)

    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the set.
        """
        await self.redis.srem(self.KEYS_KEY, idempotency_key)

    async def is_key_pending(self, idempotency_key: str) -> bool:
        """
        Check whether a key exists in our set or not.
        """
        keys = await self.redis.smembers(self.KEYS_KEY)
        return idempotency_key in keys
