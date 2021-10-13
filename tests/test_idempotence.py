import pytest


@pytest.mark.asyncio
async def test_no_idempotence(client):
    response = await client.post('/test')
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {'content-length': '18', 'content-type': 'application/json'}


@pytest.mark.asyncio
async def test_idempotence_no_stored_response(client, caplog):
    caplog.set_level('DEBUG')

    response = await client.post('/test', headers={'Idempotency-Key': 'test'})
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {'content-length': '18', 'content-type': 'application/json'}

    assert caplog.messages[0] == 'Storing response for idempotency key test'

    response = await client.post('/test', headers={'Idempotency-Key': 'test'})
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {'content-length': '18', 'content-type': 'application/json'}

    assert caplog.messages[2] == 'Storing response for idempotency key test'
