/* global WebSocket */
/* exported MetricqWebSocket */

var MetricqWebSocket = function (uri) {
  this.uri = uri

  this.onOpen = function (event) {}
  this.onClose = function (event) {}
  this.onError = function (event) {}
  this.onConnecting = function (uri) {}
  this.onData = function (metric, timestamp, value) {}
  this.onMetaData = function (metric, metadata) {}

  var webSocket = null
  var metricqWS = this
  this.connect = function () {
    if ('WebSocket' in window) {
      webSocket = new WebSocket(metricqWS.uri)
      webSocket.binaryType = 'arraybuffer'
    } else {
      console.log('[MetricqWebSocket] Browser does not support WebSockets.')
      return
    }
    metricqWS.onConnecting(metricqWS.uri)

    webSocket.onmessage = function (message) {
      var response = JSON.parse(message.data)
      if (response.hasOwnProperty('error')) {
        console.log('[MetricqWebSocket] Received error message:' + response.error)
        metricqWS.onError(response.error)
      } else if (response.hasOwnProperty('data')) {
        for (var datapoint of response.data) {
          metricqWS.onData(datapoint.id, datapoint.ts, datapoint.value)
        }
      } else if (response.hasOwnProperty('metadata')) {
        Object.keys(response.metadata).forEach(function (metric) {
          metricqWS.onMetaData(metric, response.metadata[metric])
        })
      } else {
        console.log('[MetricqWebSocket] Received unknown message')
      }
    }

    webSocket.onconnecting = function () {
      metricqWS.onConnecting()
    }

    webSocket.onopen = function (event) {
      metricqWS.onOpen(event)
    }

    webSocket.onclose = function (event) {
      webSocket = null
      metricqWS.onClose(event)

      // if (metricqWS.autoReconnect) {
      //   setTimeout(function () {
      //     metricqWS.connect()
      //   }, metricqWS.reconnectInterval)
      // }
    }
    webSocket.onerror = function (event) {
      metricqWS.onError(event)
    }
  }

  this.subscribe = function (metrics) {
    if (webSocket === null) {
      console.log('[MetricqWebSocket] Cannot subscribe, connection not established.')
      return
    }

    if (!Array.isArray(metrics)) {
      metrics = [metrics]
    }

    metricqWS.metrics = metrics

    webSocket.send(JSON.stringify({
      'function': 'subscribe',
      'metrics': metrics
    }))
  }

  this.unsubscribe = function () {
    if (webSocket === null) {
      console.log('[MetricqWebSocket] Cannot unsubscribe, connection not established.')
      return
    }

    webSocket.send(JSON.stringify({
      'function': 'unsubscribe'
    }))
  }

  this.close = function () {
    if (webSocket) {
      metricqWS.unsubscribe()
      webSocket.close()
    } else {
      metricqWS.onError('No connection to close.')
    }
  }
}
