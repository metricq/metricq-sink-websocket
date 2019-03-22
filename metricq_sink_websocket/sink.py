from collections import defaultdict
import json

import metricq
from metricq import get_logger

logger = get_logger(__name__)


class Sink(metricq.Sink):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subscriptions = defaultdict(set)

    async def connect(self):
        await super().connect()
        await self.subscribe(metrics=[])

    async def on_data(self, metric, timestamp, value):
        if self._subscriptions[metric]:
            for ws in frozenset(self._subscriptions[metric]):
                logger.debug('Sending {} to {}', metric, ws)
                try:
                    await ws.send_str(json.dumps({"data": [{"id": metric, "ts": timestamp.posix_ns, "value": value}]}))
                except ConnectionResetError:
                    logger.info('Unsubscribing stale websocket {} from metric {}', ws, metric)
                    await self.unsubscribe(ws, [metric])

    async def subscribe_ws(self, ws, metrics):
        for metric in metrics:
            if not self._subscriptions[metric]:
                # TODO bulk subscription
                await self.subscribe([metric])
            self._subscriptions[metric].add(ws)

    async def unsubscribe_ws(self, ws, metrics):
        for metric in metrics:
            try:
                self._subscriptions[metric].remove(ws)
                if not self._subscriptions[metric]:
                    # TODO bulk unsubscription
                    await self.unsubscribe([metric])
            except KeyError as ke:
                logger.error("failed to unsubscribe metric {}: {}", metric, ke)
