// Realtime client.
//
// The server renders every phase. This script watches a room revision counter
// and, when it changes, fetches the freshly rendered fragment and swaps it in.
//
//   * Firebase mode  - subscribes to RTDB `rooms/{code}/_rev` via the SDK.
//   * Fallback mode  - polls `/rooms/{code}/rev` (used in local memory mode).
//
// It also owns the client-side countdown; when it reaches zero it asks the
// server to expire the investigation (serverless has no background timers).
(function () {
  var cfg = window.PFD;
  if (!cfg || !cfg.roomCode) return;

  var FIREBASE_SDK = "https://www.gstatic.com/firebasejs/10.12.2";
  var root = document.getElementById("room-root");
  var lastRev = cfg.rev;
  var cdEl = null;
  var cdEndsAt = NaN;
  var cdOffsetMs = 0;
  var cdFired = false;

  function setConn(status) {
    var node = document.querySelector("[data-conn]");
    if (!node) return;
    node.className = "conn conn-" + status;
    node.textContent =
      status === "connected" ? "Live" : status === "reconnecting" ? "Reconnecting…" : "Offline";
  }

  function refresh() {
    if (!root) return;
    fetch(cfg.fragmentUrl + "?fragment=1&_=" + Date.now(), {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.text();
      })
      .then(function (html) {
        root.innerHTML = html;
        bindCountdown();
        updateCountdown();
        setConn("connected");
      })
      .catch(function () {
        setConn("reconnecting");
      });
  }

  function requestTick() {
    fetch(cfg.tickUrl, { method: "POST", credentials: "same-origin" }).catch(function () {});
  }

  function bindCountdown() {
    cdEl = document.getElementById("countdown");
    cdFired = false;
    if (!cdEl) {
      cdEndsAt = NaN;
      return;
    }
    cdEndsAt = parseFloat(cdEl.getAttribute("data-ends-at"));
    var serverNow = parseFloat(cdEl.getAttribute("data-server-now"));
    cdOffsetMs = isNaN(serverNow) ? 0 : serverNow * 1000 - Date.now();
  }

  function updateCountdown() {
    if (!cdEl || isNaN(cdEndsAt)) return;
    var remaining = Math.max(0, Math.floor((cdEndsAt * 1000 - (Date.now() + cdOffsetMs)) / 1000));
    var m = String(Math.floor(remaining / 60)).padStart(2, "0");
    var s = String(remaining % 60).padStart(2, "0");
    cdEl.textContent = m + ":" + s;
    if (remaining <= 0 && !cdFired) {
      cdFired = true;
      requestTick();
      setTimeout(refresh, 400);
    }
  }

  function startPolling() {
    function poll() {
      fetch(cfg.revUrl, { cache: "no-store" })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          setConn("connected");
          if (data && typeof data.rev === "number" && data.rev !== lastRev) {
            lastRev = data.rev;
            refresh();
          }
        })
        .catch(function () {
          setConn("reconnecting");
        });
    }
    poll();
    setInterval(poll, 2500);
  }

  function loadScript(src, onload) {
    var s = document.createElement("script");
    s.src = src;
    s.onload = onload;
    s.onerror = startPolling;
    document.head.appendChild(s);
  }

  function startFirebase() {
    var fb = cfg.firebase || {};
    if (!fb.databaseURL) {
      startPolling();
      return;
    }
    loadScript(FIREBASE_SDK + "/firebase-app-compat.js", function () {
      loadScript(FIREBASE_SDK + "/firebase-database-compat.js", function () {
        try {
          if (!firebase.apps.length) firebase.initializeApp(fb);
          firebase
            .database()
            .ref("rooms/" + cfg.roomCode + "/_rev")
            .on("value", function (snap) {
              setConn("connected");
              var rev = snap.val() || 0;
              if (rev !== lastRev) {
                lastRev = rev;
                refresh();
              }
            });
        } catch (e) {
          startPolling();
        }
      });
    });
  }

  bindCountdown();
  updateCountdown();
  setInterval(updateCountdown, 500);
  startFirebase();
})();
