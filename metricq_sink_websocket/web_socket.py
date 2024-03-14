import asyncio
from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict

import aiohttp
from metricq import get_logger, Metric, Timestamp, JsonDict

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .sink import Sink


class _BufferEntry(TypedDict):
    id: Metric
    ts: int
    value: float


class MetricqWebSocketResponse(aiohttp.web.WebSocketResponse):
    def __init__(self, sink: Sink) -> None:
        super().__init__()
        self._sink = sink
        self._delay = 0.2
        self._max_buffer = 1000
        self._buffer: list[_BufferEntry] = []
        self._flush_task: asyncio.Task[None] | None = None

    async def send_metadata(self, metadata: dict[Metric, JsonDict | None]) -> None:
        await self.send_json({"metadata": metadata})

    async def send_data(
        self, metric: Metric, timestamp: Timestamp, value: float
    ) -> None:
        self._buffer.append({"id": metric, "ts": timestamp.posix_ns, "value": value})
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self.delayed_flush())
        elif len(self._buffer) >= self._max_buffer:
            self._flush_task.cancel()
            await self.flush()

    async def delayed_flush(self) -> None:
        await asyncio.sleep(self._delay)
        await self.flush()
        self._flush_task = None

    def cancel(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()

    async def flush(self) -> None:
        logger.debug("flushing buffer with {} values", len(self._buffer))
        try:
            await self.send_json({"data": self._buffer})
        except (ConnectionResetError, RuntimeError):
            metrics = list({elem["id"] for elem in self._buffer})
            logger.info(
                "Unsubscribing stale websocket {} from metric {}", self, metrics
            )
            await self._sink.unsubscribe_ws(self, metrics)
        self._buffer = []
