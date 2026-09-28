/*
 * Replays: Honver's Mahjong Soul games, played back on this site.
 *
 * replay.html?g=<uuid> steps through site/replays/<uuid>.json (built by scripts/build_replays.py):
 * each hand as an ordered event stream, and at each of Honver's decisions the local Mortal policy's
 * probability for every legal action. Without ?g= the page lists site/replays/index.json.
 *
 * Other parameters: h (hand index) and e (the event index of the step), which the page keeps up to
 * date as you step; r (a round name such as "East 2-0"), t (your turn in that hand) and at=call (open
 * a turn that starts with a call on the discard you called), which the guide's links use.
 *
 * The page loads app.js first (data-app="table-only") and reuses renderMahjongTable, tileIcon,
 * tileName, escapeHtml, rankText, sameBaseTile, prescriptionTileSortKey, applyTileCompatibility,
 * renderCommitStamp, setupRetractingTopbar and setupRunningHead.
 */
(function () {
  const assetVersion = "20260928-replays";
  const hideHandsKey = "luckyj:replays:hide-hands";
  // A choice Mortal gives less than this is flagged (scripts/build_replays.py counts the same way).
  const FLAG_BELOW = 0.05;
  const REL = ["self", "shimocha", "toimen", "kamicha"];
  const REL_NAME = { self: "You", shimocha: "Shimocha", toimen: "Toimen", kamicha: "Kamicha" };
  const POSITION = { self: "current", shimocha: "next", toimen: "across", kamicha: "prev" };
  const WINDS = ["E", "S", "W", "N"];
  const ROUND_SHORT = { East: "E", South: "S", West: "W", North: "N" };
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const app = document.querySelector("[data-replay-app]");

  // ------------------------------------------------------------------ small helpers

  function signed(n) {
    const v = Number(n) || 0;
    return v > 0 ? `+${whole.format(v)}` : v < 0 ? `−${whole.format(-v)}` : "0";
  }

  function scoreText(n) {
    const v = Number(n) || 0;
    return v < 0 ? `\u2212${whole.format(-v)}` : whole.format(v);
  }

  function signedPoints(n) {
    const v = Number(n) || 0;
    const text = Math.abs(v).toFixed(1);
    return v > 0 ? `+${text}` : v < 0 ? `−${text}` : "0.0";
  }

  function pctText(p) {
    if (p < 0.001) return "0%";
    if (p < 0.01) return "<1%";
    if (p < 0.1) return `${(p * 100).toFixed(1)}%`;
    return `${Math.round(p * 100)}%`;
  }

  function dateText(value, withTime = true) {
    const m = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}:\d{2}))?/);
    if (!m) return String(value || "");
    const day = `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
    return withTime && m[4] ? `${day}, ${m[4]}` : day;
  }

  // "28 Sep, 01:38": the list's date on a phone.
  function compactDate(value) {
    const m = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}:\d{2}))?/);
    if (!m) return String(value || "");
    return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1].slice(0, 3)}${m[4] ? `, ${m[4]}` : ""}`;
  }

  function shortRound(round) {
    const m = String(round || "").match(/^(\w+) (\d)-(\d+)$/);
    if (!m) return round;
    return `${ROUND_SHORT[m[1]] || m[1][0]}${m[2]}${m[3] !== "0" ? `·${m[3]}` : ""}`;
  }

  function sortTiles(list) {
    return list.slice().sort((a, b) => prescriptionTileSortKey(a) - prescriptionTileSortKey(b));
  }

  function removeTile(list, tile) {
    let i = list.indexOf(tile);
    if (i < 0) i = list.findIndex((t) => sameBaseTile(t, tile));
    if (i >= 0) list.splice(i, 1);
  }

  function inlineTile(tile) {
    return tileIcon(tile, "inline-tile");
  }

  function tileRunHtml(tiles) {
    return tiles.map(inlineTile).join("");
  }

  function loadJson(path) {
    return fetch(`${path}?v=${assetVersion}`).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    });
  }

  function tierOf(decision) {
    const you = probOf(decision, decision.you);
    if (decision.p[0][0] === decision.you) return "match";
    return you < FLAG_BELOW ? "flag" : "differ";
  }

  function probOf(decision, action) {
    const hit = decision.p.find(([a]) => a === action);
    return hit ? hit[1] : 0;
  }

  // ------------------------------------------------------------------ the list of games

  function renderList(index) {
    document.title = "Replays: Honver’s games";
    const games = index.games || [];
    const first = games[games.length - 1];
    const turns = games.reduce((n, g) => n + (g.turns || 0), 0);
    const matched = games.reduce((n, g) => n + (g.turns_matched || 0), 0);
    const rows = games
      .map((g) => {
        const href = `replay.html?g=${encodeURIComponent(g.id)}`;
        const match = g.turns ? `${Math.round((100 * g.turns_matched) / g.turns)}%` : "";
        return `
          <tr>
            <th scope="row"><a href="${escapeHtml(href)}"><span class="date-long">${escapeHtml(dateText(g.date))}</span><span class="date-short">${escapeHtml(
              compactDate(g.date)
            )}</span></a></th>
            <td class="replay-games-place place-${g.placement}">${escapeHtml(rankText(g.placement))}</td>
            <td class="replay-games-score">${scoreText(g.score)}<small>${escapeHtml(signedPoints(g.points))}</small></td>
            <td class="replay-games-num replay-games-hands">${g.hands}</td>
            <td class="replay-games-num">${match}</td>
            <td class="replay-games-num">${g.flagged ?? ""}</td>
          </tr>`;
      })
      .join("");
    app.innerHTML = `
      <section class="replay-masthead">
        <p class="guide-eyebrow">Replays &#183; ${games.length} Jade South games since ${escapeHtml(dateText(first?.date, false))}</p>
        <h1>Your games, replayed here.</h1>
        <p class="standfirst">Each game opens here with all four hands face up and Mortal's rating of every choice you made. The links under the guide's tables open the hand at the turn they discuss.</p>
        <p class="replay-masthead-note">Across these games you played Mortal's first choice on ${whole.format(matched)} of ${whole.format(turns)} turns (${turns ? Math.round((100 * matched) / turns) : 0}%). A flagged choice is one Mortal gives under 5%.</p>
      </section>
      <div class="replay-games-scroll">
        <table class="replay-games">
          <thead>
            <tr>
              <th scope="col">Game</th>
              <th scope="col">Place</th>
              <th scope="col">Score</th>
              <th scope="col" class="replay-games-num replay-games-hands">Hands</th>
              <th scope="col" class="replay-games-num"><abbr title="Turns where you played Mortal's first choice">Mortal's pick</abbr></th>
              <th scope="col" class="replay-games-num"><abbr title="Choices Mortal gives under 5%">Flagged</abbr></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  // ------------------------------------------------------------------ one game: state

  const view = { game: null, hand: 0, stop: 0, stops: [], decisions: new Map(), turns: [] };

  function relOf(seat) {
    return REL[(seat - view.game.hero + 4) % 4];
  }

  function nameOf(seat) {
    return REL_NAME[relOf(seat)];
  }

  function objectName(seat) {
    return seat === view.game.hero ? "you" : REL_NAME[relOf(seat)];
  }

  function initialState(hand) {
    return {
      hands: hand.haipai.map((tiles) => tiles.slice()),
      drawn: [null, null, null, null],
      rivers: [[], [], [], []],
      melds: [[], [], [], []],
      riichi: [false, false, false, false],
      pendingRiichi: [false, false, false, false],
      scores: hand.scores.slice(),
      sticks: hand.sticks,
      dora: [hand.dora],
      left: 70,
      last: null,
      // Each player's turn, counted as the guide counts yours: a draw from the wall or a call.
      turns: [0, 0, 0, 0],
      // Tiles other players called out of each pond; they leave the pond but still count as turns.
      calledAway: [0, 0, 0, 0],
    };
  }

  function apply(state, e) {
    const seat = e[1];
    switch (e[0]) {
      case "t":
        state.hands[seat].push(e[2]);
        state.drawn[seat] = e[2];
        state.left -= 1;
        if (!e[3]) state.turns[seat] += 1;
        break;
      case "d":
        removeTile(state.hands[seat], e[2]);
        state.drawn[seat] = null;
        state.rivers[seat].push({ tile: e[2], tsumogiri: Boolean(e[3]), riichi: state.pendingRiichi[seat], called: false });
        state.pendingRiichi[seat] = false;
        state.last = { seat, index: state.rivers[seat].length - 1 };
        break;
      case "r":
        state.riichi[seat] = true;
        state.pendingRiichi[seat] = true;
        break;
      case "ra":
        state.scores[seat] -= 1000;
        state.sticks += 1;
        break;
      case "c":
      case "p":
      case "m": {
        const [kind, , from, tile, consumed] = e;
        consumed.forEach((t) => removeTile(state.hands[seat], t));
        const river = state.rivers[from];
        if (river.length) river[river.length - 1].called = true;
        state.calledAway[from] += 1;
        state.turns[seat] += 1;
        state.melds[seat].push({
          kind: { c: "chi", p: "pon", m: "daiminkan" }[kind],
          tiles: sortTiles([tile, ...consumed]),
          called_tile: tile,
          called_from: REL[(from - seat + 4) % 4],
        });
        state.drawn[seat] = null;
        state.last = null;
        break;
      }
      case "a":
        e[2].forEach((t) => removeTile(state.hands[seat], t));
        state.melds[seat].push({ kind: "ankan", tiles: e[2].slice() });
        state.drawn[seat] = null;
        break;
      case "k":
        removeTile(state.hands[seat], e[2]);
        state.melds[seat].push({ kind: "kakan", tiles: [e[2]] });
        state.drawn[seat] = null;
        break;
      case "dora":
        state.dora.push(e[1]);
        break;
      default:
        break;
    }
  }

  function stateAt(hand, count) {
    const state = initialState(hand);
    for (let i = 0; i < count; i += 1) apply(state, hand.ev[i]);
    return state;
  }

  // Where the page pauses: the deal, every discard, call and kan, your draws and riichi declarations,
  // and the result. Another player's draw shows with their discard; a new dora indicator and a riichi
  // stick show with the event that caused them.
  function buildStops(hand) {
    const hero = view.game.hero;
    const ev = hand.ev;
    const stops = [{ s: 0, i: -1, kind: "start" }];
    for (let i = 0; i < ev.length; i += 1) {
      const [kind, seat] = ev[i];
      if (kind === "dora" || kind === "ra") continue;
      if ((kind === "t" || kind === "r") && seat !== hero) continue;
      let s = i + 1;
      while (s < ev.length && (ev[s][0] === "dora" || ev[s][0] === "ra")) s += 1;
      stops.push({ s, i, kind: "event" });
    }
    stops.push({ s: ev.length, i: ev.length, kind: "end" });
    return stops;
  }

  // Your turn number at each event, counted as the guide counts it: each draw from the wall and each call.
  function heroTurns(hand) {
    const hero = view.game.hero;
    const turns = [];
    let turn = 0;
    hand.ev.forEach((e, i) => {
      if (e[1] === hero && ((e[0] === "t" && !e[3]) || ["c", "p", "m"].includes(e[0]))) turn += 1;
      turns[i] = turn;
    });
    return turns;
  }

  // The step for "your turn t": the draw or call that starts it, where Mortal's numbers for your
  // discard are. With atCall, a turn that starts with a call opens one step earlier, on the discard
  // you called, where Mortal's call-or-pass numbers are.
  function stopForTurn(hand, turn, atCall) {
    const hero = view.game.hero;
    const turns = heroTurns(hand);
    const start = hand.ev.findIndex((e, i) => turns[i] === turn && e[1] === hero && ["t", "c", "p", "m"].includes(e[0]));
    if (start < 0) return 0;
    let target = start;
    if (atCall && hand.ev[start][0] !== "t") {
      for (let i = start - 1; i >= 0; i -= 1) {
        if (hand.ev[i][0] === "d") {
          target = i;
          break;
        }
      }
    }
    const index = view.stops.findIndex((stop) => stop.i === target);
    return index < 0 ? 0 : index;
  }

  // ------------------------------------------------------------------ one game: the table

  function ranksFor(scores) {
    const order = [0, 1, 2, 3].sort((a, b) => scores[b] - scores[a] || a - b);
    return [0, 1, 2, 3].map((s) => order.indexOf(s) + 1);
  }

  function visibleRiver(river) {
    const shown = river.filter((item) => !item.called);
    const riichiAt = river.findIndex((item) => item.riichi);
    const riichiIndex = riichiAt < 0 ? null : river.slice(0, riichiAt).filter((item) => !item.called).length;
    return { shown, riichiIndex };
  }

  function handTiles(state, seat, extra) {
    const drawn = extra || state.drawn[seat];
    const tiles = state.hands[seat].slice();
    if (drawn && !extra) removeTile(tiles, drawn);
    const sorted = sortTiles(tiles);
    return drawn ? { list: [...sorted, drawn], drawn: true } : { list: sorted, drawn: false };
  }

  function tableFor(hand, state, winTiles) {
    const oya = hand.kyoku % 4;
    const ranks = ranksFor(state.scores);
    const seats = [0, 1, 2, 3];
    return {
      round: hand.round,
      dealer: relOf(oya),
      dora_markers: state.dora.slice(),
      scores: seats.map((s) => ({
        seat: relOf(s),
        wind: WINDS[(s - oya + 4) % 4],
        score: state.scores[s],
        rank: ranks[s],
        dealer: s === oya,
      })),
      players: seats.map((s) => {
        const river = visibleRiver(state.rivers[s]);
        return {
          seat: relOf(s),
          wind: WINDS[(s - oya + 4) % 4],
          hand: handTiles(state, s, winTiles?.[s]).list.join(" "),
          discards: river.shown.map((item) => item.tile),
          riichi_discard_index: river.riichiIndex,
          melds: state.melds[s],
          reached: state.riichi[s],
        };
      }),
    };
  }

  function markRivers(wrap, state) {
    for (let s = 0; s < 4; s += 1) {
      const slots = wrap.querySelectorAll(`.player-discards.player-${POSITION[relOf(s)]} .discard-tile-slot`);
      const shown = state.rivers[s].filter((item) => !item.called);
      shown.forEach((item, n) => {
        const slot = slots[n];
        if (!slot) return;
        if (item.tsumogiri) slot.classList.add("is-tsumogiri");
        if (state.last && state.last.seat === s && state.rivers[s][state.last.index] === item) slot.classList.add("is-last");
      });
    }
  }

  function markHand(wrap, state, decision, winTiles) {
    const hero = view.game.hero;
    const cells = Array.from(wrap.querySelectorAll(".player-hand.player-current .tile-threat-cell"));
    if (!cells.length) return;
    const { drawn } = handTiles(state, hero, winTiles?.[hero]);
    if (drawn) cells[cells.length - 1].classList.add("is-drawn");
    const probs = new Map((decision?.p || []).filter(([a]) => /^[1-9][mps]r?$|^[ESWNPFC]$/.test(a)));
    const top = decision?.p[0][0];
    const best = decision?.p[0][1] || 1;
    // Every tile has a bar slot, empty when there is nothing to rate, so bars never push the hand down.
    for (const cell of cells) {
      const tile = cell.dataset.tile;
      const bar = document.createElement("span");
      bar.className = "replay-prob";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("i");
      if (probs.size) {
        const p = probs.get(tile) || 0;
        fill.style.setProperty("--p", String(Math.max(p / best, p > 0 ? 0.04 : 0)));
        if (tile === top) fill.className = "is-top";
        else if (tile === decision.you) fill.className = "is-you";
        cell.title = `${tileName(tile)}: Mortal ${pctText(p)}`;
      }
      bar.append(fill);
      cell.prepend(bar);
    }
    steadyHand(cells, Boolean(drawn));
    if (!probs.size) return;
    // Label one copy of each marked tile: your cut (the drawn copy when you cut the tile you drew).
    const pick = (tile, preferDrawn) => {
      const matches = cells.filter((cell) => cell.dataset.tile === tile);
      if (!matches.length) return null;
      const drawnCell = drawn ? cells[cells.length - 1] : null;
      if (preferDrawn && drawnCell && matches.includes(drawnCell)) return drawnCell;
      return matches.find((cell) => cell !== drawnCell) || matches[0];
    };
    const tsumogiri = nextDiscardIsTsumogiri();
    const youCell = probs.has(decision.you) ? pick(decision.you, tsumogiri) : null;
    const topCell = probs.has(top) ? (top === decision.you ? youCell : pick(top, false)) : null;
    if (youCell && youCell === topCell) {
      youCell.classList.add("guide-better");
      youCell.dataset.mark = "You and Mortal";
      return;
    }
    if (youCell) {
      youCell.classList.add("guide-cut");
      youCell.dataset.mark = "You";
    }
    if (topCell) {
      topCell.classList.add("guide-better");
      topCell.dataset.mark = "Mortal";
    }
  }

  // Your hand keeps fourteen places at every step: after the tiles you hold come invisible places,
  // with the drawn tile's gap before the first when you have not drawn. The hand is centred on the
  // table, so a constant width keeps every tile where it was when you draw, cut or a choice is marked.
  function steadyHand(cells, drawn) {
    const run = cells[0].parentElement;
    for (let k = cells.length; k < 14; k += 1) {
      const ghost = cells[0].cloneNode(true);
      ghost.className = `tile-threat-cell is-ghost${k === cells.length && !drawn ? " is-drawn" : ""}`;
      for (const name of ["data-tile", "data-mark", "title", "aria-label"]) ghost.removeAttribute(name);
      ghost.setAttribute("aria-hidden", "true");
      run.append(ghost);
    }
  }

  // Each name on the table carries that player's turn, and how many tiles were called out of their
  // pond, since those still count: pond tiles plus called tiles is the turn once they have cut.
  function labelTurns(wrap, state) {
    for (let s = 0; s < 4; s += 1) {
      const name = wrap.querySelector(`.player-hand.player-${POSITION[relOf(s)]} .player-name`);
      if (!name || !state.turns[s]) continue;
      const turn = document.createElement("span");
      turn.className = "player-turn";
      const called = state.calledAway[s];
      turn.textContent = ` \u00b7 turn ${state.turns[s]}${called ? ` (${called} called from pond)` : ""}`;
      name.append(turn);
    }
  }

  function nextDiscardIsTsumogiri() {
    const hand = view.game.hands[view.hand];
    const stop = view.stops[view.stop];
    for (let i = stop.i + 1; i < hand.ev.length; i += 1) {
      const e = hand.ev[i];
      if (e[1] === view.game.hero && e[0] === "d") return Boolean(e[3]);
      if (e[1] !== view.game.hero && e[0] !== "dora" && e[0] !== "ra") return false;
    }
    return false;
  }

  // ------------------------------------------------------------------ one game: the panel

  function eventText(hand, stop) {
    if (stop.kind === "start") {
      const oya = hand.kyoku % 4;
      const extras = [
        hand.honba ? `${hand.honba} honba` : "",
        hand.sticks ? `${hand.sticks} riichi stick${hand.sticks === 1 ? "" : "s"} on the table` : "",
      ].filter(Boolean);
      return `The deal. ${oya === view.game.hero ? "You are" : `${nameOf(oya)} is`} the dealer.${extras.length ? ` ${extras.join(", ")}.` : ""}`;
    }
    if (stop.kind === "end") return "";
    const e = hand.ev[stop.i];
    const who = nameOf(e[1]);
    const riichiBefore = stop.i > 0 && hand.ev[stop.i - 1][0] === "r" && hand.ev[stop.i - 1][1] === e[1];
    switch (e[0]) {
      case "t":
        return `You drew ${inlineTile(e[2])}${e[3] ? " from the dead wall" : ""}.`;
      case "r":
        return "You declared riichi.";
      case "d":
        if (riichiBefore) return `${who} declared riichi, cutting ${inlineTile(e[2])}.`;
        return `${who} cut ${inlineTile(e[2])}${e[3] ? ", the tile just drawn" : ""}.`;
      case "c":
      case "p":
      case "m": {
        const verb = { c: "chi", p: "pon", m: "an open kan" }[e[0]];
        const skipped = skippedBy(e[2], e[1]).map(objectName);
        const skipText = skipped.length
          ? ` That skips ${skipped.join(" and ")}, ${skipped.length > 1 ? "who fall" : skipped[0] === "you" ? "and you fall" : "who falls"} a turn behind.`
          : "";
        return `${who} called ${verb} on ${inlineTile(e[3])} from ${objectName(e[2])}.${skipText}`;
      }
      case "a":
        return `${who} declared a closed kan of ${inlineTile(e[2][0])}.`;
      case "k":
        return `${who} added ${inlineTile(e[2])} to a pon for a kan.`;
      default:
        return "";
    }
  }

  // The players between the discarder and the caller, in turn order, whose turn a call skips.
  function skippedBy(from, caller) {
    const skipped = [];
    for (let s = (from + 1) % 4; s !== caller; s = (s + 1) % 4) skipped.push(s);
    return skipped;
  }

  function chiTiles(tile, kind) {
    const n = Number(tile[0]);
    const suit = tile[1];
    const offsets = { "chi-low": [0, 1, 2], "chi-mid": [-1, 0, 1], "chi-high": [-2, -1, 0] }[kind];
    return offsets.map((o) => (o === 0 ? tile : `${n + o}${suit}`));
  }

  function actionLabel(action, decision, hand) {
    const trigger = hand.ev[decision.i];
    const own = trigger[1] === view.game.hero;
    if (/^[1-9][mps]r?$|^[ESWNPFC]$/.test(action)) {
      return `${inlineTile(action)}<span>${escapeHtml(tileName(action))}</span>`;
    }
    const tile = trigger[0] === "d" || trigger[0] === "k" ? trigger[2] : null;
    switch (action) {
      case "riichi":
        return "<span>Riichi</span>";
      case "pass":
        return "<span>Pass</span>";
      case "pon":
        return `<span>Pon</span>${tile ? tileRunHtml([tile, tile, tile]) : ""}`;
      case "kan":
        return own ? "<span>Kan</span>" : `<span>Kan</span>${tile ? tileRunHtml([tile, tile, tile, tile]) : ""}`;
      case "chi-low":
      case "chi-mid":
      case "chi-high":
        return `<span>Chi</span>${tile ? tileRunHtml(chiTiles(tile.replace("r", ""), action)) : ""}`;
      case "win":
        return `<span>${own ? "Tsumo" : "Ron"}</span>`;
      case "draw":
        return "<span>Abortive draw</span>";
      default:
        return `<span>${escapeHtml(action)}</span>`;
    }
  }

  function actionWords(action, decision, hand) {
    if (/^[1-9][mps]r?$|^[ESWNPFC]$/.test(action)) return inlineTile(action);
    const own = hand.ev[decision.i][1] === view.game.hero;
    const words = {
      riichi: "riichi",
      pass: "a pass",
      pon: "pon",
      kan: "kan",
      "chi-low": "chi",
      "chi-mid": "chi",
      "chi-high": "chi",
      win: own ? "tsumo" : "ron",
      draw: "the abortive draw",
    };
    return escapeHtml(words[action] || action);
  }

  function mortalBlock(hand, decision) {
    const block = document.createElement("section");
    const tier = tierOf(decision);
    block.className = `replay-mortal tier-${tier}`;
    const own = hand.ev[decision.i][1] === view.game.hero;
    const [top, topP] = decision.p[0];
    const youP = probOf(decision, decision.you);
    const verdict =
      tier === "match"
        ? `You played Mortal's first choice, ${actionWords(top, decision, hand)} at ${pctText(topP)}.`
        : `Mortal puts ${actionWords(top, decision, hand)} first at ${pctText(topP)}. Your ${actionWords(
            decision.you,
            decision,
            hand
          )} gets ${pctText(youP)}.`;
    const shown = decision.p.slice(0, 6);
    if (!shown.some(([a]) => a === decision.you)) shown.push([decision.you, youP]);
    const rows = shown
      .map(([action, p]) => {
        const classes = [action === top ? "is-top" : "", action === decision.you ? "is-you" : ""].filter(Boolean).join(" ");
        const tag = action === decision.you ? '<em class="replay-bar-tag">You</em>' : "";
        return `<li class="${classes}"><span class="replay-bar-label">${actionLabel(action, decision, hand)}</span><span class="replay-bar"><i style="width:${(
          p * 100
        ).toFixed(1)}%"></i></span><b>${pctText(p)}</b>${tag}</li>`;
      })
      .join("");
    block.innerHTML = `
      <p class="replay-mortal-head"><span class="figure-label">Mortal &#183; ${own ? "your turn" : "call chance"}</span>${
        tier === "flag" ? '<span class="replay-flag">Under 5%</span>' : ""
      }</p>
      <p class="replay-verdict">${verdict}</p>
      <ol class="replay-bars">${rows}</ol>
    `;
    return block;
  }

  function resultBlock(hand) {
    const block = document.createElement("section");
    block.className = "replay-result";
    const end = hand.end;
    const before = stateAt(hand, hand.ev.length);
    const lines = [];
    if (end.kind === "win") {
      for (const win of end.wins) {
        const how = win.seat === win.from ? "by tsumo" : `by ron off ${objectName(win.from)}`;
        const yaku = win.yaku.map(([name, han]) => `${escapeHtml(name)} ${escapeHtml(String(han))}`).join(", ");
        const value = win.value.charAt(0).toUpperCase() + win.value.slice(1);
        lines.push(
          `<p><b>${escapeHtml(nameOf(win.seat))} won ${how}.</b> ${escapeHtml(value)}.${
            yaku ? ` <span class="replay-yaku">Han: ${yaku}.</span>` : ""
          }</p>`
        );
        if (before.riichi[win.seat] && end.ura?.length) {
          lines.push(`<p class="replay-ura">Ura dora indicator${end.ura.length > 1 ? "s" : ""} ${tileRunHtml(end.ura.slice(0, before.dora.length))}</p>`);
        }
      }
    }
    const after = hand.after || before.scores;
    const deltas = [0, 1, 2, 3].map((s) => after[s] - hand.scores[s]);
    if (end.kind === "draw") {
      // At an exhaustive draw the noten payments show who was tenpai.
      const tenpai = [0, 1, 2, 3].filter((s) => end.deltas[s] > 0).map(nameOf);
      const note = end.label === "Exhaustive draw" && tenpai.length ? ` Tenpai: ${tenpai.join(", ")}.` : "";
      lines.push(`<p><b>${escapeHtml(end.label)}.</b>${escapeHtml(note)}</p>`);
    }
    const order = [0, 1, 2, 3].map((k) => (view.game.hero + k) % 4);
    const scoreRows = order
      .map(
        (s) =>
          `<li class="${s === view.game.hero ? "is-you" : ""}"><span>${escapeHtml(nameOf(s))}</span><b class="${
            deltas[s] > 0 ? "is-up" : deltas[s] < 0 ? "is-down" : ""
          }">${signed(deltas[s])}</b><span>${scoreText(after[s])}</span></li>`
      )
      .join("");
    block.innerHTML = `
      <p class="figure-label">Result</p>
      ${lines.join("")}
      <ol class="replay-deltas">${scoreRows}</ol>
    `;
    return block;
  }

  // ------------------------------------------------------------------ one game: page

  function renderGameShell(game) {
    const hero = game.hero;
    const summary = gameSummary(game);
    const place = rankText(game.placement[hero]);
    document.title = `Replay: ${dateText(game.date, false)}, ${place}`;
    const handButtons = game.hands
      .map((hand, h) => {
        const flags = (hand.ai || []).filter((d) => tierOf(d) === "flag").length;
        const title = `${hand.round}${flags ? `, ${flags} flagged` : ""}`;
        return `<button type="button" class="replay-hand-button${flags ? " has-flags" : ""}" data-hand="${h}" title="${escapeHtml(
          title
        )}" aria-label="${escapeHtml(title)}">${escapeHtml(shortRound(hand.round))}</button>`;
      })
      .join("");
    app.innerHTML = `
      <section class="replay-masthead replay-game-head">
        <p class="guide-eyebrow"><a href="replay.html">All replays</a> &#183; ${escapeHtml(game.room)} &#183; ${escapeHtml(game.players[hero].rank)}</p>
        <h1>${escapeHtml(dateText(game.date))}</h1>
        <p class="replay-game-result">You finished ${escapeHtml(place)} with ${scoreText(game.final[hero])} (${escapeHtml(signedPoints(game.points[hero]))}).</p>
        <p class="replay-masthead-note">${summary} <a href="${escapeHtml(game.source)}" target="_blank" rel="noopener noreferrer">The same game in Mahjong Soul</a>.</p>
      </section>
      <nav class="replay-hands" aria-label="Hands">${handButtons}</nav>
      <figure class="replay-figure replay-viewer" aria-label="Replay">
        <div class="replay-table">
          <div class="replay-table-host"></div>
        </div>
        <div class="replay-strip" role="group" aria-label="Your choices in this hand"></div>
        <div class="replay-jumps">
          <button type="button" class="replay-jump" data-go="prev-choice" title="Shift + Left arrow">&#x2039; Your last choice</button>
          <button type="button" class="replay-jump" data-go="next-choice" title="Shift + Right arrow">Your next choice &#x203A;</button>
          <button type="button" class="replay-jump is-flag" data-go="next-flag" title="F">Next flagged &#x203A;</button>
        </div>
        <div class="replay-panel">
          <div class="replay-panel-head">
            <span class="figure-label replay-where"></span>
            <button type="button" class="hands-toggle" aria-pressed="true">Show all hands</button>
          </div>
          <p class="replay-event"></p>
          <div class="replay-detail"></div>
        </div>
        <div class="replay-controls">
          <button type="button" class="replay-button" data-go="hand-start" aria-label="Start of the hand" title="Start of the hand">&#x23EE;</button>
          <button type="button" class="replay-button" data-go="prev" aria-label="Back one step" title="Back one step (Left arrow)">&#x25C0;</button>
          <input type="range" class="replay-slider" min="0" value="0" aria-label="Step in this hand" />
          <button type="button" class="replay-button" data-go="next" aria-label="Forward one step" title="Forward one step (Right arrow)">&#x25B6;</button>
          <button type="button" class="replay-button" data-go="hand-end" aria-label="End of the hand" title="End of the hand">&#x23ED;</button>
        </div>
      </figure>
      <section class="replay-review" aria-labelledby="replay-review-title">
        <h2 id="replay-review-title">Flagged choices in this game</h2>
        <p class="replay-review-note">Mortal is an open-source mahjong AI. These numbers come from the Mortal weights the playbook uses for its cross-checks, run over each of your games. A percentage is how often Mortal would make that play at that moment, and a flagged choice is one it gives under 5%. Use it to find turns worth a second look. The guide's chapters measure you against LuckyJ.</p>
        <ol class="replay-review-list"></ol>
      </section>
      <section class="replay-review replay-counting" aria-labelledby="replay-counting-title">
        <h2 id="replay-counting-title">Counting turns</h2>
        <p class="replay-review-note">Each name on the table carries that player's turn, counted the way the guide counts yours: one for each draw from the wall and one for each call. Once a player has cut, their turn is the tiles they have cut: their pond, six tiles to a row, plus any tile another player called out of it, which leaves the pond. A chi takes the next turn in order, but a pon or kan skips the players between the discarder and the caller, so they fall a turn behind the rest. The replay says so at each call that skips someone.</p>
      </section>
      <p class="replay-keys">Keys: <kbd>&#8592;</kbd> <kbd>&#8594;</kbd> step, <kbd>Shift</kbd> + arrows for your choices, <kbd>[</kbd> <kbd>]</kbd> for hands, <kbd>F</kbd> for the next flagged choice.</p>
    `;
    renderReviewList(game);
  }

  function gameSummary(game) {
    const hero = game.hero;
    let turns = 0;
    let turnsMatched = 0;
    let calls = 0;
    let callsMatched = 0;
    let flags = 0;
    for (const hand of game.hands) {
      for (const d of hand.ai || []) {
        const own = hand.ev[d.i][1] === hero;
        const tier = tierOf(d);
        if (own) {
          turns += 1;
          if (tier === "match") turnsMatched += 1;
        } else {
          calls += 1;
          if (tier === "match") callsMatched += 1;
        }
        if (tier === "flag") flags += 1;
      }
    }
    if (!turns) return "";
    return `You played Mortal's first choice on ${turnsMatched} of ${turns} turns (${Math.round(
      (100 * turnsMatched) / turns
    )}%) and ${callsMatched} of ${calls} call chances. ${flags ? `${flags} choice${flags === 1 ? "" : "s"} under 5% ${flags === 1 ? "is" : "are"} flagged.` : "No choice fell under 5%."}`;
  }

  function renderReviewList(game) {
    const list = app.querySelector(".replay-review-list");
    const items = [];
    game.hands.forEach((hand, h) => {
      const turns = heroTurns(hand);
      for (const d of hand.ai || []) {
        if (tierOf(d) !== "flag") continue;
        const own = hand.ev[d.i][1] === game.hero;
        const where = own ? `your turn ${turns[d.i]}` : `${nameOf(hand.ev[d.i][1])}'s ${inlineTile(hand.ev[d.i][2])}`;
        items.push(`
          <li><button type="button" class="replay-review-item" data-hand="${h}" data-event="${d.i}">
            <span class="replay-review-where">${escapeHtml(hand.round)}, ${where}</span>
            <span class="replay-review-you">You: ${actionWords(d.you, d, hand)} ${pctText(probOf(d, d.you))}</span>
            <span class="replay-review-top">Mortal: ${actionWords(d.p[0][0], d, hand)} ${pctText(d.p[0][1])}</span>
          </button></li>`);
      }
    });
    list.innerHTML = items.length ? items.join("") : '<li class="replay-review-empty">No choice in this game fell under 5%.</li>';
    applyTileCompatibility(list);
  }

  function selectHand(h, stopIndex = 0) {
    const game = view.game;
    view.hand = Math.max(0, Math.min(game.hands.length - 1, h));
    const hand = game.hands[view.hand];
    view.stops = buildStops(hand);
    view.decisions = new Map((hand.ai || []).map((d) => [d.i, d]));
    view.turns = heroTurns(hand);
    const slider = app.querySelector(".replay-slider");
    slider.max = String(view.stops.length - 1);
    for (const button of app.querySelectorAll(".replay-hand-button")) {
      const current = Number(button.dataset.hand) === view.hand;
      button.classList.toggle("is-current", current);
      if (current) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
    renderStrip(hand);
    show(stopIndex);
  }

  function renderStrip(hand) {
    const strip = app.querySelector(".replay-strip");
    const hero = view.game.hero;
    strip.innerHTML = (hand.ai || [])
      .map((d) => {
        const stopIndex = view.stops.findIndex((stop) => stop.i === d.i);
        const own = hand.ev[d.i][1] === hero;
        const tier = tierOf(d);
        const label = `${own ? `Your turn ${view.turns[d.i]}` : "Call chance"}: ${
          tier === "match" ? "Mortal's first choice" : `Mortal gives your choice ${pctText(probOf(d, d.you))}`
        }`;
        return `<button type="button" class="replay-tick tier-${tier}${own ? "" : " is-call"}" data-stop="${stopIndex}" title="${escapeHtml(
          label
        )}" aria-label="${escapeHtml(label)}"></button>`;
      })
      .join("");
  }

  function show(stopIndex) {
    const game = view.game;
    const hand = game.hands[view.hand];
    view.stop = Math.max(0, Math.min(view.stops.length - 1, stopIndex));
    const stop = view.stops[view.stop];
    const state = stateAt(hand, stop.s);

    // At the result the winning tile joins the winner's hand, set apart like a draw.
    let winTiles = null;
    if (stop.kind === "end" && hand.end.kind === "win") {
      winTiles = {};
      const lastDiscard = [...hand.ev].reverse().find((e) => e[0] === "d" || e[0] === "k");
      for (const win of hand.end.wins) {
        if (win.seat !== win.from && lastDiscard) winTiles[win.seat] = lastDiscard[2];
      }
    }

    const decision = stop.kind === "event" ? view.decisions.get(stop.i) : null;
    const table = renderMahjongTable(tableFor(hand, state, winTiles));
    markRivers(table, state);
    labelTurns(table, state);
    markHand(table, state, decision && hand.ev[stop.i][1] === game.hero ? decision : null, winTiles);
    applyTileCompatibility(table);
    app.querySelector(".replay-table-host").replaceChildren(table);

    const where = [hand.round, `${state.left} tiles left`];
    if (stop.kind === "event") {
      const actor = hand.ev[stop.i][1];
      const turn = state.turns[actor];
      if (turn) where.splice(1, 0, actor === game.hero ? `your turn ${turn}` : `${nameOf(actor)}'s turn ${turn}`);
    }
    if (state.sticks) where.push(`${state.sticks} riichi stick${state.sticks === 1 ? "" : "s"}`);
    app.querySelector(".replay-where").textContent = where.join(" · ");

    const eventLine = app.querySelector(".replay-event");
    eventLine.innerHTML = eventText(hand, stop);
    eventLine.hidden = !eventLine.innerHTML;
    const detail = app.querySelector(".replay-detail");
    const blocks = [];
    if (decision) blocks.push(mortalBlock(hand, decision));
    if (stop.kind === "end") blocks.push(resultBlock(hand));
    detail.replaceChildren(...blocks);
    applyTileCompatibility(app.querySelector(".replay-panel"));

    const slider = app.querySelector(".replay-slider");
    slider.value = String(view.stop);
    slider.setAttribute("aria-valuetext", `${hand.round}, step ${view.stop + 1} of ${view.stops.length}`);
    for (const tick of app.querySelectorAll(".replay-tick")) {
      const current = Number(tick.dataset.stop) === view.stop;
      tick.classList.toggle("is-current", current);
      if (current) tick.setAttribute("aria-current", "true");
      else tick.removeAttribute("aria-current");
    }
    app.querySelector('[data-go="prev"]').disabled = view.stop === 0 && view.hand === 0;
    app.querySelector('[data-go="next"]').disabled = view.stop === view.stops.length - 1 && view.hand === game.hands.length - 1;
    writeLocation();
  }

  function writeLocation() {
    const url = new URL(window.location.href);
    url.searchParams.set("g", view.game.id);
    url.searchParams.set("h", String(view.hand));
    url.searchParams.set("e", String(view.stops[view.stop].i));
    for (const key of ["r", "t", "at"]) url.searchParams.delete(key);
    if (url.href !== window.location.href) window.history.replaceState({}, "", url);
  }

  // ------------------------------------------------------------------ one game: moving around

  function step(delta) {
    const next = view.stop + delta;
    if (next < 0) {
      if (view.hand > 0) selectHand(view.hand - 1, Infinity);
      return;
    }
    if (next >= view.stops.length) {
      if (view.hand < view.game.hands.length - 1) selectHand(view.hand + 1, 0);
      return;
    }
    show(next);
  }

  // Your choices: every decision on your turn, plus the call chances where you and Mortal differed.
  function choiceStops(hand, stops) {
    const decisions = new Map((hand.ai || []).map((d) => [d.i, d]));
    return stops
      .map((stop, n) => {
        const d = stop.kind === "event" ? decisions.get(stop.i) : null;
        const counts = d && (hand.ev[stop.i][1] === view.game.hero || tierOf(d) !== "match");
        return counts ? n : -1;
      })
      .filter((n) => n >= 0);
  }

  function jumpChoice(direction) {
    const game = view.game;
    let h = view.hand;
    let from = view.stop;
    while (h >= 0 && h < game.hands.length) {
      const hand = game.hands[h];
      const indices = choiceStops(hand, h === view.hand ? view.stops : buildStops(hand));
      const target = direction > 0 ? indices.find((n) => n > from) : [...indices].reverse().find((n) => n < from);
      if (target !== undefined) {
        if (h === view.hand) show(target);
        else selectHand(h, target);
        return;
      }
      h += direction;
      from = direction > 0 ? -1 : Infinity;
    }
  }

  function jumpFlag() {
    const game = view.game;
    const current = view.stops[view.stop].i;
    for (let k = 0; k < game.hands.length; k += 1) {
      const h = (view.hand + k) % game.hands.length;
      const hand = game.hands[h];
      const flags = (hand.ai || []).filter((d) => tierOf(d) === "flag" && (k > 0 || d.i > current));
      if (flags.length) {
        goToEvent(h, flags[0].i);
        return;
      }
    }
    // Wrap to the first flag of the current hand.
    const first = (game.hands[view.hand].ai || []).find((d) => tierOf(d) === "flag");
    if (first) goToEvent(view.hand, first.i);
  }

  function goToEvent(h, i) {
    const stops = buildStops(view.game.hands[h]);
    const index = Math.max(0, stops.findIndex((stop) => stop.i === i));
    if (h === view.hand) show(index);
    else selectHand(h, index);
  }

  function bindControls() {
    app.addEventListener("click", (event) => {
      const go = event.target.closest("[data-go]");
      if (go) {
        const action = go.dataset.go;
        if (action === "prev") step(-1);
        else if (action === "next") step(1);
        else if (action === "hand-start") show(0);
        else if (action === "hand-end") show(view.stops.length - 1);
        else if (action === "prev-choice") jumpChoice(-1);
        else if (action === "next-choice") jumpChoice(1);
        else if (action === "next-flag") jumpFlag();
        return;
      }
      const handButton = event.target.closest(".replay-hand-button");
      if (handButton) {
        selectHand(Number(handButton.dataset.hand), 0);
        return;
      }
      const tick = event.target.closest(".replay-tick");
      if (tick) {
        show(Number(tick.dataset.stop));
        return;
      }
      const item = event.target.closest(".replay-review-item");
      if (item) {
        goToEvent(Number(item.dataset.hand), Number(item.dataset.event));
        app.querySelector(".replay-viewer").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    app.querySelector(".replay-slider").addEventListener("input", (event) => show(Number(event.target.value)));
    document.addEventListener("keydown", (event) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      // Form fields keep their keys; the slider moves itself and reports through its input event.
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest("input, textarea, select, [contenteditable]")) return;
      const keys = {
        ArrowLeft: () => (event.shiftKey ? jumpChoice(-1) : step(-1)),
        ArrowRight: () => (event.shiftKey ? jumpChoice(1) : step(1)),
        "[": () => selectHand(view.hand - 1, 0),
        "]": () => selectHand(view.hand + 1, 0),
        f: () => jumpFlag(),
        F: () => jumpFlag(),
      };
      const run = keys[event.key];
      if (!run) return;
      event.preventDefault();
      run();
    });
  }

  function setupHandToggle() {
    let hidden = false;
    try {
      hidden = localStorage.getItem(hideHandsKey) === "1";
    } catch {
      hidden = false;
    }
    const apply = (visible) => {
      document.body.classList.toggle("conceal-hands", !visible);
      for (const button of app.querySelectorAll(".hands-toggle")) button.setAttribute("aria-pressed", visible ? "true" : "false");
    };
    apply(!hidden);
    app.addEventListener("click", (event) => {
      if (!event.target.closest(".hands-toggle")) return;
      const visible = document.body.classList.contains("conceal-hands");
      apply(visible);
      try {
        localStorage.setItem(hideHandsKey, visible ? "0" : "1");
      } catch {
        /* storage unavailable: the choice lasts for this visit */
      }
    });
  }

  function startPosition(game, params) {
    let h = Number.parseInt(params.get("h"), 10);
    const round = params.get("r");
    if (round) {
      const found = game.hands.findIndex((hand) => hand.round === round || shortRound(hand.round) === round);
      if (found >= 0) h = found;
    }
    if (!Number.isInteger(h) || h < 0 || h >= game.hands.length) h = 0;
    return h;
  }

  async function renderGame(id, params) {
    let game;
    try {
      game = await loadJson(`replays/${id}.json`);
    } catch (error) {
      app.innerHTML = `<section class="replay-masthead"><h1>Replay not found.</h1><p class="standfirst">This game could not load (${escapeHtml(
        error.message
      )}). <a href="replay.html">All replays</a>.</p></section>`;
      return;
    }
    view.game = game;
    renderGameShell(game);
    setupHandToggle();
    bindControls();
    const h = startPosition(game, params);
    selectHand(h, 0);
    const turn = Number.parseInt(params.get("t"), 10);
    const event = Number.parseInt(params.get("e"), 10);
    if (Number.isInteger(turn) && turn > 0) show(stopForTurn(game.hands[h], turn, params.get("at") === "call"));
    else if (Number.isInteger(event)) show(Math.max(0, view.stops.findIndex((stop) => stop.i === event)));
    applyTileCompatibility(app);
    // A link to a hand (the guide's, or a reloaded step) opens with the table in view.
    if (params.has("r") || params.has("h")) app.querySelector(".replay-hands").scrollIntoView({ block: "start" });
  }

  async function main() {
    renderCommitStamp();
    setupRetractingTopbar();
    setupRunningHead();
    const params = new URLSearchParams(window.location.search);
    const id = params.get("g") || "";
    if (/^[0-9a-f-]{8,64}$/.test(id)) {
      await renderGame(id, params);
      return;
    }
    try {
      renderList(await loadJson("replays/index.json"));
    } catch (error) {
      app.innerHTML = `<p class="guide-error">The list of games could not load (${escapeHtml(error.message)}).</p>`;
    }
    applyTileCompatibility(app);
  }

  main();
})();
