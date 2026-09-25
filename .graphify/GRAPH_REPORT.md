# Graph Report - .  (2026-09-25)

## Corpus Check
- Corpus is ~10,090 words - fits in a single context window. You may not need a graph.

## Summary
- 240 nodes · 436 edges · 18 communities detected
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 100 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: contains: 134 · calls: 111 · uses: 99 · rationale_for: 32 · method: 28 · imports_from: 8 · inherits: 8 · references: 8 · conceptually_related_to: 7 · shares_data_with: 1

## God Nodes (most connected - your core abstractions)
1. `Room` - 24 edges
2. `GameError` - 21 edges
3. `RoomManager` - 21 edges
4. `el()` - 21 edges
5. `Phase` - 19 edges
6. `Player` - 13 edges
7. `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` - 12 edges
8. `The only place a participant ever receives a fact.      Deliberately excludes th` - 12 edges
9. `Personalized reveal, only once the host has revealed this player.` - 12 edges
10. `Authorized snapshot for a single participant.` - 12 edges

## Surprising Connections (you probably didn't know these)
- `WebSocket connection registry and message delivery.` --uses--> `Room`  [INFERRED]
  /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/websocket.py → /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/models.py
- `Tracks live sockets keyed by ``player_id`` (or ``host``).` --uses--> `Room`  [INFERRED]
  /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/websocket.py → /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/models.py
- `js/websocket.js` --shares_data_with--> `websocket.py`  [INFERRED]
  frontend/index.html → README.md
- `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` --uses--> `GameError`  [INFERRED]
  /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/main.py → /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/game.py
- `Authorized snapshot for a single participant.` --uses--> `GameError`  [INFERRED]
  /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/main.py → /Users/sebastianrafaellachica/codingprojects/Detective/backend/app/game.py

## Hyperedges (group relationships)
- **Frontend JavaScript Module Stack** — index_config_js, index_state_js, index_api_js, index_websocket_js, index_ui_js, index_app_js [EXTRACTED 1.00]
- **Backend FastAPI Module Stack** — readme_main_py, readme_models_py, readme_schemas_py, readme_game_py, readme_rooms_py, readme_websocket_py, readme_security_py [EXTRACTED 1.00]

## Communities

### Community 0 - "Domain Models & State Snapshots"
Cohesion: 0.11
Nodes (29): Phase, assignment_for(), build_player_state(), Private Fact Detective — FastAPI backend.  Single persistent process, in-memory, Authorized snapshot for a single participant., Authorized snapshot for the host (host may see everything)., Send every connected client the snapshot it is authorized to see., Reveal one participant (``target_id``) or everyone (omit ``target_id``). (+21 more)

### Community 1 - "FastAPI Room API"
Cohesion: 0.15
Nodes (21): announce_phase(), _apply_host_action(), build_host_state(), _cleanup_loop(), end_game(), expire_investigation(), get_state(), host_action() (+13 more)

### Community 2 - "Frontend UI Rendering"
Cohesion: 0.23
Nodes (24): appendChildren(), button(), el(), fmtTime(), header(), hostControls(), playerList(), remainingSeconds() (+16 more)

### Community 3 - "Backend Integration Tests"
Cohesion: 0.09
Nodes (9): create_room(), join_player(), setup_room_with_players(), End-to-end simulation of the complete 7-player game over REST + WebSockets.  Thi, Repeat assignment to be confident nobody ever gets their own fact., Read messages until a 'state' message satisfies ``predicate``., test_full_seven_player_game(), test_no_self_assignment_over_many_games() (+1 more)

### Community 4 - "Game Rules & Derangement"
Cohesion: 0.12
Nodes (16): assert_transition(), can_transition(), clamp_investigation_minutes(), GameError, generate_derangement(), Pure game rules: phases, derangement assignment and validation.  This module has, Trim and validate a submitted fact., Raised for invalid, user-correctable game actions. (+8 more)

### Community 5 - "Frontend File Map"
Cohesion: 0.13
Nodes (15): js/api.js, js/app.js, js/config.js, js/state.js, css/styles.css, js/ui.js, js/websocket.js, api.js (+7 more)

### Community 6 - "WebSocket Connection Manager"
Cohesion: 0.18
Nodes (3): ConnectionManager, WebSocket connection registry and message delivery., Tracks live sockets keyed by ``player_id`` (or ``host``).

### Community 7 - "Session Security & Tokens"
Cohesion: 0.20
Nodes (9): generate_id(), generate_room_code(), generate_token(), normalize_room_code(), Temporary session authentication helpers.  No accounts, no passwords: rooms are, Return a short, human-friendly room code such as ``K7PX2``., Return a cryptographically secure URL-safe session token., Return a short random identifier used internally for entities. (+1 more)

### Community 8 - "Guessing & Reveal Tests"
Cohesion: 0.33
Nodes (7): _play_to_guessing(), test_duplicate_guess_rejected(), test_end_game(), test_full_guess_and_reveal_flow(), test_guess_unknown_target_rejected(), test_one_at_a_time_reveal(), test_self_guess_rejected()

### Community 10 - "Privacy & Visibility Tests"
Cohesion: 0.47
Nodes (7): _advance_to_ready(), _start_investigation(), test_fact_not_visible_before_investigation(), test_host_can_see_complete_state(), test_participant_cannot_receive_own_fact(), test_participant_state_hides_other_facts_and_owner(), test_reveal_exposes_owner_only_after_reveal()

### Community 11 - "WebSocket Client"
Cohesion: 0.46
Nodes (6): disconnect(), handleMessage(), open(), scheduleReconnect(), startPing(), stopPing()

### Community 14 - "Backend Package Init"
Cohesion: 1.00
Nodes (1): Private Fact Detective backend package.

### Community 17 - "Game Module"
Cohesion: 1.00
Nodes (1): game.py

### Community 18 - "Main Module"
Cohesion: 1.00
Nodes (1): main.py

### Community 19 - "Models Module"
Cohesion: 1.00
Nodes (1): models.py

### Community 20 - "Rooms Module"
Cohesion: 1.00
Nodes (1): rooms.py

### Community 21 - "Schemas Module"
Cohesion: 1.00
Nodes (1): schemas.py

### Community 22 - "Security Module"
Cohesion: 1.00
Nodes (1): security.py

## Knowledge Gaps
- **28 isolated node(s):** `Private Fact Detective backend package.`, `Pure game rules: phases, derangement assignment and validation.  This module has`, `Raised for invalid, user-correctable game actions.`, `Return a derangement mapping ``giver_id -> receiver_id``.      Each giver is ass`, `Raise ``GameError`` unless ``mapping`` is a valid derangement.` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Backend Package Init`** (1 nodes): `Private Fact Detective backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Game Module`** (1 nodes): `game.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Main Module`** (1 nodes): `main.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Models Module`** (1 nodes): `models.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Rooms Module`** (1 nodes): `rooms.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Schemas Module`** (1 nodes): `schemas.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Security Module`** (1 nodes): `security.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` connect `Domain Models & State Snapshots` to `Game Rules & Derangement`, `FastAPI Room API`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `Room` connect `Domain Models & State Snapshots` to `Game Rules & Derangement`, `WebSocket Connection Manager`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `GameError` connect `Game Rules & Derangement` to `Domain Models & State Snapshots`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `Room` (e.g. with `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` and `Authorized snapshot for a single participant.`) actually correct?**
  _`Room` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `GameError` (e.g. with `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` and `Authorized snapshot for a single participant.`) actually correct?**
  _`GameError` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `RoomManager` (e.g. with `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` and `Authorized snapshot for a single participant.`) actually correct?**
  _`RoomManager` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Phase` (e.g. with `Private Fact Detective — FastAPI backend.  Single persistent process, in-memory` and `Authorized snapshot for a single participant.`) actually correct?**
  _`Phase` has 18 INFERRED edges - model-reasoned connections that need verification._