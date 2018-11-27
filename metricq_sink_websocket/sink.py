from collections import defaultdict

import asyncio

import metricq
from metricq import get_logger

logger = get_logger(__name__)


class Sink(metricq.Sink):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subscriptions = defaultdict(set)
        self.data_queue = None

    async def connect(self):
        await super().connect()
        request_future = asyncio.Future(loop=self.event_loop)
        response = await self.rpc_response('sink_subscribe', arguments={'metrics': []})
        await self.data_config(**response)
        self.data_queue = await self.data_channel.declare_queue(
            name=response['dataQueue'], passive=True)
        logger.info('starting sink consume')
        await self.data_queue.consume(self.on_data, loop=self.event_loop)

    def subscribe(self, ws, metrics):
        for metric in metrics:
            if not self._subscriptions[metric]:
                # TODO bulk subscription
                self.rpc('sink.subscribe',
                         response_callback=None,
                         arguments={'dataQueue': self.data_queue.name,
                                    'metrics': [metric]})
            self._subscriptions[metric].add(ws)

    def unsubscribe(self, ws, metrics):
        for metric in metrics:
            try:
                self._subscriptions[metric].remove(ws)
                if not self._subscriptions[metric]:
                    # TODO bulk unsubscription
                    self.rpc('sink.unsubscribe',
                             response_callback=None,
                             arguments={'dataQueue': self.data_queue.name,
                                        'metrics': [metric]})
            except KeyError as ke:
                logger.error("failed to unsubscribe metric {}: {}", metric, ke)
