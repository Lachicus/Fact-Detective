# Private Fact Detective

A small multiplayer online team-bonding game for ~7 participants in a single
online meeting. Everyone secretly submits one interesting personal fact; the
game then privately assigns each person *someone else's* fact. Through natural
conversation, you try to work out whose fact you were given — without ever
directly asking.

No accounts. No database. Ephemeral, in-memory, single persistent server.

```
                 ┌─────────────────────┐
                 │       Vercel        │
                 │  Static Frontend    │
                 └──────────┬──────────┘
                            │
                     HTTPS / WSS
                            │
                            ▼
                 ┌─────────────────────┐
                 │  Persistent FastAPI │
                 │  WebSocket Server   │
                 │   In-memory state   │
                 └─────────────────────┘
```

## Features

- Room creation with short, readable room codes (e.g. `K7PX2`)
- Temporary session tokens (host + participant), no registration
- Realtime WebSocket lobby, phase changes and submissions
- Private fact submission (one per player, 500 char limit, immutable)
- Server-authoritative investigation timer (3–30 minutes)
- Random **derangement** assignment — nobody ever receives their own fact
- Strict privacy: participants only ever receive *their* assigned fact, with no
  owner identity until the reveal
- Host dashboard with full visibility and phase-appropriate controls
- Reveal one-at-a-time or all at once
- Automatic reconnect after refresh/disconnect
- Idle room cleanup (2 hours)

## Project structure

```
.
├── frontend/                 # Vanilla HTML/CSS/JS, deploy to Vercel
│   ├── index.html
│   ├── css/styles.css
│   ├── js/
│   │   ├── config.js         # backend URL configuration
│   │   ├── state.js          # tiny observable store
│   │   ├── api.js            # REST client
│   │   ├── websocket.js      # realtime channel + reconnect
│   │   ├── ui.js             # rendering
│   │   └── app.js            # wiring / actions
│   └── vercel.json
├── backend/                  # FastAPI, deploy to a persistent server
│   ├── app/
│   │   ├── main.py           # routes, websockets, timer, views
│   │   ├── models.py         # Player / Room
│   │   ├── schemas.py        # request models
│   │   ├── game.py           # phases, derangement, validation
│   │   ├── rooms.py          # in-memory registry + cleanup
│   │   ├── websocket.py      # connection manager
│   │   └── security.py       # tokens + room codes
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Procfile
│   └── Dockerfile
├── README.md
└── .gitignore
```

## Game flow

```
LOBBY → FACT_COLLECTION → READY → ASSIGNMENT → INVESTIGATION
      → GUESSING → REVEAL → FINISHED
```

1. **LOBBY** – host creates a room; participants join with code + name.
2. **FACT_COLLECTION** – each participant privately submits one fact.
3. **READY** – reached automatically once everyone has submitted.
4. **ASSIGNMENT / INVESTIGATION** – host starts; backend generates a
   derangement and privately delivers one fact to each participant plus a
   server-timed countdown.
5. **GUESSING** – participants pick who they think owns their fact.
6. **REVEAL** – host reveals results (one at a time or all at once).
7. **FINISHED** – game over.

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

The API is then at `http://localhost:8000` (interactive docs at `/docs`).

### Frontend

The frontend is plain static files. Serve the `frontend/` directory with any
static server, e.g.:

```bash
cd frontend
python3 -m http.server 5173
```

Open `http://localhost:5173`. When the page is served from `localhost`, the
frontend automatically targets `http://localhost:8000`, and derives the
WebSocket URL from it.

To point at a different backend without editing code:

```
http://localhost:5173/?api=http://localhost:9000
```

### Configuration

`frontend/js/config.js` controls the backend location:

```js
window.PFD_CONFIG = {
  API_BASE_URL: "", // e.g. "https://your-backend.example.com"
  WS_BASE_URL: "",  // optional; derived from API_BASE_URL when blank
};
```

Runtime overrides: `?api=...` and `?ws=...` query parameters.

Backend environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated allowed origins, or `*` |

## How to play

- Ask **natural, open questions**. Do **not** directly ask things like
  "is this your fact?" — the goal is conversation, not a quiz.
- Each participant sees only one secret fact and must identify its owner.
- The host runs the game and can see everything.

## Testing

```bash
cd backend
source .venv/bin/activate
pytest
```

The suite includes assignment/derangement unit tests, privacy/security tests,
state-machine validation, guess rules, and a full **7-player end-to-end
simulation over REST + WebSockets** (`tests/test_e2e_simulation.py`).

## API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/rooms` | – | Create a room (returns host token) |
| `POST` | `/api/rooms/{code}/join` | – | Join (returns participant token) |
| `POST` | `/api/rooms/{code}/facts` | participant | Submit your one fact |
| `POST` | `/api/rooms/{code}/start` | host | Start investigation (assigns facts) |
| `POST` | `/api/rooms/{code}/guess` | participant | Submit your guess |
| `POST` | `/api/rooms/{code}/host/action` | host | Phase controls |
| `POST` | `/api/rooms/{code}/reveal` | host | Reveal one (`target_id`) or all |
| `POST` | `/api/rooms/{code}/end` | host | End the game |
| `GET` | `/api/rooms/{code}/state` | token | Authorized state snapshot |
| `WS` | `/ws/{code}?token=…` | token | Realtime events |

Host actions for `/host/action`: `start_fact_collection`, `reset_facts`,
`start_investigation`, `end_investigation`, `start_guessing`, `end_guessing`,
`reveal_all`, `finish`.

## Deployment

### Frontend → Vercel

1. Import the repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Other** (static, no build step).
4. Set `API_BASE_URL` in `frontend/js/config.js` to your backend URL, or append
   `?api=https://your-backend` to the deployed URL.

### Backend → persistent server

Any platform that keeps a single long-lived process works (Railway, Render,
Fly.io, a VPS, etc.). **Do not** deploy the backend as Vercel serverless
functions — separate, short-lived instances would break shared in-memory state.

Using the included `Procfile`:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Or with Docker:

```bash
cd backend
docker build -t private-fact-detective .
docker run -p 8000:8000 -e CORS_ALLOW_ORIGINS="https://your-frontend.vercel.app" private-fact-detective
```

Set `CORS_ALLOW_ORIGINS` to your Vercel domain in production.

## Important limitations

> **Game data is stored only in server memory.** Restarting or redeploying the
> backend will terminate active games and erase their temporary state.

> **The backend should run as a single persistent instance.** Multiple
> independent backend instances require shared state or pub/sub and are outside
> the scope of this version.

These limitations are intentional and acceptable for a one-time team event with
approximately 7 participants.

## Privacy & security notes

- Tokens are generated with Python's `secrets` module; the backend never trusts
  a client-supplied participant id on its own.
- Before the reveal, a participant's realtime state contains exactly one fact —
  their assignment — and never an `owner_id`/`owner_name`.
- The host is the only role authorized to see the complete mapping.
- The server enforces every phase transition, one fact per player, one guess per
  player, and no self-guesses.
