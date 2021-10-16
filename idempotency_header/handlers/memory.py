import time
from typing import Any, Dict, Optional, Set

from fastapi.responses import JSONResponse

from idempotency_header.handlers.base import Handler


class MemoryHandler(Handler):
    """
    In-memory handler class.

    Warning: the in-memory handler has one major drawback; memory is not shared state.
    If you're running your web application on multiple pods/workers/threads,
    the stored responses will not be shared between them, so the middleware
    will not work as intended.

    This handler will mainly be suitable for local development or test purposes.
    """

    response_store: Dict[str, Dict[str, Any]] = {}
    keys: Set[str] = set()

    async def get_stored_response(self, idempotency_key: str) -> Optional[JSONResponse]:
        """
        Return a stored response if it exists, otherwise return None.
        """
        if idempotency_key not in self.response_store:
            return None

        if (expiry := self.response_store[idempotency_key]['expiry']) and expiry <= time.time():
            del self.response_store[idempotency_key]
            return None

        return JSONResponse(
            self.response_store[idempotency_key]['json'],
            status_code=self.response_store[idempotency_key]['status_code'],
        )

    async def store_response_data(
        self, idempotency_key: str, payload: dict, status_code: int, expiry: Optional[int] = None
    ) -> None:
        """
        Store a response in memory.
        """
        self.response_store[idempotency_key] = {
            'expiry': time.time() + expiry if expiry else None,
            'json': payload,
            'status_code': status_code,
        }

    async def store_idempotency_key(self, idempotency_key: str) -> None:
        """
        Store an idempotency key header value in a set.
        """
        self.keys.add(idempotency_key)

    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the set.
        """
        self.keys.remove(idempotency_key)

    async def is_key_pending(self, idempotency_key: str) -> bool:
        """
        Check whether a key exists in our set or not.
        """
        return idempotency_key in self.keys
