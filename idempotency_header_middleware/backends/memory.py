import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from starlette.responses import JSONResponse

from idempotency_header_middleware.backends.base import Backend


@dataclass()
class MemoryBackend(Backend):
    """
    In-memory backend.

    This backend should probably not be used in deployed environments where
    applications are hosted on several nodes, since memory is not shared state
    and the response caching then won't work as intended.

    The backend is mainly here for local development or testing.
    """

    expiry: Optional[int] = 60 * 60 * 24

    response_store: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    idempotency_keys: Dict[str, Optional[float]] = field(default_factory=dict)

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

    async def store_response_data(self, idempotency_key: str, payload: dict, status_code: int) -> None:
        """
        Store a response in memory.
        """
        self.response_store[idempotency_key] = {
            'expiry': time.time() + self.expiry if self.expiry else None,
            'json': payload,
            'status_code': status_code,
        }

    async def store_idempotency_key(self, idempotency_key: str) -> bool:
        """
        Store an idempotency key header value in a set.
        """
        if idempotency_key in self.idempotency_keys:
            return True

        self.idempotency_keys[idempotency_key] = time.time() + float(self.expiry or 0) if self.expiry else None
        return False

    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the set.
        """
        del self.idempotency_keys[idempotency_key]

    async def expire_idempotency_keys(self) -> None:
        """
        Remove any expired idempotency keys to avoid returning 409s
        after the response expires.
        """
        if not self.expiry:
            return

        now = time.time()
        for idempotency_key in list(self.idempotency_keys):
            if (expiry := self.idempotency_keys.get(idempotency_key)) and expiry <= now:
                del self.idempotency_keys[idempotency_key]
