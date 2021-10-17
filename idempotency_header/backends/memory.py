import time
from typing import Any, Dict, Optional, Set

from starlette.responses import JSONResponse

from idempotency_header.backends.base import Backend


class MemoryBackend(Backend):
    """
    In-memory backend.

    This backend should probably not be used in deployed environments where
    applications are hosted on several nodes, since memory is not shared state
    and the response caching then won't work as intended.

    The backend is mainly here for local development or testing.
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

    async def store_idempotency_key(self, idempotency_key: str) -> bool:
        """
        Store an idempotency key header value in a set.
        """
        if idempotency_key in self.keys:
            return True

        self.keys.add(idempotency_key)
        return False

    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the set.
        """
        self.keys.remove(idempotency_key)
