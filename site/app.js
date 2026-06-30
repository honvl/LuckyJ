const pageLang = document.documentElement.lang.toLowerCase().startsWith("ja") ? "ja" : "en";
const isJa = pageLang === "ja";
const locale = isJa ? "ja-JP" : "en-US";
const fmt = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
const pct = (v) => `${fmt.format(v * 100)}%`;
const chromiumTileEngine = /Chrome|Chromium|Edg|Opera|OPR|OPE|MSIE/.test(navigator.userAgent);
const useColrTiles = chromiumTileEngine && globalThis.CSS?.supports?.("font-tech(color-COLRv1)");
const useOtfTiles = chromiumTileEngine && !useColrTiles;
const tileFontClass = useColrTiles ? "colr" : useOtfTiles ? "otf" : "";
const tileFontClassSuffix = tileFontClass ? ` ${tileFontClass}` : "";
const tileFontClassPrefix = tileFontClass ? `${tileFontClass} ` : "";
const copy = {
  en: {
    none: "none",
    dora: "Dora",
    reviewCaption: "Review view: concealed opponent hands are shown after the fact. In-game, read from rivers, calls, score, and timing.",
    situation: "Situation",
    seeing: "What LuckyJ Is Seeing",
    whyTempting: "Why the Other Line Is Tempting",
    copyIt: "How to Copy It",
    limit: "When Not to Copy It",
    noModelAction: "No model action",
    discard: "Discard",
    reach: "Reach",
    chi: "Chi",
    pon: "Pon",
    openKan: "Open kan",
    closedKan: "Closed kan",
    addedKan: "Added kan",
    agrees: "agrees",
    splits: "splits",
    afterCall: "After Accepting the Call",
    postCallDiscard: "post-call discard",
    mortalCrossCheck: "Mortal cross-check",
    mortalTop: "Mortal top",
    modelCandidates: "Model Candidates",
    readingSplit: "Reading the Split",
    replayExample: "Replay example",
    finalRank: "final rank",
    call: "Call",
    meld: "Meld",
    discardAfterCall: "Discard after call",
    luckyj: "LuckyJ",
    nagaTop: "NAGA top",
    danger: "Danger",
    drill: "Drill",
    answer: "Answer",
    nagaReport: "Review page",
    tenhouLog: "Tenhou log",
    immediateDanger: "Immediate danger",
    nagaWeight: "NAGA weight",
    mortalWeight: "Mortal weight",
    keeps: "Keeps",
    honors: "honors",
    terminals: "terminals",
    mechanicalDiagnostic: "Mechanical diagnostic",
    shanten: "shanten",
    visibleUkeire: "visible ukeire",
    effective: "Effective",
    analyzedHanchan: "analyzed hanchan",
    handsReviewed: "hands reviewed",
    averagePlacement: "LuckyJ average placement",
    averageScore: "average score",
    winRate: "win rate per hand",
    dealInRate: "deal-in rate per hand",
    topHalfWins: "top-half wins per hanchan",
    bottomHalfDealIns: "bottom-half deal-ins per hanchan",
    mismatch: "mismatch",
    bad: "bad",
    dataLoadFailed: "Data load failed",
  },
  ja: {
    none: "なし",
    dora: "ドラ",
    reviewCaption: "復習用表示: 対局中は見えない相手の手牌も後から表示しています。実戦では河、鳴き、点数、タイミングから読む必要があります。",
    situation: "局面",
    seeing: "LuckyJ が見ているもの",
    whyTempting: "別ラインが魅力的に見える理由",
    copyIt: "自分の対局に移す方法",
    limit: "真似しない条件",
    noModelAction: "モデル行動なし",
    discard: "打",
    reach: "リーチ",
    chi: "チー",
    pon: "ポン",
    openKan: "大明槓",
    closedKan: "暗槓",
    addedKan: "加槓",
    agrees: "一致",
    splits: "分岐",
    afterCall: "鳴いた後",
    postCallDiscard: "鳴き後の打牌",
    mortalCrossCheck: "Mortal クロスチェック",
    mortalTop: "Mortal 最上位",
    modelCandidates: "モデル候補",
    readingSplit: "分岐の読み方",
    replayExample: "実戦例",
    finalRank: "最終順位",
    call: "鳴き",
    meld: "副露",
    discardAfterCall: "鳴き後の打牌",
    luckyj: "LuckyJ",
    nagaTop: "NAGA 最上位",
    danger: "放銃危険度",
    drill: "ドリル",
    answer: "答え",
    nagaReport: "検討ページ",
    tenhouLog: "天鳳牌譜",
    immediateDanger: "即時危険度",
    nagaWeight: "NAGA 評価",
    mortalWeight: "Mortal 重み",
    keeps: "残す枚数",
    honors: "字牌",
    terminals: "幺九牌",
    mechanicalDiagnostic: "機械的診断",
    shanten: "シャンテン",
    visibleUkeire: "見えている受け入れ",
    effective: "有効牌",
    analyzedHanchan: "解析した半荘",
    handsReviewed: "検討した局",
    averagePlacement: "LuckyJ 平均順位",
    averageScore: "平均スコア",
    winRate: "局あたり和了率",
    dealInRate: "局あたり放銃率",
    topHalfWins: "上位半分の半荘あたり和了",
    bottomHalfDealIns: "下位半分の半荘あたり放銃",
    mismatch: "不一致",
    bad: "悪手",
    dataLoadFailed: "データ読み込み失敗",
  },
};

function t(key) {
  return copy[pageLang]?.[key] || copy.en[key] || key;
}

const stageLabels = {
  early: { en: "early", ja: "序盤" },
  middle: { en: "middle", ja: "中盤" },
  late: { en: "late", ja: "終盤" },
};
const scoreBandLabels = {
  "above starting score": { en: "above starting score", ja: "原点以上" },
  behind: { en: "behind", ja: "ビハインド" },
  "danger zone": { en: "danger zone", ja: "危険圏" },
  lead: { en: "lead", ja: "リード" },
};
const tileClassLabels = {
  honor: { en: "honor", ja: "字牌" },
  terminal: { en: "terminal", ja: "端牌" },
  middle: { en: "middle", ja: "中張牌" },
};
const tileCodes = {
  "1m": "q",
  "2m": "w",
  "3m": "e",
  "4m": "r",
  "5m": "t",
  "5mr": "8",
  "6m": "y",
  "7m": "u",
  "8m": "i",
  "9m": "o",
  "1s": "a",
  "2s": "s",
  "3s": "d",
  "4s": "f",
  "5s": "g",
  "5sr": "p",
  "6s": "h",
  "7s": "j",
  "8s": "k",
  "9s": "l",
  "1p": "z",
  "2p": "x",
  "3p": "c",
  "4p": "v",
  "5p": "b",
  "5pr": "0",
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
const tileNamesJa = {
  E: "東",
  S: "南",
  W: "西",
  N: "北",
  P: "白",
  F: "發",
  C: "中",
};

function labelFrom(map, key) {
  return map[key]?.[pageLang] || map[key]?.en || key;
}

function stageText(value) {
  return labelFrom(stageLabels, value);
}

function scoreBandText(value) {
  return labelFrom(scoreBandLabels, value);
}

function tileClassText(value) {
  return labelFrom(tileClassLabels, value);
}

function roundText(round) {
  const value = String(round || "");
  if (!isJa) return value;
  return value
    .replace(/^East (\d+)-(\d+)$/, "東$1局$2本場")
    .replace(/^South (\d+)-(\d+)$/, "南$1局$2本場")
    .replace(/^West (\d+)-(\d+)$/, "西$1局$2本場")
    .replace(/^North (\d+)-(\d+)$/, "北$1局$2本場");
}

function rankText(rank) {
  if (!rank) return "";
  if (isJa) return `${rank}位`;
  return `${rank}${rank === 1 ? "st" : rank === 2 ? "nd" : rank === 3 ? "rd" : "th"}`;
}

function tilesLeftText(left) {
  return isJa ? `残り${left}枚` : `${left} tiles left`;
}

function gameLine(game, rank, score) {
  if (isJa) return `ゲーム ${game}、最終順位 ${rankText(rank)}、持ち点 ${whole.format(score)}`;
  return `Game ${game}, final rank ${rank}, score ${whole.format(score)}`;
}

function caseLabelText(label) {
  if (!isJa) return label;
  return (
    {
      "Early safety hedge": "序盤の安全保留",
      "Middle route hedge": "中盤のルート保留",
      "Kept river-safe exit": "現物の出口をキープ",
      "Kept suji exit": "筋の出口をキープ",
      "Safer than NAGA": "NAGA より安全",
      "Riskier than NAGA": "NAGA よりリスクあり",
      "Late tightening": "終盤の引き締め",
    }[label] || label
  );
}

function fetchJson(path, fallback = {}) {
  return fetch(path)
    .then((response) => (response.ok ? response.json() : fallback))
    .catch(() => fallback);
}

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

function renderDefenseTiming(retention) {
  const target = document.querySelector("#defenseTiming");
  if (!target || !retention?.stage) return;
  target.innerHTML = "";
  for (const key of ["early", "middle", "late"]) {
    const item = retention.stage[key] || {};
    const kept = item.kept_defense_tile || 0;
    const splits = item.splits || 0;
    const avgLeft = item.kept_left_count ? item.kept_left_sum / item.kept_left_count : null;
    const panel = document.createElement("div");
    panel.className = "safety-timing-card";
    panel.innerHTML = `
      <b>${stageText(key)}</b>
      <strong>${splits ? pct(kept / splits) : "n/a"}</strong>
      <span>${isJa ? "NAGA と割れた打牌で現物/筋を残した割合" : "of NAGA-split discards kept a river-safe or suji tile"}</span>
      <small>${isJa ? "内訳" : "Breakdown"}: ${whole.format(item.kept_genbutsu || 0)} ${safetyKindLabel("genbutsu")}, ${whole.format(item.kept_suji || 0)} ${safetyKindLabel("suji")}, ${whole.format(item.kept_against_live_threat || 0)} ${isJa ? "脅威相手" : "vs live threats"}${avgLeft == null ? "" : isJa ? `、平均残り${fmt.format(avgLeft)}枚` : `, avg ${fmt.format(avgLeft)} tiles left`}</small>
    `;
    target.append(panel);
  }
}

function yakuhaiContextLabel(key) {
  const labels = isJa
    ? {
        unknown_open_yaku: "役が不明な副露",
        shown_yaku_open: "役牌など役が見える副露",
        tanyao_shaped_open: "タンヤオ形の副露",
        no_open_hand: "副露なし",
      }
    : {
        unknown_open_yaku: "Unproven-yaku open hand",
        shown_yaku_open: "Visible-yaku open hand",
        tanyao_shaped_open: "Tanyao-shaped open hand",
        no_open_hand: "No open hand",
      };
  return labels[key] || key;
}

function renderYakuhaiPressure(pressure) {
  const target = document.querySelector("#yakuhaiPressure");
  const data = pressure?.yaku_condition_yakuhai || {};
  if (!target || !Object.keys(data).length) return;
  target.innerHTML = "";
  const order = ["unknown_open_yaku", "shown_yaku_open", "tanyao_shaped_open"];
  for (const key of order) {
    const item = data[key];
    if (!item) continue;
    const card = document.createElement("div");
    card.className = "evidence-card";
    card.innerHTML = `
      <b>${escapeHtml(yakuhaiContextLabel(key))}</b>
      <strong>${item.cut_rate == null ? "n/a" : pct(item.cut_rate)}</strong>
      <span>${isJa ? "相手の役になり得る役牌を今切った割合" : "cut rate for live yaku-condition yakuhai"}</span>
      <small>${whole.format(item.cuts || 0)} / ${whole.format(item.opportunities || 0)} ${isJa ? "機会" : "opportunities"} · ${isJa ? "一段目の切り" : "first-row cuts"} ${item.first_row_cut_rate == null ? "n/a" : pct(item.first_row_cut_rate)} · ${isJa ? "中央値" : "median turn"} ${fmt.format(item.median_cut_turn ?? 0)}</small>
    `;
    target.append(card);
  }
}

function defenseTargetLabel(key) {
  const labels = isJa
    ? {
        dealer_riichi: "親リーチ",
        dealer_open: "親の副露",
        dealer_closed: "親の門前河",
        closed_riichi: "子のリーチ",
        nondealer_open: "子の副露",
        nondealer_closed: "子の門前河",
      }
    : {
        dealer_riichi: "Dealer riichi",
        dealer_open: "Dealer open hand",
        dealer_closed: "Dealer closed river",
        closed_riichi: "Non-dealer riichi",
        nondealer_open: "Non-dealer open hand",
        nondealer_closed: "Non-dealer closed river",
      };
  return labels[key] || key;
}

function renderDefenseTargets(targets) {
  const target = document.querySelector("#defenseTargets");
  const data = targets?.overall || {};
  if (!target || !Object.keys(data).length) return;
  target.innerHTML = "";
  const order = ["dealer_riichi", "dealer_open", "dealer_closed", "closed_riichi", "nondealer_open", "nondealer_closed"];
  for (const key of order) {
    const item = data[key];
    const kept = item?.kept_instances || item?.instances || 0;
    const spent = item?.spent_instances || 0;
    const total = item?.total_instances || kept + spent;
    if (!total) continue;
    const keptShare = item.kept_share ?? (total ? kept / total : null);
    const spentShare = item.spent_share ?? (total ? spent / total : null);
    const keptAvgLeft = item.kept_avg_left ?? item.avg_left;
    const spentAvgLeft = item.spent_avg_left;
    const leftText = keptAvgLeft == null
      ? ""
      : spentAvgLeft == null
        ? isJa
          ? ` · 保持時平均残り${fmt.format(keptAvgLeft)}枚`
          : ` · kept avg ${fmt.format(keptAvgLeft)} tiles left`
        : isJa
          ? ` · 平均残り 保持${fmt.format(keptAvgLeft)} / 使用${fmt.format(spentAvgLeft)}枚`
          : ` · avg left kept ${fmt.format(keptAvgLeft)} / spent ${fmt.format(spentAvgLeft)}`;
    const card = document.createElement("div");
    card.className = "evidence-card";
    card.innerHTML = `
      <b>${escapeHtml(defenseTargetLabel(key))}</b>
      <strong>${keptShare == null ? whole.format(kept) : pct(keptShare)}</strong>
      <span>${isJa ? "安全牌を保持" : "safe-targets kept"} · ${whole.format(kept)} ${isJa ? "保持" : "kept"} / ${whole.format(spent)} ${isJa ? "使用" : "spent"}</span>
      <small>${isJa ? "使用率" : "spent share"} ${spentShare == null ? "n/a" : pct(spentShare)} · ${isJa ? "保持現物" : "kept genbutsu"} ${whole.format(item.kept_genbutsu || item.genbutsu || 0)} · ${isJa ? "使用現物" : "spent genbutsu"} ${whole.format(item.spent_genbutsu || 0)}${leftText}</small>
    `;
    target.append(card);
  }
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
  if (isJa) {
    if (tileNamesJa[base]) return tileNamesJa[base];
    const suitNames = { m: "萬", p: "筒", s: "索" };
    const numberNames = { 1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九" };
    if (/^[1-9][mps]$/.test(base)) {
      const name = `${numberNames[base[0]]}${suitNames[base[1]]}`;
      return key.includes("r") ? `赤${name}` : name;
    }
  }
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
  span.className = `tiles hand-tiles${tileFontClassSuffix}`;
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
  return `<span class="tiles ${tileFontClassPrefix}${className}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${escapeHtml(tileCode(tile))}</span>`;
}

function applyTileCompatibility(root = document) {
  if (!tileFontClass) return;
  root.querySelectorAll(".tiles").forEach((el) => el.classList.add(tileFontClass));
}

function shortTiles(items) {
  if (!items || !items.length) return t("none");
  return tileNamesText(items.slice(0, 12));
}

function dangerText(value) {
  return value == null ? "n/a" : pct(value);
}

function safetyKindLabel(kind) {
  if (isJa) {
    if (kind === "genbutsu") return "現物";
    if (kind === "suji") return "筋";
    return "なし";
  }
  if (kind === "genbutsu") return "river-safe";
  if (kind === "suji") return "suji";
  return "none";
}

function safetySourceText(source) {
  return isJa ? `${tileName(source.tile)} 河${source.position}枚目` : `${tileName(source.tile)} at river slot ${source.position}`;
}

function safetyReadLine(read) {
  if (!read || !read.kind) return "";
  const target = read.against?.[0];
  const sourceList = target?.genbutsu_sources?.length ? target.genbutsu_sources : target?.suji_sources || [];
  const sourceText = sourceList.length ? (isJa ? `、見え方 ${sourceList.map(safetySourceText).join("、")}` : ` via ${sourceList.map(safetySourceText).join(", ")}`) : "";
  const threatText = target?.reached
    ? isJa
      ? " / リーチ"
      : " / riichi"
    : target?.open_melds
      ? isJa
        ? ` / ${target.open_melds}副露`
        : ` / ${target.open_melds} call${target.open_melds === 1 ? "" : "s"}`
      : "";
  return isJa
    ? `${tileName(read.tile)} は ${seatLabel(target?.seat_label)} に対して ${safetyKindLabel(read.kind)}${threatText}${sourceText}`
    : `${tileName(read.tile)} is ${safetyKindLabel(read.kind)} to ${seatLabel(target?.seat_label)}${threatText}${sourceText}`;
}

function safetySummary(safety) {
  if (!safety || !safety.total) return "";
  const parts = [];
  if (safety.genbutsu) parts.push(isJa ? `現物 ${safety.genbutsu}` : `${safety.genbutsu} river-safe`);
  if (safety.suji) parts.push(isJa ? `筋 ${safety.suji}` : `${safety.suji} suji`);
  if (safety.against_threat) parts.push(isJa ? `脅威相手 ${safety.against_threat}` : `${safety.against_threat} vs live threat`);
  return parts.join(isJa ? "、" : ", ");
}

function safetyPanel(read) {
  if (!read || !read.kind) return document.createDocumentFragment();
  const block = document.createElement("div");
  block.className = "safety-read";
  const rows = (read.against || [])
    .map((item) => {
      const sourceList = item.genbutsu_sources?.length ? item.genbutsu_sources : item.suji_sources || [];
      const sources = sourceList.map((source) => `${tileIcon(source.tile, "inline-tile")} ${isJa ? `河${source.position}枚目` : `slot ${source.position}`}`).join(", ");
      const threat = item.reached
        ? isJa
          ? "リーチ"
          : "riichi"
        : item.open_melds
          ? isJa
            ? `${item.open_melds}副露`
            : `${item.open_melds} call${item.open_melds === 1 ? "" : "s"}`
          : isJa
            ? "宣言された脅威なし"
            : "no declared threat";
      return `<li><b>${escapeHtml(seatLabel(item.seat_label))}</b><span>${escapeHtml(safetyKindLabel(item.kind))} / ${escapeHtml(threat)} / ${sources}</span></li>`;
    })
    .join("");
  block.innerHTML = `
    <p><b>${isJa ? "残した守備牌" : "Kept defensive tile"}:</b> ${tileIcon(read.tile, "inline-tile")} ${escapeHtml(tileName(read.tile))} / ${escapeHtml(safetyKindLabel(read.kind))}</p>
    <ul>${rows}</ul>
  `;
  return block;
}

function tileIcons(items, className = "mini-tile") {
  const list = (items || []).filter(Boolean);
  if (!list.length) return `<span class="empty">${escapeHtml(t("none"))}</span>`;
  return list.map((tile) => tileIcon(tile, className)).join("");
}

function tileRun(items, className = "", emptyLabel = t("none")) {
  const list = (items || []).filter(Boolean);
  if (!list.length) return emptyLabel ? `<span class="empty">${escapeHtml(emptyLabel)}</span>` : "";
  const label = tileNamesText(list);
  return `<span class="tiles ${tileFontClassPrefix}${className}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${list
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
  if (!melds || !melds.length) return `<span class="empty">${escapeHtml(t("none"))}</span>`;
  return melds
    .map((meld) => `<span class="meld">${tileIcons(meld.split(" ").filter(Boolean), "mini-tile")}</span>`)
    .join("");
}

function seatLabel(seat) {
  const labels = isJa
    ? {
        self: "LuckyJ",
        shimocha: "下家",
        toimen: "対面",
        kamicha: "上家",
      }
    : {
    self: "LuckyJ",
    shimocha: "Shimocha",
    toimen: "Toimen",
    kamicha: "Kamicha",
      };
  return labels[seat] || seat;
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
      const name = `${seatLabel(player.seat)}${score.rank ? ` / ${rankText(score.rank)}` : ""}`;
      const melds = (player.melds || []).length
        ? `<div class="table-melds">${(player.melds || [])
            .map((meld) => `<span class="meld-run">${tileRun(meld.split(" "))}</span>`)
            .join("")}</div>`
        : "";
      const review = player.seat === "self" ? "" : `<span class="review-tag">${isJa ? "復習" : "review"}</span>`;
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
              <div class="round-container"><div class="round">${escapeHtml(roundText(table.round || ""))}</div></div>
              <div class="dora-indicator">${t("dora")}: ${tileRun(table.dora_markers || [])}</div>
            </div>
            ${scores}
          </div>
          ${hands}
          ${rivers}
        </div>
      </div>
      <div class="caption-text">${escapeHtml(t("reviewCaption"))}</div>
    </div>
  `;
  return wrap;
}

function renderGuideBlock(guide) {
  const block = document.createElement("div");
  block.className = "natsu-analysis";
  const rows = [
    [t("situation"), guide?.situation],
    [t("seeing"), guide?.read],
    [t("whyTempting"), guide?.whyNot],
    [t("copyIt"), guide?.copy],
    [t("limit"), guide?.limit],
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
  if (!action) return t("noModelAction");
  if (action.type === "dahai" && action.tile) {
    return `${t("discard")} ${tileIcon(action.tile, "discard-tile")} <em>${escapeHtml(tileName(action.tile))}</em>`;
  }
  if (action.type === "reach") {
    if (action.tile) {
      return `${t("reach")}, ${t("discard").toLowerCase()} ${tileIcon(action.tile, "discard-tile")} <em>${escapeHtml(tileName(action.tile))}</em>`;
    }
    return t("reach");
  }
  if (["chi", "pon", "daiminkan", "ankan", "kakan"].includes(action.type)) {
    const tile = action.tile ? ` ${tileIcon(action.tile, "discard-tile")} <em>${escapeHtml(tileName(action.tile))}</em>` : "";
    const label = {
      chi: t("chi"),
      pon: t("pon"),
      daiminkan: t("openKan"),
      ankan: t("closedKan"),
      kakan: t("addedKan"),
    }[action.type];
    return `${label || escapeHtml(action.type)}${tile}`;
  }
  return escapeHtml(action.label || action.type || t("noModelAction"));
}

function agreementBadge(label, value) {
  if (value == null) return "";
  return `<span class="model-badge ${value ? "agree" : "split"}">${escapeHtml(label)} ${value ? t("agrees") : t("splits")}</span>`;
}

function probabilityChip(label, value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return `<span class="choice-weight">${escapeHtml(label)} ${pct(numeric)}</span>`;
}

function renderMortalBlock(mortal, pointKey, mortalCopy) {
  if (!mortal) return document.createDocumentFragment();
  const localMortal = mortalCopy?.[pointKey] || {};
  const block = document.createElement("section");
  block.className = "mortal-block";
  const topCandidate = mortal.top_candidates?.[0];
  const branch =
    mortal.post_call_mortal
      ? `
        <div class="mortal-branch">
          <h5>${t("afterCall")}</h5>
          <p>${
            isJa ? "Mortal の条件付き打牌は" : "Mortal's conditional discard is"
          } ${modelActionLine(mortal.post_call_mortal)} ${agreementBadge(t("postCallDiscard"), mortal.post_call_agrees_luckyj)}</p>
        </div>
      `
      : "";
  block.innerHTML = `
    <div class="mortal-head">
      <p class="kicker">${t("mortalCrossCheck")}</p>
    </div>
    <div class="mortal-grid">
      <div class="decision mortal-choice-card">
        <b>${t("mortalTop")}</b>
        ${probabilityChip(t("mortalWeight"), topCandidate?.probability)}
        <span class="discard-line">${modelActionLine(mortal.mortal)}</span>
        <div class="model-badges">
          ${agreementBadge("LuckyJ", mortal.mortal_agrees_luckyj)}
          ${agreementBadge("NAGA", mortal.mortal_agrees_naga)}
        </div>
      </div>
      <div>
        <h5>${t("readingSplit")}</h5>
        <p>${escapeHtml(localMortal.read || mortal.read)}</p>
        <p>${escapeHtml(localMortal.how_to_use || mortal.how_to_use)}</p>
      </div>
    </div>
    ${branch}
  `;
  return block;
}

function renderYakuhaiCleanupNote(example) {
  const threats = example.yakuhai_cleanup?.threats || [];
  if (!threats.length) return document.createDocumentFragment();
  const block = document.createElement("div");
  block.className = "yaku-condition-read";
  const heading = isJa ? "役牌読み" : "Yaku-Condition Read";
  const body = isJa
    ? `${tileIcon(example.actual, "inline-tile")} <b>${escapeHtml(tileName(example.actual))}</b> は、まだ役を見せていない副露手に対して生きている役牌です。相手の役になる前に LuckyJ が先に処理しています。`
    : `${tileIcon(example.actual, "inline-tile")} <b>${escapeHtml(tileName(example.actual))}</b> is live yakuhai against an open hand that has not shown its yaku. LuckyJ cleans it before it can become the opponent's yaku condition.`;
  const windLabel = isJa ? "風" : "wind";
  const threatRows = threats
    .map(
      (threat) => `
        <span>
          <b>${escapeHtml(seatLabel(threat.seat))}</b>
          <em>${tileIcon(threat.wind, "inline-tile")} ${windLabel}</em>
          ${meldIcons(threat.melds)}
        </span>
      `
    )
    .join("");
  block.innerHTML = `
    <h5>${heading}</h5>
    <p>${body}</p>
    <div class="yaku-condition-threats">${threatRows}</div>
  `;
  return block;
}

function renderPointExamples(examples, guides, mortalPoints, mortalCopy) {
  for (const placeholder of document.querySelectorAll("[data-example]")) {
    const pointKey = placeholder.dataset.example;
    const example = examples[pointKey];
    if (!example) continue;
    const guide = guides?.[pointKey];
    const card = document.createElement("article");
    card.className = "point-example-card";
    card.innerHTML = `
      <div class="example-head">
        <div>
          <p class="kicker">${t("replayExample")}</p>
          <h4>${escapeHtml(guide?.caption || example.title)}</h4>
        </div>
        <span>${isJa ? `ゲーム ${example.game}、${escapeHtml(roundText(example.round))}、${tilesLeftText(example.left)}` : `Game ${example.game}, ${escapeHtml(example.round)}, ${tilesLeftText(example.left)}`}</span>
      </div>
      <p class="case-meta">${escapeHtml(stageText(example.stage))} / ${escapeHtml(scoreBandText(example.score_band))} / ${t("finalRank")} ${rankText(example.rank)}</p>
    `;
    card.append(renderMahjongTable(example.table));

    if (example.kind === "call") {
      const line = document.createElement("div");
      line.className = "call-line";
      line.innerHTML = `
        <span>${t("call")} ${escapeHtml(example.call)} ${tileIcon(example.called_tile, "discard-tile")} ${isJa ? "を" : "on"} ${escapeHtml(seatLabel(example.called_from))}${isJa ? "から" : ""}</span>
        <span>${t("meld")} ${tileIcons(example.post_call_meld?.split(" "), "mini-tile")}</span>
        <span>${t("discardAfterCall")} ${tileIcon(example.discard_after_call, "discard-tile")}</span>
      `;
      card.append(line);
    } else {
      const choices = document.createElement("div");
      choices.className = "comparison";
      if (example.actual_eval && example.naga_eval) {
        choices.append(
          comparison(t("luckyj"), example.actual_eval, example.actual_danger, example.actual_prob),
          comparison(t("nagaTop"), example.naga_eval, example.naga_danger, example.naga_prob)
        );
      } else {
        choices.innerHTML = `
          <div class="decision"><b>${t("luckyj")}</b>${probabilityChip(t("nagaWeight"), example.actual_prob)}<span class="discard-line">${t("discard")} ${tileIcon(example.actual, "discard-tile")} <em>${escapeHtml(tileName(example.actual))}</em></span><span>${t("danger")} ${dangerText(example.actual_danger)}</span></div>
          <div class="decision"><b>${t("nagaTop")}</b>${probabilityChip(t("nagaWeight"), example.naga_prob)}<span class="discard-line">${t("discard")} ${tileIcon(example.naga, "discard-tile")} <em>${escapeHtml(tileName(example.naga))}</em></span><span>${t("danger")} ${dangerText(example.naga_danger)}</span></div>
        `;
      }
      card.append(choices);
      card.append(safetyPanel(example.kept_tile_safety));
    }
    card.append(renderYakuhaiCleanupNote(example));
    card.append(renderMortalBlock(mortalPoints?.[pointKey], pointKey, mortalCopy));
    card.append(renderGuideBlock(guide));

    const drill = document.createElement("div");
    drill.className = "example-drill";
    drill.innerHTML = `
      <p><b>${t("drill")}:</b> ${escapeHtml(guide?.prompt || example.prompt)}</p>
      <p><b>${t("answer")}:</b> ${escapeHtml(guide?.answer || example.answer)}</p>
    `;

    const links = document.createElement("p");
    links.className = "case-links";
    links.innerHTML = `<a href="${example.report}">${t("nagaReport")}</a> <a href="${example.paifu}">${t("tenhouLog")}</a>`;

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
  if (isJa) {
    const suitNames = { m: "萬子", p: "筒子", s: "索子" };
    if (dominant && dominant[1] >= 6) fragments.push(`${suitNames[dominant[0]]}が厚い形`);
    if (pairs >= 3) fragments.push(`${pairs}組の対子候補`);
    if (suits.honor >= 2) fragments.push(`字牌${suits.honor}枚`);
    if (red) fragments.push(`赤ドラ${red}枚`);
    return fragments.length ? fragments.join("、") : "普通の混合形";
  }
  if (dominant && dominant[1] >= 6) fragments.push(`heavy ${dominant[0]}-suit shape`);
  if (pairs >= 3) fragments.push(`${pairs} pair-like anchors`);
  if (suits.honor >= 2) fragments.push(`${suits.honor} honors`);
  if (red) fragments.push(`${red} red five${red === 1 ? "" : "s"}`);
  return fragments.length ? fragments.join(", ") : "mixed ordinary blocks";
}

function dangerRead(actual, naga) {
  if (isJa) {
    if (actual == null || naga == null) return "危険度を比べにくい局面なので、ルートと点数状況を中心に読む。";
    const gap = actual - naga;
    if (Math.abs(gap) < 0.03) return "即時危険度は近く、この不一致は単純な安全牌比較よりもルート選択の問題に近い。";
    if (gap < 0) return `LuckyJ は約 ${fmt.format(Math.abs(gap) * 100)} ポイント分の危険を避け、安全側に寄せている。`;
    return `LuckyJ は約 ${fmt.format(gap * 100)} ポイント分の追加危険を受け入れているため、価値、圧力、着順価値の具体的な見返りが必要になる。`;
  }
  if (actual == null || naga == null) return "There is no clean danger comparison here, so read the hand through route and score logic.";
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
  if (isJa) {
    if (key === "early_safety_hedge") {
      return `序盤の LuckyJ は ${actualName} を、未来の選択肢を最も壊しにくい牌として扱っている。場が答えを出すまで、安全、価値、ルートを残す読みである。`;
    }
    if (key === "middle_route_hedge") {
      return `中盤では手牌が価値を証明し始める必要がある。LuckyJ の ${actualName} 切りは、NAGA ラインが点数状況や河に対して脆い一本道へ寄せすぎる可能性を示している。`;
    }
    if (key === "kept_river_safe") {
      return `NAGA が切りたい ${nagaName} を LuckyJ は残している。その牌は相手の河にあり、後のリーチや副露に対する現物の出口になる。`;
    }
    if (key === "kept_suji_exit") {
      return `NAGA が切りたい ${nagaName} を LuckyJ は残している。その牌は相手の河から筋で読めるため、完全な現物ではなくても後の押し引きに使える。`;
    }
    if (key === "safer_than_naga") {
      return "攻めている手の中で安全側に寄せている。LuckyJ は必ずしも降りていない。より危険な NAGA 牌をすぐに切らず、手を生かすラインを選んでいる。";
    }
    if (key === "riskier_than_naga") {
      return "これは真似するハードルが高い例である。LuckyJ は今の危険を払うが、残すルートが安全そうな代替より明確に良い場合に限られる。";
    }
    if (key === "late_tightening") {
      return "終盤では投機的な形の価値はかなり落ちる。和了、安全なテンパイ、降りを数える精密問題として読む。";
    }
    return `LuckyJ は ${tileClassText(actualClass)} の ${actualName} を切り、NAGA は ${tileClassText(nagaClass)} の ${nagaName} を切る。最初の問いは、どちらの牌がどの未来を守っているかである。`;
  }
  if (key === "early_safety_hedge") {
    return `Early in the hand, LuckyJ is treating ${actualName} as the tile that least damages the future menu. The idea is to delay commitment while keeping enough safety and value material to choose again after the table speaks.`;
  }
  if (key === "middle_route_hedge") {
    return `In the middle row, the hand has to start proving itself. LuckyJ's ${actualName} discard suggests that the NAGA line compresses the hand into a route that is too brittle for the score and river state.`;
  }
  if (key === "kept_river_safe") {
    return `NAGA wants to cut ${nagaName}, but LuckyJ keeps it because it is already visible in an opponent river. That retained genbutsu is an exit for the next riichi or open-hand threat.`;
  }
  if (key === "kept_suji_exit") {
    return `NAGA wants to cut ${nagaName}, but LuckyJ keeps it because opponent rivers make it suji. Treat it as a timed defensive resource, weaker than genbutsu but still useful in the right spot.`;
  }
  if (key === "safer_than_naga") {
    return `This is a safety purchase inside an attacking hand. LuckyJ is not necessarily folding; it is choosing the line that keeps the hand alive without immediately throwing the more dangerous NAGA tile.`;
  }
  if (key === "riskier_than_naga") {
    return `Copy this only with care. LuckyJ is paying danger now because the kept route has to be clearly better than the safer-looking choice.`;
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
  const safetyLine = safetyReadLine(item.kept_safety);
  if (isJa) {
    const lines = [
      `${roundText(item.round)}、残り${item.left}枚、${scoreBandText(item.score_band)}。手牌の質: ${handTexture(item.hand)}。LuckyJ は ${actualName} (${tileClassText(actualClass)}) を切り、NAGA は ${nagaName} (${tileClassText(nagaClass)}) を切る。`,
      categoryRead(key, item),
      dangerRead(item.actual_danger, item.naga_danger),
      "復習ドリル: 診断を見る前に、LuckyJ が何を残そうとしているかを書く。安全、価値、ルート数、圧力、着順のどれかを言えないなら、まだその打牌はコピーしない。",
    ];
    if (safetyLine) lines.splice(2, 0, safetyLine);
    return lines;
  }
  const lines = [
    `${item.round}, ${item.left} tiles left, ${item.score_band}. Hand texture: ${handTexture(item.hand)}. LuckyJ cuts ${actualName} (${actualClass}); NAGA cuts ${nagaName} (${nagaClass}).`,
    categoryRead(key, item),
    dangerRead(item.actual_danger, item.naga_danger),
    `Review drill: before looking at the diagnostics, write what LuckyJ is buying: safety, value, route count, pressure, or placement. If you cannot name the purchase, do not copy the move yet.`,
  ];
  if (safetyLine) lines.splice(2, 0, safetyLine);
  return lines;
}

function comparison(label, item, danger, probability) {
  const el = document.createElement("div");
  el.className = "decision";
  const keptSafety = safetySummary(item.kept_safety);
  const actionLine = item.declares_reach
    ? `${t("reach")}, ${t("discard").toLowerCase()} ${tileIcon(item.discard, "discard-tile")} <em>${escapeHtml(tileName(item.discard))}</em>`
    : `${t("discard")} ${tileIcon(item.discard, "discard-tile")} <em>${escapeHtml(tileName(item.discard))}</em>`;
  el.innerHTML = `
    <b>${label}</b>
    ${probabilityChip(t("nagaWeight"), probability)}
    <span class="discard-line">${actionLine}</span>
    <span>${t("immediateDanger")} ${danger == null ? "n/a" : pct(danger)}</span>
    <span>${t("keeps")} ${item.kept_honors} ${t("honors")}, ${item.kept_terminals} ${t("terminals")}</span>
    ${keptSafety ? `<span>${isJa ? "守備の出口" : "Defensive exits"} ${escapeHtml(keptSafety)}</span>` : ""}
    <details class="diagnostics">
      <summary>${t("mechanicalDiagnostic")}</summary>
      <span>${item.shanten} ${t("shanten")}</span>
      <span>${whole.format(item.ukeire)} ${t("visibleUkeire")}</span>
      <small>${t("effective")}: ${shortTiles(item.effective)}</small>
    </details>
  `;
  return el;
}

function renderCases(data) {
  const tabs = document.querySelector("#caseTabs");
  const grid = document.querySelector("#caseGrid");
  if (!tabs || !grid) return;

  const labels = isJa
    ? {
        early_safety_hedge: "序盤の保留",
        middle_route_hedge: "中盤のルート保留",
        kept_river_safe: "現物キープ",
        kept_suji_exit: "筋キープ",
        safer_than_naga: "安全寄せ",
        riskier_than_naga: "押し返し",
        late_tightening: "終盤の読み",
      }
    : {
        early_safety_hedge: "Early Hedges",
        middle_route_hedge: "Middle Hedges",
        kept_river_safe: "River-Safe Keeps",
        kept_suji_exit: "Suji Keeps",
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
          <p class="kicker">${stageText(item.stage)} / ${scoreBandText(item.score_band)}</p>
          <h3>${caseLabelText(item.label)}</h3>
        </div>
        <span>${roundText(item.round)}, ${tilesLeftText(item.left)}</span>
      `;

      const body = document.createElement("div");
      body.className = "case-body";
      const handTitle = document.createElement("p");
      handTitle.className = "case-meta";
      handTitle.textContent = gameLine(item.game, item.rank, item.score);
      body.append(handTitle, tiles(item.hand));
      body.append(safetyPanel(item.kept_safety));

      const choices = document.createElement("div");
      choices.className = "comparison";
      choices.append(
        comparison(t("luckyj"), item.actual_eval, item.actual_danger, item.actual_prob_min),
        comparison(t("nagaTop"), item.naga_eval, item.naga_danger, item.naga_prob_max)
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
      links.innerHTML = `<a href="${item.report}">${t("nagaReport")}</a> <a href="${item.paifu}">${t("tenhouLog")}</a>`;

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

function renderPointValidation(validation) {
  const summary = document.querySelector("#validationSummary");
  const grid = document.querySelector("#pointValidation");
  const points = validation?.points || [];

  if (summary && validation?.summary && validation?.method) {
    const strong = validation.summary.strong || 0;
    const qualified = validation.summary.qualified || 0;
    const decisions = validation.method.eligible_decisions || validation.method.book_decisions;
    summary.innerHTML = `
      <div class="stat-strip">
        <span><b>${whole.format(validation.summary.total || points.length)}</b>${isJa ? "検証ポイント" : "validated points"}</span>
        <span><b>${whole.format(strong)}</b>${isJa ? "強い" : "strong"}</span>
        <span><b>${whole.format(qualified)}</b>${isJa ? "条件付き" : "qualified"}</span>
        <span><b>${whole.format(decisions || 0)}</b>${isJa ? "判断母数" : "decision base"}</span>
      </div>
    `;
  }

  if (!grid || !points.length) return;
  grid.innerHTML = "";
  for (const item of points) {
    const card = document.createElement("article");
    card.className = `validation-card ${escapeHtml(item.strength || "qualified")}`;
    const stats = (item.stats || [])
      .map((stat) => `<li>${escapeHtml(isJa ? stat.text_ja || stat.text : stat.text)}</li>`)
      .join("");
    card.innerHTML = `
      <div class="validation-head">
        <span>${escapeHtml(item.id.replace("point-", ""))}</span>
        <b>${escapeHtml(isJa ? item.category_ja : item.category)}</b>
        <em>${escapeHtml(isJa ? item.verdict_ja : item.verdict)}</em>
      </div>
      <h3>${escapeHtml(isJa ? item.title_ja : item.title)}</h3>
      <p>${escapeHtml(isJa ? item.read_ja : item.read)}</p>
      <ul>${stats}</ul>
      <div class="validation-example">
        <strong>${isJa ? "実戦チェック" : "Table check"}</strong>
        <span>${escapeHtml(isJa ? item.example_ja : item.example)}</span>
      </div>
      <p class="validation-caveat">${escapeHtml(isJa ? item.caveat_ja : item.caveat)}</p>
    `;
    grid.append(card);
  }
}

async function main() {
  applyTileCompatibility();
  const guidePath = isJa ? "strategy-guides.ja.json" : "strategy-guides.json";
  const [bookResponse, caseResponse, exampleResponse, guideResponse, mortalResponse, mortalCopy, validation] = await Promise.all([
    fetch("book-data.json"),
    fetch("case-studies.json"),
    fetch("point-examples.json"),
    fetch(guidePath),
    fetch("mortal-analysis.json"),
    isJa ? fetchJson("mortal-analysis.ja.json", {}) : Promise.resolve({}),
    fetchJson("point-validation.json", {}),
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
  if (metrics) {
    metrics.append(
      metric(t("analyzedHanchan"), fmt.format(summary.games)),
      metric(t("handsReviewed"), fmt.format(summary.hands)),
      metric(t("averagePlacement"), fmt.format(summary.avg_rank)),
      metric(t("averageScore"), `+${fmt.format(summary.avg_score)}`),
      metric(t("winRate"), pct(summary.win_rate_per_hand)),
      metric(t("dealInRate"), pct(summary.deal_in_rate_per_hand)),
      metric(t("topHalfWins"), fmt.format(top.wins_per_game)),
      metric(t("bottomHalfDealIns"), fmt.format(bottom.deal_ins_per_game))
    );
  }

  const stage = data.decision_counters.stage;
  const chart = document.querySelector("#stageChart");
  if (chart) {
    for (const key of ["early", "middle", "late"]) {
      const item = stage[key];
      chart.append(bar(`${stageText(key)} ${t("mismatch")}`, item.mismatch / item.decisions));
      chart.append(bar(`${stageText(key)} ${t("bad")}`, item.bad / item.decisions));
    }
  }
  renderDefenseTiming(data.decision_counters.defense_retention);
  renderYakuhaiPressure(data.decision_counters.yakuhai_pressure);
  renderDefenseTargets(data.decision_counters.defense_targets);

  renderPointValidation(validation);
  renderPointExamples(examples, guides, mortal.points, mortalCopy);
  renderCases(caseData);
  applyTileCompatibility();
}

main().catch((error) => {
  const metrics = document.querySelector("#metrics");
  if (metrics) {
    metrics.innerHTML = `<div class="metric"><b>${t("dataLoadFailed")}</b><span>${error.message}</span></div>`;
  }
});
