[![tests](https://github.com/sondrelg/asgi-idempotency-header/actions/workflows/test.yml/badge.svg)](https://github.com/sondrelg/asgi-idempotency-header/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/sondrelg/asgi-idempotency-header/branch/main/graph/badge.svg?token=UOJTCSY8H7)](https://codecov.io/gh/sondrelg/asgi-idempotency-header)

# Idempotency Header ASGI Middleware

Middleware for providing idempotency in `POST` and `PATCH` endpoints.
Compatible with both [Starlette](https://github.com/encode/starlette) and [FastAPI](https://github.com/tiangolo/fastapi).

The middleware prevents repeated creation of resources, by
caching responses and replaying them back to the user,
when an idempotency-key HTTP header is detected.

The middleware's implementation is largely modelled after [stripe](stripe.com)'s implementation. See [this](https://stripe.com/blog/idempotency) blog post for details.

## Installation

```
pip install asgi-idempotency-header
```

## Setup

The middleware can be added in one of (at least) two ways:

**Add to app**

```python
from fastapi import FastAPI

from idempotency_header_middleware import IdempotencyHeaderMiddleware
from idempotency_header_middleware.backends import AioredisBackend

app = FastAPI()
app.add_middleware(IdempotencyHeaderMiddleware(backend=AioredisBackend(redis=redis)))
```
or

**Pass on app instantiation**

```python
from fastapi import FastAPI
from fastapi.middleware import Middleware

from idempotency_header_middleware import IdempotencyHeaderMiddleware
from idempotency_header_middleware.backends import AioredisBackend

app = FastAPI(
    middleware=[
        Middleware(
            IdempotencyHeaderMiddleware,
            enforce_uuid4_formatting=True,
            backend=AioredisBackend(redis=redis),
        )
    ]
)
```



## Configuration

The middleware takes a few arguments:

```python
from aioredis import from_url

from idempotency_header_middleware import IdempotencyHeaderMiddleware
from idempotency_header_middleware.backends import AioredisBackend

redis = from_url(redis_url)
backend = AioredisBackend(redis=redis)

IdempotencyHeaderMiddleware(
    backend,
    idempotency_header_key='Idempotency-Key',
    replay_header_key='Idempotent-Replayed',
    enforce_uuid4_formatting=False,
    expiry=60 * 60 * 24,
)
```

**Backend**

The backend is the only required argument. The backend defines where to store a response.

The middleware comes with a backend implementation for [aioredis](https://github.com/aio-libs/aioredis-py),
and a memory-backend for testing.

Contributions for more backends are welcomed, and configuring a custom backend is pretty simple - just
take a look at the existing ones.

**Idempotency header key**

The idempotency header key is the header value to check for.
The default value is `"Idempotency-Key"`, but it could be set to any string.

**Replay header key**

The replay header key is added to replayed responses. It provides a way for the client
to tell whether the action was performed for the first time or not.

**Enforce UUID formatting**

Clients could set any header value they want, but the shorter the key value, the higher the risk is for collisions.
If two clients send in the same header value for what's meant to be two separate requests, the
middleware will interpret them as the same.
By enabling this option, you can force users to use UUIDs as header values, and eliminate this risk.

When validation fails, a 422 response is returned from the middleware:

```python
JSONResponse({'detail': f"'{self.idempotency_header_key}' header value must be formatted as a v4 UUID"}, 422)
```

**Expiry**

Responses probably shouldn't be cached forever. Expiry defines how long to cache responses for, in seconds. Set
to 24 hours by default.

## Nice to knows

Middleware behavior briefly summarized:

- The first request is processed; consequent requests are replayed, until the response expires.
- If another request comes in while the first request is being processed, the middleware will
return a 409 telling the user that a request is already being processed.
- If for some reason you want to avoid the replay behavior on subsequent requests, just generate a new idempotency key.
- The middleware only handles HTTP requests.
- The middleware only handles requests with `POST` and `PATCH` methods. Other HTTP methods are idempotent by default.

## Example

Once implemented, the first request sent will go through to the endpoint as normal,
while the second will immediately be replayed back to the user:

```python
import asyncio

from httpx import AsyncClient


async def main():
    async with AsyncClient() as client:
        first_response = await client.post(
            endpoint,
            headers={'Idempotency-Key': '9525c412-e5b9-43b4-a62a-54b751fac989'}
        )
        print(first_response.headers)  # --> {'content-type': 'application/json'}

        second_response = await client.post(
            endpoint,
            headers={'Idempotency-Key': '9525c412-e5b9-43b4-a62a-54b751fac989'}
        )
        print(second_response.headers)  # --> {'content-type': 'application/json', 'idempotency-replayed': true}


if __name__ == '__main__':
    asyncio.run(main())
```
