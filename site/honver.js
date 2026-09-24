/*
 * Honver's Playbook: renders the turns in honver-guide.json.
 *
 * The page loads app.js first (with data-app="table-only" on <body>) and reuses its tile
 * and table renderers: renderMahjongTable, tileIcon, tileName, richText, escapeHtml,
 * roundText, rankText, applyTileCompatibility, convertStaticTileMarkup, renderCommitStamp,
 * setupRetractingTopbar and setupRunningHead.
 *
 * Each turn is a felt figure: the table, then a panel with the situation and your line against
 * the better one; the commentary and every discard of the hand follow on paper.
 */
(function () {
  const guideAsset = "honver-guide.json?v=20260924-guide-7";
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

  // A call frame shows the hand before the call: what the call left, against passing.
  function callBlocks(frame) {
    const you = frame.you;
    const action = you.action ? you.action[0].toUpperCase() + you.action.slice(1) : "Call";
    const meld = (you.meld || []).map((t) => tileIcon(t, "inline-tile")).join("");
    const from = REL[frame.call_from] || frame.call_from || "";
    return `
      <div class="decision guide-you">
        <b>You</b>
        <span class="discard-line">${escapeHtml(action)} ${tileIcon(you.tile, "discard-tile")} <em>off ${escapeHtml(from)}</em></span>
        <span>Meld ${meld}, then cut ${tileIcon(you.then_cut, "inline-tile")}</span>
        <span>Leaves ${shantenText(you.shanten)}, open</span>
      </div>
      <div class="decision guide-better">
        <b>Better</b>
        <span class="discard-line">Pass</span>
        <span>Stays ${shantenText(frame.better.shanten)} and closed, ${frame.better.accept} tiles improve it</span>
      </div>
    `;
  }

  function comparisonBlock(frame) {
    const wrap = document.createElement("div");
    wrap.className = "comparison guide-comparison";
    if (frame.kind === "call") {
      wrap.innerHTML = callBlocks(frame);
      return wrap;
    }
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
      const cell = cells[frame.cut_index];
      if (cell) {
        cell.classList.add("guide-better", "guide-riichi");
        cell.dataset.mark = "Riichi";
      }
      return;
    }
    const cut = Number.isInteger(frame.cut_index) ? cells[frame.cut_index] : null;
    if (cut) {
      cut.classList.add("guide-cut");
      cut.dataset.mark = "Your cut";
    }
    if (Number.isInteger(frame.better_index) && frame.better_index !== frame.cut_index) {
      const better = cells[frame.better_index];
      if (better) {
        better.classList.add("guide-better");
        better.dataset.mark = "Better";
      }
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

  function renderFrame(hosts, example, frame) {
    const table = renderMahjongTable(frame.table);
    markHand(table, frame);
    hosts.table.replaceChildren(table);
    hosts.compare.replaceChildren(comparisonBlock(frame));
    const options = optionsBlock(frame);
    hosts.options.replaceChildren(...(options ? [options] : []));
    hosts.note.replaceChildren();
    const note = analysisStep(`Turn ${frame.turn}`, frame.note);
    if (note) {
      note.classList.add("guide-frame-note");
      hosts.note.append(note);
    }
    for (const host of Object.values(hosts)) applyTileCompatibility(host);
  }

  // "8-tile" and "3-han" stay on one line in titles.
  function keepNumberHyphens(text) {
    return String(text || "").replace(/(\d)-(?=\p{L})/gu, "$1\u2011");
  }

  // Cards that are not mistakes carry a verdict label, and their last step is "The verdict".
  const VERDICT_LABELS = { fine: "No mistake", unlucky: "Bad luck", close: "Close call" };

  function renderCard(example, index, total) {
    const card = document.createElement("article");
    card.className = "point-example-card guide-card";
    card.id = `guide-${example.id}`;
    const first = example.frames[0];
    const game = example.game || {};
    const verdict = VERDICT_LABELS[example.verdict];
    const label = `Your turn ${index + 1} of ${total}`;
    const meta = [
      roundText(example.round),
      `turn ${first.turn}`,
      `${first.left} tile${first.left === 1 ? "" : "s"} left`,
      [game.date, placementText(game.placement)].filter(Boolean).join(", "),
    ]
      .filter(Boolean)
      .map(escapeHtml)
      .join(" &#183; ");
    card.innerHTML = `
      <figure class="replay-figure" aria-label="${escapeHtml(label)}">
        <div class="replay-table">
          <div class="guide-frame-host"></div>
          <div class="guide-table-host"></div>
        </div>
        <div class="replay-panel">
          <div class="replay-panel-head">
            <span class="figure-label">${escapeHtml(label)}</span>
            ${handsToggleHtml()}
          </div>
          <h4 class="guide-card-title">${escapeHtml(keepNumberHyphens(example.title))}</h4>
          ${verdict ? `<p class="guide-verdict">${escapeHtml(verdict)}</p>` : ""}
          <p class="guide-card-meta">${meta}</p>
          <p class="guide-situation"></p>
          <div class="guide-compare-host"></div>
          ${
            game.url
              ? `<p class="guide-game-link"><a href="${escapeHtml(game.url)}" target="_blank" rel="noopener noreferrer">Open the game in Mahjong Soul</a></p>`
              : ""
          }
        </div>
      </figure>
      <div class="replay-notes"></div>
    `;
    card.querySelector(".guide-situation").append(richText(example.text.situation || ""));
    const hosts = {
      table: card.querySelector(".guide-table-host"),
      compare: card.querySelector(".guide-compare-host"),
      options: document.createElement("div"),
      note: document.createElement("div"),
    };
    hosts.options.className = "guide-options-host";
    hosts.note.className = "guide-note-host";

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
        renderFrame(hosts, example, example.frames[i]);
      }
      card.querySelector(".guide-frame-host").append(strip);
      select(0);
    } else {
      renderFrame(hosts, example, first);
    }

    const notes = card.querySelector(".replay-notes");
    const analysis = document.createElement("div");
    analysis.className = "natsu-analysis";
    const steps = [
      analysisStep("What you did", example.text.did),
      analysisStep("What LuckyJ does", example.text.luckyj),
      analysisStep(verdict ? "The verdict" : "The fix", example.text.fix),
    ].filter(Boolean);
    analysis.append(...steps);
    const result = document.createElement("p");
    result.className = "guide-result";
    result.innerHTML = `<b>How the hand ended</b> ${escapeHtml(resultText(example))}`;
    notes.append(hosts.note, analysis, result, hosts.options);
    applyTileCompatibility(card);
    return card;
  }

  function renderChapter(placeholder, examples) {
    const shell = document.createElement("div");
    shell.className = "point-example-tabs";
    const head = document.createElement("div");
    head.className = "example-tab-head";
    head.innerHTML = `<p class="label">Your turns</p><div class="example-tab-heading"><h4>${
      examples.length === 1 ? "A turn from your games" : "Turns from your games"
    }</h4></div>`;
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
    head.append(tablist);
    shell.append(head, body);
    placeholder.replaceChildren(shell);
    const wanted = decodeURIComponent(location.hash.replace(/^#guide-/, ""));
    const start = Math.max(0, examples.findIndex((e) => e.id === wanted));
    show(start);
  }

  // Opponents' hands: the checkbox under "Reading the tables" and the button on each figure are one
  // switch, remembered between visits.
  function handsVisible() {
    return !document.body.classList.contains("conceal-hands");
  }

  function handsToggleHtml() {
    return `<button type="button" class="hands-toggle" aria-pressed="${handsVisible() ? "true" : "false"}">Show all hands</button>`;
  }

  function setHandsVisible(visible) {
    document.body.classList.toggle("conceal-hands", !visible);
    const checkbox = document.querySelector("#showOpponentHands");
    if (checkbox) checkbox.checked = visible;
    for (const button of document.querySelectorAll(".hands-toggle")) {
      button.setAttribute("aria-pressed", visible ? "true" : "false");
    }
    try {
      localStorage.setItem(hideHandsKey, visible ? "0" : "1");
    } catch {
      /* storage unavailable: the choice lasts for this visit */
    }
  }

  function setupHandToggle() {
    let hidden = false;
    try {
      hidden = localStorage.getItem(hideHandsKey) === "1";
    } catch {
      hidden = false;
    }
    document.body.classList.toggle("conceal-hands", hidden);
    const checkbox = document.querySelector("#showOpponentHands");
    if (checkbox) {
      checkbox.checked = !hidden;
      checkbox.addEventListener("change", () => setHandsVisible(checkbox.checked));
    }
    document.addEventListener("click", (event) => {
      const button = event.target.closest(".hands-toggle");
      if (button) setHandsVisible(!handsVisible());
    });
  }

  // Chapter tables marked data-chart get a pair of small line charts above them: your rate against
  // LuckyJ's across the rows. The table stays as the exact numbers, folded under the charts.
  const CHARTS = {
    "dora-deal": {
      caption: "Your win rate stays flat as the dora in the deal go up; LuckyJ's climbs.",
      short: ["None", "One", "Two", "Three+"],
      panels: [
        { title: "Win rate", sub: "Hands won, by dora and red fives in the deal", you: 1, lj: 2, min: 15, max: 35, ticks: [15, 20, 25, 30, 35], unit: "%" },
        { title: "Mangan per 100 hands", sub: "Wins of mangan or more, per 100 hands dealt", you: 3, lj: 4, min: 0, max: 25, ticks: [0, 5, 10, 15, 20, 25], unit: "" },
      ],
      // The three-dora row holds 14 of your hands, which the chapter calls noise.
      noiseRow: 3,
      noiseNote: "14 hands, noise",
    },
  };
  const SVG_NS = "http://www.w3.org/2000/svg";

  function svgEl(name, attrs = {}, text = "") {
    const el = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
    if (text) el.textContent = text;
    return el;
  }

  function chartValue(cell) {
    const number = Number.parseFloat(String(cell?.textContent || "").replace(/[^0-9.\-]/g, ""));
    return Number.isFinite(number) ? number : null;
  }

  function linePanel(spec, panel, rows) {
    const W = 460;
    const H = 290;
    const m = { l: 44, r: 92, t: 14, b: 40 };
    const pw = W - m.l - m.r;
    const ph = H - m.t - m.b;
    const x = (i) => m.l + (pw * i) / (rows.length - 1);
    const y = (v) => m.t + ph * (1 - (v - panel.min) / (panel.max - panel.min));
    const fmt = (v) => (panel.unit === "%" ? `${v.toFixed(1)}%` : v.toFixed(1));
    const you = rows.map((r) => r.values[panel.you]);
    const lj = rows.map((r) => r.values[panel.lj]);

    const wrap = document.createElement("div");
    wrap.className = "guide-chart-panel";
    const head = document.createElement("div");
    head.className = "guide-chart-head";
    head.innerHTML = `<b>${escapeHtml(panel.title)}</b><span>${escapeHtml(panel.sub)}</span>`;
    const plot = document.createElement("div");
    plot.className = "guide-chart-plot";
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${panel.title}, you against LuckyJ, by dora in the deal` });
    for (const tick of panel.ticks) {
      svg.append(svgEl("line", { x1: m.l, x2: m.l + pw, y1: y(tick), y2: y(tick), class: "grid" }));
      svg.append(svgEl("text", { x: m.l - 10, y: y(tick) + 4, class: "tick" }, `${tick}${panel.unit}`));
    }
    rows.forEach((_, i) => svg.append(svgEl("text", { x: x(i), y: m.t + ph + 24, class: "cat" }, spec.short[i] || rows[i].label)));
    const cross = svgEl("line", { x1: 0, x2: 0, y1: m.t, y2: m.t + ph, class: "cross" });
    svg.append(cross);
    const series = [
      { key: "lj", values: lj, name: "LuckyJ" },
      { key: "you", values: you, name: "You" },
    ];
    for (const line of series) {
      svg.append(svgEl("polyline", { points: line.values.map((v, i) => `${x(i)},${y(v)}`).join(" "), class: `line ${line.key}` }));
      line.values.forEach((v, i) => {
        const hollow = line.key === "you" && i === spec.noiseRow;
        svg.append(svgEl("circle", { cx: x(i), cy: y(v), r: hollow ? 4 : 4.5, class: `dot ${line.key}${hollow ? " hollow" : ""}` }));
      });
      const last = line.values.length - 1;
      svg.append(svgEl("text", { x: x(last) + 12, y: y(line.values[last]) + 4, class: "end" }, `${line.name} ${fmt(line.values[last])}`));
      if (line.key === "you" && spec.noiseNote) {
        svg.append(svgEl("text", { x: x(last) + 12, y: y(line.values[last]) + 19, class: "note" }, spec.noiseNote));
      }
    }
    const tip = document.createElement("div");
    tip.className = "guide-chart-tip";
    tip.hidden = true;
    plot.append(svg, tip);
    // one hit column per category: hover or focus shows both values at that point
    rows.forEach((row, i) => {
      const left = i === 0 ? m.l - 20 : (x(i - 1) + x(i)) / 2;
      const right = i === rows.length - 1 ? x(i) + 30 : (x(i) + x(i + 1)) / 2;
      const hit = svgEl("rect", {
        x: left,
        y: m.t,
        width: right - left,
        height: ph + 30,
        class: "hit",
        tabindex: 0,
        "aria-label": `${row.label}: you ${fmt(you[i])}, LuckyJ ${fmt(lj[i])}`,
      });
      const show = () => {
        cross.setAttribute("x1", x(i));
        cross.setAttribute("x2", x(i));
        cross.classList.add("is-on");
        tip.hidden = false;
        tip.innerHTML = `<span>${escapeHtml(row.label)} dora in the deal</span><b class="you">${fmt(you[i])} <small>you</small></b><b class="lj">${fmt(lj[i])} <small>LuckyJ</small></b>`;
        const px = (x(i) / W) * 100;
        tip.style.left = i === rows.length - 1 ? "auto" : `calc(${px}% + 12px)`;
        tip.style.right = i === rows.length - 1 ? `calc(${100 - px}% + 12px)` : "auto";
      };
      const hide = () => {
        cross.classList.remove("is-on");
        tip.hidden = true;
      };
      hit.addEventListener("pointerenter", show);
      hit.addEventListener("focus", show);
      hit.addEventListener("pointerleave", hide);
      hit.addEventListener("blur", hide);
      svg.append(hit);
    });
    wrap.append(head, plot);
    return wrap;
  }

  function renderGuideChart(table) {
    const spec = CHARTS[table.dataset.chart];
    if (!spec || table.dataset.charted) return;
    table.dataset.charted = "1";
    const rows = Array.from(table.tBodies[0]?.rows || []).map((tr) => ({
      label: tr.cells[0]?.textContent.trim() || "",
      values: Array.from(tr.cells).map(chartValue),
    }));
    if (rows.length < 2 || rows.some((r) => spec.panels.some((p) => r.values[p.you] == null || r.values[p.lj] == null))) return;
    const figure = document.createElement("figure");
    figure.className = "guide-chart";
    const legend = document.createElement("div");
    legend.className = "guide-chart-legend";
    legend.innerHTML = `<span class="key you">You, 80 games</span><span class="key lj">LuckyJ, 1,255 games</span>${
      spec.noiseNote ? '<span class="key hollow">too few hands to read</span>' : ""
    }`;
    const panels = document.createElement("div");
    panels.className = "guide-chart-panels";
    for (const panel of spec.panels) panels.append(linePanel(spec, panel, rows));
    const caption = document.createElement("figcaption");
    caption.textContent = spec.caption;
    figure.append(legend, panels, caption);
    const scroll = table.closest(".guide-data-scroll") || table;
    const details = document.createElement("details");
    details.className = "guide-chart-table";
    const summary = document.createElement("summary");
    summary.textContent = "The numbers as a table";
    scroll.replaceWith(details);
    details.append(summary, scroll);
    details.before(figure);
  }

  async function main() {
    renderCommitStamp();
    setupRetractingTopbar();
    setupRunningHead();
    convertStaticTileMarkup();
    applyTileCompatibility();
    setupHandToggle();
    for (const table of document.querySelectorAll("table.guide-data[data-chart]")) renderGuideChart(table);
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
    for (const placeholder of document.querySelectorAll("[data-guide-examples]")) {
      const examples = data.chapters?.[placeholder.dataset.guideExamples] || [];
      if (!examples.length) continue;
      renderChapter(placeholder, examples);
    }
    returnToAnchor();
  }

  // The browser jumps to a link's anchor before the example tables load, and the tables then add
  // height above most chapters, so the page has to go to the anchor again once they are in place
  // (and once the web fonts have loaded: app.js's settleHashScroll waits for both).
  function returnToAnchor() {
    settleHashScroll();
  }

  main();
})();
