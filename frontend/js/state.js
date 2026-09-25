// Tiny observable store for app state. No framework, just a pub/sub.
(function () {
  var listeners = [];

  var state = {
    session: loadSession(), // { role, roomCode, token, playerId, name } | null
    game: null,             // latest authorized state from the server
    connection: "disconnected",
    error: null,
    guessSelection: null,
  };

  function loadSession() {
    try {
      var raw = localStorage.getItem("pfd.session");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function persist() {
    try {
      if (state.session) {
        localStorage.setItem("pfd.session", JSON.stringify(state.session));
      } else {
        localStorage.removeItem("pfd.session");
      }
    } catch (e) {
      /* storage may be unavailable */
    }
  }

  function notify() {
    listeners.forEach(function (fn) {
      try {
        fn(state);
      } catch (e) {
        console.error(e);
      }
    });
  }

  window.Store = {
    get: function () {
      return state;
    },
    subscribe: function (fn) {
      listeners.push(fn);
      return function () {
        listeners = listeners.filter(function (l) {
          return l !== fn;
        });
      };
    },
    setSession: function (session) {
      state.session = session;
      persist();
      notify();
    },
    clearSession: function () {
      state.session = null;
      state.game = null;
      state.guessSelection = null;
      persist();
      notify();
    },
    setGame: function (game) {
      state.game = game;
      if (state.error) state.error = null;
      notify();
    },
    setConnection: function (status) {
      state.connection = status;
      notify();
    },
    setError: function (message) {
      state.error = message;
      notify();
    },
    setGuessSelection: function (id) {
      state.guessSelection = id;
      notify();
    },
  };
})();
