/* global $, MetricqWebSocket */

$(document).ready(function () {
  var mq = null

  $('#connect').click(function () {
    if (mq !== null) return

    mq = new Paho.Client("localhost", 15675, "/ws", "sink-websocket");

    counter = 0
    mq.onMessageArrived = function (message) {
      counter += 1
      if (counter % 1000 == 0) {
        $('#data').append("" + counter + "\n")
      }
    }

    mq.onConnectionLost = function (responseObject) {
      $('#data').append('Connection lost. (' + responseObject.errorMessage + ')\n')
      $('#connect').show()
      $('#disconnect').hide()
      mq = null
    }

    var options = {
        timeout: 3,
        keepAliveInterval: 30,
        onSuccess: function (responseObject) {
            $('#data').append("CONNECTION SUCCESS");
            mq.subscribe('test/0');
            mq.subscribe('test/1');
        },
        onFailure: function (responseObject) {
            $('#data').append("CONNECTION FAILURE - " + responseObject.errorMessage);
        }
    };
    mq.connect(options)
  })

  $('#disconnect').hide()
  $('#disconnect').click(function () {
    mq.close()
  })
})
