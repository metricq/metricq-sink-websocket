import asyncio

import aiohttp

from metricq import get_logger

logger = get_logger(__name__)


class MetricqWebSocketResponse(aiohttp.web.WebSocketResponse):
    def __init__(self, sink):
        super().__init__()
        self._sink = sink
        self._delay = 0.2
        self._max_buffer = 1000
        self._buffer = []
        self._flush_task = None

    async def send_data(self, metric, timestamp, value):
        self._buffer.append({'id': metric, 'ts': timestamp.posix_ns, 'value': value})
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self.delayed_flush())
        elif len(self._buffer) >= self._max_buffer:
            self._flush_task.cancel()
            await self.flush()

    async def delayed_flush(self):
        await asyncio.sleep(self._delay)
        await self.flush()
        self._flush_task = None

    async def flush(self):
        logger.debug('flushing buffer with {} values', len(self._buffer))
        try:
            await self.send_json({'data': self._buffer})
        except ConnectionResetError:
            metrics = list({elem['id'] for elem in self._buffer})
            logger.info('Unsubscribing stale websocket {} from metric {}', self, metrics)
            await self._sink.unsubscribe_ws(self, metrics)
        self._buffer = []
