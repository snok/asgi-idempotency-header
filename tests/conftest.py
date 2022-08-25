import asyncio
import json
import logging
from pathlib import Path

import fakeredis.aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse, UJSONResponse
from httpx import AsyncClient
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)

from idempotency_header_middleware.backends.redis import RedisBackend
from idempotency_header_middleware.middleware import IdempotencyHeaderMiddleware

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

app = FastAPI()

method_configs = {
    'default': {'setting': ['POST', 'PATCH'], 'applicable_methods': ['post', 'patch']},
    'post only': {'setting': ['POST'], 'applicable_methods': ['post']},
    'with put': {'setting': ['POST', 'PATCH', 'PUT'], 'applicable_methods': ['post', 'patch', 'put']},
}


@pytest.fixture(scope='session', ids=method_configs.keys(), params=method_configs.values())
def method_config(request):
    return request.param


@pytest.fixture(scope='session', autouse=True)
def app_with_middleware(method_config):
    app.add_middleware(
        IdempotencyHeaderMiddleware,
        enforce_uuid4_formatting=True,
        backend=RedisBackend(redis=fakeredis.aioredis.FakeRedis(decode_responses=True)),
        applicable_methods=method_config['setting'],
    )
    yield app
    # Remove the middleware
    app.user_middleware.pop(0)
    app.middleware_stack = app.build_middleware_stack()


dummy_response = {'test': 'test'}


@app.patch('/json-response')
@app.post('/json-response')
@app.put('/json-response')
async def create_json_response() -> JSONResponse:
    return JSONResponse(dummy_response, 201)


@app.patch('/dict-response', status_code=201)
@app.post('/dict-response', status_code=201)
@app.put('/dict-response', status_code=201)
async def create_dict_response() -> dict:
    return dummy_response


@app.patch('/normal-byte-response')
@app.post('/normal-byte-response')
@app.put('/normal-byte-response')
async def create_normal_byte_response() -> Response:
    return Response(content=json.dumps(dummy_response).encode(), status_code=201)


@app.patch('/normal-response', response_class=Response)
@app.post('/normal-response', response_class=Response)
@app.put('/normal-response', response_class=Response)
async def create_normal_response():
    return Response(content=json.dumps(dummy_response), media_type='application/json')


@app.patch('/bad-response', response_class=Response)
@app.post('/bad-response', response_class=Response)
@app.put('/bad-response', response_class=Response)
async def create_bad_response():
    return Response(content=json.dumps(dummy_response), media_type='application/xml')


@app.patch('/xml-response')
@app.post('/xml-response')
@app.put('/xml-response')
async def create_xml_response():
    data = """<?xml version="1.0"?>
    <shampoo>
    <Header>
        Apply shampoo here.
    </Header>
    <Body>
        You'll have to use soap here.
    </Body>
    </shampoo>
    """
    return Response(content=data, media_type='application/xml')


@app.patch('/orjson-response', response_class=ORJSONResponse)
@app.post('/orjson-response', response_class=ORJSONResponse)
@app.put('/orjson-response', response_class=ORJSONResponse)
async def create_orjson_response():
    return dummy_response


@app.patch('/ujson-response', response_class=UJSONResponse)
@app.post('/ujson-response', response_class=UJSONResponse)
@app.put('/ujson-response', response_class=UJSONResponse)
async def create_ujson_response():
    return dummy_response


@app.patch('/html-response', response_class=HTMLResponse)
@app.post('/html-response', response_class=HTMLResponse)
@app.put('/html-response', response_class=HTMLResponse)
async def create_html_response():
    return """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Look ma! HTML!</h1>
        </body>
    </html>
    """


@app.patch('/file-response', response_class=FileResponse)
@app.post('/file-response', response_class=FileResponse)
@app.put('/file-response', response_class=FileResponse)
async def create_file_response():
    path = Path(__file__)
    return path.parent / 'static/image.jpeg'


@app.patch('/plain-text-response', response_class=FileResponse)
@app.post('/plain-text-response', response_class=FileResponse)
@app.put('/plain-text-response', response_class=FileResponse)
async def create_plaintext_response():
    return PlainTextResponse('test')


@app.patch('/redirect-response', response_class=FileResponse)
@app.post('/redirect-response', response_class=FileResponse)
@app.put('/redirect-response', response_class=FileResponse)
async def create_redirect_response():
    return RedirectResponse('test')


@app.get('/idempotent-method', response_class=JSONResponse)
@app.options('/idempotent-method', response_class=JSONResponse)
@app.delete('/idempotent-method', response_class=JSONResponse)
@app.put('/idempotent-method', response_class=JSONResponse)
@app.head('/idempotent-method', response_class=JSONResponse)
@app.patch('/idempotent-method', response_class=JSONResponse)
async def idempotent_method():
    return Response(status_code=204)


@app.post('/slow-endpoint', response_class=JSONResponse)
async def slow_endpoint():
    await asyncio.sleep(1)
    return dummy_response


async def fake_video_streamer():
    for _ in range(10):
        yield b'some fake video bytes'


@app.patch('/streaming-response', response_class=FileResponse)
@app.post('/streaming-response', response_class=FileResponse)
@app.put('/streaming-response', response_class=FileResponse)
async def create_streaming_response():
    return StreamingResponse(fake_video_streamer())


@pytest.fixture(scope='session', autouse=True)
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='module')
async def client() -> AsyncClient:
    async with AsyncClient(app=app, base_url='http://test') as client:
        yield client


@pytest.fixture(params=['post', 'patch', 'put'])
def applicable_method(method_config, client, request):
    if request.param in method_config['applicable_methods']:
        return client.__getattribute__(request.param)
    else:
        raise pytest.skip(request.param + ' is not an applicable method in this configuration.')


@pytest.fixture(params=['get', 'delete', 'options', 'head', 'put', 'patch'])
def inapplicable_method(method_config, client, request):
    if request.param in method_config['applicable_methods']:
        raise pytest.skip(request.param + ' is an applicable method in this configuration.')
    else:
        return client.__getattribute__(request.param)
