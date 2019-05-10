from collections import defaultdict
import json

import metricq
from metricq import get_logger

logger = get_logger(__name__)


class Sink(metricq.Sink):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subscriptions = defaultdict(set)
        self._last_send = defaultdict(int)

    async def connect(self):
        await super().connect()
        await self.subscribe(metrics=[])

    async def on_data(self, metric, timestamp, value):
        if self._subscriptions[metric] and self._last_send[metric] < timestamp.posix_ns - 500000000:
            self._last_send[metric] = timestamp.posix_ns
            for ws in frozenset(self._subscriptions[metric]):
                logger.debug('Sending {} to {}', metric, ws)
                await ws.send_data(metric, timestamp, value)

    async def subscribe_ws(self, ws, metrics):
        subscribe_metrics = set()
        for metric in metrics:
            if not self._subscriptions[metric]:
                subscribe_metrics.add(metric)
            self._subscriptions[metric].add(ws)
        if subscribe_metrics:
            result = await self.subscribe(list(subscribe_metrics))
            for metric, metadata in result['metrics'].items():
                if 'error' in metadata:
                    logger.warning('missing metric: {}', metric)

    async def unsubscribe_ws(self, ws, metrics):
        unsubscribe_metrics = set()
        for metric in metrics:
            try:
                self._subscriptions[metric].remove(ws)
                if not self._subscriptions[metric]:
                    unsubscribe_metrics.add(metric)
            except KeyError as ke:
                logger.error("failed to unsubscribe metric {}: {}", metric, ke)
        if unsubscribe_metrics:
            await self.unsubscribe(list(unsubscribe_metrics))
