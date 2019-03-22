import json
import asyncio

import aiohttp

from metricq import get_logger

logger = get_logger(__name__)


async def websocket_handler(request):
    logger.info('Websocket handler')
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    logger.info('Websocket opened')
    sink = request.app['sink']
    metrics = set()
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug('Parsing message: {}', msg.data)
                try:
                    msg_data = json.loads(msg.data)
                    if msg_data['function'] == 'subscribe':
                        new_metrics = set(msg_data['metrics'])
                        await sink.subscribe_ws(ws, new_metrics - metrics)
                        metrics |= new_metrics
                except Exception as e:
                    logger.error('error during message handling: {}', e)
                    break
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error('ws connection closed with exception {}', ws.exception())
                break
        logger.info('finished websocket message loop normally')
    except Exception as e:
        logger.error("error during websocket message loop: {}", e)
        pass

    if metrics:
        # aiohttp brutally murders our task when the browser is closed hard
        # we must defend our precious unsubscription!
        # FOR AIUR
        await asyncio.shield(sink.unsubscribe_ws(ws, list(metrics)))

    logger.info('Websocket closed')
    return ws
