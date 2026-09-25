// Thin REST client. All endpoints are authorized by opaque session tokens.
(function () {
  var API = window.PFD_CONFIG.API_BASE_URL;

  function request(path, options) {
    options = options || {};
    return fetch(API + path, {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (resp) {
      return resp.text().then(function (text) {
        var data = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch (e) {
          data = { detail: text };
        }
        if (!resp.ok) {
          var message =
            (data && (data.detail || data.message)) ||
            "Request failed (" + resp.status + ").";
          if (Array.isArray(message)) message = message[0].msg || "Invalid input.";
          throw new Error(message);
        }
        return data;
      });
    });
  }

  window.API = {
    base: API,
    createRoom: function () {
      return request("/api/rooms", { method: "POST", body: {} });
    },
    joinRoom: function (roomCode, name) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/join", {
        method: "POST",
        body: { name: name },
      });
    },
    submitFact: function (roomCode, token, fact) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/facts", {
        method: "POST",
        body: { token: token, fact: fact },
      });
    },
    start: function (roomCode, token, minutes) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/start", {
        method: "POST",
        body: { token: token, investigation_minutes: minutes },
      });
    },
    guess: function (roomCode, token, targetId) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/guess", {
        method: "POST",
        body: { token: token, target_id: targetId },
      });
    },
    hostAction: function (roomCode, token, action) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/host/action", {
        method: "POST",
        body: { token: token, action: action },
      });
    },
    reveal: function (roomCode, token, targetId) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/reveal", {
        method: "POST",
        body: { token: token, target_id: targetId || null },
      });
    },
    end: function (roomCode, token) {
      return request("/api/rooms/" + encodeURIComponent(roomCode) + "/end", {
        method: "POST",
        body: { token: token },
      });
    },
    getState: function (roomCode, token) {
      return request(
        "/api/rooms/" +
          encodeURIComponent(roomCode) +
          "/state?token=" +
          encodeURIComponent(token)
      );
    },
  };
})();
