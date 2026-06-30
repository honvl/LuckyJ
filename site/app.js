const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const pct = (v) => `${fmt.format(v * 100)}%`;
const useOtfTiles = /Chrome|Opera|OPE|MSIE/.test(navigator.userAgent);
const tileCodes = {
  "1m": "q",
  "2m": "w",
  "3m": "e",
  "4m": "r",
  "5m": "t",
  "5mr": "t",
  "6m": "y",
  "7m": "u",
  "8m": "i",
  "9m": "o",
  "1s": "a",
  "2s": "s",
  "3s": "d",
  "4s": "f",
  "5s": "g",
  "5sr": "g",
  "6s": "h",
  "7s": "j",
  "8s": "k",
  "9s": "l",
  "1p": "z",
  "2p": "x",
  "3p": "c",
  "4p": "v",
  "5p": "b",
  "5pr": "b",
  "6p": "n",
  "7p": "m",
  "8p": ",",
  "9p": ".",
  E: "1",
  S: "2",
  W: "3",
  N: "4",
  P: "5",
  F: "6",
  C: "7",
};
const tileNames = {
  E: "East wind",
  S: "South wind",
  W: "West wind",
  N: "North wind",
  P: "White dragon",
  F: "Green dragon",
  C: "Red dragon",
};

function metric(label, value) {
  const el = document.createElement("div");
  el.className = "metric";
  el.innerHTML = `<b>${value}</b><span>${label}</span>`;
  return el;
}

function bar(label, value) {
  const row = document.createElement("div");
  row.className = "bar-row";
  row.innerHTML = `
    <b>${label}</b>
    <div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, value * 100))}%"></div></div>
    <span>${pct(value)}</span>
  `;
  return row;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tileCode(tile) {
  const key = String(tile || "");
  return tileCodes[key] || tileCodes[key.replace("r", "")] || key;
}

function tileName(tile) {
  const key = String(tile || "");
  const base = key.replace("r", "");
  if (tileNames[base]) return tileNames[base];
  if (/^5[mps]r$/.test(key)) return `red ${key[0]}${key[1]}`;
  return key;
}

function tileNamesText(items) {
  return (items || []).filter(Boolean).map(tileName).join(", ");
}

function tiles(text) {
  const wrap = document.createElement("div");
  wrap.className = "tile-list";
  const span = document.createElement("span");
  span.className = `tiles hand-tiles${useOtfTiles ? " otf" : ""}`;
  const list = text.split(" ").filter(Boolean);
  const label = tileNamesText(list);
  span.textContent = list.map(tileCode).join("");
  span.title = label;
  span.setAttribute("aria-label", label);
  wrap.append(span);
  return wrap;
}

function tileIcon(tile, className = "") {
  const label = tileName(tile);
  return `<span class="tiles ${useOtfTiles ? "otf " : ""}${className}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${escapeHtml(tileCode(tile))}</span>`;
}

function applyTileCompatibility(root = document) {
  if (!useOtfTiles) return;
  root.querySelectorAll(".tiles").forEach((el) => el.classList.add("otf"));
}

function shortTiles(items) {
  if (!items || !items.length) return "none";
  return tileNamesText(items.slice(0, 12));
}

function dangerText(value) {
  return value == null ? "n/a" : pct(value);
}

function tileIcons(items, className = "mini-tile") {
  const list = (items || []).filter(Boolean);
  if (!list.length) return `<span class="empty">none</span>`;
  return list.map((tile) => tileIcon(tile, className)).join("");
}

function tileRun(items, className = "", emptyLabel = "none") {
  const list = (items || []).filter(Boolean);
  if (!list.length) return emptyLabel ? `<span class="empty">${escapeHtml(emptyLabel)}</span>` : "";
  const label = tileNamesText(list);
  return `<span class="tiles ${useOtfTiles ? "otf " : ""}${className}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${list
    .map(tileCode)
    .join("")}</span>`;
}

function richText(text) {
  const template = document.createElement("template");
  const parts = String(text || "").split(/(\[\[[^\]]+\]\])/g);
  for (const part of parts) {
    const match = part.match(/^\[\[([^\]]+)\]\]$/);
    if (match) {
      template.content.appendChild(document.createRange().createContextualFragment(tileIcon(match[1], "inline-tile")));
    } else {
      template.content.append(document.createTextNode(part));
    }
  }
  return template.content;
}

function meldIcons(melds) {
  if (!melds || !melds.length) return `<span class="empty">none</span>`;
  return melds
    .map((meld) => `<span class="meld">${tileIcons(meld.split(" ").filter(Boolean), "mini-tile")}</span>`)
    .join("");
}

function seatLabel(seat) {
  return {
    self: "LuckyJ",
    shimocha: "Shimocha",
    toimen: "Toimen",
    kamicha: "Kamicha",
  }[seat] || seat;
}

function seatPosition(seat) {
  return {
    self: "current",
    shimocha: "next",
    toimen: "across",
    kamicha: "prev",
  }[seat] || "current";
}

function playerFor(table, seat) {
  return (table.players || []).find((player) => player.seat === seat) || { seat, hand: "", discards: [], melds: [] };
}

function scoreFor(table, seat) {
  return (table.scores || []).find((player) => player.seat === seat) || { seat, score: 0, wind: "?", rank: "?" };
}

function discardRows(discards) {
  const rows = [];
  const list = discards || [];
  for (let i = 0; i < 18; i += 6) {
    rows.push(list.slice(i, i + 6));
  }
  return rows;
}

function renderMahjongTable(table) {
  const wrap = document.createElement("div");
  wrap.className = "caption-flex-container lucky-table-wrap";
  const positions = ["current", "next", "across", "prev"];
  const seats = {
    current: "self",
    next: "shimocha",
    across: "toimen",
    prev: "kamicha",
  };
  const scores = positions
    .map((position) => {
      const score = scoreFor(table, seats[position]);
      return `
        <div class="player-score player-${position}">
          <div class="wind">${escapeHtml(score.wind || "?")}</div>
          <div class="score">${whole.format(score.score || 0)}</div>
        </div>
      `;
    })
    .join("");

  const hands = positions
    .map((position) => {
      const player = playerFor(table, seats[position]);
      const score = scoreFor(table, seats[position]);
      const name = `${seatLabel(player.seat)}${score.rank ? ` / ${score.rank}${score.rank === 1 ? "st" : score.rank === 2 ? "nd" : score.rank === 3 ? "rd" : "th"}` : ""}`;
      const melds = (player.melds || []).length
        ? `<div class="table-melds">${(player.melds || [])
            .map((meld) => `<span class="meld-run">${tileRun(meld.split(" "))}</span>`)
            .join("")}</div>`
        : "";
      const review = player.seat === "self" ? "" : `<span class="review-tag">review</span>`;
      return `
        <div class="player-hand player-${position}">
          <span class="player-name">${escapeHtml(name)} ${review}</span>
          <div class="hand compact"><div class="hand-contents">${tileRun((player.hand || "").split(" "))}</div></div>
          ${melds}
        </div>
      `;
    })
    .join("");

  const rivers = positions
    .map((position) => {
      const player = playerFor(table, seats[position]);
      return `
        <div class="player-discards player-${position}">
          ${discardRows(player.discards)
            .map((row) => `<div class="discard-row">${tileRun(row, "", "")}</div>`)
            .join("")}
        </div>
      `;
    })
    .join("");

  wrap.innerHTML = `
    <div class="caption-container">
      <div class="caption-content">
        <div class="mahjong-table">
          <div class="center">
            <div class="situation-container">
              <div class="round-container"><div class="round">${escapeHtml(table.round || "")}</div></div>
              <div class="dora-indicator">Dora: ${tileRun(table.dora_markers || [])}</div>
            </div>
            ${scores}
          </div>
          ${hands}
          ${rivers}
        </div>
      </div>
      <div class="caption-text">Review view: concealed opponent hands are shown after the fact. In-game, read from rivers, calls, score, and timing.</div>
    </div>
  `;
  return wrap;
}

function renderGuideBlock(guide) {
  const block = document.createElement("div");
  block.className = "natsu-analysis";
  const rows = [
    ["Situation", guide?.situation],
    ["What LuckyJ Is Seeing", guide?.read],
    ["Why the Other Line Is Tempting", guide?.whyNot],
    ["How to Copy It", guide?.copy],
    ["When Not to Copy It", guide?.limit],
  ];
  for (const [title, text] of rows) {
    if (!text) continue;
    const section = document.createElement("section");
    section.className = "analysis-step";
    const heading = document.createElement("h5");
    heading.textContent = title;
    const para = document.createElement("p");
    para.append(richText(text));
    section.append(heading, para);
    block.append(section);
  }
  return block;
}

function modelActionLine(action) {
  if (!action) return "No model action";
  if (action.type === "dahai" && action.tile) {
    return `Discard ${tileIcon(action.tile, "discard-tile")} <em>${escapeHtml(tileName(action.tile))}</em>`;
  }
  if (action.type === "reach") return "Reach";
  if (["chi", "pon", "daiminkan", "ankan", "kakan"].includes(action.type)) {
    const tile = action.tile ? ` ${tileIcon(action.tile, "discard-tile")} <em>${escapeHtml(tileName(action.tile))}</em>` : "";
    const label = {
      chi: "Chi",
      pon: "Pon",
      daiminkan: "Open kan",
      ankan: "Closed kan",
      kakan: "Added kan",
    }[action.type];
    return `${label || escapeHtml(action.type)}${tile}`;
  }
  return escapeHtml(action.label || action.type || "No model action");
}

function candidateLine(candidate) {
  if (candidate.type === "dahai" && candidate.tile) {
    return `<span>Discard ${tileIcon(candidate.tile, "inline-tile")} <em>${escapeHtml(tileName(candidate.tile))}</em></span>`;
  }
  return `<span>${escapeHtml(candidate.label)}</span>`;
}

function agreementBadge(label, value) {
  if (value == null) return "";
  return `<span class="model-badge ${value ? "agree" : "split"}">${escapeHtml(label)} ${value ? "agrees" : "splits"}</span>`;
}

function renderMortalBlock(mortal) {
  if (!mortal) return document.createDocumentFragment();
  const block = document.createElement("section");
  block.className = "mortal-block";
  const topCandidates = (mortal.top_candidates || [])
    .slice(0, 4)
    .map(
      (candidate, index) => `
        <li>
          <b>${index + 1}</b>
          ${candidateLine(candidate)}
          <strong>${pct(candidate.probability)}</strong>
        </li>
      `
    )
    .join("");
  const branch =
    mortal.post_call_mortal && mortal.post_call_candidates?.length
      ? `
        <div class="mortal-branch">
          <h5>After Accepting the Call</h5>
          <p>Mortal's conditional discard is ${modelActionLine(mortal.post_call_mortal)} ${agreementBadge(
            "post-call discard",
            mortal.post_call_agrees_luckyj
          )}</p>
          <ol>
            ${mortal.post_call_candidates
              .slice(0, 3)
              .map(
                (candidate, index) => `
                  <li>
                    <b>${index + 1}</b>
                    ${candidateLine(candidate)}
                    <strong>${pct(candidate.probability)}</strong>
                  </li>
                `
              )
              .join("")}
          </ol>
        </div>
      `
      : "";
  block.innerHTML = `
    <div class="mortal-head">
      <div>
        <p class="kicker">Mortal cross-check</p>
        <h5>${modelActionLine(mortal.mortal)}</h5>
      </div>
      <div class="model-badges">
        ${agreementBadge("LuckyJ", mortal.mortal_agrees_luckyj)}
        ${agreementBadge("NAGA", mortal.mortal_agrees_naga)}
      </div>
    </div>
    <div class="mortal-grid">
      <div>
        <h5>Model Candidates</h5>
        <ol>${topCandidates}</ol>
      </div>
      <div>
        <h5>Reading the Split</h5>
        <p>${escapeHtml(mortal.read)}</p>
        <p>${escapeHtml(mortal.how_to_use)}</p>
      </div>
    </div>
    ${branch}
  `;
  return block;
}

function renderPointExamples(examples, guides, mortalPoints) {
  for (const placeholder of document.querySelectorAll("[data-example]")) {
    const example = examples[placeholder.dataset.example];
    if (!example) continue;
    const guide = guides?.[placeholder.dataset.example];
    const card = document.createElement("article");
    card.className = "point-example-card";
    card.innerHTML = `
      <div class="example-head">
        <div>
          <p class="kicker">Replay example</p>
          <h4>${escapeHtml(guide?.caption || example.title)}</h4>
        </div>
        <span>Game ${example.game}, ${escapeHtml(example.round)}, ${example.left} tiles left</span>
      </div>
      <p class="case-meta">${escapeHtml(example.stage)} / ${escapeHtml(example.score_band)} / final rank ${example.rank}</p>
    `;
    card.append(renderMahjongTable(example.table));

    if (example.kind === "call") {
      const line = document.createElement("div");
      line.className = "call-line";
      line.innerHTML = `
        <span>Call ${escapeHtml(example.call)} on ${tileIcon(example.called_tile, "discard-tile")} from ${escapeHtml(seatLabel(example.called_from))}</span>
        <span>Meld ${tileIcons(example.post_call_meld?.split(" "), "mini-tile")}</span>
        <span>Discard after call ${tileIcon(example.discard_after_call, "discard-tile")}</span>
      `;
      card.append(line);
    } else {
      const choices = document.createElement("div");
      choices.className = "comparison";
      if (example.actual_eval && example.naga_eval) {
        choices.append(
          comparison("LuckyJ", example.actual_eval, example.actual_danger),
          comparison("NAGA top", example.naga_eval, example.naga_danger)
        );
      } else {
        choices.innerHTML = `
          <div class="decision"><b>LuckyJ</b><span class="discard-line">Discard ${tileIcon(example.actual, "discard-tile")} <em>${escapeHtml(tileName(example.actual))}</em></span><span>Danger ${dangerText(example.actual_danger)}</span></div>
          <div class="decision"><b>NAGA top</b><span class="discard-line">Discard ${tileIcon(example.naga, "discard-tile")} <em>${escapeHtml(tileName(example.naga))}</em></span><span>Danger ${dangerText(example.naga_danger)}</span></div>
        `;
      }
      card.append(choices);
    }
    card.append(renderMortalBlock(mortalPoints?.[placeholder.dataset.example]));
    card.append(renderGuideBlock(guide));

    const drill = document.createElement("div");
    drill.className = "example-drill";
    drill.innerHTML = `
      <p><b>Drill:</b> ${escapeHtml(example.prompt)}</p>
      <p><b>Answer:</b> ${escapeHtml(example.answer)}</p>
    `;

    const links = document.createElement("p");
    links.className = "case-links";
    links.innerHTML = `<a href="${example.report}">NAGA report</a> <a href="${example.paifu}">Tenhou log</a>`;

    card.append(drill, links);
    placeholder.replaceChildren(card);
  }
}

function tileClass(tile) {
  const base = String(tile || "").replace("r", "");
  if (["E", "S", "W", "N", "P", "F", "C"].includes(base)) return "honor";
  if (base.startsWith("1") || base.startsWith("9")) return "terminal";
  return "middle";
}

function parseTiles(text) {
  return String(text || "").split(" ").filter(Boolean);
}

function handTexture(hand) {
  const tiles = parseTiles(hand);
  const suits = { m: 0, p: 0, s: 0, honor: 0 };
  const counts = {};
  for (const tile of tiles) {
    const base = tile.replace("r", "");
    counts[base] = (counts[base] || 0) + 1;
    if (["E", "S", "W", "N", "P", "F", "C"].includes(base)) suits.honor += 1;
    else suits[base[1]] += 1;
  }
  const pairs = Object.values(counts).filter((count) => count >= 2).length;
  const dominant = Object.entries(suits)
    .filter(([key]) => key !== "honor")
    .sort((a, b) => b[1] - a[1])[0];
  const red = tiles.filter((tile) => tile.includes("r")).length;
  const fragments = [];
  if (dominant && dominant[1] >= 6) fragments.push(`heavy ${dominant[0]}-suit shape`);
  if (pairs >= 3) fragments.push(`${pairs} pair-like anchors`);
  if (suits.honor >= 2) fragments.push(`${suits.honor} honors`);
  if (red) fragments.push(`${red} red five${red === 1 ? "" : "s"}`);
  return fragments.length ? fragments.join(", ") : "mixed ordinary blocks";
}

function dangerRead(actual, naga) {
  if (actual == null || naga == null) return "The report does not provide a clean danger comparison, so the review should lean on route and score logic.";
  const gap = actual - naga;
  if (Math.abs(gap) < 0.03) return "Immediate danger is close, so the disagreement is mostly about route selection rather than a simple safe-tile trade.";
  if (gap < 0) return `LuckyJ buys immediate safety by avoiding about ${fmt.format(Math.abs(gap) * 100)} danger points.`;
  return `LuckyJ accepts about ${fmt.format(gap * 100)} extra danger points, so the hand must be buying concrete value, pressure, or placement equity.`;
}

function categoryRead(key, item) {
  const actualClass = tileClass(item.actual);
  const nagaClass = tileClass(item.naga);
  const actualName = tileName(item.actual);
  const nagaName = tileName(item.naga);
  if (key === "early_safety_hedge") {
    return `Early in the hand, LuckyJ is treating ${actualName} as the tile that least damages the future menu. This bucket is about delaying commitment: keep enough safety/value material to choose again after the table speaks.`;
  }
  if (key === "middle_route_hedge") {
    return `In the middle row, the hand has to start proving itself. LuckyJ's ${actualName} discard suggests that the NAGA line compresses the hand into a route that is too brittle for the score and river state.`;
  }
  if (key === "safer_than_naga") {
    return `This is a safety purchase inside an attacking hand. LuckyJ is not necessarily folding; it is choosing the line that keeps the hand alive without immediately throwing the more dangerous NAGA tile.`;
  }
  if (key === "riskier_than_naga") {
    return `This is a high-bar imitation case. LuckyJ is willing to pay danger now, but only because the retained route must be meaningfully better than the safe-looking alternative.`;
  }
  if (key === "late_tightening") {
    return `Late in the hand, speculative shape has mostly expired. Read this as an exact-counting problem: win, take safe tenpai, or fold.`;
  }
  return `LuckyJ cuts a ${actualClass} (${actualName}) while NAGA cuts a ${nagaClass} (${nagaName}); the first question is which future each tile is protecting.`;
}

function caseLesson(key, item) {
  const actualClass = tileClass(item.actual);
  const nagaClass = tileClass(item.naga);
  const actualName = tileName(item.actual);
  const nagaName = tileName(item.naga);
  return [
    `${item.round}, ${item.left} tiles left, ${item.score_band}. Hand texture: ${handTexture(item.hand)}. LuckyJ cuts ${actualName} (${actualClass}); NAGA cuts ${nagaName} (${nagaClass}).`,
    categoryRead(key, item),
    dangerRead(item.actual_danger, item.naga_danger),
    `Review drill: before looking at the diagnostics, write what LuckyJ is buying: safety, value, route count, pressure, or placement. If you cannot name the purchase, do not copy the move yet.`,
  ];
}

function comparison(label, item, danger) {
  const el = document.createElement("div");
  el.className = "decision";
  el.innerHTML = `
    <b>${label}</b>
    <span class="discard-line">Discard ${tileIcon(item.discard, "discard-tile")} <em>${escapeHtml(tileName(item.discard))}</em></span>
    <span>Immediate danger ${danger == null ? "n/a" : pct(danger)}</span>
    <span>Keeps ${item.kept_honors} honors, ${item.kept_terminals} terminals</span>
    <details class="diagnostics">
      <summary>Mechanical diagnostic</summary>
      <span>${item.shanten} shanten</span>
      <span>${whole.format(item.ukeire)} visible ukeire</span>
      <small>Effective: ${shortTiles(item.effective)}</small>
    </details>
  `;
  return el;
}

function renderCases(data) {
  const tabs = document.querySelector("#caseTabs");
  const grid = document.querySelector("#caseGrid");
  if (!tabs || !grid) return;

  const labels = {
    early_safety_hedge: "Early Hedges",
    middle_route_hedge: "Middle Hedges",
    safer_than_naga: "Safety Buys",
    riskier_than_naga: "Risk Buys",
    late_tightening: "Late Precision",
  };
  const keys = Object.keys(labels).filter((key) => data[key]?.length);
  let active = keys[0];

  function paint(key) {
    active = key;
    tabs.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("active", button.dataset.key === key);
    });
    grid.innerHTML = "";
    for (const item of data[key].slice(0, 6)) {
      const card = document.createElement("article");
      card.className = "case-card";

      const head = document.createElement("div");
      head.className = "case-head";
      head.innerHTML = `
        <div>
          <p class="kicker">${item.stage} / ${item.score_band}</p>
          <h3>${item.label}</h3>
        </div>
        <span>${item.round}, ${item.left} tiles left</span>
      `;

      const body = document.createElement("div");
      body.className = "case-body";
      const handTitle = document.createElement("p");
      handTitle.className = "case-meta";
      handTitle.textContent = `Game ${item.game}, final rank ${item.rank}, score ${whole.format(item.score)}`;
      body.append(handTitle, tiles(item.hand));

      const choices = document.createElement("div");
      choices.className = "comparison";
      choices.append(
        comparison("LuckyJ", item.actual_eval, item.actual_danger),
        comparison("NAGA top", item.naga_eval, item.naga_danger)
      );

      const lesson = document.createElement("div");
      lesson.className = "case-lesson";
      for (const paragraph of caseLesson(key, item)) {
        const p = document.createElement("p");
        p.textContent = paragraph;
        lesson.append(p);
      }

      const links = document.createElement("p");
      links.className = "case-links";
      links.innerHTML = `<a href="${item.report}">NAGA report</a> <a href="${item.paifu}">Tenhou log</a>`;

      card.append(head, body, choices, lesson, links);
      grid.append(card);
    }
  }

  for (const key of keys) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.key = key;
    button.textContent = `${labels[key]} (${data[key].length})`;
    button.addEventListener("click", () => paint(key));
    tabs.append(button);
  }
  paint(active);
}

async function main() {
  applyTileCompatibility();
  const [bookResponse, caseResponse, exampleResponse, guideResponse, mortalResponse] = await Promise.all([
    fetch("book-data.json"),
    fetch("case-studies.json"),
    fetch("point-examples.json"),
    fetch("strategy-guides.json"),
    fetch("mortal-analysis.json"),
  ]);
  const data = await bookResponse.json();
  const caseData = await caseResponse.json();
  const examples = await exampleResponse.json();
  const guides = await guideResponse.json();
  const mortal = await mortalResponse.json();
  const summary = data.summary;
  const top = data.top_bottom.top_half;
  const bottom = data.top_bottom.bottom_half;
  const metrics = document.querySelector("#metrics");
  metrics.append(
    metric("analyzed hanchan", fmt.format(summary.games)),
    metric("hands reviewed", fmt.format(summary.hands)),
    metric("LuckyJ average placement", fmt.format(summary.avg_rank)),
    metric("average score", `+${fmt.format(summary.avg_score)}`),
    metric("win rate per hand", pct(summary.win_rate_per_hand)),
    metric("deal-in rate per hand", pct(summary.deal_in_rate_per_hand)),
    metric("top-half wins per hanchan", fmt.format(top.wins_per_game)),
    metric("bottom-half deal-ins per hanchan", fmt.format(bottom.deal_ins_per_game))
  );

  const stage = data.decision_counters.stage;
  const chart = document.querySelector("#stageChart");
  for (const key of ["early", "middle", "late"]) {
    const item = stage[key];
    chart.append(bar(`${key} mismatch`, item.mismatch / item.decisions));
    chart.append(bar(`${key} bad`, item.bad / item.decisions));
  }

  renderPointExamples(examples, guides, mortal.points);
  renderCases(caseData);
  applyTileCompatibility();
}

main().catch((error) => {
  const metrics = document.querySelector("#metrics");
  metrics.innerHTML = `<div class="metric"><b>Data load failed</b><span>${error.message}</span></div>`;
});
