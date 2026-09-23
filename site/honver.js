/*
 * Honver's Playbook: renders the turns in honver-guide.json.
 *
 * The page loads app.js first (with data-app="table-only" on <body>) and reuses its tile
 * and table renderers: renderMahjongTable, tileIcon, tileName, richText, escapeHtml,
 * roundText, rankText, applyTileCompatibility, convertStaticTileMarkup, renderCommitStamp
 * and setupRetractingTopbar.
 */
(function () {
  const guideAsset = "honver-guide.json?v=20260923-guide-5";
  const hideHandsKey = "luckyj:honver-guide:hide-hands";
  const SAFETY_CLASS = {
    genbutsu: "safe",
    dead: "safe",
    suji: "mostly",
    nakasuji: "mostly",
    "honor, 2 seen": "mostly",
    "virtual nakasuji": "live",
    "half suji": "danger",
    "live honor": "live",
    "live terminal": "live",
    "live 2-3-7-8": "danger",
    "live 4-5-6": "danger",
  };
  const SAFETY_TEXT = {
    genbutsu: "genbutsu",
    dead: "dead honor",
    suji: "suji",
    nakasuji: "nakasuji",
    "virtual nakasuji": "virtual nakasuji",
    "half suji": "half suji",
    "honor, 2 seen": "honor, 2 others seen",
    "live honor": "live honor",
    "live terminal": "live terminal",
    "live 2-3-7-8": "live 2-3-7-8",
    "live 4-5-6": "live 4-5-6",
  };
  const REL = { self: "You", shimocha: "Shimocha", toimen: "Toimen", kamicha: "Kamicha" };
  const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

  function shantenText(s) {
    return s === 0 ? "tenpai" : `${s}-shanten`;
  }

  function acceptText(option) {
    if (option.shanten === 0) {
      const waits = (option.waits || []).map((w) => tileIcon(w, "inline-tile")).join("");
      return `${option.accept} live tile${option.accept === 1 ? "" : "s"}${waits ? ` on ${waits}` : ""}`;
    }
    return `${option.accept} tiles improve it`;
  }

  function safetyChip(label) {
    if (!label) return "";
    return `<i class="safety-chip ${SAFETY_CLASS[label] || ""}">${escapeHtml(SAFETY_TEXT[label] || label)}</i>`;
  }

  function safetyLines(option, threats) {
    if (!threats?.length) return "";
    return `<span class="guide-safety">${threats
      .map((threat, i) => `<span>vs ${escapeHtml(threat.label)}: ${safetyChip(option.safety?.[i])}</span>`)
      .join("")}</span>`;
  }

  function decisionBlock(kind, title, option, frame, extra = "") {
    const tile = option?.tile;
    const action =
      frame.kind === "riichi"
        ? `${option.action === "riichi" ? "Riichi" : "Dama"}, cut ${tileIcon(tile, "discard-tile")}`
        : `Cut ${tileIcon(tile, "discard-tile")} <em>${escapeHtml(tileName(tile))}</em>`;
    return `
      <div class="decision guide-${kind}">
        <b>${escapeHtml(title)}</b>
        <span class="discard-line">${action}</span>
        <span>Leaves ${shantenText(option.shanten)}, ${acceptText(option)}</span>
        ${frame.kind === "riichi" ? "" : safetyLines(option, frame.threats)}
        ${extra}
      </div>
    `;
  }

  function comparisonBlock(frame) {
    const wrap = document.createElement("div");
    wrap.className = "comparison guide-comparison";
    if (frame.kind === "riichi") {
      const yakuNote = frame.ron_yaku_without_riichi
        ? "Has a yaku without riichi, so dama can ron."
        : "No yaku without riichi: dama can only win by tsumo.";
      wrap.innerHTML =
        decisionBlock("you", "You", frame.you, frame, `<small>${escapeHtml(yakuNote)}</small>`) +
        decisionBlock("better", "Better", frame.better, frame, "<small>Same tile, declared.</small>");
      return wrap;
    }
    const you = decisionBlock(
      "you",
      frame.you.tsumogiri ? "You (cut the tile you drew)" : "You",
      frame.you,
      frame
    );
    const better = frame.better ? decisionBlock("better", "Better", frame.better, frame) : "";
    wrap.innerHTML = you + better;
    return wrap;
  }

  function optionsBlock(frame) {
    if (!frame.options?.length) return null;
    const details = document.createElement("details");
    details.className = "guide-options";
    const threatHeads = (frame.threats || []).map((t) => `<th scope="col">vs ${escapeHtml(t.label)}</th>`).join("");
    const rows = frame.options
      .map((option) => {
        const classes = [
          option.tile === frame.you?.tile ? "is-you" : "",
          frame.better && option.tile === frame.better.tile ? "is-better" : "",
        ]
          .filter(Boolean)
          .join(" ");
        const tag =
          option.tile === frame.you?.tile ? "<small>you</small>" : frame.better && option.tile === frame.better.tile ? "<small>better</small>" : "";
        const safety = (frame.threats || []).map((_, i) => `<td>${safetyChip(option.safety?.[i])}</td>`).join("");
        return `<tr class="${classes}"><th scope="row">${tileIcon(option.tile, "inline-tile")}${tag}</th><td>${shantenText(
          option.shanten
        )}</td><td>${acceptText(option)}</td>${safety}</tr>`;
      })
      .join("");
    details.innerHTML = `
      <summary>Every discard from this hand</summary>
      <div class="guide-options-scroll">
        <table>
          <thead><tr><th scope="col">Cut</th><th scope="col">Leaves</th><th scope="col">Acceptance</th>${threatHeads}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="guide-options-note">Acceptance counts the unseen copies of every tile that would improve the hand, from what you could see at the table. At tenpai it counts live winning tiles, before yaku.</p>
    `;
    return details;
  }

  function markHand(tableWrap, frame) {
    const cells = tableWrap.querySelectorAll(".player-hand.player-current .tile-threat-cell");
    if (!cells.length) return;
    if (frame.drawn) cells[cells.length - 1].classList.add("guide-drawn");
    if (frame.kind === "riichi") {
      cells[frame.cut_index]?.classList.add("guide-better", "guide-riichi");
      return;
    }
    if (Number.isInteger(frame.cut_index)) cells[frame.cut_index]?.classList.add("guide-cut");
    if (Number.isInteger(frame.better_index) && frame.better_index !== frame.cut_index) {
      cells[frame.better_index]?.classList.add("guide-better");
    }
  }

  function resultText(example) {
    const r = example.result || {};
    if (r.draw || !r.wins?.length) return `Hand ended in a draw. Your score for the hand: ${signed(r.hero_delta)}.`;
    const parts = r.wins.map((win) => {
      const who = win.winner === "self" ? "You" : REL[win.winner];
      const how = win.tsumo ? "by tsumo" : `by ron off ${win.from === "self" ? "you" : REL[win.from]}`;
      const yaku = win.yaku?.length ? ` (${win.yaku.join(", ")})` : "";
      return `${who} won ${how}, ${whole.format(win.points)}${yaku}.`;
    });
    return `${parts.join(" ")} Your score for the hand: ${signed(r.hero_delta)}.`;
  }

  function signed(n) {
    const v = Number(n) || 0;
    return v > 0 ? `+${whole.format(v)}` : v < 0 ? `−${whole.format(-v)}` : "0";
  }

  function analysisStep(title, text) {
    if (!text) return null;
    const section = document.createElement("section");
    section.className = "analysis-step";
    const heading = document.createElement("h5");
    heading.textContent = title;
    const para = document.createElement("p");
    para.append(richText(text));
    section.append(heading, para);
    return section;
  }

  function placementText(n) {
    return rankText(n) ? `finished ${rankText(n)}` : "";
  }

  function renderFrame(host, noteHost, example, frame) {
    const table = renderMahjongTable(frame.table);
    markHand(table, frame);
    const parts = [table, comparisonBlock(frame)];
    const options = optionsBlock(frame);
    if (options) parts.push(options);
    host.replaceChildren(...parts);
    noteHost.replaceChildren();
    const note = analysisStep(`Turn ${frame.turn}`, frame.note);
    if (note) {
      note.classList.add("guide-frame-note");
      noteHost.append(note);
    }
    applyTileCompatibility(host);
    applyTileCompatibility(noteHost);
  }

  // Cards that are not mistakes carry a verdict label, and their last step is "The verdict".
  const VERDICT_LABELS = { fine: "No mistake", unlucky: "Bad luck", close: "Close call" };

  function renderCard(example, index, total) {
    const card = document.createElement("article");
    card.className = "point-example-card guide-card";
    card.id = `guide-${example.id}`;
    const first = example.frames[0];
    const game = example.game || {};
    card.innerHTML = `
      <div class="example-head">
        <div>
          <p class="kicker">Your turn ${index + 1}/${total}</p>
          <h4>${escapeHtml(example.title)}</h4>
          ${VERDICT_LABELS[example.verdict] ? `<p class="guide-verdict">${escapeHtml(VERDICT_LABELS[example.verdict])}</p>` : ""}
        </div>
        <span>${escapeHtml(roundText(example.round))}, turn ${first.turn}, ${first.left} tiles left<small class="guide-game">${escapeHtml(
          game.date || ""
        )}, ${escapeHtml(placementText(game.placement))}</small></span>
      </div>
    `;
    const layout = document.createElement("div");
    layout.className = "point-example-layout";
    const replay = document.createElement("div");
    replay.className = "point-example-replay";
    const explanation = document.createElement("div");
    explanation.className = "point-example-explanation";
    const frameHost = document.createElement("div");
    const noteHost = document.createElement("div");

    if (example.frames.length > 1) {
      const strip = document.createElement("div");
      strip.className = "guide-frame-tabs";
      strip.setAttribute("role", "tablist");
      strip.setAttribute("aria-label", "Turns in this hand");
      const buttons = example.frames.map((frame, i) => {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "tab");
        button.textContent = `Turn ${frame.turn}`;
        button.addEventListener("click", () => select(i));
        strip.append(button);
        return button;
      });
      function select(i) {
        buttons.forEach((b, j) => {
          b.classList.toggle("active", i === j);
          b.setAttribute("aria-selected", i === j ? "true" : "false");
        });
        renderFrame(frameHost, noteHost, example, example.frames[i]);
      }
      replay.append(strip, frameHost);
      select(0);
    } else {
      replay.append(frameHost);
      renderFrame(frameHost, noteHost, example, first);
    }

    const analysis = document.createElement("div");
    analysis.className = "natsu-analysis";
    const steps = [
      analysisStep("Situation", example.text.situation),
      noteHost,
      analysisStep("What you did", example.text.did),
      analysisStep("What LuckyJ does", example.text.luckyj),
      analysisStep(VERDICT_LABELS[example.verdict] ? "The verdict" : "The fix", example.text.fix),
    ].filter(Boolean);
    analysis.append(...steps);
    const result = document.createElement("p");
    result.className = "guide-result";
    result.innerHTML = `<b>How the hand ended:</b> ${escapeHtml(resultText(example))}`;
    const links = document.createElement("p");
    links.className = "case-links";
    if (game.url) {
      links.innerHTML = `<a href="${escapeHtml(game.url)}" target="_blank" rel="noopener noreferrer">Open the game in Mahjong Soul</a>`;
    }
    explanation.append(analysis, result, links);
    layout.append(replay, explanation);
    card.append(layout);
    return card;
  }

  function renderChapter(placeholder, examples) {
    const shell = document.createElement("div");
    shell.className = "point-example-tabs";
    const tablist = document.createElement("div");
    tablist.className = "example-tab-list";
    tablist.setAttribute("role", "tablist");
    const body = document.createElement("div");
    body.className = "example-tab-body";
    const buttons = examples.map((example, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.dataset.index = String(index);
      button.innerHTML = `<b>${index + 1}</b><span>${escapeHtml(roundText(example.round).replace(/-\d+$/, ""))}</span>`;
      button.title = example.title;
      tablist.append(button);
      return button;
    });
    function show(index) {
      buttons.forEach((button, i) => {
        button.classList.toggle("active", i === index);
        button.setAttribute("aria-selected", i === index ? "true" : "false");
        button.tabIndex = i === index ? 0 : -1;
      });
      body.replaceChildren(renderCard(examples[index], index, examples.length));
    }
    tablist.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-index]");
      if (button) show(Number(button.dataset.index));
    });
    tablist.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const current = buttons.findIndex((b) => b.classList.contains("active"));
      const next = (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
      show(next);
      buttons[next].focus();
    });
    shell.append(tablist, body);
    placeholder.replaceChildren(shell);
    const wanted = decodeURIComponent(location.hash.replace(/^#guide-/, ""));
    const start = Math.max(0, examples.findIndex((e) => e.id === wanted));
    show(start);
    return start > 0 || examples[0]?.id === wanted;
  }

  function setupHandToggle() {
    const toggle = document.querySelector("#showOpponentHands");
    if (!toggle) return;
    let hidden = false;
    try {
      hidden = localStorage.getItem(hideHandsKey) === "1";
    } catch {
      hidden = false;
    }
    toggle.checked = !hidden;
    document.body.classList.toggle("hide-opponent-hands", hidden);
    toggle.addEventListener("change", () => {
      document.body.classList.toggle("hide-opponent-hands", !toggle.checked);
      try {
        localStorage.setItem(hideHandsKey, toggle.checked ? "0" : "1");
      } catch {
        /* storage unavailable: the choice lasts for this visit */
      }
    });
  }

  async function main() {
    renderCommitStamp();
    setupRetractingTopbar();
    convertStaticTileMarkup();
    applyTileCompatibility();
    setupHandToggle();
    let data;
    try {
      const response = await fetch(guideAsset);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
    } catch (error) {
      for (const placeholder of document.querySelectorAll("[data-guide-examples]")) {
        placeholder.innerHTML = `<p class="guide-error">The example tables could not load (${escapeHtml(error.message)}).</p>`;
      }
      return;
    }
    let targetFound = false;
    for (const placeholder of document.querySelectorAll("[data-guide-examples]")) {
      const examples = data.chapters?.[placeholder.dataset.guideExamples] || [];
      if (!examples.length) continue;
      if (renderChapter(placeholder, examples)) targetFound = true;
    }
    if (targetFound) document.querySelector(location.hash)?.scrollIntoView({ block: "start" });
  }

  main();
})();
