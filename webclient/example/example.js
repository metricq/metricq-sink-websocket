/* global $, MetricqWebSocket */

$(document).ready(function () {
  var mq = null

  $('#connect').click(function () {
    if (mq !== null) return

    mq = new MetricqWebSocket($('#uri').val())

    mq.onData = function (id, ts, val) {
      $('#data').append(id + ': ' + ts + ' @ ' + val + '\n')
    }

    mq.onOpen = function (event) {
      $('#data').append('Connected.\n')

      mq.subscribe(['dummy.source'])
    }

    mq.onConnecting = function (uri) {
      $('#data').append('Connecting to ' + uri + '\n')
    }

    mq.onError = function (event) {
      $('#data').append('He\'s dead Jimmy. (' + event.message + ')\n')
      mq = null
    }
    mq.connect()
  })
})
