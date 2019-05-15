import asyncio
from collections import defaultdict
import json
from typing import Union, List, Iterable

from bidict import bidict

import metricq
from metricq import get_logger

logger = get_logger(__name__)


class Sink(metricq.DurableSink):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subscriptions = defaultdict(set)
        self._last_send = defaultdict(int)

        self._internal_name_by_primary_name = None
        self._suffix = None
        self._mapping_lock = asyncio.Lock()

    async def connect(self):
        await super().connect()
        await self.subscribe(metrics=[])

    @metricq.rpc_handler('config')
    async def config(self, suffix=None, **_) -> None:
        async with self._mapping_lock:
            self._suffix = suffix
            if self._suffix:
                self._internal_name_by_primary_name = bidict()
            else:
                self._internal_name_by_primary_name = None
            # TODO Close all clients or re-subscribe everything

    def _internal_to_primary(self, internal_metric: str) -> str:
        if self._internal_name_by_primary_name is None:
            return internal_metric
        return self._internal_name_by_primary_name.inverse[internal_metric]

    def _primary_to_internal(self, primary_metric: Union[str, Iterable[str]]) -> Union[str, List[str]]:
        if self._internal_name_by_primary_name is None:
            return primary_metric
        if isinstance(primary_metric, list):
            return list(map(self._primary_to_internal, primary_metric))
        return self._internal_name_by_primary_name[primary_metric]

    def _suffix_metric(self, metric: str) -> str:
        assert self._suffix
        return metric + '.' + self._suffix

    async def _resolve_primary_metrics(self, metrics):
        # Use a lock here so there aren't two subscriptions spamming the get_metrics
        # at the same time for redundant information
        async with self._mapping_lock:
            unknown_metrics = set(metrics) - set(self._internal_name_by_primary_name.keys())
            possible_metrics = [*metrics, *[self._suffix_metric(metric) for metric in unknown_metrics]]
            available_metrics = set(await self.get_metrics(selector=possible_metrics, metadata=False))

            for metric in unknown_metrics:
                if self._suffix_metric(metric) in available_metrics:
                    self._internal_name_by_primary_name[metric] = self._suffix_metric(metric)

    async def subscribe(self, metrics: Iterable[str]) -> None:
        if self._suffix:
            self._resolve_primary_metrics(metrics)

        await super().subscribe(self._primary_to_internal(metrics))

    async def unsubscribe(self, metrics: Iterable[str]) -> None:
        await super().unsubscribe(self._primary_to_internal(metrics))

    async def on_data(self, metric, timestamp, value):
        primary_metric = self._internal_to_primary(metric)
        if self._subscriptions[primary_metric] and self._last_send[primary_metric] < timestamp.posix_ns - 500000000:
            self._last_send[primary_metric] = timestamp.posix_ns
            for ws in frozenset(self._subscriptions[primary_metric]):
                logger.debug('Sending {} to {}', primary_metric, ws)
                await ws.send_data(primary_metric, timestamp, value)

    async def subscribe_ws(self, ws, metrics):
        subscribe_metrics = set()
        for metric in metrics:
            if not self._subscriptions[metric]:
                subscribe_metrics.add(metric)
            self._subscriptions[metric].add(ws)
        if subscribe_metrics:
            await self.subscribe(list(subscribe_metrics))

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
