[![tests](https://github.com/sondrelg/asgi-idempotency-header/actions/workflows/test.yml/badge.svg)](https://github.com/sondrelg/asgi-idempotency-header/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/sondrelg/asgi-idempotency-header/branch/main/graph/badge.svg?token=UOJTCSY8H7)](https://codecov.io/gh/sondrelg/asgi-idempotency-header)

# ASGI Idempotency Header Middleware

Middleware for idempotency in `POST` and `PATCH` endpoints.

The middleware works by caching responses when an idempotency key is
specified in a request's headers. Once cached, future requests containing
the same header can have the response of the original request returned.
This is a good way of making sure actions are only performed once.

The implementation is largely modelled after [stripe](stripe.com)'s implementation. See [this](https://stripe.com/blog/idempotency) blog post for a breakdown.
