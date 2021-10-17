import asyncio
from uuid import uuid4

import fakeredis.aioredis
import pytest

from idempotency_header_middleware.backends.aioredis import AioredisBackend
from idempotency_header_middleware.backends.base import Backend
from idempotency_header_middleware.backends.memory import MemoryBackend
from tests.conftest import dummy_response

pytestmark = pytest.mark.asyncio

base_methods = [
    'get_stored_response',
    'store_response_data',
    'store_idempotency_key',
    'clear_idempotency_key',
]


def test_base_backend():
    h = Backend
    for method in base_methods:
        assert hasattr(h, method)


redis = fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.parametrize('backend', [AioredisBackend(redis), MemoryBackend()])
async def test_backend(backend: Backend):
    assert issubclass(backend.__class__, Backend)

    # Test setting and clearing key
    id_ = str(uuid4())
    already_existed = await backend.store_idempotency_key(id_)
    assert already_existed is False
    already_existed = await backend.store_idempotency_key(id_)
    assert already_existed is True
    await backend.clear_idempotency_key(id_)
    already_existed = await backend.store_idempotency_key(id_)
    assert already_existed is False

    # Test storing and fetching response data
    assert (await backend.get_stored_response(id_)) is None
    await backend.store_response_data(id_, dummy_response, 201)
    stored_response = await backend.get_stored_response(id_)
    assert stored_response.status_code == 201
    assert stored_response.body == b'{"test":"test"}'

    # Test fetching data after expiry
    await backend.store_response_data(id_, dummy_response, 201, expiry=1)
    await asyncio.sleep(1)
    assert (await backend.get_stored_response(id_)) is None
