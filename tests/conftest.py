import asyncio
import json
import logging
from pathlib import Path

import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse, UJSONResponse
from httpx import AsyncClient
from starlette.middleware import Middleware
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)

from idempotency_header.handlers.memory import MemoryHandler
from idempotency_header.middleware import get_idempotency_header_middleware

logger = logging.getLogger('sanity_html')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

app = FastAPI()

dummy_response = {'test': 'test'}


@app.patch('/json-response')
@app.post('/json-response')
async def create_json_response() -> JSONResponse:
    return JSONResponse(dummy_response, 201)


@app.patch('/dict-response', status_code=201)
@app.post('/dict-response', status_code=201)
async def create_dict_response() -> dict:
    return dummy_response


@app.patch('/normal-byte-response')
@app.post('/normal-byte-response')
async def create_normal_byte_response() -> Response:
    return Response(content=json.dumps(dummy_response).encode(), status_code=201)


@app.patch('/normal-response', response_class=Response)
@app.post('/normal-response', response_class=Response)
async def create_normal_response():
    return Response(content=json.dumps(dummy_response), media_type='application/json')


@app.patch('/bad-response', response_class=Response)
@app.post('/bad-response', response_class=Response)
async def create_bad_response():
    return Response(content=json.dumps(dummy_response), media_type='application/xml')


@app.patch('/xml-response')
@app.post('/xml-response')
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
async def create_orjson_response():
    return dummy_response


@app.patch('/ujson-response', response_class=UJSONResponse)
@app.post('/ujson-response', response_class=UJSONResponse)
async def create_ujson_response():
    return dummy_response


@app.patch('/html-response', response_class=HTMLResponse)
@app.post('/html-response', response_class=HTMLResponse)
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
async def create_file_response():
    path = Path(__file__)
    return path.parent / 'static/image.jpeg'


@app.patch('/plain-text-response', response_class=FileResponse)
@app.post('/plain-text-response', response_class=FileResponse)
async def create_plaintext_response():
    return PlainTextResponse('test')


@app.patch('/redirect-response', response_class=FileResponse)
@app.post('/redirect-response', response_class=FileResponse)
async def create_redirect_response():
    return RedirectResponse('test')


@app.get('/idempotent-method', response_class=JSONResponse)
@app.options('/idempotent-method', response_class=JSONResponse)
@app.delete('/idempotent-method', response_class=JSONResponse)
@app.put('/idempotent-method', response_class=JSONResponse)
@app.head('/idempotent-method', response_class=JSONResponse)
async def idempotent_method():
    return Response(status_code=204)


@app.post('/slow-endpoint', response_class=JSONResponse)
async def slow_endpoint():
    await asyncio.sleep(1)
    return dummy_response


async def fake_video_streamer():
    for _ in range(10):
        yield b'some fake video bytes'


@app.post('/streaming-response', response_class=FileResponse)
async def create_streaming_response():
    return StreamingResponse(fake_video_streamer())


get_idempotency_header_middleware(app, enforce_uuid4_formatting=True, handler=MemoryHandler())


@pytest.fixture(scope='session', autouse=True)
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
async def client() -> AsyncClient:
    async with AsyncClient(app=app, base_url='http://test') as client:
        yield client
