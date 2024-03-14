import asyncio
import json
import traceback

import aiohttp
from aiohttp.web import Request
from metricq import JsonDict, get_logger

from .web_socket import MetricqWebSocketResponse

logger = get_logger(__name__)


async def websocket_handler(request: Request) -> MetricqWebSocketResponse:
    logger.info("Websocket handler")
    sink = request.app["sink"]
    ws = MetricqWebSocketResponse(sink)
    await ws.prepare(request)
    logger.info("Websocket opened")
    metrics: set[JsonDict] = set()
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug("Parsing message: {}", msg.data)
                try:
                    msg_data = json.loads(msg.data)
                    if msg_data["function"] == "subscribe":
                        new_metrics = set(msg_data["metrics"])
                        metadata = await sink.subscribe_ws(ws, new_metrics - metrics)
                        await ws.send_metadata(metadata)
                        metrics |= new_metrics
                except Exception as e:
                    logger.error(
                        "error during message handling {}: {}\n{}",
                        type(e),
                        e,
                        traceback.format_exc(),
                    )
                    break
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("ws connection closed with exception {}", ws.exception())
                break
        logger.info("finished websocket message loop normally")
    except Exception as e:
        logger.error("error during websocket message loop {}: {}", type(e), e)
        pass

    # Avoid delayed flushes. The unsubscribe right after will hopefully ensure that we
    # don't get new metric data sent to the ws
    ws.cancel()

    if metrics:
        # aiohttp brutally murders our task when the browser is closed hard
        # we must defend our precious unsubscription!
        # FOR AIUR
        await asyncio.shield(sink.unsubscribe_ws(ws, list(metrics)))

    logger.info("Websocket closed")
    return ws
