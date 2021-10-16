import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_idempotent_method(client: AsyncClient, caplog) -> None:
    caplog.set_level('DEBUG')
    await client.get('/get-endpoint', headers={'Idempotency-key': 'test'})
    assert caplog.messages[0] == 'Returning response directly since request method is already idempotent'


async def test_multiple_concurrent_requests(client: AsyncClient, caplog) -> None:
    caplog.set_level('DEBUG')
    id_ = str(uuid4())

    async def fire_request():
        return await client.post('/slow-endpoint', headers={'Idempotency-key': id_})

    response1, response2 = await asyncio.gather(
        *[asyncio.create_task(fire_request()), asyncio.create_task(fire_request())]
    )

    assert response1.status_code == 200
    assert response2.status_code == 409
    assert caplog.messages[0] == f"Returning 409 since a request is already in progress for idempotency key '{id_}'"
