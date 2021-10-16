import json
import logging
import uuid
from json import JSONDecodeError
from typing import Any, Callable, Optional, TypeVar

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from idempotency_header.handlers.base import Handler

logger = logging.getLogger('fastapi_idempotency_header')


def validate_uuid(uuid_: str) -> bool:
    """
    Validate string as uuid4.
    """
    try:
        return bool(uuid.UUID(uuid_, version=4).hex)
    except ValueError:
        return False


T = TypeVar('T', bound=type[Handler])


def get_idempotency_header_middleware(
    app: FastAPI,
    handler: T,
    idempotency_header_key: str = 'Idempotency-Key',
    replay_header_key: str = 'Idempotent-Replayed',
    enforce_uuid4_formatting: bool = False,
    expiry: Optional[int] = 60 * 60 * 24,
) -> None:
    h = handler()

    @app.middleware('http')
    async def idempotency_header_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
        """
        Enable idempotent operations in POST and PATCH endpoints.
        """
        if request.method not in ['POST', 'PATCH']:
            logger.debug('Returning response directly since request method is already idempotent')
            return await call_next(request)

        if not (idempotency_key := request.headers.get(idempotency_header_key.lower())):
            logger.debug('Returning response directly since no idempotency key is present in the request headers')
            return await call_next(request)
        elif enforce_uuid4_formatting and not validate_uuid(idempotency_key):
            logger.warning('Returning 422 since idempotency key is malformed')
            return JSONResponse(
                {'detail': f"'{idempotency_header_key}' header value must be formatted as a v4 UUID."}, 422
            )

        if stored_response := h.get_stored_response(idempotency_key):
            logger.info("Returning stored response from idempotency key '%s'", idempotency_key)
            stored_response.headers[replay_header_key] = 'true'
            return stored_response

        if h.is_key_pending(idempotency_key):
            logger.warning(
                "Returning 409 since a request is already in progress for idempotency key '%s'", idempotency_key
            )
            return JSONResponse({'detail': f"Request already pending for idempotency key '{idempotency_key}'."}, 409)

        # Store key before calling the endpoint, so we can reject following requests with a 409 like above
        h.store_idempotency_key(idempotency_key)

        # Call the endpoint
        response: StreamingResponse = await call_next(request)

        headers = dict(response.headers)
        byte_payload = [item async for item in response.body_iterator][0]

        if 'content-type' not in headers:
            try:
                json_payload = json.loads(byte_payload)
            except JSONDecodeError:
                logger.debug('Failed to decode payload as JSON. Returning early.')
                h.clear_idempotency_key(idempotency_key)
                return response
        elif headers['content-type'] != 'application/json':
            logger.info('Cannot handle non-JSON response. Returning early.')
            h.clear_idempotency_key(idempotency_key)
            return response
        else:
            json_payload = json.loads(byte_payload)

        # Store and clean up before returning the response to the user
        logger.info("Storing response for idempotency key '%s'", idempotency_key)
        h.store_response_data(
            idempotency_key=idempotency_key, payload=json_payload, status_code=response.status_code, expiry=expiry
        )
        h.clear_idempotency_key(idempotency_key)
        return JSONResponse(json_payload, response.status_code)
