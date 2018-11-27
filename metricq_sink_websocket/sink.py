from collections import defaultdict
import json

import asyncio
import aio_pika

import metricq
from metricq import get_logger
from metricq.datachunk_pb2 import DataChunk

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

    async def on_data(self, message: aio_pika.IncomingMessage):
        with message.process(requeue=True):
            body = message.body
            from_token = message.app_id
            metric = message.routing_key
            correlation_id = message.correlation_id.decode()

            logger.info('received message from {}, correlation id: {}, reply_to: {}',
                        from_token, correlation_id, message.reply_to)
            data_response = DataChunk()
            data_response.ParseFromString(body)

            logger.debug('message is an data response')
            try:
                await self._on_data_chunk(metric, data_response)
            except KeyError:
                logger.error('received history response with unknown correlation id {} '
                             'from {}', correlation_id, from_token)
                return

    async def _on_data_chunk(self, metric, data_chunk: DataChunk):
        last_timed = 0
        zipped_tv = zip(data_chunk.time_delta, data_chunk.value)
        for time_delta, value in zipped_tv:
            last_timed += time_delta
            await self._on_data_tv(metric, last_timed, value)

    async def _on_data_tv(self, metric, timestamp, value):
        if self._subscriptions[metric]:
            for ws in self._subscriptions[metric]:
                await ws.send_str(json.dumps({"data": [{"id": metric, "ts": timestamp, "value": value}]}))

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
