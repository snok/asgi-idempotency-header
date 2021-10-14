import logging
import uuid
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response

from idempotence.handlers import get_stored_response, key_pending, remove_pending_key, save_key, save_response

logger = logging.getLogger('fastapi_idempotency_header')


def validate_uuid(uuid_: str) -> bool:
    """
    Validate string as uuid4.
    """
    try:
        return bool(uuid.UUID(uuid_, version=4).hex)
    except ValueError:
        return False


def get_idempotency_header_middleware(
    app: FastAPI,
    save_result_handler: Callable[[str, Response, Optional[int]], None] = save_response,
    fetch_result_handler: Callable[[str], Optional[Response]] = get_stored_response,
    save_key_handler=save_key,
    key_pending_handler=key_pending,
    remove_pending_key_handler=remove_pending_key,
    idempotency_header_key: str = 'Idempotency-Key',
    replay_header_key: str = 'Idempotent-Replayed',
    enforce_uuid4_formatting: bool = False,
    store_successful_responses: bool = True,
    store_client_error_responses: bool = True,
    store_server_error_responses: bool = True,
    expiry: Optional[int] = None,
) -> None:
    @app.middleware('http')
    async def idempotency_header_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
        """
        Enable idempotent operations in POST and PATCH endpoints.
        """
        if request.method not in ['POST', 'PATCH']:
            logger.debug('Returning early since method %s is already idempotent', request.method)
            return await call_next(request)

        idempotency_key = request.headers.get(idempotency_header_key.lower())

        if not idempotency_key:
            logger.debug('Returning early since idempotency key is not present in the request headers')
            return await call_next(request)

        if enforce_uuid4_formatting and not validate_uuid(idempotency_key):
            logger.warning('Returning error since idempotency key is malformed')
            return JSONResponse(
                {'detail': f"'{idempotency_header_key}' header must be formatted as a version 4 UUID."}, 422
            )

        stored_response = fetch_result_handler(idempotency_key)

        if stored_response:
            logger.info('Returning stored response from idempotency key %s', idempotency_key)
            stored_response.headers[replay_header_key] = 'true'
            return stored_response

        pending_request_exists = key_pending_handler(idempotency_key)

        if pending_request_exists:
            return JSONResponse(
                {'detail': f"Request already pending for idempotency key '{idempotency_header_key}'."}, 409
            )

        save_key_handler(idempotency_key)

        fresh_response: Response = await call_next(request)

        if (
            store_successful_responses
            and 200 <= fresh_response.status_code <= 299
            or store_client_error_responses
            and 400 <= fresh_response.status_code <= 499
            or store_server_error_responses
            and 500 <= fresh_response.status_code <= 599
        ):
            # Store a response to return next time if one didn't exist
            logger.info('Storing response for idempotency key %s', idempotency_key)
            save_result_handler(idempotency_key, fresh_response, expiry)

        remove_pending_key_handler(idempotency_key)

        return fresh_response
