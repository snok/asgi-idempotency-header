"""
File contains a data-saving and -fetching handler.

The idea is to provide *a* default; but any project implementing the middleware *should*
roll their own handlers, using cache or database backends already configured.
"""
import time
from typing import Any, Dict, Optional

from starlette.responses import Response, JSONResponse, StreamingResponse

storage: Dict[str, Any] = {}


def get_stored_response(idempotency_key: str) -> Optional[Response]:
    """
    Return a stored response if it exists.

    This is the default implementation. Users should pass their own handlers as needed.
    """
    if idempotency_key in storage:
        expiry = storage[idempotency_key]['expiry']
        if expiry and expiry >= time.time():
            del storage[idempotency_key]
        else:
            return JSONResponse(storage[idempotency_key]['json'], status_code=storage[idempotency_key]['status_code'])
    return None


def save_response(idempotency_key: str, response: StreamingResponse, expiry: Optional[int] = None) -> None:
    """
    Store a response.

    This is the default implementation. Users should pass their own handlers as needed.
    """
    if not isinstance(response, JSONResponse):
        print('Returning early, was ', type(response))
        return

    global storage
    expire = time.time() + expiry if expiry else None
    storage[idempotency_key] = {'expiry': expire, 'json': response.json(), 'status_code': response.status_code}
    print(f'stored {storage=}')
