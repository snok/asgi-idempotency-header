import json
import logging
from collections import namedtuple
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Any, List, Union
from uuid import UUID

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from idempotency_header_middleware.backends.base import Backend

logger = logging.getLogger(__name__)


def is_valid_uuid(uuid_: str) -> bool:
    """
    Check whether a string is a valid v4 uuid.
    """
    try:
        return bool(UUID(uuid_, version=4))
    except ValueError:
        return False


@dataclass
class IdempotencyHeaderMiddleware:
    app: ASGIApp
    backend: Backend
    idempotency_header_key: str = 'Idempotency-Key'
    replay_header_key: str = 'Idempotent-Replayed'
    enforce_uuid4_formatting: bool = False
    applicable_methods: List[str] = field(default_factory=lambda: ['POST', 'PATCH'])

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> Union[JSONResponse, Any]:
        """
        Enable idempotent operations in POST and PATCH endpoints.
        """
        if scope['type'] != 'http' or scope['method'] not in self.applicable_methods:
            return await self.app(scope, receive, send)

        if not (idempotency_key := Headers(scope=scope).get(self.idempotency_header_key.lower())):
            return await self.app(scope, receive, send)

        if self.enforce_uuid4_formatting and not is_valid_uuid(idempotency_key):
            payload = {'detail': f"'{self.idempotency_header_key}' header value must be formatted as a v4 UUID"}
            response = JSONResponse(payload, 422)
            return await response(scope, receive, send)

        await self.backend.expire_idempotency_keys()
        if stored_response := await self.backend.get_stored_response(idempotency_key):
            stored_response.headers[self.replay_header_key] = 'true'
            return await stored_response(scope, receive, send)

        # Check if request is already pending
        if await self.backend.store_idempotency_key(idempotency_key):
            payload = {'detail': f"Request already pending for idempotency key '{idempotency_key}'"}
            response = JSONResponse(payload, 409)
            return await response(scope, receive, send)

        # Spin up a request-specific class instance, so we can read and write to it in the `send_wrapper` below
        response_state = namedtuple('response_state', ['status_code', 'response_headers'])

        async def send_wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                response_state.status_code = message['status']
                response_state.response_headers = Headers(scope=message)

            elif message['type'] == 'http.response.body':
                if (
                    'content-type' in response_state.response_headers
                    and response_state.response_headers['content-type'] != 'application/json'
                ):
                    await self.backend.clear_idempotency_key(idempotency_key)
                    await send(message)
                    return

                try:
                    json_payload = json.loads(message['body'])
                except JSONDecodeError as e:
                    logger.info('Failed to save JSON response: %s', e)
                    await self.backend.clear_idempotency_key(idempotency_key)
                    await send(message)
                    return

                await self.backend.store_response_data(
                    idempotency_key=idempotency_key,
                    payload=json_payload,
                    status_code=response_state.status_code,
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)
