// Realtime channel: one persistent WebSocket per session, with auto-reconnect.
(function () {
  var socket = null;
  var roomCode = null;
  var token = null;
  var reconnectTimer = null;
  var pingTimer = null;
  var attempts = 0;
  var manuallyClosed = false;

  function connect(rc, tk) {
    roomCode = rc;
    token = tk;
    manuallyClosed = false;
    open();
  }

  function open() {
    if (!roomCode || !token) return;
    Store.setConnection(attempts === 0 ? "connecting" : "reconnecting");

    var url =
      window.PFD_CONFIG.WS_BASE_URL +
      "/ws/" +
      encodeURIComponent(roomCode) +
      "?token=" +
      encodeURIComponent(token);

    try {
      socket = new WebSocket(url);
    } catch (e) {
      scheduleReconnect();
      return;
    }

    socket.onopen = function () {
      attempts = 0;
      Store.setConnection("connected");
      startPing();
      // Re-sync full authorized state after any reconnect.
      API.getState(roomCode, token)
        .then(Store.setGame)
        .catch(function () {});
    };

    socket.onmessage = function (event) {
      var msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        return;
      }
      handleMessage(msg);
    };

    socket.onclose = function () {
      stopPing();
      Store.setConnection("disconnected");
      if (!manuallyClosed) scheduleReconnect();
    };

    socket.onerror = function () {
      try {
        socket.close();
      } catch (e) {}
    };
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case "state":
        Store.setGame(msg);
        break;
      case "phase_change":
        // A full state push follows; ignore for now.
        break;
      case "error":
        Store.setError(msg.message);
        break;
      case "pong":
        break;
      default:
        break;
    }
  }

  function startPing() {
    stopPing();
    pingTimer = setInterval(function () {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);
  }

  function stopPing() {
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = null;
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    attempts += 1;
    var delay = Math.min(1000 * Math.pow(1.6, attempts), 10000);
    reconnectTimer = setTimeout(function () {
      reconnectTimer = null;
      open();
    }, delay);
  }

  function disconnect() {
    manuallyClosed = true;
    stopPing();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      try {
        socket.close();
      } catch (e) {}
    }
    socket = null;
  }

  window.Socket = { connect: connect, disconnect: disconnect };
})();
