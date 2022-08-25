[![tests](https://github.com/sondrelg/asgi-idempotency-header/actions/workflows/test.yml/badge.svg)](https://github.com/sondrelg/asgi-idempotency-header/actions/workflows/test.yml)
[![pypi](https://img.shields.io/pypi/v/asgi-idempotency-header.svg)](https://pypi.org/project/drf-openapi-tester/)
[![python-versions](https://img.shields.io/badge/python-3.8%2B-blue)](https://pypi.org/project/asgi-idempotency-header)
[![codecov](https://codecov.io/gh/sondrelg/asgi-idempotency-header/branch/main/graph/badge.svg?token=UOJTCSY8H7)](https://codecov.io/gh/sondrelg/asgi-idempotency-header)

# Idempotency Header ASGI Middleware

A middleware for making endpoints idempotent.

The purpose of the middleware is to guarantee that execution of mutating endpoints happens exactly once,
regardless of the number of requests.
We achieve this by caching responses, and returning already-saved responses to the user on repeated requests.
Responses are only cached when an idempotency-key HTTP header is present, so clients must opt-into this behaviour.
Additionally, only configured HTTP methods (by default, `POST` and `PATCH`) that return JSON payloads are cached and replayed.

This is largely modelled after [stripe' implementation](https://stripe.com/docs/api/idempotent_requests).

The middleware is compatible with both [Starlette](https://github.com/encode/starlette)
and [FastAPI](https://github.com/tiangolo/fastapi) apps.

## Installation

```
pip install asgi-idempotency-header
```

## Setup

Add the middleware to your app like this:

```python
from fastapi import FastAPI

from idempotency_header_middleware import IdempotencyHeaderMiddleware
from idempotency_header_middleware.backends import RedisBackend

backend = RedisBackend(redis=redis)

app = FastAPI()
app.add_middleware(IdempotencyHeaderMiddleware(backend=backend))
```

or like this:

```python
from fastapi import FastAPI
from fastapi.middleware import Middleware

from idempotency_header_middleware import IdempotencyHeaderMiddleware
from idempotency_header_middleware.backends import RedisBackend

backend = RedisBackend(redis=redis)

app = FastAPI(
    middleware=[
        Middleware(
            IdempotencyHeaderMiddleware,
            backend=backend,
        )
    ]
)
```

If you're using `Starlette`, just substitute `FastAPI` for `Starlette` and it should work the same.

## Configuration

The middleware takes a few arguments. A full example looks like this:

```python
from redis.asyncio import from_url

from idempotency_header_middleware import IdempotencyHeaderMiddleware
from idempotency_header_middleware.backends import RedisBackend

redis = from_url(redis_url)
backend = RedisBackend(redis=redis)

IdempotencyHeaderMiddleware(
    backend,
    idempotency_header_key='Idempotency-Key',
    replay_header_key='Idempotent-Replayed',
    enforce_uuid4_formatting=False,
    expiry=60 * 60 * 24,
    applicable_methods=['POST', 'PATCH']
)
```

The following section describes each argument:

### Backend

```python
from idempotency_header_middleware.backends import RedisBackend, MemoryBackend

backend: Union[RedisBackend, MemoryBackend]
```

The backend is the only required argument, as it defines **how** and **where** to store a response.

The package comes with a [redis-py async](https://github.com/redis/redis-py) backend implementation, and a
memory-backend for testing.

Contributions for more backends are welcomed, and configuring a custom backend is pretty simple - just take a look at
the existing ones.

### Idempotency header key

```python
idempotency_header_key: str = 'Idempotency-Key'
```

The idempotency header key is the header value to check for. When present, the middleware will be used if the HTTP
method is in the [applicable methods](#applicable-methods).

The default value is `"Idempotency-Key"`, but it can be defined as any string.

### Replay header key

```python
replay_header_key: str = 'Idempotent-Replayed'
```

The replay header is added to replayed responses. It provides a way for the client to tell whether the action was
performed for the first time or not.

### Enforce UUID formatting

```python
enforce_uuid4_formatting: bool = False
```

Convenience option for stricter header value validation.

Clients can technically set any value they want in their header,
but the shorter the key value is, the higher the risk of value-collisions is from other users.
If two users accidentally send in the same header value for what's meant to be two separate requests,
the middleware will interpret them as the same.

By enabling this option, you can force users to use UUIDs as header values, and pretty much eliminate this risk.

When validation fails, a 422 response is returned from the middleware, informing the user that the header value is malformed.

### Expiry

```python
expiry: int = 60 * 60 * 24
```

How long to cache responses for, measured in seconds. Set to 24 hours by default.

### Applicable Methods

```python
applicable_methods=['POST', 'PATCH']
```

What HTTP methods to consider for idempotency. If the request method is one of the methods in this list, and the
[idempotency header](#idempotency-header-key) is sent, the middleware will be used. By default, only `POST`
and `PATCH` methods are cached and replayed.

## Quick summary of behaviours

Briefly summarized, this is how the middleware functions:

- The first request is processed, and consequent requests are replayed, until the response expires.
  `expiry` *can* be set to `None` to skip expiry, but most likely you will want to expire responses
  after a while.
- If two requests comes in at the same time - i.e., if a second request hits the middlware *before*
  the first request has finished, the middleware will return a 409, informing the user that a request
  is being processed, and that we cannot handle the second request.
- The middleware only handles HTTP requests.
- By default, the middleware only handles requests with `POST` and `PATCH` methods. Other HTTP methods skip this middleware.
- Only valid JSON responses with `content-type` == `application/json` are cached.
