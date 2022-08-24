import asyncio
from typing import Awaitable, Callable
from uuid import uuid4

import pytest
from httpx import AsyncClient, Response

from tests.conftest import app, dummy_response

pytestmark = pytest.mark.asyncio

http_call = Callable[..., Awaitable[Response]]


async def test_no_idempotence(applicable_method: http_call) -> None:
    response = await applicable_method('/json-response')
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


@pytest.mark.parametrize('endpoint', json_response_endpoints)
async def test_idempotence_works_for_json_responses(applicable_method: http_call, endpoint: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}

    # First request
    response = await applicable_method(endpoint, headers=idempotency_header)
    assert response.json() == dummy_response
    assert 'idempotent-replayed' not in dict(response.headers)

    # Second request
    response = await applicable_method(endpoint, headers=idempotency_header)
    assert response.json() == dummy_response
    assert dict(response.headers)['idempotent-replayed'] == 'true'


other_response_endpoints = [
    '/xml-response',
    '/html-response',
    '/bad-response',
    '/file-response',
    '/plain-text-response',
]


@pytest.mark.parametrize('endpoint', other_response_endpoints)
async def test_non_json_responses(applicable_method: http_call, endpoint: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}

    # First request
    response = await applicable_method(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)

    # Second request
    response = await applicable_method(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)


non_json_encoding_endpoints = [
    '/redirect-response',
    '/streaming-response',
]


@pytest.mark.parametrize('endpoint', non_json_encoding_endpoints)
async def test_wrong_response_encoding(caplog, applicable_method: http_call, endpoint: str) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}

    # First request
    response = await applicable_method(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)

    # Second request
    response = await applicable_method(endpoint, headers=idempotency_header)
    assert 'idempotent-replayed' not in dict(response.headers)


async def test_idempotent_method(inapplicable_method: http_call) -> None:
    idempotency_header = {'Idempotency-Key': uuid4().hex}
    await inapplicable_method('/idempotent-method', headers=idempotency_header)
    second_response = await inapplicable_method('/idempotent-method', headers=idempotency_header)
    assert second_response.headers == {}


async def test_multiple_concurrent_requests(caplog) -> None:
    async with AsyncClient(app=app, base_url='http://test') as client:
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
async def test_bad_header_formatting(value: str) -> None:
    async with AsyncClient(app=app, base_url='http://test') as client:
        response = await client.post('/json-response', headers={'Idempotency-key': value})
        assert response.json() == {'detail': "'Idempotency-Key' header value must be formatted as a v4 UUID"}
        assert response.status_code == 422
