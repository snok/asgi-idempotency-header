import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_no_idempotence(client: AsyncClient) -> None:
    response = await client.post('/test')
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {'content-length': '18', 'content-type': 'application/json'}


@pytest.mark.asyncio
async def test_idempotence_no_stored_response(client: AsyncClient, caplog) -> None:
    caplog.set_level('DEBUG')

    response = await client.post('/test', headers={'Idempotency-Key': 'test'})
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {'content-length': '18', 'content-type': 'application/json'}

    assert caplog.messages[0] == "Storing response for idempotency key 'test'"

    response = await client.post('/test', headers={'Idempotency-Key': 'test'})
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {
        'content-length': '18',
        'content-type': 'application/json',
        'idempotent-replayed': 'true',
    }

    assert caplog.messages[2] == "Returning stored response from idempotency key 'test'"
