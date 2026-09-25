// ---------------------------------------------------------------------------
// Backend location configuration.
//
// Leave these blank to auto-detect:
//   - localhost  -> http://localhost:8000
//   - production -> same origin (only works if the backend serves this frontend)
//
// For the recommended setup (frontend on Vercel, backend on a persistent
// server) set API_BASE_URL to your backend URL, e.g.
//   https://private-fact-detective.up.railway.app
//
// You can also override at runtime without editing this file:
//   https://your-frontend.vercel.app/?api=https://your-backend.example.com
// ---------------------------------------------------------------------------
window.PFD_CONFIG = {
  API_BASE_URL: "", // e.g. "https://your-backend.example.com"
  WS_BASE_URL: "",  // optional; derived from API_BASE_URL when blank
};

(function resolveConfig() {
  var params = new URLSearchParams(window.location.search);
  var override = params.get("api");

  var api = override || window.PFD_CONFIG.API_BASE_URL || "";
  if (!api && (location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    api = "http://localhost:8000";
  }
  if (!api) {
    api = window.location.origin;
  }
  api = api.replace(/\/+$/, "");

  var ws = window.PFD_CONFIG.WS_BASE_URL || params.get("ws") || "";
  if (!ws) {
    ws = api.replace(/^http/, "ws");
  }

  window.PFD_CONFIG.API_BASE_URL = api;
  window.PFD_CONFIG.WS_BASE_URL = ws;
})();
