// All rendering. Builds DOM directly (textContent only) so user-provided
// names and facts can never be interpreted as HTML.
(function () {
  var PHASE_LABELS = {
    LOBBY: "Lobby",
    FACT_COLLECTION: "Fact Collection",
    READY: "Ready",
    ASSIGNMENT: "Assigning…",
    INVESTIGATION: "Investigation",
    GUESSING: "Guessing",
    REVEAL: "Reveal",
    FINISHED: "Finished",
  };

  var PROMPT_IDEAS = [
    "What's something unusual that happened to you when you were younger?",
    "Have you ever had a really weird travel experience?",
    "What's a hobby people wouldn't expect you to have?",
    "What's the most random thing you've ever done?",
    "Have you ever gotten yourself into a funny situation?",
    "What's something most people here probably don't know about you?",
  ];

  var factDraft = "";
  var serverOffsetMs = 0;
  var hostMinutes = 10;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "value") node.value = v;
        else if (k === "checked") node.checked = !!v;
        else if (k === "disabled") node.disabled = !!v;
        else if (k.indexOf("on") === 0 && typeof v === "function") {
          node.addEventListener(k.slice(2), v);
        } else {
          node.setAttribute(k, v);
        }
      });
    }
    appendChildren(node, children);
    return node;
  }

  function appendChildren(node, children) {
    if (children === null || children === undefined) return;
    if (Array.isArray(children)) {
      children.forEach(function (c) {
        appendChildren(node, c);
      });
    } else if (children instanceof Node) {
      node.appendChild(children);
    } else {
      node.appendChild(document.createTextNode(String(children)));
    }
  }

  function fmtTime(totalSeconds) {
    var s = Math.max(0, Math.floor(totalSeconds));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return String(m).padStart(2, "0") + ":" + String(r).padStart(2, "0");
  }

  function remainingSeconds() {
    var st = Store.get();
    if (!st.game || !st.game.investigation) return null;
    var endsAt = st.game.investigation.ends_at;
    if (!endsAt) return null;
    return endsAt - (Date.now() + serverOffsetMs) / 1000;
  }

  function header(state) {
    var g = state.game;
    var badge =
      g && g.phase
        ? el("span", { class: "badge badge-" + g.phase, text: PHASE_LABELS[g.phase] || g.phase })
        : null;
    var connText =
      state.connection === "connected"
        ? "Live"
        : state.connection === "reconnecting"
        ? "Reconnecting…"
        : "Offline";
    return el("header", { class: "topbar" }, [
      el("div", { class: "brand" }, [
        el("span", { class: "brand-mark", text: "🔍" }),
        el("span", { class: "brand-name", text: "Private Fact Detective" }),
      ]),
      el("div", { class: "topbar-right" }, [
        g ? el("span", { class: "room-pill", text: "ROOM " + g.room_code }) : null,
        badge,
        el("span", { class: "conn conn-" + state.connection, text: connText }),
      ]),
    ]);
  }

  function playerList(players, opts) {
    opts = opts || {};
    return el(
      "ul",
      { class: "player-list" },
      players.map(function (p) {
        var marks = [];
        if (opts.showSubmitted) marks.push(p.submitted ? "✓ fact" : "…");
        if (opts.showGuessed) marks.push(p.guessed ? "✓ guess" : "…");
        if (opts.showConnection && p.connected === false) marks.push("offline");
        return el("li", { class: "player-chip" + (p.connected === false ? " offline" : "") }, [
          el("span", { class: "dot" }),
          el("span", { class: "player-name", text: p.name }),
          marks.length ? el("span", { class: "player-meta", text: marks.join(" · ") }) : null,
        ]);
      })
    );
  }

  // -------------------------------------------------------------------------
  // Landing
  // -------------------------------------------------------------------------
  function renderLanding(state) {
    var error = state.error ? el("p", { class: "error", text: state.error }) : null;
    var params = new URLSearchParams(location.search);
    var prefilledRoom = (params.get("room") || "").toUpperCase();

    var nameInput = el("input", { type: "text", placeholder: "Your name", maxlength: "40" });
    var roomInput = el("input", {
      type: "text",
      placeholder: "Room code",
      maxlength: "5",
      value: prefilledRoom,
      class: "uppercase",
    });

    function doJoin() {
      App.joinRoom(roomInput.value.trim(), nameInput.value.trim());
    }

    return el("main", { class: "screen screen-landing" }, [
      el("section", { class: "hero" }, [
        el("h1", { text: "PRIVATE FACT DETECTIVE" }),
        el("p", { class: "tagline", text: "A team bonding game where conversation is the clue." }),
      ]),
      error,
      el("section", { class: "card" }, [
        el("h2", { text: "Create a room" }),
        el("p", { class: "muted", text: "You'll be the host and run the game." }),
        el("button", { class: "btn primary", text: "Create Room", onclick: App.createRoom }),
      ]),
      el("section", { class: "card" }, [
        el("h2", { text: "Join a room" }),
        el("div", { class: "field" }, [el("label", { text: "Room code" }), roomInput]),
        el("div", { class: "field" }, [el("label", { text: "Display name" }), nameInput]),
        el("button", { class: "btn", text: "Join Room", onclick: doJoin }),
      ]),
      el("p", { class: "footnote", text: "No accounts. No database. Just one team meeting." }),
    ]);
  }

  // -------------------------------------------------------------------------
  // Participant views
  // -------------------------------------------------------------------------
  function renderLobbyParticipant(state) {
    var g = state.game;
    return el("section", { class: "card center" }, [
      el("h2", { text: "You're in!" }),
      el("p", { class: "muted", text: "Waiting for the host to start fact collection…" }),
      el("div", { class: "players-block" }, [
        el("h3", { text: "Players (" + g.players.length + ")" }),
        playerList(g.players, { showConnection: true }),
      ]),
      el("p", { class: "footnote", text: "Share the room code " + g.room_code + " with your team." }),
    ]);
  }

  function renderFactCollectionParticipant(state) {
    var g = state.game;
    if (g.you.submitted) {
      return el("section", { class: "card center" }, [
        el("div", { class: "success-mark", text: "✓" }),
        el("h2", { text: "Fact submitted" }),
        el("p", { class: "muted", text: "Waiting for everyone else…" }),
        el("p", { class: "progress", text: g.facts_submitted + " / " + g.facts_total + " submitted" }),
      ]);
    }

    var textarea = el("textarea", {
      class: "fact-input",
      maxlength: "500",
      rows: "4",
      placeholder: "I once…",
      oninput: function (e) {
        factDraft = e.target.value;
        counter.textContent = e.target.value.length + " / 500";
      },
    });
    textarea.value = factDraft;
    var counter = el("span", { class: "counter", text: factDraft.length + " / 500" });

    var categories = el(
      "div",
      { class: "chips" },
      [
        "Childhood",
        "Travel",
        "Unexpected hobbies",
        "Funny accidents",
        "Unusual skills",
        "Strange experiences",
        "Accomplishments",
        "Random experiences",
        "Interesting firsts",
        "Things people don't know",
      ].map(function (c) {
        return el("span", { class: "chip", text: c });
      })
    );

    return el("section", { class: "card" }, [
      el("h2", { text: "YOUR SECRET FACT" }),
      el("p", {
        class: "muted",
        text: "Submit one interesting personal fact that others could discover through conversation.",
      }),
      categories,
      textarea,
      counter,
      el("p", {
        class: "footnote",
        text: "Please avoid highly sensitive information. You can't change it after submitting.",
      }),
      el("button", {
        class: "btn primary",
        text: "Submit Fact",
        onclick: function () {
          App.submitFact(factDraft);
        },
      }),
    ]);
  }

  function renderReadyParticipant(state) {
    var g = state.game;
    return el("section", { class: "card center" }, [
      el("h2", { text: "Everyone's ready 🎉" }),
      el("p", { class: "muted", text: "The host will start the investigation shortly." }),
      el("p", { class: "progress", text: g.facts_submitted + " / " + g.facts_total + " facts submitted" }),
    ]);
  }

  function renderInvestigationParticipant(state) {
    var g = state.game;
    var fact = g.assignment ? g.assignment.fact : "";
    var rem = remainingSeconds();
    return el("section", { class: "card investigation" }, [
      el("p", { class: "eyebrow", text: "YOUR SECRET FACT" }),
      el("blockquote", { class: "secret-fact", text: '"' + fact + '"' }),
      el("div", { class: "timer", id: "countdown", text: rem === null ? "--:--" : fmtTime(rem) }),
      el("h3", { text: "Who does this belong to?" }),
      el("p", { class: "muted", text: "Talk to everyone and figure out who this fact belongs to." }),
      el("div", { class: "rules" }, [
        el("h4", { text: "How to investigate" }),
        el("ul", null, [
          el("li", { text: "Ask natural, open questions." }),
          el("li", { text: "Don't directly ask “is this your fact?”" }),
          el("li", { text: "Listen for the story behind the fact." }),
        ]),
        el("p", { class: "muted", text: "Try questions like:" }),
        el(
          "ul",
          { class: "prompts" },
          PROMPT_IDEAS.map(function (p) {
            return el("li", { text: p });
          })
        ),
      ]),
    ]);
  }

  function renderGuessingParticipant(state) {
    var g = state.game;
    if (g.you.guessed) {
      return el("section", { class: "card center" }, [
        el("div", { class: "success-mark", text: "✓" }),
        el("h2", { text: "Guess submitted" }),
        el("p", { class: "muted", text: "Waiting for everyone else…" }),
        el("p", { class: "progress", text: g.guesses_submitted + " / " + g.facts_total + " guessed" }),
      ]);
    }

    var selection = Store.get().guessSelection;
    var options = g.players
      .filter(function (p) {
        return p.id !== g.you.id;
      })
      .map(function (p) {
        return el("label", { class: "radio-row" + (selection === p.id ? " selected" : "") }, [
          el("input", {
            type: "radio",
            name: "guess",
            value: p.id,
            checked: selection === p.id,
            onchange: function () {
              Store.setGuessSelection(p.id);
            },
          }),
          el("span", { text: p.name }),
        ]);
      });

    return el("section", { class: "card" }, [
      el("p", { class: "eyebrow", text: "TIME'S UP" }),
      el("h2", { text: "Who owns this fact?" }),
      g.assignment
        ? el("blockquote", { class: "secret-fact small", text: '"' + g.assignment.fact + '"' })
        : null,
      el("div", { class: "radio-list" }, options),
      el("button", {
        class: "btn primary",
        text: "Submit Guess",
        disabled: !selection,
        onclick: function () {
          App.submitGuess(selection);
        },
      }),
    ]);
  }

  function renderRevealParticipant(state) {
    var g = state.game;
    if (!g.reveal) {
      return el("section", { class: "card center" }, [
        el("h2", { text: "The reveal is coming…" }),
        el("p", { class: "muted", text: "Waiting for the host to reveal results." }),
        el("p", {
          class: "progress",
          text: (g.revealed_count || 0) + " / " + g.facts_total + " revealed",
        }),
      ]);
    }
    var r = g.reveal;
    return el("section", { class: "card reveal" }, [
      el("p", { class: "eyebrow", text: "THE REVEAL" }),
      el("blockquote", { class: "secret-fact small", text: '"' + r.fact + '"' }),
      el("div", { class: "reveal-grid" }, [
        revealRow("Fact owner", r.owner_name),
        revealRow("Your guess", r.your_guess_name || "—"),
      ]),
      el("div", { class: "verdict " + (r.correct ? "correct" : "incorrect") }, [
        el("span", { text: r.correct ? "✓ Correct!" : "✗ Incorrect" }),
      ]),
      el("p", {
        class: "muted",
        text:
          "Now let " +
          (r.owner_name || "the owner") +
          " tell the story behind this fact.",
      }),
    ]);
  }

  function revealRow(label, value) {
    return el("div", { class: "reveal-item" }, [
      el("span", { class: "reveal-label", text: label }),
      el("span", { class: "reveal-value", text: value }),
    ]);
  }

  function renderFinishedParticipant(state) {
    var g = state.game;
    return el("section", { class: "card center" }, [
      el("h1", { text: "Case closed 🔍" }),
      el("p", { class: "muted", text: "Thanks for playing Private Fact Detective!" }),
      g.reveal ? renderRevealParticipant(state) : null,
    ]);
  }

  // -------------------------------------------------------------------------
  // Host dashboard
  // -------------------------------------------------------------------------
  function hostControls(state) {
    var g = state.game;
    var phase = g.phase;
    var controls = [];

    if (phase === "LOBBY") {
      controls.push(
        button("Start Fact Collection", "primary", function () {
          App.hostAction("start_fact_collection");
        })
      );
    } else if (phase === "FACT_COLLECTION" || phase === "READY") {
      controls.push(
        button("Reset Facts", "ghost", function () {
          App.hostAction("reset_facts");
        })
      );
      if (phase === "READY") {
        var minutesInput = el("input", {
          type: "number",
          min: "3",
          max: "30",
          value: String(hostMinutes),
          class: "minutes-input",
          oninput: function (e) {
            hostMinutes = parseInt(e.target.value || "10", 10);
          },
        });
        controls.push(
          el("div", { class: "minutes-control" }, [
            el("label", { text: "Investigation minutes" }),
            minutesInput,
          ])
        );
        controls.push(
          button("Start Investigation", "primary", function () {
            App.startGame(hostMinutes);
          })
        );
      }
    } else if (phase === "INVESTIGATION") {
      controls.push(
        button("End Investigation", "primary", function () {
          App.hostAction("end_investigation");
        })
      );
    } else if (phase === "GUESSING") {
      controls.push(
        button("Reveal All Results", "primary", function () {
          App.hostAction("reveal_all");
        })
      );
    } else if (phase === "REVEAL") {
      controls.push(
        button("Reveal All", "primary", function () {
          App.hostAction("reveal_all");
        })
      );
      controls.push(
        button("Finish Game", "ghost", function () {
          App.hostAction("finish");
        })
      );
    } else if (phase === "FINISHED") {
      controls.push(
        button("End Session", "danger", function () {
          App.endGame();
        })
      );
    }
    return el("div", { class: "controls" }, controls);
  }

  function button(label, kind, onclick) {
    return el("button", { class: "btn " + (kind || ""), text: label, onclick: onclick });
  }

  function renderHost(state) {
    var g = state.game;
    var phase = g.phase;

    var scoreboard = el("section", { class: "card" }, [
      el("h2", { text: "Host Dashboard" }),
      el("div", { class: "stat-row" }, [
        stat("Players", g.players.length),
        stat("Facts", g.facts_submitted + " / " + g.facts_total),
        stat("Guesses", g.guesses_submitted + " / " + g.facts_total),
        stat("Revealed", (g.revealed_players || []).length + " / " + g.facts_total),
      ]),
      g.investigation && phase === "INVESTIGATION"
        ? el("div", { class: "timer small", id: "countdown", text: "--:--" })
        : null,
      hostControls(state),
    ]);

    var roster = el("section", { class: "card" }, [
      el("h3", { text: "Players" }),
      g.players.length === 0
        ? el("p", { class: "muted", text: "No players yet. Share room code " + g.room_code + "." })
        : playerList(g.players, { showSubmitted: true, showGuessed: true, showConnection: true }),
    ]);

    var content = [scoreboard, roster];

    if (
      (phase === "INVESTIGATION" || phase === "GUESSING" || phase === "REVEAL" || phase === "FINISHED") &&
      g.assignments &&
      g.assignments.length
    ) {
      content.push(renderHostAssignments(state));
    }

    if (phase === "REVEAL" || phase === "FINISHED") {
      content.push(renderHostRevealControls(state));
    }

    return el("div", { class: "host-grid" }, content);
  }

  function stat(label, value) {
    return el("div", { class: "stat" }, [
      el("span", { class: "stat-value", text: String(value) }),
      el("span", { class: "stat-label", text: label }),
    ]);
  }

  function renderHostAssignments(state) {
    var g = state.game;
    var rows = g.assignments.map(function (a) {
      return el("tr", null, [
        el("td", { text: a.giver_name }),
        el("td", { class: "arrow", text: "→" }),
        el("td", { text: a.owner_name }),
        el("td", { class: "fact-cell", text: a.fact || "" }),
      ]);
    });
    return el("section", { class: "card wide" }, [
      el("h3", { text: "Assignments (host only)" }),
      el("table", { class: "assignments" }, [
        el("thead", null, [
          el("tr", null, [
            el("th", { text: "Detective" }),
            el("th", null),
            el("th", { text: "Fact owner" }),
            el("th", { text: "Fact" }),
          ]),
        ]),
        el("tbody", null, rows),
      ]),
    ]);
  }

  function renderHostRevealControls(state) {
    var g = state.game;
    var revealed = {};
    (g.revealed_players || []).forEach(function (id) {
      revealed[id] = true;
    });
    var items = g.players.map(function (p) {
      return el("div", { class: "reveal-control-row" }, [
        el("span", { text: p.name }),
        revealed[p.id]
          ? el("span", { class: "tag done", text: "revealed" })
          : button("Reveal", "small", function () {
              App.revealPlayer(p.id);
            }),
      ]);
    });
    return el("section", { class: "card wide" }, [
      el("h3", { text: "Reveal results" }),
      el("p", { class: "muted", text: "Reveal one at a time, or all at once." }),
      el("div", { class: "reveal-controls" }, items),
    ]);
  }

  // -------------------------------------------------------------------------
  // Router
  // -------------------------------------------------------------------------
  function render(state) {
    var root = document.getElementById("screen");
    root.innerHTML = "";

    // Track server/client clock offset whenever fresh state arrives.
    if (state.game && state.game.server_now) {
      serverOffsetMs = state.game.server_now * 1000 - Date.now();
    }

    var content;
    if (!state.session || !state.game) {
      content = renderLanding(state);
    } else if (state.game.role === "host") {
      content = renderHost(state);
    } else {
      content = renderParticipant(state);
    }

    root.appendChild(header(state));
    if (state.error && state.session && state.game) {
      root.appendChild(el("p", { class: "error banner", text: state.error }));
    }
    root.appendChild(content);
  }

  function renderParticipant(state) {
    var phase = state.game.phase;
    switch (phase) {
      case "LOBBY":
        return renderLobbyParticipant(state);
      case "FACT_COLLECTION":
        return renderFactCollectionParticipant(state);
      case "READY":
        return renderReadyParticipant(state);
      case "ASSIGNMENT":
      case "INVESTIGATION":
        return renderInvestigationParticipant(state);
      case "GUESSING":
        return renderGuessingParticipant(state);
      case "REVEAL":
        return renderRevealParticipant(state);
      case "FINISHED":
        return renderFinishedParticipant(state);
      default:
        return el("section", { class: "card center" }, [el("p", { text: "Loading…" })]);
    }
  }

  function updateCountdown() {
    var node = document.getElementById("countdown");
    if (!node) return;
    var rem = remainingSeconds();
    if (rem === null) {
      node.textContent = "--:--";
      return;
    }
    if (rem <= 0) {
      node.textContent = "00:00";
      return;
    }
    node.textContent = fmtTime(rem);
  }

  window.UI = {
    render: render,
    updateCountdown: updateCountdown,
    clearFactDraft: function () {
      factDraft = "";
    },
  };
})();
