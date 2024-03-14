from math import isfinite
import asyncio
from collections import defaultdict
from typing import Optional, overload, Any, Iterable

import metricq
from bidict import bidict
from metricq import get_logger
from metricq.types import Metric, JsonDict, Timestamp, Timedelta

from .web_socket import MetricqWebSocketResponse

logger = get_logger(__name__)


class Sink(metricq.DurableSink):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._subscriptions: defaultdict[Metric, set[MetricqWebSocketResponse]] = (
            defaultdict(set)
        )
        self._last_send: defaultdict[Metric, Timestamp] = defaultdict(
            lambda: Timestamp(0)
        )

        self._metadata: dict[Metric, JsonDict] = {}

        self._internal_name_by_primary_name: bidict[str, str] | None = None
        self._suffix: str | None = None
        self._mapping_lock = asyncio.Lock()
        self._subscribe_lock = asyncio.Lock()
        self._min_interval: Timedelta | None = None

    async def connect(self) -> None:
        await super().connect()
        await self.subscribe(metrics=[])

    @metricq.rpc_handler("config")
    async def config(
        self, suffix: Optional[str] = None, skip_interval: str = "0.5s", **_: Any
    ) -> None:
        self._min_interval = Timedelta.from_string(skip_interval)

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

    @overload
    def _primary_to_internal(self, primary_metric: str) -> str: ...

    @overload
    def _primary_to_internal(self, primary_metric: list[str]) -> list[str]: ...

    def _primary_to_internal(self, primary_metric: str | list[str]) -> str | list[str]:
        if self._internal_name_by_primary_name is None:
            return primary_metric
        if isinstance(primary_metric, list):
            return list(map(self._primary_to_internal, primary_metric))
        return self._internal_name_by_primary_name[primary_metric]

    def _suffix_metric(self, metric: str) -> str:
        assert self._suffix
        return metric + "." + self._suffix

    async def _resolve_primary_metrics(self, metrics: Iterable[Metric]) -> None:
        # Use a lock here so there aren't two subscriptions spamming the get_metrics
        # at the same time for redundant information
        async with self._mapping_lock:
            assert self._internal_name_by_primary_name is not None
            unknown_metrics = set(metrics) - set(
                self._internal_name_by_primary_name.keys()
            )
            possible_metrics = [
                *unknown_metrics,
                *[self._suffix_metric(metric) for metric in unknown_metrics],
            ]
            if possible_metrics:
                available_metrics = set(
                    await self.get_metrics(selector=possible_metrics, metadata=False)
                )
            else:
                available_metrics = set()

            for metric in unknown_metrics:
                if self._suffix_metric(metric) in available_metrics:
                    logger.info(
                        "using suffix {} for primary {}",
                        self._suffix_metric(metric),
                        metric,
                    )
                    self._internal_name_by_primary_name[metric] = self._suffix_metric(
                        metric
                    )
                else:
                    if metric not in available_metrics:
                        logger.warn(
                            "trying to subscribe to metric with no metadata {}", metric
                        )
                    # For now, let's just subscribe even if it may not be in the metadata
                    self._internal_name_by_primary_name[metric] = metric

    async def subscribe(
        self, metrics: list[Metric], *args: Any, **kwargs: Any
    ) -> JsonDict:
        if self._suffix:
            await asyncio.shield(self._resolve_primary_metrics(metrics))

        return await super().subscribe(
            self._primary_to_internal(metrics), *args, **kwargs
        )

    async def unsubscribe(self, metrics: list[Metric]) -> None:
        await super().unsubscribe(self._primary_to_internal(metrics))

    async def on_data(self, metric: Metric, timestamp: Timestamp, value: float) -> None:
        if not isfinite(value):
            return

        primary_metric = self._internal_to_primary(metric)
        assert self._min_interval is not None
        if (
            self._subscriptions[primary_metric]
            and self._last_send[primary_metric] + self._min_interval < timestamp
        ):
            self._last_send[primary_metric] = timestamp
            for ws in frozenset(self._subscriptions[primary_metric]):
                logger.debug("Sending {} to {}", primary_metric, ws)
                await ws.send_data(primary_metric, timestamp, value)

    async def subscribe_ws(
        self, ws: MetricqWebSocketResponse, metrics: Iterable[Metric]
    ) -> dict[Metric, JsonDict | None]:
        async with self._subscribe_lock:
            subscribe_metrics = set()
            for metric in metrics:
                if not self._subscriptions[metric]:
                    subscribe_metrics.add(metric)
                self._subscriptions[metric].add(ws)
            if subscribe_metrics:
                response = await self.subscribe(list(subscribe_metrics), metadata=True)
                for metric, metadata in response["metrics"].items():
                    self._metadata[self._internal_to_primary(metric)] = metadata

            return {
                metric: self._metadata[metric] if metric in self._metadata else None
                for metric in metrics
            }

    async def unsubscribe_ws(
        self, ws: MetricqWebSocketResponse, metrics: Iterable[Metric]
    ) -> None:
        async with self._subscribe_lock:
            unsubscribe_metrics = set()
            for metric in metrics:
                try:
                    self._subscriptions[metric].remove(ws)
                    if not self._subscriptions[metric]:
                        unsubscribe_metrics.add(metric)
                        del self._metadata[metric]
                except KeyError as ke:
                    logger.error("failed to unsubscribe metric {}: {}", metric, ke)
            if unsubscribe_metrics:
                await self.unsubscribe(list(unsubscribe_metrics))
