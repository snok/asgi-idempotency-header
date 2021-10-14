import time
from typing import Any, Dict, Optional, Set

from fastapi.responses import JSONResponse
from starlette.responses import Response

from idempotence.handlers.base import Handler


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

    def get_stored_response(self, idempotency_key: str) -> Optional[Response]:
        """
        Return a stored response if it exists, otherwise return None.
        """
        if idempotency_key not in self.response_store:
            return None

        if (expiry := self.response_store[idempotency_key]['expiry']) and expiry >= time.time():
            del self.response_store[idempotency_key]

        return JSONResponse(
            content=self.response_store[idempotency_key]['json'],
            status_code=self.response_store[idempotency_key]['status_code'],
        )

    def store_response_data(self, idempotency_key: str, response: JSONResponse, expiry: Optional[int] = None) -> None:
        """
        Store a response in memory.
        """
        self.response_store[idempotency_key] = {
            'expiry': time.time() + expiry if expiry else None,
            'json': response.json(),
            'status_code': response.status_code,
        }

    def store_idempotency_key(self, idempotency_key: str) -> None:
        """
        Store an idempotency key header value in a set.
        """
        self.keys.add(idempotency_key)

    def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the set.
        """
        self.keys.remove(idempotency_key)

    def is_key_pending(self, idempotency_key: str) -> bool:
        """
        Check whether a key exists in our set or not.
        """
        return idempotency_key in self.keys
