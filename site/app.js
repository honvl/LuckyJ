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

function tiles(text) {
  const wrap = document.createElement("div");
  wrap.className = "tile-list";
  const span = document.createElement("span");
  span.className = `tiles hand-tiles${useOtfTiles ? " otf" : ""}`;
  span.textContent = text.split(" ").filter(Boolean).map(tileCode).join("");
  span.title = text;
  span.setAttribute("aria-label", text);
  wrap.append(span);
  return wrap;
}

function tileIcon(tile, className = "") {
  return `<span class="tiles ${useOtfTiles ? "otf " : ""}${className}" aria-label="${escapeHtml(tile)}" title="${escapeHtml(tile)}">${escapeHtml(tileCode(tile))}</span>`;
}

function applyTileCompatibility(root = document) {
  if (!useOtfTiles) return;
  root.querySelectorAll(".tiles").forEach((el) => el.classList.add("otf"));
}

function shortTiles(items) {
  if (!items || !items.length) return "none";
  return items.slice(0, 12).join(" ");
}

function dangerText(value) {
  return value == null ? "n/a" : pct(value);
}

function tileIcons(items, className = "mini-tile") {
  const list = (items || []).filter(Boolean);
  if (!list.length) return `<span class="empty">none</span>`;
  return list.map((tile) => tileIcon(tile, className)).join("");
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

function renderTableContext(table) {
  const wrap = document.createElement("div");
  wrap.className = "table-context";
  const scoreLine = (table.scores || [])
    .map((player) => {
      const dealer = player.dealer ? " dealer" : "";
      const rank = player.rank ? `${player.rank}${player.rank === 1 ? "st" : player.rank === 2 ? "nd" : player.rank === 3 ? "rd" : "th"}` : "rank ?";
      return `<span><b>${seatLabel(player.seat)}</b> ${whole.format(player.score || 0)} / ${rank}${dealer}</span>`;
    })
    .join("");

  wrap.innerHTML = `
    <div class="table-summary">
      <span><b>${escapeHtml(table.round || "")}</b></span>
      <span>Dealer: ${escapeHtml(seatLabel(table.dealer))}</span>
      <span>Dora: ${tileIcons(table.dora_markers, "mini-tile")}</span>
    </div>
    <div class="score-strip">${scoreLine}</div>
  `;

  const visible = document.createElement("div");
  visible.className = "player-grid";
  for (const player of table.players || []) {
    const card = document.createElement("div");
    card.className = `player-card ${player.seat === "self" ? "self-player" : ""}`;
    const lines = [
      `<h5>${seatLabel(player.seat)}${player.reached ? " <span>riichi</span>" : ""}</h5>`,
      player.seat === "self" ? `<p class="row-label">Hand</p><div class="mini-hand">${tileIcons(player.hand?.split(" "), "mini-tile")}</div>` : "",
      `<p class="row-label">River</p><div class="river">${tileIcons(player.discards, "mini-tile")}</div>`,
      `<p class="row-label">Melds</p><div class="river">${meldIcons(player.melds)}</div>`,
    ];
    card.innerHTML = lines.join("");
    visible.append(card);
  }
  wrap.append(visible);

  const details = document.createElement("details");
  details.className = "hidden-hands";
  details.innerHTML = `<summary>Review-only hidden hands</summary>`;
  const hidden = document.createElement("div");
  hidden.className = "hidden-hand-grid";
  for (const player of table.players || []) {
    const item = document.createElement("div");
    item.innerHTML = `<b>${seatLabel(player.seat)}</b><div class="mini-hand">${tileIcons(player.hand?.split(" "), "mini-tile")}</div>`;
    hidden.append(item);
  }
  details.append(hidden);
  wrap.append(details);
  return wrap;
}

function exampleAnalysis(example) {
  const parts = [];
  if (example.kind === "call") {
    parts.push(
      `LuckyJ calls ${example.call} on ${example.called_tile} from ${seatLabel(example.called_from)} and plans to discard ${example.discard_after_call}.`
    );
    parts.push(`The lesson is the contract: this is a tempo/open-route decision, not an automatic call because a set is available.`);
  } else {
    const action = example.kind === "reach" ? "reaches and discards" : "discards";
    parts.push(`LuckyJ ${action} ${example.actual}; NAGA's top discard is ${example.naga}.`);
    if (example.actual_eval && example.naga_eval) {
      const ukeireDelta = example.actual_eval.ukeire - example.naga_eval.ukeire;
      const shantenDelta = example.actual_eval.shanten - example.naga_eval.shanten;
      parts.push(
        `That leaves ${example.actual_eval.shanten} shanten and ${whole.format(example.actual_eval.ukeire)} visible ukeire, versus NAGA's ${example.naga_eval.shanten} shanten and ${whole.format(example.naga_eval.ukeire)} ukeire.`
      );
      if (shantenDelta > 0 && ukeireDelta > 0) {
        parts.push("This is the classic LuckyJ trade: one step slower now, but broader recovery and more ways to change plans.");
      } else if (shantenDelta === 0 && ukeireDelta < 0) {
        parts.push("Here the cost is pure acceptance, so the kept material must be buying safety, value, or future flexibility.");
      } else if (ukeireDelta >= 0) {
        parts.push("The move is not just defensive; it also keeps the next-draw menu wide.");
      }
    }
    if (example.actual_danger != null || example.naga_danger != null) {
      parts.push(`Danger read: LuckyJ's tile is ${dangerText(example.actual_danger)} and NAGA's tile is ${dangerText(example.naga_danger)}.`);
    }
    if (example.kind === "reach") {
      parts.push(`The reach model is high here (${pct(example.reach_prob || 0)}), so the riichi itself is part of the equity calculation.`);
    }
  }
  parts.push(`Outcome: ${example.outcome}`);
  return parts.join(" ");
}

function renderPointExamples(examples) {
  for (const placeholder of document.querySelectorAll("[data-example]")) {
    const example = examples[placeholder.dataset.example];
    if (!example) continue;
    const card = document.createElement("article");
    card.className = "point-example-card";
    card.innerHTML = `
      <div class="example-head">
        <div>
          <p class="kicker">Replay example</p>
          <h4>${escapeHtml(example.title)}</h4>
        </div>
        <span>Game ${example.game}, ${escapeHtml(example.round)}, ${example.left} tiles left</span>
      </div>
      <p class="case-meta">${escapeHtml(example.stage)} / ${escapeHtml(example.score_band)} / final rank ${example.rank}</p>
      <p><b>Hand before decision</b></p>
    `;
    card.append(tiles(example.hand));

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
          <div class="decision"><b>LuckyJ</b><span class="discard-line">Discard ${tileIcon(example.actual, "discard-tile")} <em>${escapeHtml(example.actual)}</em></span><span>Danger ${dangerText(example.actual_danger)}</span></div>
          <div class="decision"><b>NAGA top</b><span class="discard-line">Discard ${tileIcon(example.naga, "discard-tile")} <em>${escapeHtml(example.naga)}</em></span><span>Danger ${dangerText(example.naga_danger)}</span></div>
        `;
      }
      card.append(choices);
    }

    const analysis = document.createElement("p");
    analysis.className = "case-lesson";
    analysis.textContent = exampleAnalysis(example);

    const drill = document.createElement("div");
    drill.className = "example-drill";
    drill.innerHTML = `
      <p><b>Drill:</b> ${escapeHtml(example.prompt)}</p>
      <p><b>Answer:</b> ${escapeHtml(example.answer)}</p>
    `;

    const links = document.createElement("p");
    links.className = "case-links";
    links.innerHTML = `<a href="${example.report}">NAGA report</a> <a href="${example.paifu}">Tenhou log</a>`;

    card.append(analysis, drill, renderTableContext(example.table), links);
    placeholder.replaceChildren(card);
  }
}

function caseLesson(key, item) {
  const ukeireDelta = item.actual_eval.ukeire - item.naga_eval.ukeire;
  const shantenDelta = item.actual_eval.shanten - item.naga_eval.shanten;
  const dangerDelta =
    item.actual_danger == null || item.naga_danger == null
      ? null
      : item.actual_danger - item.naga_danger;

  const summary = [
    `${item.round} with ${item.left} tiles left is a ${item.stage} ${item.score_band} spot: LuckyJ cuts ${item.actual}, while NAGA's top line cuts ${item.naga}.`,
  ];
  if (shantenDelta > 0 && ukeireDelta > 0) {
    summary.push(`LuckyJ spends one visible shanten step to gain ${Math.abs(ukeireDelta)} ukeire, so the hand is buying a wider next draw rather than a cleaner current shape.`);
  } else if (shantenDelta > 0) {
    summary.push(`LuckyJ falls ${Math.abs(shantenDelta)} shanten step behind NAGA, so the kept tiles must be justified by safety, value, or a route NAGA is discarding.`);
  } else if (shantenDelta < 0) {
    summary.push(`LuckyJ is actually ${Math.abs(shantenDelta)} shanten step closer, which means the disagreement is about the tile class and future danger more than speed.`);
  } else if (ukeireDelta >= 0) {
    summary.push(`Shanten is equal and LuckyJ keeps ${Math.abs(ukeireDelta)} more visible ukeire, so the NAGA preference is not a simple speed win.`);
  } else {
    summary.push(`Shanten is equal but LuckyJ gives up ${Math.abs(ukeireDelta)} ukeire, so this is a deliberate payment for another objective.`);
  }
  if (dangerDelta != null) {
    summary.push(
      dangerDelta <= 0
        ? `It also lowers immediate danger by ${fmt.format(Math.abs(dangerDelta) * 100)} points.`
        : `It accepts ${fmt.format(Math.abs(dangerDelta) * 100)} extra danger points, so the upside must be concrete.`
    );
  }
  const honorDelta = item.actual_eval.kept_honors - item.naga_eval.kept_honors;
  const terminalDelta = item.actual_eval.kept_terminals - item.naga_eval.kept_terminals;
  if (honorDelta > 0) summary.push(`It keeps ${honorDelta} more honor tile${honorDelta === 1 ? "" : "s"}, which usually means yaku/safety has entered the price.`);
  if (terminalDelta > 0) summary.push(`It keeps ${terminalDelta} more terminal tile${terminalDelta === 1 ? "" : "s"}, useful for outside safety or a non-tanyao route.`);
  if (key === "riskier_than_naga") {
    summary.push("Treat this as a high-bar imitation case: copy it only if the score job and route count justify pushing the extra danger.");
  } else if (key === "late_tightening") {
    summary.push("The drill is exact: identify whether this is safe tenpai, winning tenpai, or a clean fold before calling it style.");
  } else {
    summary.push("Review question: what did LuckyJ buy with the disagreement, and would that purchase still matter if one opponent became live next turn?");
  }

  return summary.join(" ");
}

function comparison(label, item, danger) {
  const el = document.createElement("div");
  el.className = "decision";
  el.innerHTML = `
    <b>${label}</b>
    <span class="discard-line">Discard ${tileIcon(item.discard, "discard-tile")} <em>${escapeHtml(item.discard)}</em></span>
    <span>${item.shanten} shanten</span>
    <span>${whole.format(item.ukeire)} visible ukeire</span>
    <span>Danger ${danger == null ? "n/a" : pct(danger)}</span>
    <small>Effective: ${shortTiles(item.effective)}</small>
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

      const lesson = document.createElement("p");
      lesson.className = "case-lesson";
      lesson.textContent = caseLesson(key, item);

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
  const [bookResponse, caseResponse, exampleResponse] = await Promise.all([
    fetch("book-data.json"),
    fetch("case-studies.json"),
    fetch("point-examples.json"),
  ]);
  const data = await bookResponse.json();
  const caseData = await caseResponse.json();
  const examples = await exampleResponse.json();
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

  renderPointExamples(examples);
  renderCases(caseData);
  applyTileCompatibility();
}

main().catch((error) => {
  const metrics = document.querySelector("#metrics");
  metrics.innerHTML = `<div class="metric"><b>Data load failed</b><span>${error.message}</span></div>`;
});
