import json
import logging
import uuid
from collections import namedtuple
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Optional, Union

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from idempotency_header_middleware.backends.base import Backend

logger = logging.getLogger('asgi_idempotency_header')


def is_valid_uuid(uuid_: str) -> bool:
    """
    Check whether a string is a uuid.
    """
    try:
        return bool(uuid.UUID(uuid_, version=4).hex)
    except ValueError:
        return False


@dataclass
class IdempotencyHeaderMiddleware:
    app: ASGIApp
    backend: Backend
    idempotency_header_key: str = 'Idempotency-Key'
    replay_header_key: str = 'Idempotent-Replayed'
    enforce_uuid4_formatting: bool = False
    expiry: Optional[int] = 60 * 60 * 24

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> Union[JSONResponse, Any]:
        """
        Enable idempotent operations in POST and PATCH endpoints.
        """
        if scope['type'] != 'http' or scope['method'] not in ['POST', 'PATCH']:
            logger.debug('Returning response directly since request method is already idempotent')
            return await self.app(scope, receive, send)

        request_headers = Headers(scope=scope)
        idempotency_key = request_headers.get(self.idempotency_header_key.lower())

        if not idempotency_key:
            logger.debug('Returning response directly since no idempotency key is present in the request headers')
            return await self.app(scope, receive, send)

        elif self.enforce_uuid4_formatting and not is_valid_uuid(idempotency_key):
            logger.warning('Returning 422 since idempotency key is malformed')
            payload = {'detail': f"'{self.idempotency_header_key}' header value must be formatted as a v4 UUID"}
            response = JSONResponse(payload, 422)
            return await response(scope, receive, send)

        if stored_response := await self.backend.get_stored_response(idempotency_key):
            logger.info("Returning stored response from idempotency key '%s'", idempotency_key)
            stored_response.headers[self.replay_header_key] = 'true'
            return await stored_response(scope, receive, send)

        request_already_pending = await self.backend.store_idempotency_key(idempotency_key)

        if request_already_pending:
            msg = "Returning 409 since a request is already in progress for idempotency key '%s'"
            logger.warning(msg, idempotency_key)
            payload = {'detail': f"Request already pending for idempotency key '{idempotency_key}'"}
            response = JSONResponse(payload, 409)
            return await response(scope, receive, send)

        response_state = namedtuple('response_state', ['status_code', 'response_headers', 'expiry'])

        async def send_wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                response_state.status_code = message['status']
                response_state.response_headers = Headers({k.decode(): v.decode() for (k, v) in message['headers']})

            elif message['type'] == 'http.response.body':
                if (
                    'content-type' in response_state.response_headers
                    and response_state.response_headers['content-type'] != 'application/json'
                ):
                    logger.info('Cannot handle non-JSON response. Returning early.')
                    await self.backend.clear_idempotency_key(idempotency_key)
                    await send(message)
                    return

                try:
                    json_payload = json.loads(message['body'])
                except JSONDecodeError:
                    logger.debug('Failed to decode payload as JSON. Returning early.')
                    await self.backend.clear_idempotency_key(idempotency_key)
                    await send(message)
                    return

                logger.info("Storing response for idempotency key '%s'", idempotency_key)
                await self.backend.store_response_data(
                    idempotency_key=idempotency_key,
                    payload=json_payload,
                    status_code=response_state.status_code,
                    expiry=self.expiry,
                )
                await self.backend.clear_idempotency_key(idempotency_key)

            await send(message)

        await self.app(scope, receive, send_wrapper)
