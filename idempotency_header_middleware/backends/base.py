from abc import ABC, abstractmethod
from typing import Optional

from starlette.responses import Response


class Backend(ABC):
    expiry: Optional[int] = 60 * 60 * 24

    @abstractmethod
    async def get_stored_response(self, idempotency_key: str) -> Optional[Response]:
        """
        Return a stored response if it exists, otherwise return None.
        """
        ...

    @abstractmethod
    async def store_response_data(self, idempotency_key: str, payload: dict, status_code: int) -> None:
        """
        Store a response to an appropriate backend (redis, postgres, etc.).
        """
        ...

    @abstractmethod
    async def store_idempotency_key(self, idempotency_key: str) -> bool:
        """
        Store an idempotency key header value in a set, if it doesn't already exist.

        Returns False if we wrote to the backend, True if the key already existed.

        The primary purpose of this method is to make sure we reject repeated requests
        (with a 409) when a request has been initiated but is not yet completed.

        All implementations of this most likely will want to implement some locking
        mechanism to prevent race conditions and double execution.
        """
        ...

    @abstractmethod
    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from the backend.

        Once a request has been completed, we should pop the idempotency
        key stored in 'store_idempotency_key'.
        """
        ...

    @abstractmethod
    async def expire_idempotency_keys(self) -> None:
        """
        Remove any expired idempotency keys to avoid returning 409s
        after the response expires.
        """
        ...
