import asyncio
from uuid import uuid4

import fakeredis.aioredis
import pytest

from idempotency_header.handlers.aioredis import RedisHandler
from idempotency_header.handlers.base import Handler
from idempotency_header.handlers.memory import MemoryHandler

pytestmark = pytest.mark.asyncio

base_methods = [
    'get_stored_response',
    'store_response_data',
    'store_idempotency_key',
    'clear_idempotency_key',
    'clear_idempotency_key',
    'is_key_pending',
]


def test_base_handler():
    h = Handler
    for method in base_methods:
        assert hasattr(h, method)


async def test_memory_handler():
    assert issubclass(MemoryHandler, Handler)

    h = MemoryHandler()

    # Test setting and clearing key
    id_ = str(uuid4())
    await h.store_idempotency_key(id_)
    assert (await h.is_key_pending(id_)) is True
    await h.clear_idempotency_key(id_)
    assert (await h.is_key_pending(id_)) is False

    # Test storing and fetching response data
    await h.store_response_data(id_, {'test': 'test'}, 201)
    stored_response = await h.get_stored_response(id_)
    assert stored_response.status_code == 201
    assert stored_response.body == b'{"test":"test"}'

    # Test fetching data after expiry
    await h.store_response_data(id_, {'test': 'test'}, 201, expiry=1)
    await asyncio.sleep(1)
    assert (await h.get_stored_response(id_)) is None


async def test_aioredis_handler():
    assert issubclass(MemoryHandler, Handler)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    h = RedisHandler(redis=redis)

    # Test setting and clearing key
    id_ = str(uuid4())
    await h.store_idempotency_key(id_)
    assert (await h.is_key_pending(id_)) is True
    await h.clear_idempotency_key(id_)
    assert (await h.is_key_pending(id_)) is False

    # Test storing and fetching response data
    await h.store_response_data(id_, {'test': 'test'}, 201)
    stored_response = await h.get_stored_response(id_)
    assert stored_response.status_code == 201
    assert stored_response.body == b'{"test":"test"}'

    # Test fetching data after expiry
    await h.store_response_data(id_, {'test': 'test'}, 201, expiry=1)
    await asyncio.sleep(1)
    assert (await h.get_stored_response(id_)) is None
