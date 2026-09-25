const pageLang = document.documentElement.lang.toLowerCase().startsWith("ja") ? "ja" : "en";
const isJa = pageLang === "ja";
const locale = isJa ? "ja-JP" : "en-US";
const fmt = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
const pct = (v) => `${fmt.format(v * 100)}%`;
const dataAssetVersion = "20260925-fold-prep";
const dataAsset = (path) => `${path}${String(path).includes("?") ? "&" : "?"}v=${dataAssetVersion}`;
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
const siteCommitFallback = {
  repo: "honvl/LuckyJ",
  branch: "main",
  sha: "a372172cb67ff60654aaef37f7f7696239735e76",
  date: "2026-07-01T14:02:11-04:00",
};
const pointExampleControllers = new Map();
const pointExampleSelections = new Map();
const pointExampleSelectionsKey = "luckyj:point-example-selections:v1";
let pointExampleSelectionsLoaded = false;

function setupRetractingTopbar() {
  const topbar = document.querySelector(".running-head, .topbar");
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

    // The head stays while its contents panel is open, since the panel hangs from it.
    if (scrollY <= revealAtTop || topbar.matches(":focus-within") || topbar.querySelector('[aria-expanded="true"]')) {
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

// The web fonts and the example tables change the page's height after the browser has jumped to a
// link's anchor, so the page goes to the anchor again once both are in place, unless the reader has
// already started scrolling.
let readerHasScrolled = false;
for (const type of ["wheel", "touchstart", "keydown", "pointerdown"]) {
  window.addEventListener(type, () => { readerHasScrolled = true; }, { once: true, passive: true });
}

function returnToHashTarget() {
  let id = "";
  try {
    id = decodeURIComponent(window.location.hash.slice(1));
  } catch {
    return;
  }
  if (!id || readerHasScrolled) return;
  document.getElementById(id)?.scrollIntoView({ block: "start", behavior: "instant" });
}

// The text faces come from a stylesheet that loads without blocking the page. This resolves once
// that stylesheet applies (or fails, or takes too long), when the faces it declares start loading.
function fontStylesheetApplied() {
  const link = document.querySelector("link[data-font-css]");
  if (!link || link.media === "all") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      // Its inline onload handler has switched it on by now; laying out the page starts the font loads.
      void document.body.offsetHeight;
      resolve();
    };
    link.addEventListener("load", done, { once: true });
    link.addEventListener("error", done, { once: true });
    setTimeout(resolve, 3000);
  });
}

function settleHashScroll(ready) {
  Promise.resolve(ready)
    .catch(() => {})
    .then(fontStylesheetApplied)
    .then(() => document.fonts?.ready)
    .then(() => requestAnimationFrame(returnToHashTarget));
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

function loadPointExampleSelections() {
  if (pointExampleSelectionsLoaded) return;
  pointExampleSelectionsLoaded = true;
  try {
    const saved = JSON.parse(window.localStorage?.getItem(pointExampleSelectionsKey) || "{}");
    if (!saved || Array.isArray(saved) || typeof saved !== "object") return;
    for (const [key, value] of Object.entries(saved)) {
      const pointKey = normalizePointKey(key);
      const index = Number.parseInt(String(value), 10);
      if (pointKey && Number.isFinite(index) && index >= 0) {
        pointExampleSelections.set(pointKey, index);
      }
    }
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
}

function savePointExampleSelections() {
  try {
    window.localStorage?.setItem(pointExampleSelectionsKey, JSON.stringify(Object.fromEntries(pointExampleSelections)));
  } catch {
    // Keep tab memory in-page if storage is unavailable.
  }
}

function pointExampleProgressText(count, total) {
  return isJa ? `例 ${count}/${total}` : `Example ${count}/${total}`;
}

function updatePointRailProgress(pointKey, index, total) {
  if (!pointKey || total <= 0) return;
  const count = clampExampleIndex(index, total) + 1;
  // The contents list marks only the points where the reader has moved past the first replay.
  const shown = total > 1 && count > 1;
  for (const link of document.querySelectorAll(`.contents-panel a[data-point="${pointKey}"]`)) {
    const baseLabel = [link.dataset.number, link.dataset.label].filter(Boolean).join(" ");
    const progress = link.querySelector("small");
    if (progress) progress.textContent = shown ? `${count}/${total}` : "";
    link.setAttribute("aria-label", shown ? `${baseLabel}, ${pointExampleProgressText(count, total)}` : baseLabel);
  }
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
  const index =
    target.exampleIndex === null
      ? clampExampleIndex(pointExampleSelections.get(target.pointKey) ?? controller.index, controller.total)
      : clampExampleIndex(target.exampleIndex, controller.total);
  controller.show(index, { updateLocation: false, reveal: target.exampleIndex !== null });
  if (!scroll) return;
  requestAnimationFrame(() => {
    const anchor = target.exampleIndex === null ? target.pointKey : exampleAnchorId(target.pointKey, index);
    const element = document.getElementById(anchor) || document.getElementById(target.pointKey);
    element?.scrollIntoView({ block: "start", behavior: "instant" });
  });
}

function modelName(keyOrLabel) {
  const raw = String(keyOrLabel || "");
  const key = raw.toLowerCase();
  return modelNames[pageLang]?.[key] || modelNames.en[key] || raw;
}

// The running head: where the reader is in the book, a reading-progress line, and a contents panel
// built from the page's own sections. On a page without chapters (the home page) the Contents link
// keeps its href and goes to the contents list on that page.
function setupRunningHead() {
  const head = document.querySelector(".running-head");
  if (!head || head.dataset.ready) return;
  head.dataset.ready = "1";
  const location = head.querySelector("[data-running-location]");
  const progress = head.querySelector(".reading-progress");
  const fill = progress?.querySelector("span");
  const cover = document.querySelector(".cover");
  const isGuide = document.body?.dataset.book === "guide";
  const words = isJa
    ? { point: "ポイント", before: "前付け", points: "ポイント", after: "後付け", contents: "目次" }
    : isGuide
      ? { point: "Chapter", before: "Before the chapters", points: "Chapters", after: "After the chapters", contents: "Contents" }
      : { point: "Point", before: "Before the points", points: "The points", after: "After the points", contents: "Contents" };

  const points = Array.from(document.querySelectorAll(".point[id]"));
  const sections = Array.from(document.querySelectorAll("section.section[id], section.cover[id]")).filter(
    (section) => !section.classList.contains("concept-divider")
  );
  const itemFor = (element) => {
    if (element.classList.contains("point")) {
      const number = element.querySelector(".point-number")?.textContent.trim() || "";
      const title = element.querySelector("h3")?.textContent.trim() || "";
      return { element, id: element.id, number, title, location: `${words.point} ${number} · ${title}`, isPoint: true };
    }
    const label =
      element.dataset.contentsLabel ||
      element.querySelector(":scope > .kicker")?.textContent.trim() ||
      element.querySelector("h2, h1")?.textContent.trim() ||
      element.id;
    return { element, id: element.id, number: "", title: label, location: label, isPoint: false };
  };
  const items = [...points, ...sections]
    .sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1))
    .map(itemFor);

  // The contents panel, when the page holds chapters.
  let toggle = head.querySelector(".contents-toggle");
  let panel = null;
  const links = [];
  if (points.length && toggle) {
    panel = document.createElement("div");
    panel.className = "contents-panel";
    panel.id = "contents-panel";
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", words.contents);
    const groups = [
      [words.before, items.filter((item) => !item.isPoint && item.element.compareDocumentPosition(points[0]) & Node.DOCUMENT_POSITION_FOLLOWING)],
      [words.points, items.filter((item) => item.isPoint)],
      [words.after, items.filter((item) => !item.isPoint && points[points.length - 1].compareDocumentPosition(item.element) & Node.DOCUMENT_POSITION_FOLLOWING)],
    ];
    for (const [label, group] of groups) {
      if (!group.length) continue;
      const heading = document.createElement("p");
      heading.className = "label";
      heading.textContent = label;
      const list = document.createElement("ol");
      for (const item of group) {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = `#${item.id}`;
        link.dataset.point = item.id;
        link.dataset.number = item.number;
        link.dataset.label = item.title;
        const number = document.createElement("b");
        number.textContent = item.number;
        const title = document.createElement("span");
        title.textContent = item.title;
        const progressText = document.createElement("small");
        link.append(number, title, progressText);
        li.append(link);
        list.append(li);
        links.push(link);
      }
      panel.append(heading, list);
    }
    document.body.append(panel);

    const button = document.createElement("button");
    button.type = "button";
    button.className = toggle.className;
    button.innerHTML = toggle.innerHTML;
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", panel.id);
    toggle.replaceWith(button);
    toggle = button;

    const close = ({ focus = false } = {}) => {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      if (focus) toggle.focus();
    };
    toggle.addEventListener("click", () => {
      const open = panel.hidden;
      panel.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) (panel.querySelector("a.is-active") || panel.querySelector("a"))?.focus({ preventScroll: true });
    });
    panel.addEventListener("click", (event) => {
      if (event.target.closest("a")) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !panel.hidden) close({ focus: true });
    });
    document.addEventListener("click", (event) => {
      if (!panel.hidden && !panel.contains(event.target) && !toggle.contains(event.target)) close();
    });
  }

  function setActive(id) {
    for (const link of links) {
      const selected = link.dataset.point === id;
      link.classList.toggle("is-active", selected);
      if (selected) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  }

  let frame = null;
  function update() {
    frame = null;
    const scrollY = window.scrollY || window.pageYOffset || 0;
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    if (fill) fill.style.setProperty("--progress", `${Math.min(100, Math.max(0, (scrollY / max) * 100)).toFixed(2)}%`);
    if (cover && head.dataset.felt !== "never") {
      const overFelt = cover.getBoundingClientRect().bottom > head.offsetHeight;
      head.classList.toggle("on-felt", overFelt);
    }
    const readingLine = window.innerHeight * 0.38;
    let active = null;
    for (const item of items) {
      if (item.element.getBoundingClientRect().top <= readingLine) active = item;
    }
    const coverVisible = cover && cover.getBoundingClientRect().bottom > readingLine;
    if (location) {
      const text = active && !coverVisible ? active.location : "";
      if (location.dataset.text !== text) {
        location.dataset.text = text;
        location.replaceChildren();
        if (text) {
          const span = document.createElement("span");
          span.textContent = text;
          location.append(span);
        }
      }
    }
    progress?.classList.toggle("is-live", points.length > 0 && !coverVisible);
    setActive(active?.id || "");
  }
  function schedule() {
    if (frame !== null) return;
    frame = requestAnimationFrame(update);
  }
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  window.addEventListener("hashchange", schedule);
  update();
}

const copy = {
  en: {
    none: "none",
    dora: "Ind.",
    doraFull: "Dora indicators",
    seeing: "What LuckyJ Is Seeing",
    whyTempting: "Why the Other Line Is Tempting",
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
	    replayExample: "Replay example",
	    example: "Example",
	    examples: "examples",
	    finalRank: "final rank",
    call: "Call",
    meld: "Meld",
    discardAfterCall: "Discard after call",
    luckyj: "LuckyJ",
    nagaTop: "Nishiki top",
    danger: "NAGA danger proxy",
    nagaThreat: "NAGA danger proxy",
    drill: "Drill",
    nagaReport: "Review page",
    tenhouLog: "Tenhou log",
    immediateDanger: "NAGA danger proxy",
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
    bad: "Nishiki severe",
    dataLoadFailed: "Data load failed",
    yourCall: "Your call",
    showAnswer: "Show the answer",
    askAgain: "Ask me again",
    cut: "Cut",
    pass: "Pass",
    tenpaiWord: "Tenpai",
    replaysLabel: "Replays",
    replaysTitle: "Replays from LuckyJ's games",
    replaysNote: "Make the call before you read the answer.",
  },
  ja: {
    none: "なし",
    dora: "表示",
    doraFull: "ドラ表示牌",
    seeing: "LuckyJ が見ているもの",
    whyTempting: "別ラインが魅力的に見える理由",
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
	    replayExample: "実戦例",
	    example: "例",
	    examples: "例",
	    finalRank: "最終順位",
    call: "鳴き",
    meld: "副露",
    discardAfterCall: "鳴き後の打牌",
    luckyj: "LuckyJ",
    nagaTop: "ニシキ最上位",
    danger: "NAGA危険度指標",
    nagaThreat: "NAGA危険度指標",
    drill: "ドリル",
    nagaReport: "検討ページ",
    tenhouLog: "天鳳牌譜",
    immediateDanger: "NAGA危険度指標",
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
    bad: "ニシキ重度不一致",
    dataLoadFailed: "データ読み込み失敗",
    yourCall: "あなたの判断",
    showAnswer: "答えを見る",
    askAgain: "もう一度考える",
    cut: "打",
    pass: "鳴かない",
    tenpaiWord: "テンパイ",
    replaysLabel: "実戦例",
    replaysTitle: "LuckyJ の実戦から",
    replaysNote: "答えを読む前に、自分の打牌を選ぶ。",
  },
};

function t(key) {
  return copy[pageLang]?.[key] || copy.en[key] || key;
}

function formatCommitDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

function updateCommitStamp(element, commit) {
  const sha = String(commit?.sha || siteCommitFallback.sha);
  const shortSha = sha.slice(0, 7);
  const dateText = formatCommitDate(commit?.date || siteCommitFallback.date);
  const label = isJa ? `最終コミット ${dateText}` : `Last commit ${dateText}`;
  element.textContent = `${label} (${shortSha})`;
  element.href = `https://github.com/${siteCommitFallback.repo}/commit/${sha}`;
  element.title = isJa ? "GitHub でコミットを見る" : "View commit on GitHub";
  element.setAttribute("aria-label", element.textContent);
}

async function renderCommitStamp() {
  const placeholder = document.querySelector("[data-commit-stamp]");
  if (!placeholder && document.querySelector(".commit-stamp")) return;
  if (placeholder?.dataset.ready) return;

  // Pages with a colophon hold the stamp there; older pages get the floating one.
  const stamp = placeholder || document.createElement("a");
  if (placeholder) placeholder.dataset.ready = "1";
  stamp.classList.add("commit-stamp");
  if (!placeholder) stamp.classList.add("is-floating");
  stamp.target = "_blank";
  stamp.rel = "noopener noreferrer";
  updateCommitStamp(stamp, siteCommitFallback);
  if (!placeholder) document.body.append(stamp);

  try {
    const response = await fetch(
      `https://api.github.com/repos/${siteCommitFallback.repo}/commits/${siteCommitFallback.branch}`,
      { headers: { Accept: "application/vnd.github+json" } }
    );
    if (!response.ok) throw new Error(`GitHub commit lookup failed: ${response.status}`);
    const payload = await response.json();
    updateCommitStamp(stamp, {
      sha: payload.sha,
      date: payload.commit?.committer?.date || payload.commit?.author?.date,
    });
  } catch {
    stamp.classList.add("is-fallback");
  }
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

function fetchJson(path, fallback = {}) {
  return fetch(dataAsset(path))
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
  const rooms = {
    General: isJa ? "一般" : "General",
    Upper: isJa ? "上級" : "Upper",
    Tokujou: isJa ? "特上" : "Tokujou",
  };
  const room = item.room ? `<span class="source-room">${escapeHtml(rooms[item.room] || item.room)}</span> ` : "";
  return `${room}${externalLink(reviewHref(item), t("nagaReport"))} ${externalLink(tenhouHref(item), t("tenhouLog"))}`;
}

function renderSourceScope(data) {
  const summary = data?.summary || {};
  const scope = data?.source_scope || {};
  const rooms = scope.room_counts || {};
  const intro = document.querySelector("#corpusIntro");
  const scopeText = document.querySelector("#sourceScopeDynamic");
  const date = (value) => {
    if (!value) return "";
    const parsed = new Date(`${value}T00:00:00`);
    return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
  };
  if (intro) {
    intro.textContent = isJa
      ? `${whole.format(summary.games || 0)}件の重複なしNAGA検討付き半荘、${whole.format(summary.hands || 0)}局、LuckyJ打牌${whole.format(summary.decisions || 0)}件を見直し、実戦で使える習慣へまとめた。`
      : `I reviewed ${whole.format(summary.games || 0)} unique NAGA-reviewed hanchan, ${whole.format(summary.hands || 0)} hands, and ${whole.format(summary.decisions || 0)} LuckyJ discard decisions, then grouped them into habits you can use at the table.`;
  }
  if (scopeText) {
    const dateRange = scope.date_start && scope.date_end ? `${date(scope.date_start)}–${date(scope.date_end)}` : "the recorded run";
    scopeText.textContent = isJa
      ? `本書の対象は${dateRange}の重複なし${whole.format(scope.unique_reports || summary.games || 0)}半荘。内訳は特上${whole.format(rooms.Tokujou || 0)}、上級${whole.format(rooms.Upper || 0)}、一般${whole.format(rooms.General || 0)}。鳳凰卓と雀魂の標本は含まれない。下の教材例は特上卓に限定している。`
      : `This book covers ${whole.format(scope.unique_reports || summary.games || 0)} unique hanchan from ${dateRange}: ${whole.format(rooms.Tokujou || 0)} Tokujou, ${whole.format(rooms.Upper || 0)} Upper, and ${whole.format(rooms.General || 0)} General. It contains no Houou or Mahjong Soul sample. Teaching examples below are restricted to Tokujou.`;
  }
}

function valueAtPath(root, path) {
  return String(path || "").split(".").reduce((value, key) => (value == null ? undefined : value[key]), root);
}

function renderBookStatSpans(data) {
  for (const node of document.querySelectorAll("[data-book-stat]")) {
    const value = valueAtPath(data, node.dataset.bookStat);
    if (value != null) node.textContent = whole.format(value);
  }
  for (const node of document.querySelectorAll("[data-book-pct]")) {
    const value = valueAtPath(data, node.dataset.bookPct);
    if (value != null) node.textContent = pct(value);
  }
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
      return `<span class="tile-threat-cell" data-tile="${escapeHtml(tile)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${tileThreatBars(
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
  const hasAddedKan = items.some((item) => item.addedKanTile);
  const addedKanEdgeClass =
    hasAddedKan && items[0]?.addedKanTile
      ? " added-kan-edge-start"
      : hasAddedKan && items[items.length - 1]?.addedKanTile
        ? " added-kan-edge-end"
        : "";
  return `<span class="meld-run${hasAddedKan ? " added-kan-run" : ""}${addedKanEdgeClass}" aria-label="${escapeHtml(
    label
  )}" title="${escapeHtml(label)}">${items
    .map(
      (item, index) => {
        const adjacentKanClass =
          !item.addedKanTile && items[index + 1]?.addedKanTile
            ? " added-kan-neighbor-before"
            : !item.addedKanTile && items[index - 1]?.addedKanTile
              ? " added-kan-neighbor-after"
              : "";
        return item.addedKanTile
          ? `<span class="meld-tile-slot called-tile-slot added-kan-slot called-from-${item.calledFrom}"><span class="added-kan-stack">${tileIcon(
              item.tile,
              "meld-tile called-tile added-kan-stack-tile"
            )}${tileIcon(item.addedKanTile, "meld-tile called-tile added-kan-stack-tile")}</span></span>`
          : `<span class="meld-tile-slot${adjacentKanClass}${item.called ? ` called-tile-slot called-from-${item.calledFrom}` : ""}">${tileIcon(
              item.tile,
              `meld-tile${item.called ? " called-tile" : ""}`
            )}</span>`;
      }
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

function convertStaticTileMarkup(root = document) {
  // Static chapter prose uses the same [[tile]] markup as data-driven text.
  const walker = document.createTreeWalker(root.body || root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.nodeValue.includes("[[") && node.parentElement && !node.parentElement.closest("script,style")
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT,
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    node.parentNode.replaceChild(richText(node.nodeValue), node);
  }
}

function prescriptionTileSortKey(tile) {
  const base = String(tile || "").replace("r", "");
  const honorOrder = { E: 27, S: 28, W: 29, N: 30, P: 31, F: 32, C: 33 };
  if (honorOrder[base] !== undefined) return honorOrder[base] * 10;
  const match = base.match(/^([1-9])([mps])$/);
  if (!match) return 999;
  const suitOffset = { m: 0, p: 9, s: 18 }[match[2]];
  const redOffset = String(tile || "").includes("r") ? 1 : 0;
  return (suitOffset + Number(match[1]) - 1) * 10 + redOffset;
}

function sortedPrescriptionHand(hand) {
  return (Array.isArray(hand) ? hand : [])
    .map((tile, index) => ({ tile, index }))
    .sort((a, b) => prescriptionTileSortKey(a.tile) - prescriptionTileSortKey(b.tile) || a.index - b.index)
    .map((item) => item.tile);
}

function selfSeatLabel() {
  // Pages that replay someone else's games (the personal guide) name the bottom seat.
  return document.body?.dataset.selfName || "LuckyJ";
}

function seatLabel(seat) {
  const labels = isJa
    ? {
        self: selfSeatLabel(),
        shimocha: "下家",
        toimen: "対面",
        kamicha: "上家",
      }
    : {
    self: selfSeatLabel(),
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
  const doraMarkers = table.dora_markers || [];
  const doraFullLabel = t("doraFull");
  const doraTitle = [doraFullLabel, tileNamesText(doraMarkers)].filter(Boolean).join(": ");
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
          <div class="wind${score.wind === "E" ? " is-dealer" : ""}">${escapeHtml(score.wind || "?")}</div>
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
        player.seat === "self"
          ? tileRunWithThreats(handTiles, player.tile_threats || [])
          : `${tileRun(handTiles)}<span class="tile-backs" aria-hidden="true">${"<i></i>".repeat(handTiles.length)}</span>`;
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
              <div class="dora-indicator" aria-label="${escapeHtml(doraTitle)}" title="${escapeHtml(doraTitle)}"><span>${escapeHtml(t("dora"))}:</span> ${tileRun(doraMarkers)}</div>
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
    [t("seeing"), guide?.read],
    [t("whyTempting"), guide?.whyNot],
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

function renderMortalBlock(mortal) {
  if (!mortal) return document.createDocumentFragment();
  const block = document.createElement("div");
  block.className = "mortal-block";
  const topCandidate = mortal.top_candidates?.[0];
  const branch = mortal.post_call_mortal
    ? `<p class="mortal-branch"><b>${t("afterCall")}</b> ${modelActionLine(mortal.post_call_mortal)} ${agreementBadge(t("postCallDiscard"), mortal.post_call_agrees_luckyj)}</p>`
    : "";
  block.innerHTML = `
    <p class="kicker">${t("mortalCrossCheck")}</p>
    <p class="mortal-summary-line">
      <b>${t("mortalTop")}</b>
      ${probabilityChip(t("mortalWeight"), topCandidate?.probability)}
      <span class="discard-line">${modelActionLine(mortal.mortal)}</span>
      ${agreementBadge("LuckyJ", mortal.mortal_agrees_luckyj)}
      ${agreementBadge(modelName("nishiki"), mortal.mortal_agrees_naga)}
    </p>
    ${branch}
  `;
  return block;
}

function renderYakuhaiCleanupNote(example) {
  const threats = example.yakuhai_cleanup?.threats || [];
  if (!threats.length) return document.createDocumentFragment();
  const block = document.createElement("div");
  block.className = "yaku-condition-read";
  const heading = isJa ? "役がまだ見えない副露" : "Open hands with no yaku showing";
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
  // A head that passes already reads "Do not call"; it needs no note.
  if (Number(head?.top_kind) === 0 || action === "pass") return "";
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

// Examples the reader has answered (or opened from a link) during this visit, and what they picked.
const replayPicks = new Map();

function plainCallHeadName(head) {
  return isJa ? head.label_ja || modelName(head.key || head.label) : head.label || modelName(head.key);
}

function shantenNote(evalItem) {
  if (!evalItem) return "";
  const shanten = Number(evalItem.shanten);
  const ukeire = Number(evalItem.ukeire);
  const state =
    shanten === 0 ? t("tenpaiWord") : Number.isFinite(shanten) ? (isJa ? `${shanten}シャンテン` : `${shanten}-shanten`) : "";
  const count = Number.isFinite(ukeire)
    ? isJa
      ? `受け入れ${whole.format(ukeire)}枚`
      : `${whole.format(ukeire)} tile${ukeire === 1 ? "" : "s"}`
    : "";
  return [state, count].filter(Boolean).join(" · ");
}

function discardActionText(tile, declares) {
  const name = escapeHtml(tileName(tile));
  if (isJa) return `${declares ? "リーチ、" : ""}打${name}`;
  return `${declares ? `${t("reach")}, ${t("cut").toLowerCase()}` : t("cut")} ${name}`;
}

// The two lines the reader chooses between: LuckyJ's and Nishiki's. Each carries the engines that
// chose it, which the answer names once the reader has picked.
function quizChoices(example, mortal) {
  if (example.kind === "call") {
    const heads = example.call_model_heads || [];
    const callers = heads.filter((head) => head.supports_call).map(plainCallHeadName);
    const passers = heads
      .filter((head) => Number(head.top_kind) === 0 || String(head.top_action || "").toLowerCase() === "pass")
      .map(plainCallHeadName);
    const label = callActionLabel(example.call);
    const tile = tileIcon(example.called_tile, "inline-tile");
    return [
      {
        id: "luckyj",
        tile: example.called_tile,
        action: isJa ? `${label}` : `${label}`,
        html: isJa ? `${tile}を${label}` : `${label} on ${tile}`,
        note: isJa ? `${escapeHtml(seatLabel(example.called_from))}の捨て牌` : `from ${escapeHtml(seatLabel(example.called_from))}`,
        owners: ["LuckyJ", ...callers, ...(mortal?.mortal_agrees_luckyj ? ["Mortal"] : [])],
      },
      {
        id: "model",
        tile: null,
        action: t("pass"),
        html: t("pass"),
        note: isJa ? "門前のまま" : "stay closed",
        owners: [...passers, ...(mortal && mortal.mortal_agrees_luckyj === false ? ["Mortal"] : [])],
      },
    ];
  }
  const heads = example.model_heads || [];
  const headsFor = (tile) => heads.filter((head) => head.top === tile).map((head) => modelName(head.key || head.label));
  // Mortal's verdict on a riichi covers the declaration, not the tile, so it is not credited to either cut.
  if (example.kind === "reach") mortal = null;
  const lines = [
    {
      id: "luckyj",
      tile: example.actual,
      declares: Boolean(example.actual_eval?.declares_reach),
      note: shantenNote(example.actual_eval),
      owners: ["LuckyJ", ...headsFor(example.actual), ...(mortal?.mortal_agrees_luckyj ? ["Mortal"] : [])],
    },
    {
      id: "model",
      tile: example.naga,
      declares: Boolean(example.naga_eval?.declares_reach),
      note: shantenNote(example.naga_eval),
      owners: [...headsFor(example.naga), ...(mortal?.mortal_agrees_naga ? ["Mortal"] : [])],
    },
  ];
  for (const line of lines) {
    line.action = discardActionText(line.tile, line.declares);
    line.html = `${line.declares ? `${t("reach")}${isJa ? "、" : ", "}` : ""}${tileIcon(line.tile, "inline-tile")}`;
  }
  // Tile order, so LuckyJ's line is not always the first button.
  return lines.sort((a, b) => prescriptionTileSortKey(a.tile) - prescriptionTileSortKey(b.tile));
}

function quizResultHtml(choices, pickedId) {
  const luckyj = choices.find((choice) => choice.id === "luckyj");
  const model = choices.find((choice) => choice.id === "model");
  const list = (owners) => readableList(owners.map(escapeHtml));
  if (!pickedId) {
    return isJa
      ? `LuckyJ は ${luckyj.html}${model.owners.length ? `、${list(model.owners)}は ${model.html}` : ""}。`
      : `LuckyJ: ${luckyj.html}.${model.owners.length ? ` ${list(model.owners)}: ${model.html}.` : ""}`;
  }
  const picked = pickedId === "luckyj" ? luckyj : model;
  const other = pickedId === "luckyj" ? model : luckyj;
  if (isJa) {
    const same = picked.owners.length ? `で、${list(picked.owners)}と同じ` : "";
    const rest = other.owners.length ? `${list(other.owners)}は ${other.html} を選んだ。` : "";
    return `あなたの選択は ${picked.html}${same}。${rest}`;
  }
  const same = picked.owners.length ? `, the same as ${list(picked.owners)}` : "";
  const rest = other.owners.length ? ` ${list(other.owners)} chose ${other.html}.` : "";
  return `You picked ${picked.html}${same}.${rest}`;
}

function replayCaption(example) {
  const round = roundText(example.round);
  const left = tilesLeftText(example.left);
  const standing = example.current_rank
    ? isJa
      ? `LuckyJ は${whole.format(example.score || 0)}点で現在${rankText(example.current_rank)}`
      : `LuckyJ is ${rankText(example.current_rank)} on ${whole.format(example.score || 0)}`
    : "";
  if (example.kind === "call") {
    return isJa
      ? `${round}、${left}。${standing}。${seatLabel(example.called_from)}が[[${example.called_tile}]]を切った。`
      : `${round}, ${left}. ${standing}; ${seatLabel(example.called_from)} has just discarded the [[${example.called_tile}]].`;
  }
  if (example.draw) {
    return isJa
      ? `${round}、${left}。${standing}、[[${example.draw}]]をツモった。`
      : `${round}, ${left}. ${standing} and has just drawn the [[${example.draw}]].`;
  }
  return isJa ? `${round}、${left}。${standing}。` : `${round}, ${left}. ${standing}.`;
}

function handCellFor(cells, tile, preferLast) {
  const exact = (cell) => cell.dataset.tile === tile;
  const base = (cell) => sameBaseTile(cell.dataset.tile, tile);
  if (preferLast && cells.length && (exact(cells[cells.length - 1]) || base(cells[cells.length - 1]))) {
    return cells[cells.length - 1];
  }
  return cells.find(exact) || cells.find(base) || null;
}

function markReplayHand(card, example, revealed) {
  const cells = Array.from(card.querySelectorAll(".player-hand.player-current .tile-threat-cell"));
  if (!cells.length) return;
  const last = cells[cells.length - 1];
  if (example.draw && sameBaseTile(last.dataset.tile, example.draw)) last.classList.add("is-drawn");
  for (const cell of cells) {
    cell.classList.remove("is-luckyj-cut", "is-model-cut");
    delete cell.dataset.mark;
  }
  if (!revealed || example.kind === "call") return;
  const drewActual = example.draw && sameBaseTile(example.draw, example.actual);
  const drewModel = example.draw && sameBaseTile(example.draw, example.naga);
  const model = handCellFor(cells, example.naga, drewModel);
  const luckyj = handCellFor(cells, example.actual, drewActual);
  if (model) {
    model.classList.add("is-model-cut");
    model.dataset.mark = modelName("nishiki");
  }
  if (luckyj) {
    luckyj.classList.add("is-luckyj-cut");
    luckyj.dataset.mark = "LuckyJ";
  }
}

// The hand's result, from the build's "draw, self delta +1500" shorthand.
function outcomeText(outcome) {
  const text = String(outcome || "");
  const signed = (value) => `${Number(value) > 0 ? "+" : ""}${whole.format(Number(value))}`;
  // A result that cost or paid nothing needs no number after it.
  const change = (value) => (Number(value) === 0 ? "" : ` (${signed(value)})`);
  const seat = (name) => seatLabel(name);
  let m = text.match(/^draw, self delta ([+-]?\d+)/);
  if (m) return isJa ? `流局${change(m[1])}` : `Hand ended in a draw${change(m[1])}`;
  m = text.match(/^self won (.*), delta ([+-]?\d+)/);
  if (m) return isJa ? `LuckyJ の和了${change(m[2])}` : `LuckyJ won the hand${change(m[2])}`;
  m = text.match(/^self dealt into (\w+), delta ([+-]?\d+)/);
  if (m) return isJa ? `LuckyJ が${seat(m[1])}に放銃${change(m[2])}` : `LuckyJ dealt into ${seat(m[1])}${change(m[2])}`;
  m = text.match(/^(\w+) won, self delta ([+-]?\d+)/);
  if (m) return isJa ? `${seat(m[1])}の和了${change(m[2])}` : `${seat(m[1])} won the hand${change(m[2])}`;
  return "";
}

function renderPointExampleCard(pointKey, example, guide, mortalPoints, index, total) {
  const exampleGuide = (isJa ? example.guide_ja || example.guide : example.guide) || guide || {};
  const exampleMortal = example.mortal || pointMortalForExample(mortalPoints, pointKey, example, index);
  const anchorId = exampleAnchorId(pointKey, index);
  const choices = quizChoices(example, exampleMortal);
  const card = document.createElement("article");
  card.className = "point-example-card conceal-hands";
  card.id = anchorId;
  const replayLabel = isJa ? `実戦例 ${index + 1}/${total}` : `Replay ${index + 1} of ${total}`;
  const buttons = choices
    .map(
      (choice) => `
        <button type="button" class="quiz-choice" data-choice="${choice.id}" aria-pressed="false">
          ${choice.tile ? tileIcon(choice.tile, "quiz-tile") : ""}
          <span class="quiz-choice-text">
            <span class="quiz-choice-action">${choice.action}</span>
            <span class="quiz-choice-note">${choice.note || ""}</span>
          </span>
        </button>`
    )
    .join("");
  card.innerHTML = `
    <figure class="replay-figure" aria-label="${escapeHtml(replayLabel)}">
      <div class="replay-table"></div>
      <div class="replay-panel">
        <div class="replay-panel-head"><span class="figure-label">${escapeHtml(replayLabel)}</span></div>
        <p class="replay-caption"></p>
        <div class="replay-rule" aria-hidden="true"></div>
        <div class="replay-quiz">
          <p class="quiz-label">${t("yourCall")}</p>
          <p class="quiz-prompt"></p>
          <div class="quiz-choices" role="group" aria-label="${escapeHtml(t("yourCall"))}">${buttons}</div>
          <button type="button" class="quiz-skip">${t("showAnswer")}</button>
        </div>
        <div class="replay-answer" hidden>
          <p class="quiz-result" aria-live="polite"></p>
        </div>
      </div>
    </figure>
    <div class="replay-notes" hidden></div>
  `;
  card.querySelector(".replay-caption").append(richText(replayCaption(example)));
  card.querySelector(".quiz-prompt").append(richText(exampleGuide.prompt || ""));
  card.querySelector(".replay-table").append(renderMahjongTable(example.table));

  const answer = card.querySelector(".replay-answer");
  if (example.kind === "call") {
    const line = document.createElement("div");
    line.className = "call-line";
    line.innerHTML = `
      <span>${t("call")} ${escapeHtml(callActionLabel(example.call))} ${tileIcon(example.called_tile, "discard-tile")} ${isJa ? "を" : "from"} ${escapeHtml(seatLabel(example.called_from))}${isJa ? "から" : ""}</span>
      <span>${t("meld")} ${callMeldForExample(example)}</span>
      <span>${t("discardAfterCall")} ${tileIcon(example.discard_after_call, "discard-tile")}</span>
    `;
    answer.append(line, renderCallModelBlock(example));
  } else {
    const compare = document.createElement("div");
    compare.className = "comparison";
    if (example.actual_eval && example.naga_eval) {
      compare.append(
        comparison(t("luckyj"), example.actual_eval, example.actual_danger, example.actual_prob, t("nagaThreat")),
        comparison(t("nagaTop"), example.naga_eval, example.naga_danger, example.naga_prob, t("nagaThreat"))
      );
    } else {
      compare.innerHTML = `
        <div class="decision"><b>${t("luckyj")}</b>${probabilityChip(t("nagaWeight"), example.actual_prob)}<span class="discard-line">${t("discard")} ${tileIcon(example.actual, "discard-tile")} <em>${escapeHtml(tileName(example.actual))}</em></span><span>${t("nagaThreat")} ${dangerText(example.actual_danger)}</span></div>
        <div class="decision"><b>${t("nagaTop")}</b>${probabilityChip(t("nagaWeight"), example.naga_prob)}<span class="discard-line">${t("discard")} ${tileIcon(example.naga, "discard-tile")} <em>${escapeHtml(tileName(example.naga))}</em></span><span>${t("nagaThreat")} ${dangerText(example.naga_danger)}</span></div>
      `;
    }
    answer.append(compare, safetyPanel(example.kept_tile_safety));
  }
  const footer = document.createElement("div");
  footer.className = "replay-footer";
  footer.innerHTML = `
    <span class="evidence-tier ${escapeHtml(example.evidence_tier || "")}">${escapeHtml(pointEvidenceTierText(example))}</span>
    <button type="button" class="quiz-again">${t("askAgain")}</button>
  `;
  answer.append(footer);

  // The commentary, on paper under the figure, opens with the answer.
  const notes = card.querySelector(".replay-notes");
  notes.append(renderGuideBlock(exampleGuide));
  notes.append(renderMortalBlock(exampleMortal));
  notes.append(renderYakuhaiCleanupNote(example));
  const links = document.createElement("p");
  links.className = "case-links";
  const handResult = outcomeText(example.outcome);
  links.innerHTML = `<span>${handResult ? `${escapeHtml(handResult)} · ` : ""}${t("finalRank")} ${escapeHtml(rankText(example.rank))}</span> ${sourceLinks(example)}`;
  notes.append(links);

  const choiceButtons = Array.from(card.querySelectorAll(".quiz-choice"));
  const skip = card.querySelector(".quiz-skip");
  const result = card.querySelector(".quiz-result");

  function paint(pickedId, revealed) {
    card.classList.toggle("is-revealed", revealed);
    card.classList.toggle("conceal-hands", !revealed);
    answer.hidden = !revealed;
    notes.hidden = !revealed;
    skip.hidden = revealed;
    for (const button of choiceButtons) {
      const choice = choices.find((item) => item.id === button.dataset.choice);
      button.setAttribute("aria-pressed", revealed && pickedId === choice.id ? "true" : "false");
      const note = button.querySelector(".quiz-choice-note");
      if (revealed) {
        const owners = choice.owners.length ? choice.owners : [isJa ? "該当なし" : "no engine"];
        note.innerHTML = `<span class="quiz-owner${choice.id === "model" ? " is-model" : ""}">${escapeHtml(readableList(owners))}</span>`;
      } else {
        note.innerHTML = choice.note || "";
      }
    }
    result.innerHTML = revealed ? quizResultHtml(choices, pickedId) : "";
    markReplayHand(card, example, revealed);
    applyTileCompatibility(card);
  }

  for (const button of choiceButtons) {
    button.addEventListener("click", () => {
      replayPicks.set(anchorId, button.dataset.choice);
      paint(button.dataset.choice, true);
    });
  }
  skip.addEventListener("click", () => {
    replayPicks.set(anchorId, "");
    paint("", true);
  });
  footer.querySelector(".quiz-again").addEventListener("click", () => {
    replayPicks.delete(anchorId);
    paint("", false);
    choiceButtons[0]?.focus();
  });

  const remembered = replayPicks.get(anchorId);
  paint(remembered || "", remembered !== undefined);
  return card;
}

function renderPointExamples(examples, guides, mortalPoints) {
  pointExampleControllers.clear();
  loadPointExampleSelections();
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
    const head = document.createElement("div");
    head.className = "example-tab-head";
    head.innerHTML = `<p class="label">${t("replaysLabel")}</p><div class="example-tab-heading"><h4>${t("replaysTitle")}</h4><p>${t("replaysNote")}</p></div>`;
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

    function showExample(index, { updateLocation = false, reveal = false } = {}) {
      selectedIndex = clampExampleIndex(index, items.length);
      // A link to one example opens it answered: the reader came for that frame.
      const anchorId = exampleAnchorId(pointKey, selectedIndex);
      if (reveal && !replayPicks.has(anchorId)) replayPicks.set(anchorId, "");
      pointExampleSelections.set(pointKey, selectedIndex);
      savePointExampleSelections();
      updatePointRailProgress(pointKey, selectedIndex, items.length);
      buttons.forEach((button, buttonIndex) => {
        const selected = buttonIndex === selectedIndex;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", selected ? "true" : "false");
        button.tabIndex = selected ? 0 : -1;
      });
      body.replaceChildren(renderPointExampleCard(pointKey, items[selectedIndex], guide, mortalPoints, selectedIndex, items.length));
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

    head.append(tablist);
    shell.append(head, body);
    placeholder.replaceChildren(shell);
    const target = parsePointExampleLocation();
    const linked = target.pointKey === pointKey && target.exampleIndex !== null;
    const initialIndex = linked ? target.exampleIndex : (pointExampleSelections.get(pointKey) ?? 0);
    showExample(initialIndex, { reveal: linked });
  }
}

function tileClass(tile) {
  const base = String(tile || "").replace("r", "");
  if (["E", "S", "W", "N", "P", "F", "C"].includes(base)) return "honor";
  if (base.startsWith("1") || base.startsWith("9")) return "terminal";
  return "middle";
}

function pointEvidenceTierText(item) {
  const labels = isJa
    ? { corroborated: "複数系統支持", split_supported: "分岐支持", contested: "対立例", unverified: "第二確認なし", unsupported: "支持なし" }
    : { corroborated: "corroborated", split_supported: "split-supported", contested: "contested", unverified: "second-check unavailable", unsupported: "unsupported" };
  return labels[item.evidence_tier] || (isJa ? "証拠区分未設定" : "evidence tier unavailable");
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

function renderEngineConsensus(mortalPoints) {
  const target = document.querySelector("#engineConsensus");
  if (!target || !mortalPoints) return;
  let backed = 0;
  let total = 0;
  const rows = Object.entries(mortalPoints)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([pointKey, entries]) => {
      const agree = entries.filter((item) => item.mortal_agrees_luckyj).length;
      backed += agree;
      total += entries.length;
      return { pointKey, agree, count: entries.length };
    });
  if (!total) return;
  const intro = isJa
    ? `選ばれた${total}例のうち、Mortal が LuckyJ の選択を支持したのは${backed}例。残りは NAGA 系ヘッドの支持、または意図的に収録した不一致例（検討ポイント用）である。`
    : `Across the ${total} showcased examples, Mortal independently backs LuckyJ's line in ${backed}. The rest are backed by a NAGA head or kept deliberately as disagreement studies.`;
  const bars = rows
    .map(({ pointKey, agree, count }) => {
      const pct = count ? Math.round((agree / count) * 100) : 0;
      const num = pointKey.replace("point-", "");
      return `
        <div class="consensus-row">
          <a href="#${pointKey}">${escapeHtml(num)}</a>
          <div class="consensus-bar" role="img" aria-label="${escapeHtml(pointKey)}: Mortal ${agree}/${count}">
            <span style="width:${pct}%"></span>
          </div>
          <em>${agree}/${count}</em>
        </div>
      `;
    })
    .join("");
  target.innerHTML = `
    <div class="engine-consensus">
      <h3>${isJa ? "第二エンジンの支持率" : "Second-engine agreement"}</h3>
      <p>${intro}</p>
      <div class="consensus-grid">${bars}</div>
    </div>
  `;
}

function renderPointValidation(validation) {
  const summary = document.querySelector("#validationSummary");
  const grid = document.querySelector("#pointValidation");
  const points = validation?.points || [];

  if (summary && validation?.summary && validation?.method) {
    const proxySupported = validation.summary.proxy_supported || 0;
    const contextQualified = validation.summary.context_qualified || 0;
    const contested = validation.summary.contested || 0;
    const decisions = validation.method.eligible_decisions || validation.method.book_decisions;
    summary.innerHTML = `
      <div class="stat-strip">
        <span><b>${whole.format(validation.summary.total || points.length)}</b>${isJa ? "監査した主張" : "audited claims"}</span>
        <span><b>${whole.format(proxySupported)}</b>${isJa ? "proxy支持" : "proxy-supported"}</span>
        <span><b>${whole.format(contextQualified)}</b>${isJa ? "文脈条件付き" : "context-qualified"}</span>
        <span><b>${whole.format(contested)}</b>${isJa ? "例示は反対多数" : "contested showcases"}</span>
        <span><b>${whole.format(decisions || 0)}</b>${isJa ? "判断母数" : "decision base"}</span>
      </div>
      <p class="validation-method-warning">${escapeHtml(isJa ? validation.method.note_ja : validation.method.note)}</p>
    `;
  }

  if (!grid || !points.length) return;
  grid.innerHTML = "";
  for (const item of points) {
    const card = document.createElement("article");
    card.className = `validation-card ${escapeHtml(item.strength || "context_qualified")}`;
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
  renderCommitStamp();
  setupRetractingTopbar();
  setupRunningHead();
  convertStaticTileMarkup();
  applyTileCompatibility();
  const guidePath = isJa ? "strategy-guides.ja.json" : "strategy-guides.json";
  const [bookResponse, exampleResponse, guideResponse, mortalResponse, validation] = await Promise.all([
    fetch(dataAsset("book-data.json")),
    fetch(dataAsset("point-examples.json")),
    fetch(dataAsset(guidePath)),
    fetch(dataAsset("mortal-analysis.json")),
    fetchJson("point-validation.json", {}),
  ]);
  const data = await bookResponse.json();
  const examples = await exampleResponse.json();
  const guides = await guideResponse.json();
  const mortal = await mortalResponse.json();
  const summary = data.summary;
  const top = data.top_bottom.top_half;
  const bottom = data.top_bottom.bottom_half;
  const metrics = document.querySelector("#metrics");
  renderSourceScope(data);
  renderBookStatSpans(data);
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
  renderEngineConsensus(mortal.points);
  renderPointExamples(examples, guides, mortal.points);
  syncPointExamplesFromLocation({ scroll: true });
  applyTileCompatibility();
}

// Pages marked data-app="table-only" load app.js for its tile and table renderers
// and run their own script, so the playbook data is not fetched there. The home page
// (data-app="home") only needs the running head, the tiles and the commit stamp.
if (document.body?.dataset.app === "home") {
  renderCommitStamp();
  setupRetractingTopbar();
  setupRunningHead();
  convertStaticTileMarkup();
  applyTileCompatibility();
  settleHashScroll();
} else if (document.body?.dataset.app !== "table-only") {
  window.addEventListener("hashchange", () => syncPointExamplesFromLocation({ scroll: true }));
  window.addEventListener("popstate", () => syncPointExamplesFromLocation({ scroll: true }));

  const loaded = main();
  settleHashScroll(loaded);
  loaded.catch((error) => {
    const metrics = document.querySelector("#metrics");
    if (metrics) {
      metrics.innerHTML = `<div class="metric"><b>${t("dataLoadFailed")}</b><span>${error.message}</span></div>`;
    }
  });
}
