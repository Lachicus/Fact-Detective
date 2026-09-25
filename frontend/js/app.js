// Application wiring: user actions, session resume, and the render loop.
(function () {
  function handleError(err) {
    console.error(err);
    Store.setError(err && err.message ? err.message : "Something went wrong.");
  }

  function activateSession(session, game) {
    Store.setSession(session);
    if (game) Store.setGame(game);
    Socket.connect(session.roomCode, session.token);
  }

  var App = {
    createRoom: function () {
      API.createRoom()
        .then(function (data) {
          var session = {
            role: "host",
            roomCode: data.room_code,
            token: data.host_token,
            name: "Host",
          };
          activateSession(session, null);
        })
        .catch(handleError);
    },

    joinRoom: function (roomCode, name) {
      if (!roomCode || !name) {
        Store.setError("Enter both a room code and your name.");
        return;
      }
      API.joinRoom(roomCode, name)
        .then(function (data) {
          var session = {
            role: "participant",
            roomCode: data.room_code,
            token: data.participant_token,
            playerId: data.participant_id,
            name: name,
          };
          activateSession(session, null);
        })
        .catch(handleError);
    },

    submitFact: function (fact) {
      var s = Store.get().session;
      if (!s) return;
      API.submitFact(s.roomCode, s.token, fact)
        .then(function () {
          UI.clearFactDraft();
        })
        .catch(handleError);
    },

    startGame: function (minutes) {
      var s = Store.get().session;
      if (!s) return;
      API.start(s.roomCode, s.token, minutes).catch(handleError);
    },

    hostAction: function (action) {
      var s = Store.get().session;
      if (!s) return;
      API.hostAction(s.roomCode, s.token, action).catch(handleError);
    },

    revealPlayer: function (playerId) {
      var s = Store.get().session;
      if (!s) return;
      API.reveal(s.roomCode, s.token, playerId).catch(handleError);
    },

    submitGuess: function (targetId) {
      var s = Store.get().session;
      if (!s || !targetId) return;
      API.guess(s.roomCode, s.token, targetId).catch(handleError);
    },

    endGame: function () {
      var s = Store.get().session;
      if (!s) return;
      API.end(s.roomCode, s.token).catch(handleError);
    },

    leave: function () {
      Socket.disconnect();
      Store.clearSession();
      window.location.search = "";
    },

    resume: function () {
      var s = Store.get().session;
      if (!s) {
        UI.render(Store.get());
        return;
      }
      API.getState(s.roomCode, s.token)
        .then(function (game) {
          activateSession(s, game);
        })
        .catch(function () {
          // Session/room no longer valid (server restarted, room cleaned up).
          Socket.disconnect();
          Store.clearSession();
          Store.setError("Your previous room is no longer available.");
        });
    },
  };

  window.App = App;

  // Re-render on every state change.
  Store.subscribe(function (state) {
    UI.render(state);
  });

  // Local countdown ticker; the server remains authoritative.
  setInterval(function () {
    UI.updateCountdown();
  }, 500);

  // Update the clock immediately after each state push too.
  Store.subscribe(function () {
    UI.updateCountdown();
  });

  document.addEventListener("DOMContentLoaded", function () {
    App.resume();
  });
})();
