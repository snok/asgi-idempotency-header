import pytest
from httpx import AsyncClient

from tests.conftest import dummy_response

pytestmark = pytest.mark.asyncio


async def test_no_idempotence(client: AsyncClient) -> None:
    response = await client.post('/json-response')
    assert response.json() == {'thisIs': 'aTest'}
    assert dict(response.headers) == {'content-length': '18', 'content-type': 'application/json'}


async def test_idempotence_works_for_json_responses(client: AsyncClient, caplog) -> None:
    caplog.set_level('DEBUG')

    for i, url in enumerate(
        [
            '/json-response',
            '/dict-response',
            '/normal-response',
            '/normal-byte-response',
            '/orjson-response',
            '/ujson-response',
        ]
    ):
        caplog.clear()
        idempotency_header = {'Idempotency-Key': f'test{i}'}

        # First request
        response = await client.post(url, headers=idempotency_header)
        assert response.json() == dummy_response
        assert 'idempotent-replayed' not in dict(response.headers)
        assert caplog.messages[0] == f"Storing response for idempotency key 'test{i}'"

        # Second request
        response = await client.post(url, headers=idempotency_header)
        assert response.json() == dummy_response
        assert dict(response.headers)['idempotent-replayed'] == 'true'
        assert caplog.messages[2] == f"Returning stored response from idempotency key 'test{i}'"


async def test_idempotence_doesnt_work_for_non_json_responses_wrong_media(client: AsyncClient, caplog) -> None:
    caplog.set_level('DEBUG')

    for i, url in enumerate(
        [
            '/xml-response',
            '/html-response',
            '/bad-response',
            '/file-response',
            '/plain-text-response',
        ]
    ):
        caplog.clear()
        idempotency_header = {'Idempotency-Key': f'test{i + 100}'}

        # First request
        response = await client.post(url, headers=idempotency_header)
        assert 'idempotent-replayed' not in dict(response.headers)
        assert caplog.messages[0] == 'Cannot handle non-JSON response. Returning early.'

        # Second request
        response = await client.post(url, headers=idempotency_header)
        assert 'idempotent-replayed' not in dict(response.headers)
        assert caplog.messages[0] == 'Cannot handle non-JSON response. Returning early.'


async def test_idempotence_doesnt_work_for_non_json_responses_bad_encoding(client: AsyncClient, caplog) -> None:
    caplog.set_level('DEBUG')

    for i, url in enumerate(
        [
            '/redirect-response',
            '/streaming-response',
        ]
    ):
        caplog.clear()
        idempotency_header = {'Idempotency-Key': f'test{i + 100}'}

        # First request
        response = await client.post(url, headers=idempotency_header)
        assert 'idempotent-replayed' not in dict(response.headers)
        assert caplog.messages[0] == 'Failed to decode payload as JSON. Returning early.'

        # Second request
        response = await client.post(url, headers=idempotency_header)
        assert 'idempotent-replayed' not in dict(response.headers)
        assert caplog.messages[0] == 'Failed to decode payload as JSON. Returning early.'
