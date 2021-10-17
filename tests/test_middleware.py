import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import dummy_response

pytestmark = pytest.mark.asyncio

methods = ['post', 'patch']


@pytest.mark.parametrize('method', methods)
async def test_no_idempotence(client: AsyncClient, method: str) -> None:
    response = await client.__getattribute__(method)('/json-response')
    assert response.json() == dummy_response
    assert dict(response.headers) == {'content-length': '15', 'content-type': 'application/json'}


json_response_endpoints = [
    '/json-response',
    '/dict-response',
    '/normal-response',
    '/normal-byte-response',
    '/orjson-response',
    '/ujson-response',
]


@pytest.mark.parametrize('method', methods)
@pytest.mark.parametrize('endpoint', json_response_endpoints)
async def test_idempotence_works_for_json_responses(client: AsyncClient, method: str, endpoint: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}

    # First request
    response = await client.__getattribute__(method)(endpoint, headers=idempotency_header)
    assert response.json() == dummy_response
    assert 'idempotent-replayed' not in dict(response.headers)

    # Second request
    response = await client.__getattribute__(method)(endpoint, headers=idempotency_header)
    assert response.json() == dummy_response
    assert dict(response.headers)['idempotent-replayed'] == 'true'


other_response_endpoints = [
    '/xml-response',
    '/html-response',
    '/bad-response',
    '/file-response',
    '/plain-text-response',
]


@pytest.mark.parametrize('method', methods)
@pytest.mark.parametrize('endpoint', other_response_endpoints)
async def test_non_json_responses(client: AsyncClient, method: str, endpoint: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}

    # First request
    response = await client.__getattribute__(method)(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)

    # Second request
    response = await client.__getattribute__(method)(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)


non_json_encoding_endpoints = [
    '/redirect-response',
    '/streaming-response',
]


@pytest.mark.parametrize('method', methods)
@pytest.mark.parametrize('endpoint', non_json_encoding_endpoints)
async def test_wrong_response_encoding(client: AsyncClient, caplog, method: str, endpoint: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}

    # First request
    response = await client.__getattribute__(method)(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)

    # Second request
    response = await client.__getattribute__(method)(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)


already_idempotent_methods = ['get', 'put', 'delete', 'options', 'head']


@pytest.mark.parametrize('method', already_idempotent_methods)
async def test_idempotent_method(client: AsyncClient, method: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}
    await client.__getattribute__(method)('/idempotent-method', headers=idempotency_header)
    second_response = await client.__getattribute__(method)('/idempotent-method', headers=idempotency_header)
    assert second_response.headers == {}


async def test_multiple_concurrent_requests(client: AsyncClient, caplog) -> None:
    id_ = str(uuid4())

    async def fire_request():
        return await client.post('/slow-endpoint', headers={'Idempotency-key': id_})

    response1, response2 = await asyncio.gather(
        *[asyncio.create_task(fire_request()), asyncio.create_task(fire_request())]
    )

    assert response1.status_code == 200
    assert response2.status_code == 409


bad_header_values = ['test', uuid4().hex[:-1] + 'u', '123', 'ssssssssssssssssssss']


@pytest.mark.parametrize('value', bad_header_values)
async def test_bad_header_formatting(client: AsyncClient, value: str) -> None:
    response = await client.post('/json-response', headers={'Idempotency-key': value})
    assert response.json() == {'detail': "'Idempotency-Key' header value must be formatted as a v4 UUID"}
    assert response.status_code == 422
