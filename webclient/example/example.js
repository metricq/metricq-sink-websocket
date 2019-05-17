/* global $, MetricqWebSocket */

$(document).ready(function () {
  var mq = null
  var units = {}

  $('#connect').click(function () {
    if (mq !== null) return

    mq = new MetricqWebSocket($('#uri').val())

    mq.onData = function (id, ts, val) {
      $('#data').append(id + ': ' + ts + ' @ ' + val + ' ' + units[id] + '\n').scrollTop($('#data')[0].scrollHeight)
    }

    mq.onMetaData = function (id, metadata) {
      units[id] = metadata.unit
    }

    mq.onOpen = function (event) {
      $('#data').append('Connected.\n')

      mq.subscribe(['elab.ariel.power', 'elab.ariel.s0.package.power', 'elab.temp'])
    }

    mq.onConnecting = function (uri) {
      $('#data').html('')
      $('#data').append('Connecting to ' + uri + '\n')
      $('#connect').hide()
      $('#disconnect').show()
    }

    mq.onError = function (event) {
      $('#data').append('He\'s dead Jimmy. (' + event.message + ')\n')

      $('#connect').show()
      $('#disconnect').hide()

      mq = null
    }

    mq.onClose = function (event) {
      $('#data').append('Connection closed. (' + event.message + ')\n')
      $('#connect').show()
      $('#disconnect').hide()
      mq = null
    }

    mq.connect()
  })

  $('#disconnect').hide()
  $('#disconnect').click(function () {
    mq.close()
  })
})
