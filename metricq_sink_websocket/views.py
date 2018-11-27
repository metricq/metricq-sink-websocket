import json

import aiohttp

from metricq import get_logger

logger = get_logger(__name__)


async def websocket_handler(request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    logger.info('Websocket opened')
    sink = request.app['sink']
    metrics = None
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                msg_data = json.loads(msg.data)
                if msg_data['function'] == 'subscribe':
                    assert metrics is None
                    metrics = msg_data['metrics']
                    await sink.subscribe(ws, metrics)
            except Exception as e:
                logger.error('error during message handling {}', e)
                break
        elif msg.type == aiohttp.WSMsgType.ERROR:
            logger.error('ws connection closed with exception {}', ws.exception())
            break

    if metrics is not None:
        await sink.unsubscribe(ws, metrics)

    logger.info('Websocket closed')
    return ws
