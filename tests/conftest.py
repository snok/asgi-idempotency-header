import asyncio
import logging

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.responses import JSONResponse

from idempotence.middleware import get_idempotency_header_middleware

logger = logging.getLogger('sanity_html')

logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

app = FastAPI()


@app.post('/test')
def create() -> JSONResponse:
    return JSONResponse({'thisIs': 'aTest'}, 201)


get_idempotency_header_middleware(app)


@pytest.fixture(scope='session', autouse=True)
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
async def client():
    async with AsyncClient(app=app, base_url='http://test') as client:
        yield client
