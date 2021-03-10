# metricq-sink-websocket
🕸 A MetricQ sink, which provides live data to consumers over WebSocket connections

## Usage

Any client can connect to this websocket endpoint. For JavaScript you can use the `metricq-live` from [here](https://github.com/metricq/metricq-js)

## Installation

Normal installation works just fine with pip:

```
pip install ./path/to/metricq-sink-websocket
```

For better performance, uvloop is recommened.

```
pip install './path/to/metricq-sink-websocket[uvloop]'
```

It will automatically be picked up if installed.