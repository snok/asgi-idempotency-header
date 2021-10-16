import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_bad_header_formatting(client: AsyncClient) -> None:
    response = await client.post('/json-response', headers={'Idempotency-key': 'test'})
    assert response.json() == {'detail': "'Idempotency-Key' header value must be formatted as a v4 UUID."}
    assert response.status_code == 422
