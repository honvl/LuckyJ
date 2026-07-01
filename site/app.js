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
const modelNames = {
  en: { nishiki: "Nishiki", hibakari: "Hibakari", kagashi: "Kagashi" },
  ja: { nishiki: "ニシキ", hibakari: "ヒバカリ", kagashi: "カガシ" },
};
const pointRailFallbackLabels = {
  en: [
    "Start with the placement problem.",
    "Combine chances until the table forces a commitment.",
    "Bad shapes favor opening, but only with a plan.",
    "Every open call increases the price of safe tiles.",
    "Throw dangerous floating tiles before they become your problem.",
    "Value planning starts while the hand is still far away.",
    "Call for tempo, denial, survival, and hand completion.",
    "Riichi is a pressure tool.",
    "Push-fold is recalculated every draw.",
    "Late hands tighten: fewer deviations, fewer bad moves.",
    "Drawn-hand points are part of the attack plan.",
    "Use NAGA match rate as a review cue.",
    "Cut live yakuhai earlier when an open hand's yaku is unproven.",
    "Keep genbutsu and suji tiles on purpose.",
    "Safe tiles expire when they stop defending the current danger.",
    "Late outside cuts can preserve the winning route.",
    "A kept genbutsu or suji tile must name its target.",
    "Name the honor's job: value, yaku condition, dead tile, or safety.",
    "Leader safety still has to calculate.",
  ],
};
const pointExampleControllers = new Map();

function setupRetractingTopbar() {
  const topbar = document.querySelector(".topbar");
  if (!topbar || !window.matchMedia) return;

  const touchQuery = window.matchMedia("(hover: none), (pointer: coarse), (max-width: 900px)");
  const revealAtTop = 28;
  const minScrollDelta = 8;
  let enabled = false;
  let ticking = false;
  let lastScrollY = Math.max(window.scrollY || window.pageYOffset || 0, 0);

  function setRetracted(retracted) {
    topbar.classList.toggle("is-retracted", retracted);
  }

  function update() {
    ticking = false;
    if (!enabled) return;

    const scrollY = Math.max(window.scrollY || window.pageYOffset || 0, 0);
    const delta = scrollY - lastScrollY;

    if (scrollY <= revealAtTop || topbar.matches(":focus-within")) {
      setRetracted(false);
    } else if (Math.abs(delta) >= minScrollDelta) {
      setRetracted(delta > 0);
    }

    lastScrollY = scrollY;
  }

  function scheduleUpdate() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  }

  function syncMode() {
    enabled = touchQuery.matches;
    topbar.classList.toggle("can-touch-retract", enabled);
    if (!enabled) {
      setRetracted(false);
      return;
    }
    lastScrollY = Math.max(window.scrollY || window.pageYOffset || 0, 0);
    scheduleUpdate();
  }

  window.addEventListener("scroll", scheduleUpdate, { passive: true });
  window.addEventListener("resize", scheduleUpdate);
  topbar.addEventListener("focusin", () => setRetracted(false));

  if (touchQuery.addEventListener) {
    touchQuery.addEventListener("change", syncMode);
  } else if (touchQuery.addListener) {
    touchQuery.addListener(syncMode);
  }

  syncMode();
}

function normalizePointKey(value) {
  const raw = String(value || "").trim();
  const match = raw.match(/^point-(\d{1,2})$/i) || raw.match(/^(\d{1,2})$/);
  if (!match) return "";
  const number = Number.parseInt(match[1], 10);
  if (!Number.isFinite(number) || number < 1) return "";
  return `point-${String(number).padStart(2, "0")}`;
}

function parseExampleIndex(value) {
  if (value === undefined || value === null || value === "") return null;
  const number = Number.parseInt(String(value), 10);
  return Number.isFinite(number) && number > 0 ? number - 1 : null;
}

function parsePointExampleLocation() {
  const search = new URLSearchParams(window.location.search);
  let rawHash = String(window.location.hash || "").replace(/^#/, "");
  try {
    rawHash = decodeURIComponent(rawHash);
  } catch {
    rawHash = "";
  }
  const hashMatch = rawHash.match(/^point-(\d{1,2})(?:-(?:example|ex)-?(\d{1,2}))?$/i);
  const pointKey = hashMatch ? normalizePointKey(`point-${hashMatch[1]}`) : normalizePointKey(search.get("point"));
  const exampleIndex = hashMatch?.[2] ? parseExampleIndex(hashMatch[2]) : parseExampleIndex(search.get("example"));
  return { pointKey, exampleIndex };
}

function clampExampleIndex(index, total) {
  const number = Number.isFinite(index) ? index : 0;
  return Math.max(0, Math.min(total - 1, number));
}

function exampleAnchorId(pointKey, index) {
  return `${pointKey}-example-${String(index + 1).padStart(2, "0")}`;
}

function writeExampleLocation(pointKey, index) {
  if (!window.history?.pushState) return;
  const url = new URL(window.location.href);
  url.searchParams.delete("point");
  url.searchParams.delete("example");
  url.hash = exampleAnchorId(pointKey, index);
  if (url.href === window.location.href) return;
  window.history.pushState({}, "", url);
}

function syncPointExamplesFromLocation({ scroll = false } = {}) {
  const target = parsePointExampleLocation();
  if (!target.pointKey) return;
  const controller = pointExampleControllers.get(target.pointKey);
  if (!controller) return;
  const index = target.exampleIndex === null ? 0 : clampExampleIndex(target.exampleIndex, controller.total);
  controller.show(index, { updateLocation: false });
  if (!scroll) return;
  requestAnimationFrame(() => {
    const anchor = target.exampleIndex === null ? target.pointKey : exampleAnchorId(target.pointKey, index);
    const element = document.getElementById(anchor) || document.getElementById(target.pointKey);
    element?.scrollIntoView({ block: "start" });
  });
}

function modelName(keyOrLabel) {
  const raw = String(keyOrLabel || "");
  const key = raw.toLowerCase();
  return modelNames[pageLang]?.[key] || modelNames.en[key] || raw;
}

function renderPointRail() {
  if (document.querySelector(".point-rail")) return;
  const sections = Array.from(document.querySelectorAll(".point[id^='point-']")).filter((section) =>
    /^point-\d{2}$/.test(section.id)
  );
  const hasLocalPoints = sections.length > 0;
  const points = hasLocalPoints
    ? sections.map((section) => {
        const number = section.querySelector(".point-number")?.textContent.trim() || section.id.replace("point-", "");
        const heading = section.querySelector("h3")?.textContent.trim() || "";
        return { href: `#${section.id}`, id: section.id, number, title: heading, section };
      })
    : Array.from({ length: 19 }, (_, index) => {
        const number = String(index + 1).padStart(2, "0");
        return {
          href: `points.html#point-${number}`,
          id: `point-${number}`,
          number,
          title: pointRailFallbackLabels[pageLang]?.[index] || "",
          section: null,
        };
      });

  if (!points.length) return;

  const rail = document.createElement("nav");
  rail.className = "point-rail";
  rail.setAttribute("aria-label", isJa ? "ポイント索引" : "Point index");
  rail.setAttribute("aria-controls", "point-rail-panel");

  const panel = document.createElement("div");
  panel.className = "point-rail-panel";
  panel.id = "point-rail-panel";
  panel.setAttribute("aria-label", isJa ? "ポイント一覧" : "Point list");
  const panelList = document.createElement("ol");
  panel.append(panelList);

  const railLinks = points.map((point) => {
    const link = document.createElement("a");
    link.href = point.href;
    link.textContent = point.number;
    if (point.title) {
      link.setAttribute("aria-label", `${point.number} ${point.title}`);
      link.dataset.label = point.title;
    }
    link.dataset.point = point.id;
    rail.append(link);
    return link;
  });

  const panelLinks = points.map((point) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    const number = document.createElement("b");
    const label = document.createElement("span");

    link.href = point.href;
    link.dataset.point = point.id;
    number.textContent = point.number;
    label.textContent = point.title || point.number;

    link.append(number, label);
    item.append(link);
    panelList.append(item);
    return link;
  });

  const links = [...railLinks, ...panelLinks];

  document.body.append(rail, panel);

  if (!hasLocalPoints) return;

  function setActive(id) {
    for (const link of links) {
      const selected = link.dataset.point === id;
      link.classList.toggle("is-active", selected);
      if (selected) {
        link.setAttribute("aria-current", "location");
      } else {
        link.removeAttribute("aria-current");
      }
    }
  }

  let frame = null;
  function updateActive() {
    frame = null;
    const readingLine = window.innerHeight * 0.38;
    let active = sections[0]?.id;
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= readingLine) active = section.id;
    }
    if (active) setActive(active);
  }

  function scheduleActiveUpdate() {
    if (frame !== null) return;
    frame = requestAnimationFrame(updateActive);
  }

  window.addEventListener("scroll", scheduleActiveUpdate, { passive: true });
  window.addEventListener("resize", scheduleActiveUpdate);
  window.addEventListener("hashchange", scheduleActiveUpdate);
  updateActive();
}

const copy = {
  en: {
    none: "none",
    dora: "Dora",
    situation: "Situation",
    seeing: "What LuckyJ Is Seeing",
    whyTempting: "Why the Other Line Is Tempting",
    copyIt: "How to Copy It",
    limit: "Use This When",
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
	    example: "Example",
	    examples: "examples",
	    finalRank: "final rank",
    call: "Call",
    meld: "Meld",
    discardAfterCall: "Discard after call",
    luckyj: "LuckyJ",
    nagaTop: "Nishiki top",
    danger: "Danger",
    nagaThreat: "NAGA threat",
    drill: "Drill",
    answer: "Answer",
    nagaReport: "Review page",
    tenhouLog: "Tenhou log",
    immediateDanger: "Immediate danger",
    nagaWeight: "Nishiki weight",
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
    situation: "局面",
    seeing: "LuckyJ が見ているもの",
    whyTempting: "別ラインが魅力的に見える理由",
    copyIt: "自分の対局に移す方法",
    limit: "使う条件",
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
	    example: "例",
	    examples: "例",
	    finalRank: "最終順位",
    call: "鳴き",
    meld: "副露",
    discardAfterCall: "鳴き後の打牌",
    luckyj: "LuckyJ",
    nagaTop: "ニシキ最上位",
    danger: "放銃危険度",
    nagaThreat: "NAGA脅威",
    drill: "ドリル",
    answer: "答え",
    nagaReport: "検討ページ",
    tenhouLog: "天鳳牌譜",
    immediateDanger: "即時危険度",
    nagaWeight: "ニシキ評価",
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

function gameLine(rank, score) {
  if (isJa) return `最終順位 ${rankText(rank)}、持ち点 ${whole.format(score)}`;
  return `Final rank ${rank}, score ${whole.format(score)}`;
}

function caseLabelText(label) {
  if (!isJa) return label;
  return (
    {
      "Early safety hedge": "序盤の安全保留",
      "Middle route hedge": "中盤のルート保留",
      "Kept genbutsu tile": "現物牌をキープ",
      "Kept suji tile": "筋牌をキープ",
      "Safer than Nishiki": "ニシキより安全",
      "Riskier than Nishiki": "ニシキよりリスクあり",
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
      <span>${isJa ? "ニシキと割れた打牌で現物/筋を残した割合" : "of Nishiki-split discards kept a genbutsu or suji tile"}</span>
      <small>${isJa ? "内訳" : "Breakdown"}: ${whole.format(item.kept_genbutsu || 0)} ${safetyKindLabel("genbutsu")}, ${whole.format(item.kept_suji || 0)} ${safetyKindLabel("suji")}, ${whole.format(item.kept_against_live_threat || 0)} ${isJa ? "実脅威牌" : "live-threat tiles"}${avgLeft == null ? "" : isJa ? `、平均残り${fmt.format(avgLeft)}枚` : `, avg ${fmt.format(avgLeft)} tiles left`}</small>
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

function withQueryParam(href, key, value) {
  if (!href || value === undefined || value === null || value === "") return href || "";
  try {
    const url = new URL(href, window.location.href);
    url.searchParams.set(key, String(value));
    return url.href;
  } catch {
    const separator = String(href).includes("?") ? "&" : "?";
    return `${href}${separator}${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`;
  }
}

function externalLink(href, label) {
  return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function reviewHref(item) {
  return withQueryParam(withQueryParam(item.report, "ts", item.kyoku_index), "tv", item.position);
}

function tenhouHref(item) {
  return withQueryParam(item.paifu, "ts", item.kyoku_index);
}

function sourceLinks(item) {
  return `${externalLink(reviewHref(item), t("nagaReport"))} ${externalLink(tenhouHref(item), t("tenhouLog"))}`;
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

function hasGenbutsuItem(item) {
  return Boolean(item?.genbutsu_sources?.length);
}

function hasDisplaySotogawaItem(item) {
  return Boolean(item?.sotogawa_sources?.length) && !hasGenbutsuItem(item);
}

function isWeakSotogawaItem(item) {
  if (!hasDisplaySotogawaItem(item)) return false;
  const sources = item?.sotogawa_sources || [];
  return sources.length > 0 && !sources.some((source) => Number(source.position) <= 4);
}

function hasWeakSotogawa(read) {
  const items = (read?.against || []).filter(hasDisplaySotogawaItem);
  return items.length > 0 && items.every(isWeakSotogawaItem);
}

function hasDisplaySotogawa(read) {
  return (read?.against || []).some(hasDisplaySotogawaItem);
}

function safetyTarget(read) {
  const against = read?.against || [];
  const liveTargets = against.filter(
    (item) =>
      (item.genbutsu_sources?.length || item.suji_sources?.length || hasDisplaySotogawaItem(item)) &&
      (item.reached || item.open_melds)
  );
  return liveTargets[0] || against[0] || {};
}

function safetyKindLabel(kind, options = {}) {
  if (isJa) {
    if (kind === "genbutsu") return "現物";
    if (kind === "suji") return "筋";
    if (kind === "sotogawa") return options.weak ? "弱い外側牌（ソト側）" : "外側牌（ソト側）";
    return "なし";
  }
  if (kind === "genbutsu") return "genbutsu";
  if (kind === "suji") return "suji";
  if (kind === "sotogawa") return options.weak ? "weak outside tile (sotogawa)" : "outside tile (sotogawa)";
  return "none";
}

function safetyReadLabel(read, target = null) {
  const labels = [];
  const kind = target ? target.kind : read?.kind;
  if (kind) labels.push(safetyKindLabel(kind));
  const showSotogawa = target ? hasDisplaySotogawaItem(target) : hasDisplaySotogawa(read);
  if (showSotogawa) labels.push(safetyKindLabel("sotogawa", { weak: target ? isWeakSotogawaItem(target) : hasWeakSotogawa(read) }));
  return labels.length ? labels.join(isJa ? " / " : " / ") : safetyKindLabel("none");
}

function safetySourceText(source) {
  return isJa ? `${tileName(source.tile)} 河${source.position}枚目` : `${tileName(source.tile)} at river slot ${source.position}`;
}

function safetyReadLine(read) {
  if (!read || !(read.kind || read.has_sotogawa)) return "";
  const target = safetyTarget(read);
  const sourceList = target?.genbutsu_sources?.length ? [] : target?.suji_sources || [];
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
    ? `${tileName(read.tile)} は ${seatLabel(target?.seat_label)} に対して ${safetyReadLabel(read, target)}${threatText}${sourceText}`
    : `${tileName(read.tile)} is ${safetyReadLabel(read, target)} to ${seatLabel(target?.seat_label)}${threatText}${sourceText}`;
}

function safetySummary(safety) {
  if (!safety || !safety.total) return "";
  const parts = [];
  if (safety.genbutsu) parts.push(isJa ? `現物 ${safety.genbutsu}` : `${safety.genbutsu} genbutsu`);
  if (safety.suji) parts.push(isJa ? `筋 ${safety.suji}` : `${safety.suji} suji`);
  if (safety.against_threat) parts.push(isJa ? `実脅威牌 ${safety.against_threat}` : `${safety.against_threat} live-threat tiles`);
  return parts.join(isJa ? "、" : ", ");
}

function safetyPanel(read) {
  if (!read || !(read.kind || read.has_sotogawa)) return document.createDocumentFragment();
  const block = document.createElement("div");
  block.className = "safety-read";
  const rows = (read.against || [])
    .map((item) => {
      const rowLabelParts = [];
      if (item.kind) rowLabelParts.push(safetyKindLabel(item.kind));
      if (hasDisplaySotogawaItem(item)) rowLabelParts.push(safetyKindLabel("sotogawa", { weak: isWeakSotogawaItem(item) }));
      const rowLabels = rowLabelParts.join(isJa ? " / " : " / ");
      const sourceGroups = hasGenbutsuItem(item)
        ? []
        : [
            ["suji", item.suji_sources || []],
          ].filter(([, list]) => list.length);
      const sources = sourceGroups
        .map(
          ([kind, list]) =>
            `${escapeHtml(safetyKindLabel(kind))}: ${list
              .map((source) => `${tileIcon(source.tile, "inline-tile")} ${isJa ? `河${source.position}枚目` : `slot ${source.position}`}`)
              .join(", ")}`
        )
        .join(isJa ? "、" : "; ");
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
            : "no called threat";
      return `<li><b>${escapeHtml(seatLabel(item.seat_label))}</b><span>${escapeHtml(rowLabels || safetyKindLabel("none"))} / ${escapeHtml(threat)}${sources ? ` / ${sources}` : ""}</span></li>`;
    })
    .join("");
  block.innerHTML = `
    <p><b>${isJa ? "残した守備牌" : "Kept defensive tile"}:</b> ${tileIcon(read.tile, "inline-tile")} ${escapeHtml(tileName(read.tile))} / ${escapeHtml(safetyReadLabel(read))}</p>
    <ul>${rows}</ul>
  `;
  return block;
}

function tileIcons(items, className = "mini-tile") {
  const list = (items || []).filter(Boolean);
  if (!list.length) return `<span class="empty">${escapeHtml(t("none"))}</span>`;
  return list.map((tile) => tileIcon(tile, className)).join("");
}

function meldTileList(meld) {
  if (!meld) return [];
  if (Array.isArray(meld)) return meld.filter(Boolean);
  if (typeof meld === "object") return (meld.tiles || []).filter(Boolean);
  return String(meld).split(" ").filter(Boolean);
}

function tileRun(items, className = "", emptyLabel = t("none")) {
  const list = (items || []).filter(Boolean);
  if (!list.length) return emptyLabel ? `<span class="empty">${escapeHtml(emptyLabel)}</span>` : "";
  const label = tileNamesText(list);
  return `<span class="tiles ${tileFontClassPrefix}${className}" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${list
    .map(tileCode)
    .join("")}</span>`;
}

function tileThreatBarLabel(bar) {
  const value = bar?.danger == null ? "n/a" : pct(clamp01(bar.danger));
  const source = bar?.label || bar?.head || (bar?.seat ? seatLabel(bar.seat) : "danger");
  return `${source} ${value}`;
}

function calibratedDangerHeat(value) {
  const danger = clamp01(value);
  const stops = [
    [0, 0],
    [0.07, 0.25],
    [0.19, 0.52],
    [0.32, 0.84],
    [0.52, 1],
  ];
  for (let i = 1; i < stops.length; i += 1) {
    const [raw, heat] = stops[i];
    const [prevRaw, prevHeat] = stops[i - 1];
    if (danger <= raw) {
      const span = raw - prevRaw || 1;
      const progress = (danger - prevRaw) / span;
      return prevHeat + progress * (heat - prevHeat);
    }
  }
  return 1;
}

function tileThreatBars(tile, threat) {
  const bars = threat?.bars || [];
  if (!bars.length) return "";
  const title = `${tileName(tile)}: ${bars.map(tileThreatBarLabel).join(", ")}`;
  return `<span class="tile-threat-bars" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${bars
    .map((bar) => {
      const value = bar?.danger == null ? 0 : calibratedDangerHeat(bar.danger);
      const label = `${tileName(tile)} ${tileThreatBarLabel(bar)}`;
      return `<span class="tile-threat-bar" style="--bar-level:${Math.round(value * 1000) / 10}%" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"></span>`;
    })
    .join("")}</span>`;
}

function tileRunWithThreats(items, threats = [], className = "", emptyLabel = t("none")) {
  const list = (items || []).filter(Boolean);
  if (!list.length) return emptyLabel ? `<span class="empty">${escapeHtml(emptyLabel)}</span>` : "";
  const label = tileNamesText(list);
  const tileClass = [tileFontClass, className, "threat-tile"].filter(Boolean).join(" ");
  return `<span class="tile-threat-hand" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${list
    .map((tile, index) => {
      const threat = threats[index]?.tile === tile ? threats[index] : threats[index] || {};
      const title = threat?.bars?.length ? `${tileName(tile)}: ${threat.bars.map(tileThreatBarLabel).join(", ")}` : tileName(tile);
      return `<span class="tile-threat-cell" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${tileThreatBars(
        tile,
        threat
      )}<span class="tiles ${tileClass}" aria-hidden="true">${escapeHtml(tileCode(tile))}</span></span>`;
    })
    .join("")}</span>`;
}

function sameBaseTile(a, b) {
  return String(a || "").replace("r", "") === String(b || "").replace("r", "");
}

function calledTileIndex(calledFrom, total) {
  if (calledFrom === "kamicha") return 0;
  if (calledFrom === "toimen") return Math.min(total - 1, Math.floor((total - 1) / 2));
  if (calledFrom === "shimocha") return total - 1;
  return total - 1;
}

function normalizedCallSource(value) {
  return ["shimocha", "toimen", "kamicha"].includes(value) ? value : "";
}

function orderedMeldTiles(meld) {
  const tiles = meldTileList(meld);
  const calledTile = typeof meld === "object" ? meld.called_tile : "";
  const calledFrom = normalizedCallSource(typeof meld === "object" ? meld.called_from : "");
  const addedKanTile = typeof meld === "object" ? meld.added_kan_tile : "";
  if (!calledTile || !calledFrom || !tiles.length) {
    return tiles.map((tile) => ({ tile, called: false, calledFrom: "" }));
  }
  const remaining = tiles.slice();
  let calledSourceIndex = remaining.findIndex((tile) => tile === calledTile);
  if (calledSourceIndex < 0) calledSourceIndex = remaining.findIndex((tile) => sameBaseTile(tile, calledTile));
  const renderedCalledTile = calledSourceIndex >= 0 ? remaining.splice(calledSourceIndex, 1)[0] : calledTile;
  const insertAt = calledTileIndex(calledFrom, remaining.length + 1);
  remaining.splice(insertAt, 0, renderedCalledTile);
  return remaining.map((tile, index) => ({
    tile,
    called: index === insertAt,
    calledFrom,
    addedKanTile: index === insertAt ? addedKanTile : "",
  }));
}

function matchingPonForAddedKan(meld, addedTile) {
  const tiles = meldTileList(meld);
  const kind = String(typeof meld === "object" ? meld.kind || "" : "").toLowerCase();
  return (
    tiles.length >= 3 &&
    (!kind || kind === "pon" || kind === "kakan") &&
    tiles.every((tile) => sameBaseTile(tile, addedTile)) &&
    typeof meld === "object" &&
    meld.called_tile &&
    meld.called_from
  );
}

function meldsWithAddedKanStacks(melds) {
  const merged = [];
  for (const meld of melds || []) {
    const kind = String(typeof meld === "object" ? meld.kind || "" : "").toLowerCase();
    const tiles = meldTileList(meld);
    if (kind !== "kakan" || tiles.length !== 1) {
      merged.push(meld);
      continue;
    }

    const addedTile = tiles[0];
    let targetIndex = -1;
    for (let index = merged.length - 1; index >= 0; index -= 1) {
      if (matchingPonForAddedKan(merged[index], addedTile)) {
        targetIndex = index;
        break;
      }
    }
    if (targetIndex < 0) {
      merged.push(meld);
      continue;
    }

    merged[targetIndex] = {
      ...merged[targetIndex],
      kind: "kakan",
      added_kan_tile: addedTile,
    };
  }
  return merged;
}

function tableMeld(meld) {
  const items = orderedMeldTiles(meld);
  if (!items.length) return "";
  const label = tileNamesText(items.map((item) => item.tile));
  return `<span class="meld-run" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${items
    .map(
      (item) =>
        item.addedKanTile
          ? `<span class="meld-tile-slot called-tile-slot added-kan-slot called-from-${item.calledFrom}"><span class="added-kan-stack">${tileIcon(
              item.tile,
              "meld-tile called-tile added-kan-stack-tile"
            )}${tileIcon(item.addedKanTile, "meld-tile called-tile added-kan-stack-tile")}</span></span>`
          : `<span class="meld-tile-slot${item.called ? ` called-tile-slot called-from-${item.calledFrom}` : ""}">${tileIcon(
              item.tile,
              `meld-tile${item.called ? " called-tile" : ""}`
            )}</span>`
    )
    .join("")}</span>`;
}

function callMeldForExample(example) {
  return tableMeld({
    tiles: String(example.post_call_meld || "").split(" ").filter(Boolean),
    called_tile: example.called_tile,
    called_from: example.called_from,
    kind: example.call,
  });
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
    .map((meld) => `<span class="meld">${tileIcons(meldTileList(meld), "mini-tile")}</span>`)
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

function clamp01(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(1, number));
}

function discardRows(discards) {
  const rows = [];
  const list = discards || [];
  for (let i = 0; i < 18; i += 6) {
    rows.push(list.slice(i, i + 6).map((tile, offset) => ({ tile, index: i + offset })));
  }
  return rows;
}

function discardTileRun(items, riichiIndex, emptyLabel = "") {
  const list = (items || []).filter((item) => item?.tile);
  if (!list.length) return emptyLabel ? `<span class="empty">${escapeHtml(emptyLabel)}</span>` : "";
  const label = tileNamesText(list.map((item) => item.tile));
  return `<span class="discard-tiles" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${list
    .map((item) => {
      const isRiichiDiscard = Number.isInteger(riichiIndex) && item.index === riichiIndex;
      const slotClass = `discard-tile-slot${isRiichiDiscard ? " riichi-discard-slot" : ""}`;
      const tileClass = `discard-tile${isRiichiDiscard ? " riichi-discard-tile" : ""}`;
      return `<span class="${slotClass}">${tileIcon(item.tile, tileClass)}</span>`;
    })
    .join("")}</span>`;
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
      const handTiles = (player.hand || "").split(" ").filter(Boolean);
      const handRun =
        player.seat === "self" ? tileRunWithThreats(handTiles, player.tile_threats || []) : tileRun(handTiles);
      const playerMelds = meldsWithAddedKanStacks(player.melds || []);
      const melds = playerMelds.length
        ? `<div class="table-melds">${playerMelds.map(tableMeld).join("")}</div>`
        : "";
      return `
        <div class="player-hand player-${position}">
          <span class="player-name">${escapeHtml(name)}</span>
          <div class="table-tile-group table-hand-group">
            <div class="hand compact"><div class="hand-contents">${handRun}</div></div>
          </div>
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
            .map((row) => `<div class="discard-row">${discardTileRun(row, player.riichi_discard_index)}</div>`)
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

function logIdFromPaifu(paifu) {
  if (!paifu) return "";
  const match = paifu.match(/[?&]log=([^&]+)/);
  return match ? match[1] : "";
}

function mortalInputSignature(pointKey, example) {
  if (!example) return null;
  const logId = logIdFromPaifu(example.paifu);
  if (!logId) return null;
  const kind = example.kind;
  let actionType = "dahai";
  let actionTile = example.actual ?? null;
  let postDiscard = null;
  if (kind === "call") {
    actionType = String(example.call || "").toLowerCase();
    actionTile = example.called_tile ?? null;
    postDiscard = example.discard_after_call ?? null;
  } else if (kind === "reach") {
    actionType = "reach";
  }
  return [pointKey, logId, example.kyoku_index ?? null, example.left ?? null, actionType, actionTile, postDiscard];
}

function sameSignature(left, right) {
  return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, index) => value === right[index]);
}

function mortalCopyForExample(mortalCopy, pointKey, index) {
  const value = mortalCopy?.[pointKey];
  if (Array.isArray(value)) return value[index] || {};
  return value || {};
}

function pointMortalForExample(mortalPoints, pointKey, example, index) {
  const list = mortalPoints?.[pointKey];
  if (!Array.isArray(list)) return list || null;

  if (example) {
    const logId = logIdFromPaifu(example.paifu);
    const kyokuIndex = example.kyoku_index;
    const actualTile = example.actual;
    const expectedSignature = mortalInputSignature(pointKey, example);

    if (expectedSignature && list.some((item) => Array.isArray(item.input_signature))) {
      return list.find((item) => sameSignature(item.input_signature, expectedSignature)) || null;
    }

    for (const item of list) {
      if (item.log_id === logId && item.kyoku_index === kyokuIndex) {
        const itemActual = item.actual || {};
        const itemTile = itemActual.tile || itemActual.discard_after_call;
        if (itemTile === actualTile) {
          return item;
        }
      }
    }

    for (const item of list) {
      if (item.log_id === logId && item.kyoku_index === kyokuIndex) {
        return item;
      }
    }

    if (logId || kyokuIndex != null) return null;
  }

  return list[index] || null;
}

function renderMortalBlock(mortal, pointKey, mortalCopy, index) {
  if (!mortal) return document.createDocumentFragment();
  const localMortal = mortalCopyForExample(mortalCopy, pointKey, index);
  const readText = isJa ? mortal.read_ja || localMortal.read || mortal.read : localMortal.read || mortal.read;
  const useText = isJa ? mortal.how_to_use_ja || localMortal.how_to_use || mortal.how_to_use : localMortal.how_to_use || mortal.how_to_use;
  const block = document.createElement("details");
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
    <summary class="mortal-summary">
      <span class="kicker">${t("mortalCrossCheck")}</span>
      <span class="mortal-summary-line">
        <b>${t("mortalTop")}</b>
        ${probabilityChip(t("mortalWeight"), topCandidate?.probability)}
        <span class="discard-line">${modelActionLine(mortal.mortal)}</span>
        ${agreementBadge("LuckyJ", mortal.mortal_agrees_luckyj)}
        ${agreementBadge(modelName("nishiki"), mortal.mortal_agrees_naga)}
      </span>
    </summary>
    <div class="mortal-details">
      <div class="mortal-read">
        <h5>${t("readingSplit")}</h5>
        <p data-mortal-read></p>
        <p data-mortal-use></p>
      </div>
      ${branch}
    </div>
  `;
  block.querySelector("[data-mortal-read]")?.append(richText(readText || ""));
  block.querySelector("[data-mortal-use]")?.append(richText(useText || ""));
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
    : `${tileIcon(example.actual, "inline-tile")} <b>${escapeHtml(tileName(example.actual))}</b> is live yakuhai against an open hand with an unclear yaku. LuckyJ cleans it before it can become the opponent's yaku condition.`;
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

function pointExampleList(examples, pointKey) {
  const value = examples?.[pointKey];
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
}

function callActionLabel(action) {
  const key = String(action || "").toLowerCase();
  return (
    {
      chi: t("chi"),
      pon: t("pon"),
      daiminkan: t("openKan"),
      ankan: t("closedKan"),
      kakan: t("addedKan"),
    }[key] || escapeHtml(action || t("noModelAction"))
  );
}

function postCallModelHead(example, head) {
  const key = String(head?.key || head?.label || "").toLowerCase();
  return (example.post_call_model_heads || []).find((item) => String(item?.key || item?.label || "").toLowerCase() === key);
}

function callModelHeadName(head) {
  return escapeHtml(isJa ? head.label_ja || modelName(head.key || head.label) : head.label || modelName(head.key));
}

function readableList(items) {
  const clean = items.filter(Boolean);
  if (clean.length <= 1) return clean.join("");
  if (clean.length === 2) return isJa ? clean.join("、") : clean.join(" and ");
  const last = clean[clean.length - 1];
  const first = clean.slice(0, -1).join(isJa ? "、" : ", ");
  return isJa ? `${first}、${last}` : `${first}, and ${last}`;
}

function callModelActionKey(example, head) {
  const action = String(head?.top_action || "").toLowerCase();
  const postHead = postCallModelHead(example, head);
  const postDiscard = postHead?.top || example.post_call_naga || example.discard_after_call || "";
  return [
    Number(head?.top_kind) === 0 || action === "pass" ? "pass" : action,
    head?.supports_call ? "actual" : "other",
    example.called_tile || "",
    example.called_from || "",
    postDiscard,
  ].join("|");
}

function callModelActionLine(example, head) {
  const action = String(head?.top_action || "").toLowerCase();
  if (Number(head?.top_kind) === 0 || action === "pass") {
    return `<span>${isJa ? "鳴かない" : "Do not call"}</span>`;
  }
  const calledTile = example.called_tile
    ? `${tileIcon(example.called_tile, "discard-tile")} <em>${escapeHtml(tileName(example.called_tile))}</em>`
    : "";
  const from = example.called_from ? escapeHtml(seatLabel(example.called_from)) : "";
  const postHead = postCallModelHead(example, head);
  const postDiscard = postHead?.top || example.post_call_naga || example.discard_after_call;
  const discardText = postDiscard
    ? `${tileIcon(postDiscard, "discard-tile")} <em>${escapeHtml(tileName(postDiscard))}</em>`
    : "";
  const label = callActionLabel(action);
  const text = isJa
    ? `${label}${calledTile ? ` ${calledTile}` : ""}${from ? ` を${from}から` : ""}${discardText ? `、${t("discard")} ${discardText}` : ""}`
    : `${label}${calledTile ? ` on ${calledTile}` : ""}${from ? ` from ${from}` : ""}${discardText ? `, then ${t("discard").toLowerCase()} ${discardText}` : ""}`;
  return `<span class="call-action-line">${text}</span>`;
}

function callModelNote(example, head) {
  const action = String(head?.top_action || "").toLowerCase();
  if (head?.supports_call && action === String(example.call || "").toLowerCase()) return "";
  if (Number(head?.top_kind) === 0 || action === "pass") {
    return isJa ? "実戦の鳴きは選ばない読み。" : "This head would leave the tile alone instead of taking LuckyJ's call.";
  }
  if (action === String(example.call || "").toLowerCase()) {
    return isJa ? "同じ鳴き種類だが、実戦とは別の鳴き方。" : "Same call type, but a different call line from LuckyJ.";
  }
  return isJa ? "実戦とは別の鳴き方。" : "Different call line from LuckyJ.";
}

function renderCallModelBlock(example) {
  const heads = example.call_model_heads;
  if (!Array.isArray(heads) || !heads.length) return document.createDocumentFragment();
  const block = document.createElement("div");
  block.className = "comparison";
  const actionKeys = heads.map((head) => callModelActionKey(example, head));
  const allSameLine = actionKeys.length > 1 && actionKeys.every((key) => key === actionKeys[0]);
  if (allSameLine) {
    const card = document.createElement("div");
    card.className = "decision decision-wide";
    const names = readableList(heads.map(callModelHeadName));
    card.innerHTML = `
      <b>${isJa ? "NAGA各ヘッド" : "NAGA heads"}</b>
      ${callModelActionLine(example, heads[0])}
      <small>${isJa ? `${names} は同じラインを選ぶ。` : `${names} agree on this line.`}</small>
    `;
    block.append(card);
    return block;
  }
  for (const head of heads) {
    const card = document.createElement("div");
    card.className = "decision";
    const note = callModelNote(example, head);
    card.innerHTML = `
      <b>${callModelHeadName(head)}</b>
      ${callModelActionLine(example, head)}
      ${note ? `<small>${escapeHtml(note)}</small>` : ""}
    `;
    block.append(card);
  }
  return block;
}

function renderPointExampleCard(pointKey, example, guide, mortalPoints, mortalCopy, index, total) {
  const exampleGuide = (isJa ? example.guide_ja || example.guide : example.guide) || guide || {};
  const exampleMortal = example.mortal || pointMortalForExample(mortalPoints, pointKey, example, index);
  const card = document.createElement("article");
  card.className = "point-example-card";
  card.id = exampleAnchorId(pointKey, index);
  card.innerHTML = `
    <div class="example-head">
      <div>
        <p class="kicker">${t("replayExample")} ${index + 1}/${total}</p>
        <h4>${escapeHtml(exampleGuide.caption || example.title)}</h4>
      </div>
      <span>${escapeHtml(roundText(example.round))}, ${tilesLeftText(example.left)}</span>
    </div>
    <p class="case-meta">${escapeHtml(stageText(example.stage))} / ${escapeHtml(scoreBandText(example.score_band))} / ${t("finalRank")} ${rankText(example.rank)}</p>
  `;
  const layout = document.createElement("div");
  layout.className = "point-example-layout";
  const replay = document.createElement("div");
  replay.className = "point-example-replay";
  const explanation = document.createElement("div");
  explanation.className = "point-example-explanation";

  replay.append(renderMahjongTable(example.table));

  if (example.kind === "call") {
    const line = document.createElement("div");
    line.className = "call-line";
    line.innerHTML = `
      <span>${t("call")} ${escapeHtml(example.call)} ${tileIcon(example.called_tile, "discard-tile")} ${isJa ? "を" : "on"} ${escapeHtml(seatLabel(example.called_from))}${isJa ? "から" : ""}</span>
      <span>${t("meld")} ${callMeldForExample(example)}</span>
      <span>${t("discardAfterCall")} ${tileIcon(example.discard_after_call, "discard-tile")}</span>
    `;
    replay.append(line);
    replay.append(renderCallModelBlock(example));
  } else {
    const choices = document.createElement("div");
    choices.className = "comparison";
    if (example.actual_eval && example.naga_eval) {
      choices.append(
        comparison(t("luckyj"), example.actual_eval, example.actual_danger, example.actual_prob, t("nagaThreat")),
        comparison(t("nagaTop"), example.naga_eval, example.naga_danger, example.naga_prob, t("nagaThreat"))
      );
    } else {
      choices.innerHTML = `
        <div class="decision"><b>${t("luckyj")}</b>${probabilityChip(t("nagaWeight"), example.actual_prob)}<span class="discard-line">${t("discard")} ${tileIcon(example.actual, "discard-tile")} <em>${escapeHtml(tileName(example.actual))}</em></span><span>${t("nagaThreat")} ${dangerText(example.actual_danger)}</span></div>
        <div class="decision"><b>${t("nagaTop")}</b>${probabilityChip(t("nagaWeight"), example.naga_prob)}<span class="discard-line">${t("discard")} ${tileIcon(example.naga, "discard-tile")} <em>${escapeHtml(tileName(example.naga))}</em></span><span>${t("nagaThreat")} ${dangerText(example.naga_danger)}</span></div>
      `;
    }
    replay.append(choices);
    replay.append(safetyPanel(example.kept_tile_safety));
  }
  explanation.append(renderYakuhaiCleanupNote(example));
  explanation.append(renderGuideBlock(exampleGuide));
  explanation.append(renderMortalBlock(exampleMortal, pointKey, mortalCopy, index));

  const drill = document.createElement("div");
  drill.className = "example-drill";
  const drillPrompt = document.createElement("p");
  const drillAnswer = document.createElement("p");
  drillPrompt.innerHTML = `<b>${t("drill")}:</b> `;
  drillAnswer.innerHTML = `<b>${t("answer")}:</b> `;
  drillPrompt.append(richText(exampleGuide.prompt || example.prompt || ""));
  drillAnswer.append(richText(exampleGuide.answer || example.answer || ""));
  drill.append(drillPrompt, drillAnswer);

  const links = document.createElement("p");
  links.className = "case-links";
  links.innerHTML = sourceLinks(example);

  explanation.append(drill, links);
  layout.append(replay, explanation);
  card.append(layout);
  return card;
}

function renderPointExamples(examples, guides, mortalPoints, mortalCopy) {
  pointExampleControllers.clear();
  for (const placeholder of document.querySelectorAll("[data-example]")) {
    const pointKey = placeholder.dataset.example;
    const items = pointExampleList(examples, pointKey);
    if (!items.length) continue;
    const guide = guides?.[pointKey];
    const shell = document.createElement("div");
    shell.className = "point-example-tabs";
    const tablist = document.createElement("div");
    tablist.className = "example-tab-list";
    tablist.setAttribute("role", "tablist");
    tablist.setAttribute("aria-label", `${t("replayExample")} ${pointKey}`);
    const body = document.createElement("div");
    body.className = "example-tab-body";
    const buttons = items.map((example, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.dataset.index = String(index);
      button.innerHTML = `<b>${index + 1}</b><span>${escapeHtml(stageText(example.stage))}</span>`;
      button.title = `${t("example")} ${index + 1}: ${roundText(example.round)}`;
      tablist.append(button);
      return button;
    });
    let selectedIndex = 0;

    function showExample(index, { updateLocation = false } = {}) {
      selectedIndex = clampExampleIndex(index, items.length);
      buttons.forEach((button, buttonIndex) => {
        const selected = buttonIndex === selectedIndex;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", selected ? "true" : "false");
        button.tabIndex = selected ? 0 : -1;
      });
      body.replaceChildren(renderPointExampleCard(pointKey, items[selectedIndex], guide, mortalPoints, mortalCopy, selectedIndex, items.length));
      applyTileCompatibility(body);
      if (updateLocation) writeExampleLocation(pointKey, selectedIndex);
    }

    pointExampleControllers.set(pointKey, {
      total: items.length,
      show: showExample,
      get index() {
        return selectedIndex;
      },
    });

    tablist.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-index]");
      if (!button) return;
      showExample(Number(button.dataset.index), { updateLocation: true });
    });
    tablist.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? buttons.length - 1
            : (selectedIndex + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
      showExample(next, { updateLocation: true });
      buttons[next].focus();
    });

    shell.append(tablist, body);
    placeholder.replaceChildren(shell);
    const target = parsePointExampleLocation();
    const initialIndex = target.pointKey === pointKey && target.exampleIndex !== null ? target.exampleIndex : 0;
    showExample(initialIndex);
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
  if (Math.abs(gap) < 0.03) return "Immediate danger is close, so the disagreement is mostly about route selection.";
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
      return `中盤では手牌が価値を証明し始める必要がある。LuckyJ の ${actualName} 切りは、ニシキラインが点数状況や河に対して脆い一本道へ寄せすぎる可能性を示している。`;
    }
    if (key === "kept_river_safe") {
      return `ニシキが切りたい ${nagaName} を LuckyJ は残している。その牌は相手の河にあり、後のリーチや副露に対する現物牌になる。`;
    }
    if (key === "kept_suji_exit") {
      return `ニシキが切りたい ${nagaName} を LuckyJ は残している。その牌は相手の河から筋で読めるため、後の押し引きに使える。`;
    }
    if (key === "safer_than_naga") {
      return "攻めている手の中で安全側に寄せている。LuckyJ は手を生かしながら、危険なニシキ牌を後回しにしている。";
    }
    if (key === "riskier_than_naga") {
      return "これは真似するハードルが高い例である。LuckyJ は今の危険を払うが、残すルートが安全そうな代替より明確に良い場合に限られる。";
    }
    if (key === "late_tightening") {
      return "終盤では投機的な形の価値はかなり落ちる。和了、安全なテンパイ、降りを数える精密問題として読む。";
    }
    return `LuckyJ は ${tileClassText(actualClass)} の ${actualName} を切り、ニシキは ${tileClassText(nagaClass)} の ${nagaName} を切る。最初の問いは、どちらの牌がどの未来を守っているかである。`;
  }
  if (key === "early_safety_hedge") {
    return `Early in the hand, LuckyJ is treating ${actualName} as the tile that least damages the future menu. The idea is to delay commitment while keeping enough safety and value material to choose again after the table speaks.`;
  }
  if (key === "middle_route_hedge") {
    return `In the middle row, the hand has to start proving itself. LuckyJ's ${actualName} discard suggests that the Nishiki line compresses the hand into a route that is too brittle for the score and river state.`;
  }
  if (key === "kept_river_safe") {
    return `Nishiki wants to cut ${nagaName}, but LuckyJ keeps it because it is already visible in an opponent river. That retained genbutsu is a defensive tile for the next riichi or open-hand threat.`;
  }
  if (key === "kept_suji_exit") {
    return `Nishiki wants to cut ${nagaName}, but LuckyJ keeps it because opponent rivers make it suji. Treat it as a timed defensive resource, weaker than genbutsu but still useful in the right spot.`;
  }
  if (key === "safer_than_naga") {
    return `This is a safety purchase inside an attacking hand. LuckyJ keeps the hand alive while delaying the more dangerous Nishiki tile.`;
  }
  if (key === "riskier_than_naga") {
    return `Copy this only with care. LuckyJ is paying danger now because the kept route has to be clearly better than the safer-looking choice.`;
  }
  if (key === "late_tightening") {
    return `Late in the hand, speculative shape has mostly expired. Read this as an exact-counting problem: win, take safe tenpai, or fold.`;
  }
  return `LuckyJ cuts a ${actualClass} (${actualName}) while Nishiki cuts a ${nagaClass} (${nagaName}); the first question is which future each tile is protecting.`;
}

function caseLesson(key, item) {
  const actualClass = tileClass(item.actual);
  const nagaClass = tileClass(item.naga);
  const actualName = tileName(item.actual);
  const nagaName = tileName(item.naga);
  const safetyLine = safetyReadLine(item.kept_safety);
  if (isJa) {
    const lines = [
      `${roundText(item.round)}、残り${item.left}枚、${scoreBandText(item.score_band)}。手牌の質: ${handTexture(item.hand)}。LuckyJ は ${actualName} (${tileClassText(actualClass)}) を切り、ニシキは ${nagaName} (${tileClassText(nagaClass)}) を切る。`,
      categoryRead(key, item),
      dangerRead(item.actual_danger, item.naga_danger),
      "復習ドリル: 診断を見る前に、LuckyJ が何を残そうとしているかを書く。安全、価値、ルート数、圧力、着順のどれかを言える打牌だけ自分の形にする。",
    ];
    if (safetyLine) lines.splice(2, 0, safetyLine);
    return lines;
  }
  const lines = [
    `${item.round}, ${item.left} tiles left, ${item.score_band}. Hand texture: ${handTexture(item.hand)}. LuckyJ cuts ${actualName} (${actualClass}); Nishiki cuts ${nagaName} (${nagaClass}).`,
    categoryRead(key, item),
    dangerRead(item.actual_danger, item.naga_danger),
    `Review drill: before looking at the diagnostics, write what LuckyJ is buying: safety, value, route count, pressure, or placement. Copy the move after the purchase is clear.`,
  ];
  if (safetyLine) lines.splice(2, 0, safetyLine);
  return lines;
}

function comparison(label, item, danger, probability, dangerLabel = t("immediateDanger")) {
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
    <span>${dangerLabel} ${danger == null ? "n/a" : pct(danger)}</span>
    <span>${t("keeps")} ${item.kept_honors} ${t("honors")}, ${item.kept_terminals} ${t("terminals")}</span>
    ${keptSafety ? `<span>${isJa ? "守備牌" : "Defensive tiles"} ${escapeHtml(keptSafety)}</span>` : ""}
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
      handTitle.textContent = gameLine(item.rank, item.score);
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
      links.innerHTML = sourceLinks(item);

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
    const reviewExample = isJa ? item.review_example_ja : item.review_example;
    const reviewExampleText = String(reviewExample || "").replace(/^(Review example|検討例):\s*/, "");
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
      ${
        reviewExample
          ? `<div class="validation-example review-derived">
              <strong>${isJa ? "検討由来例" : "Review-derived example"}</strong>
              <span>${escapeHtml(reviewExampleText)}</span>
            </div>`
          : ""
      }
      <p class="validation-caveat">${escapeHtml(isJa ? item.caveat_ja : item.caveat)}</p>
    `;
    grid.append(card);
  }
}

async function main() {
  setupRetractingTopbar();
  renderPointRail();
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
  syncPointExamplesFromLocation({ scroll: true });
  renderCases(caseData);
  applyTileCompatibility();
}

window.addEventListener("hashchange", () => syncPointExamplesFromLocation({ scroll: true }));
window.addEventListener("popstate", () => syncPointExamplesFromLocation({ scroll: true }));

main().catch((error) => {
  const metrics = document.querySelector("#metrics");
  if (metrics) {
    metrics.innerHTML = `<div class="metric"><b>${t("dataLoadFailed")}</b><span>${error.message}</span></div>`;
  }
});
