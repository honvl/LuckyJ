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
  return tileCodes[tile] || tileCodes[tile.replace("r", "")] || tile;
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

function caseLesson(key, item) {
  const ukeireDelta = item.actual_eval.ukeire - item.naga_eval.ukeire;
  const shantenDelta = item.actual_eval.shanten - item.naga_eval.shanten;
  const dangerDelta =
    item.actual_danger == null || item.naga_danger == null
      ? null
      : item.actual_danger - item.naga_danger;

  const summary = [
    `${shantenDelta > 0 ? "Spent" : shantenDelta < 0 ? "Gained" : "Held"} ${Math.abs(shantenDelta)} shanten step${Math.abs(shantenDelta) === 1 ? "" : "s"}`,
    `${ukeireDelta >= 0 ? "gained" : "lost"} ${Math.abs(ukeireDelta)} visible ukeire`,
  ];
  if (dangerDelta != null) {
    summary.push(`${dangerDelta <= 0 ? "reduced" : "accepted"} ${fmt.format(Math.abs(dangerDelta) * 100)} danger points`);
  }

  const lessons = {
    early_safety_hedge:
      "Early LuckyJ often pays shanten to keep breadth, yaku fragments, and future exits. This is strongest when the hand is too far away to justify locking into one narrow line.",
    middle_route_hedge:
      "In the middle row, the issue is route compression. LuckyJ avoids a prettier immediate shape when that shape leaves a brittle hand with poor follow-up or awkward danger.",
    safer_than_naga:
      "These are defensive upgrades hidden inside attacking hands. LuckyJ spends some shape when the current discard removes a future liability and the score situation does not demand maximum greed.",
    riskier_than_naga:
      "These are the dangerous examples to copy. LuckyJ accepts extra danger only when the hand's route count, score job, or comeback need makes the price coherent.",
    late_tightening:
      "Late decisions should have no vague upside. LuckyJ's late deviations are about exact tenpai, safe tenpai, or cutting a future landmine before it becomes mandatory.",
  };

  return `${summary.join("; ")}. ${lessons[key] || lessons.early_safety_hedge}`;
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
  const [bookResponse, caseResponse] = await Promise.all([
    fetch("book-data.json"),
    fetch("case-studies.json"),
  ]);
  const data = await bookResponse.json();
  const caseData = await caseResponse.json();
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

  renderCases(caseData);
  applyTileCompatibility();
}

main().catch((error) => {
  const metrics = document.querySelector("#metrics");
  metrics.innerHTML = `<div class="metric"><b>Data load failed</b><span>${error.message}</span></div>`;
});
