from abc import ABC, abstractmethod
from typing import Optional

from starlette.responses import Response


class Backend(ABC):
    @abstractmethod
    async def get_stored_response(self, idempotency_key: str) -> Optional[Response]:
        """
        Return a stored response if it exists, otherwise return None.
        """
        raise NotImplementedError()

    @abstractmethod
    async def store_response_data(
        self, idempotency_key: str, payload: dict, status_code: int, expiry: Optional[int] = None
    ) -> None:
        """
        Store a response to an appropriate backend (redis, postgres, etc.).
        """
        raise NotImplementedError()

    @abstractmethod
    async def store_idempotency_key(self, idempotency_key: str) -> bool:
        """
        Store an idempotency key header value in a set.

        The purpose of this is to make sure we reject repeated requests
        (with a 409) when a request has been initiated but is not yet completed.

        All implementations of this most likely will want to implement some locking
        mechanism to prevent race conditions and double execution.
        """
        raise NotImplementedError()

    @abstractmethod
    async def clear_idempotency_key(self, idempotency_key: str) -> None:
        """
        Remove an idempotency header value from a set.

        Once a request has been completed, we should pop the idempotency
        key stored when calling the 'store_idempotency_key' method.
        """
        raise NotImplementedError()
