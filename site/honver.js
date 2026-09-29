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
 *
 * The Japanese edition (honver-ja.html, <html lang="ja">) renders the same tables with app.js's isJa
 * words and swaps in each card's Japanese text from honver-guide-ja.json.
 */
(function () {
  const guideAsset = "honver-guide.json?v=20260929-guide-ja";
  const guideJaAsset = "honver-guide-ja.json?v=20260929-guide-ja";
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
  const SAFETY_TEXT = isJa
    ? {
        genbutsu: "現物",
        dead: "3枚見えの字牌",
        suji: "筋",
        nakasuji: "中筋",
        "virtual nakasuji": "疑似中筋",
        "half suji": "片筋",
        "honor, 2 seen": "2枚見えの字牌",
        "live honor": "生きた字牌",
        "live terminal": "無筋の端牌",
        "live 2-3-7-8": "無筋の2・3・7・8",
        "live 4-5-6": "無筋の4・5・6",
      }
    : {
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
  const REL = isJa
    ? { self: "あなた", shimocha: "下家", toimen: "対面", kamicha: "上家" }
    : { self: "You", shimocha: "Shimocha", toimen: "Toimen", kamicha: "Kamicha" };
  const YOU = isJa ? "あなた" : "You";
  const BETTER = isJa ? "推奨" : "Better";
  // honver-guide.json keeps the English yaku names; the Japanese edition shows the usual ones.
  const YAKU_JA = {
    riichi: "リーチ", "double riichi": "ダブルリーチ", ippatsu: "一発", "menzen tsumo": "門前清自摸和",
    tanyao: "断幺九", pinfu: "平和", iipeikou: "一盃口", ryanpeikou: "二盃口", haku: "白", hatsu: "發", chun: "中",
    "seat wind": "自風牌", "round wind": "場風牌", honitsu: "混一色", chinitsu: "清一色", toitoi: "対々和",
    chiitoitsu: "七対子", sanshoku: "三色同順", ittsu: "一気通貫", chanta: "混全帯幺九", junchan: "純全帯幺九",
    sanankou: "三暗刻", shousangen: "小三元", honroutou: "混老頭", sankantsu: "三槓子", "sanshoku doukou": "三色同刻",
    haitei: "海底摸月", houtei: "河底撈魚", rinshan: "嶺上開花", chankan: "槍槓", dora: "ドラ", "red five": "赤ドラ",
    "ura dora": "裏ドラ",
  };
  const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

  function shantenText(s) {
    if (isJa) return s === 0 ? "テンパイ" : `${s}シャンテン`;
    return s === 0 ? "tenpai" : `${s}-shanten`;
  }

  function acceptText(option) {
    if (option.shanten === 0) {
      const waits = (option.waits || []).map((w) => tileIcon(w, "inline-tile")).join("");
      if (isJa) return `${waits ? `${waits}待ち、` : ""}残り${option.accept}枚`;
      return `${option.accept} live tile${option.accept === 1 ? "" : "s"}${waits ? ` on ${waits}` : ""}`;
    }
    return isJa ? `有効牌${option.accept}枚` : `${option.accept} tiles improve it`;
  }

  // "Kamicha riichi (turn 3)" or "Toimen 2 calls", from the threat's seat, kind and count.
  function threatLabel(threat) {
    if (!isJa) return threat.label;
    const seat = REL[threat.rel] || threat.rel;
    return threat.kind === "riichi" ? `${seat}リーチ（${threat.turn}巡目）` : `${seat}${threat.calls}副露`;
  }

  function versus(threat) {
    return isJa ? `対${threatLabel(threat)}` : `vs ${threat.label}`;
  }

  function safetyChip(label) {
    if (!label) return "";
    return `<i class="safety-chip ${SAFETY_CLASS[label] || ""}">${escapeHtml(SAFETY_TEXT[label] || label)}</i>`;
  }

  function safetyLines(option, threats) {
    if (!threats?.length) return "";
    return `<span class="guide-safety">${threats
      .map((threat, i) => `<span>${escapeHtml(versus(threat))}: ${safetyChip(option.safety?.[i])}</span>`)
      .join("")}</span>`;
  }

  function decisionBlock(kind, title, option, frame, extra = "") {
    const tile = option?.tile;
    const declared = option.action === "riichi";
    const action = isJa
      ? frame.kind === "riichi"
        ? `${declared ? "リーチ" : "ダマ"}、打${tileIcon(tile, "discard-tile")}`
        : `${option?.riichi ? "リーチ、打" : "打"}${tileIcon(tile, "discard-tile")} <em>${escapeHtml(tileName(tile))}</em>`
      : frame.kind === "riichi"
        ? `${declared ? "Riichi" : "Dama"}, cut ${tileIcon(tile, "discard-tile")}`
        : `${option?.riichi ? "Riichi, cut" : "Cut"} ${tileIcon(tile, "discard-tile")} <em>${escapeHtml(tileName(tile))}</em>`;
    const leaves = isJa
      ? `${shantenText(option.shanten)}、${acceptText(option)}`
      : `Leaves ${shantenText(option.shanten)}, ${acceptText(option)}`;
    return `
      <div class="decision guide-${kind}">
        <b>${escapeHtml(title)}</b>
        <span class="discard-line">${action}</span>
        <span>${leaves}</span>
        ${frame.kind === "riichi" ? "" : safetyLines(option, frame.threats)}
        ${extra}
      </div>
    `;
  }

  // A call frame shows the hand before the call: what the call left, against passing.
  function callBlocks(frame) {
    const you = frame.you;
    const meld = (you.meld || []).map((t) => tileIcon(t, "inline-tile")).join("");
    const from = REL[frame.call_from] || frame.call_from || "";
    const better = frame.better;
    if (isJa) {
      const action = { chi: "チー", pon: "ポン" }[you.action] || "鳴き";
      return `
      <div class="decision guide-you">
        <b>${YOU}</b>
        <span class="discard-line">${tileIcon(you.tile, "discard-tile")}を${escapeHtml(action)} <em>${escapeHtml(from)}の捨て牌</em></span>
        <span>副露${meld}、打${tileIcon(you.then_cut, "inline-tile")}</span>
        <span>${shantenText(you.shanten)}（副露）</span>
      </div>
      <div class="decision guide-better">
        <b>${BETTER}</b>
        <span class="discard-line">鳴かない</span>
        <span>${shantenText(better.shanten)}のまま${better.closed === false ? "" : "門前"}、有効牌${better.accept}枚</span>
      </div>
    `;
    }
    const action = you.action ? you.action[0].toUpperCase() + you.action.slice(1) : "Call";
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
        <span>Stays ${shantenText(better.shanten)}${better.closed === false ? "" : " and closed"}, ${better.accept} tiles improve it</span>
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
      const yakuNote = isJa
        ? frame.ron_yaku_without_riichi
          ? "リーチなしでも役があり、ダマでロンできる。"
          : "リーチなしでは役がなく、ダマではツモでしかアガれない。"
        : frame.ron_yaku_without_riichi
          ? "Has a yaku without riichi, so dama can ron."
          : "No yaku without riichi: dama can only win by tsumo.";
      const sameTile = isJa ? "同じ牌でリーチ。" : "Same tile, declared.";
      wrap.innerHTML =
        decisionBlock("you", YOU, frame.you, frame, `<small>${escapeHtml(yakuNote)}</small>`) +
        decisionBlock("better", BETTER, frame.better, frame, `<small>${escapeHtml(sameTile)}</small>`);
      return wrap;
    }
    const you = decisionBlock(
      "you",
      frame.you.tsumogiri ? (isJa ? "あなた（ツモ切り）" : "You (cut the tile you drew)") : YOU,
      frame.you,
      frame
    );
    const better = frame.better ? decisionBlock("better", BETTER, frame.better, frame) : "";
    wrap.innerHTML = you + better;
    return wrap;
  }

  function optionsBlock(frame) {
    if (!frame.options?.length) return null;
    const details = document.createElement("details");
    details.className = "guide-options";
    const threatHeads = (frame.threats || []).map((t) => `<th scope="col">${escapeHtml(versus(t))}</th>`).join("");
    const rows = frame.options
      .map((option) => {
        const classes = [
          option.tile === frame.you?.tile ? "is-you" : "",
          frame.better && option.tile === frame.better.tile ? "is-better" : "",
        ]
          .filter(Boolean)
          .join(" ");
        const tag =
          option.tile === frame.you?.tile
            ? `<small>${isJa ? YOU : "you"}</small>`
            : frame.better && option.tile === frame.better.tile
              ? `<small>${isJa ? BETTER : "better"}</small>`
              : "";
        const safety = (frame.threats || []).map((_, i) => `<td>${safetyChip(option.safety?.[i])}</td>`).join("");
        return `<tr class="${classes}"><th scope="row">${tileIcon(option.tile, "inline-tile")}${tag}</th><td>${shantenText(
          option.shanten
        )}</td><td>${acceptText(option)}</td>${safety}</tr>`;
      })
      .join("");
    const words = isJa
      ? {
          summary: "この手のすべての打牌",
          heads: ["打牌", "残る形", "受け入れ"],
          note: "受け入れは、手を進める牌それぞれについて、卓上から見えていない枚数を数えたもの。テンパイでは役を問わず、生きているアガリ牌を数える。",
        }
      : {
          summary: "Every discard from this hand",
          heads: ["Cut", "Leaves", "Acceptance"],
          note: "Acceptance counts the unseen copies of every tile that would improve the hand, from what you could see at the table. At tenpai it counts live winning tiles, before yaku.",
        };
    details.innerHTML = `
      <summary>${words.summary}</summary>
      <div class="guide-options-scroll">
        <table>
          <thead><tr>${words.heads.map((head) => `<th scope="col">${head}</th>`).join("")}${threatHeads}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="guide-options-note">${words.note}</p>
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
        cell.dataset.mark = isJa ? "リーチ" : "Riichi";
      }
      return;
    }
    const cut = Number.isInteger(frame.cut_index) ? cells[frame.cut_index] : null;
    if (cut) {
      cut.classList.add("guide-cut");
      cut.dataset.mark = isJa ? (frame.you?.riichi ? "あなたのリーチ" : YOU) : frame.you?.riichi ? "Your riichi" : "Your cut";
    }
    if (Number.isInteger(frame.better_index) && frame.better_index !== frame.cut_index) {
      const better = cells[frame.better_index];
      if (better) {
        better.classList.add("guide-better");
        better.dataset.mark = BETTER;
      }
    }
  }

  function resultText(example) {
    const r = example.result || {};
    if (isJa) {
      const total = `この局のあなたの収支: ${signed(r.hero_delta)}。`;
      if (r.draw || !r.wins?.length) return `流局。${total}`;
      const parts = r.wins.map((win) => {
        const who = win.winner === "self" ? "あなた" : REL[win.winner];
        const how = win.tsumo ? "ツモ" : `${win.from === "self" ? "あなた" : REL[win.from]}からロン`;
        const yaku = win.yaku?.length ? `（${win.yaku.map((y) => YAKU_JA[y] || y).join("、")}）` : "";
        return `${who}が${how}、${whole.format(win.points)}点${yaku}。`;
      });
      return `${parts.join("")}${total}`;
    }
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

  // A corrected step is highlighted the way corrected chapter sentences are.
  function analysisStep(title, text, changed = false) {
    if (!text) return null;
    const section = document.createElement("section");
    section.className = "analysis-step";
    const heading = document.createElement("h5");
    heading.textContent = title;
    const para = document.createElement("p");
    if (changed) {
      const mark = document.createElement("mark");
      mark.className = "guide-changed";
      mark.append(richText(text));
      para.append(mark);
    } else {
      para.append(richText(text));
    }
    section.append(heading, para);
    return section;
  }

  function placementText(n) {
    if (!rankText(n)) return "";
    return isJa ? `${rankText(n)}で終了` : `finished ${rankText(n)}`;
  }

  function turnText(turn) {
    return isJa ? `${turn}巡目` : `Turn ${turn}`;
  }

  // The Japanese edition drops a zero honba: "East 2-0" is 東2局, "South 2-2" is 南2局2本場.
  function roundLabel(round) {
    return isJa ? roundText(round).replace(/0本場$/, "") : roundText(round);
  }

  function roundShort(round) {
    return isJa ? roundText(round).replace(/\d+本場$/, "") : roundText(round).replace(/-\d+$/, "");
  }

  // Correction dates are written "28 September" in the spots file.
  function dateLabel(text) {
    if (!isJa) return text;
    const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    const m = String(text || "").match(/^(\d{1,2}) ([A-Z][a-z]+)$/);
    return m && months.includes(m[2]) ? `${months.indexOf(m[2]) + 1}月${m[1]}日` : text;
  }

  function renderFrame(hosts, example, frame) {
    const table = renderMahjongTable(frame.table);
    markHand(table, frame);
    hosts.table.replaceChildren(table);
    hosts.compare.replaceChildren(comparisonBlock(frame));
    const options = optionsBlock(frame);
    hosts.options.replaceChildren(...(options ? [options] : []));
    hosts.note.replaceChildren();
    const note = analysisStep(turnText(frame.turn), frame.note);
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

  // The site's own replay of the game (replay.html), opened at this hand and turn: a call frame on the
  // discard you called, any other frame on your draw or call, where your discard is decided.
  function replayHref(example, frame) {
    const params = new URLSearchParams({ g: example.game.uuid, r: example.round, t: String(frame.turn) });
    if (frame.kind === "call") params.set("at", "call");
    return `replay.html?${params}`;
  }

  // Cards that are not mistakes carry a verdict label, and their last step is "The verdict".
  const VERDICT_LABELS = isJa
    ? { fine: "ミスなし", unlucky: "不運", close: "際どい判断" }
    : { fine: "No mistake", unlucky: "Bad luck", close: "Close call" };

  function renderCard(example, index, total) {
    const card = document.createElement("article");
    card.className = "point-example-card guide-card";
    card.id = `guide-${example.id}`;
    const first = example.frames[0];
    const game = example.game || {};
    const verdict = VERDICT_LABELS[example.verdict];
    const label = isJa ? `局面 ${index + 1} / ${total}` : `Your turn ${index + 1} of ${total}`;
    const meta = [
      roundLabel(example.round),
      isJa ? turnText(first.turn) : `turn ${first.turn}`,
      isJa ? tilesLeftText(first.left) : `${first.left} tile${first.left === 1 ? "" : "s"} left`,
      [game.date, placementText(game.placement)].filter(Boolean).join(isJa ? "、" : ", "),
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
          ${example.corrected ? `<p class="changed-tag guide-card-corrected">${isJa ? `${escapeHtml(dateLabel(example.corrected.date))}に訂正` : `Corrected ${escapeHtml(example.corrected.date)}`}</p>` : ""}
          <p class="guide-card-meta">${meta}</p>
          <p class="guide-situation"></p>
          <div class="guide-compare-host"></div>
          ${
            game.uuid
              ? `<p class="guide-game-link"><a href="${escapeHtml(replayHref(example, first))}" target="_blank" rel="noopener">${isJa ? "この局を再生（英語）" : "Replay this hand"}</a></p>`
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
      strip.setAttribute("aria-label", isJa ? "この局の巡目" : "Turns in this hand");
      const buttons = example.frames.map((frame, i) => {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "tab");
        button.textContent = turnText(frame.turn);
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
        const link = card.querySelector(".guide-game-link a");
        if (link) link.href = replayHref(example, example.frames[i]);
      }
      card.querySelector(".guide-frame-host").append(strip);
      select(0);
    } else {
      renderFrame(hosts, example, first);
    }

    const notes = card.querySelector(".replay-notes");
    const analysis = document.createElement("div");
    analysis.className = "natsu-analysis";
    const changed = new Set(example.corrected?.fields || []);
    const steps = [
      analysisStep(isJa ? "あなたの選択" : "What you did", example.text.did, changed.has("did")),
      analysisStep(isJa ? "LuckyJの選択" : "What LuckyJ does", example.text.luckyj, changed.has("luckyj")),
      analysisStep(verdict ? (isJa ? "判定" : "The verdict") : isJa ? "修正点" : "The fix", example.text.fix, changed.has("fix")),
    ].filter(Boolean);
    analysis.append(...steps);
    const result = document.createElement("p");
    result.className = "guide-result";
    result.innerHTML = `<b>${isJa ? "局の結果" : "How the hand ended"}</b> ${escapeHtml(resultText(example))}`;
    notes.append(hosts.note, analysis, result, hosts.options);
    applyTileCompatibility(card);
    return card;
  }

  function renderChapter(placeholder, examples) {
    const shell = document.createElement("div");
    shell.className = "point-example-tabs";
    const head = document.createElement("div");
    head.className = "example-tab-head";
    const heading = isJa
      ? examples.length === 1 ? "実戦からの1局面" : "実戦からの局面"
      : examples.length === 1 ? "A turn from your games" : "Turns from your games";
    head.innerHTML = `<p class="label">${isJa ? "あなたの局面" : "Your turns"}</p><div class="example-tab-heading"><h4>${heading}</h4></div>`;
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
      button.innerHTML = `<b>${index + 1}</b><span>${escapeHtml(roundShort(example.round))}</span>`;
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
    // A link to #guide-<id> elsewhere on the page (the What's new notices) opens that card.
    window.addEventListener("hashchange", () => {
      let id = "";
      try {
        id = decodeURIComponent(location.hash.replace(/^#guide-/, ""));
      } catch {
        return;
      }
      const index = examples.findIndex((e) => e.id === id);
      if (index < 0) return;
      show(index);
      document.getElementById(`guide-${id}`)?.scrollIntoView({ block: "start", behavior: "instant" });
    });
  }

  // Opponents' hands: the checkbox under "Reading the tables" and the button on each figure are one
  // switch, remembered between visits.
  function handsVisible() {
    return !document.body.classList.contains("conceal-hands");
  }

  function handsToggleHtml() {
    return `<button type="button" class="hands-toggle" aria-pressed="${handsVisible() ? "true" : "false"}">${isJa ? "全員の手牌を表示" : "Show all hands"}</button>`;
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
    "dora-deal": isJa
      ? {
          caption: "配牌のドラが増えても、あなたの和了率は横ばいのまま。LuckyJの和了率は上がっていく。",
          short: ["なし", "1枚", "2枚", "3枚以上"],
          panels: [
            { title: "和了率", sub: "配牌のドラと赤5の枚数別、アガった局の割合", you: 1, lj: 2, min: 15, max: 35, ticks: [15, 20, 25, 30, 35], unit: "%" },
            { title: "100局あたりの満貫", sub: "配牌100局あたりの満貫以上のアガリ", you: 3, lj: 4, min: 0, max: 25, ticks: [0, 5, 10, 15, 20, 25], unit: "" },
          ],
          noiseRow: 3,
          noiseNote: "14局、誤差の範囲",
          legend: ["あなた、80半荘", "LuckyJ、1,255半荘", "局数が少なく読めない"],
          byDora: "配牌のドラ",
          table: "数値の表",
        }
      : {
          caption: "Your win rate stays flat as the dora in the deal go up; LuckyJ's climbs.",
          short: ["None", "One", "Two", "Three+"],
          panels: [
            { title: "Win rate", sub: "Hands won, by dora and red fives in the deal", you: 1, lj: 2, min: 15, max: 35, ticks: [15, 20, 25, 30, 35], unit: "%" },
            { title: "Mangan per 100 hands", sub: "Wins of mangan or more, per 100 hands dealt", you: 3, lj: 4, min: 0, max: 25, ticks: [0, 5, 10, 15, 20, 25], unit: "" },
          ],
          // The three-dora row holds 14 of your hands, which the chapter calls noise.
          noiseRow: 3,
          noiseNote: "14 hands, noise",
          legend: ["You, 80 games", "LuckyJ, 1,255 games", "too few hands to read"],
          byDora: "by dora in the deal",
          table: "The numbers as a table",
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
    const svg = svgEl("svg", {
      viewBox: `0 0 ${W} ${H}`,
      role: "img",
      "aria-label": isJa ? `${panel.title}、あなたとLuckyJ、${spec.byDora}別` : `${panel.title}, you against LuckyJ, ${spec.byDora}`,
    });
    for (const tick of panel.ticks) {
      svg.append(svgEl("line", { x1: m.l, x2: m.l + pw, y1: y(tick), y2: y(tick), class: "grid" }));
      svg.append(svgEl("text", { x: m.l - 10, y: y(tick) + 4, class: "tick" }, `${tick}${panel.unit}`));
    }
    rows.forEach((_, i) => svg.append(svgEl("text", { x: x(i), y: m.t + ph + 24, class: "cat" }, spec.short[i] || rows[i].label)));
    const cross = svgEl("line", { x1: 0, x2: 0, y1: m.t, y2: m.t + ph, class: "cross" });
    svg.append(cross);
    const series = [
      { key: "lj", values: lj, name: "LuckyJ" },
      { key: "you", values: you, name: YOU },
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
        "aria-label": isJa
          ? `${spec.byDora} ${row.label}: あなた ${fmt(you[i])}、LuckyJ ${fmt(lj[i])}`
          : `${row.label}: you ${fmt(you[i])}, LuckyJ ${fmt(lj[i])}`,
      });
      const show = () => {
        cross.setAttribute("x1", x(i));
        cross.setAttribute("x2", x(i));
        cross.classList.add("is-on");
        tip.hidden = false;
        const place = isJa ? `${spec.byDora}: ${row.label}` : `${row.label} dora in the deal`;
        tip.innerHTML = `<span>${escapeHtml(place)}</span><b class="you">${fmt(you[i])} <small>${isJa ? YOU : "you"}</small></b><b class="lj">${fmt(lj[i])} <small>LuckyJ</small></b>`;
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
    legend.innerHTML = `<span class="key you">${spec.legend[0]}</span><span class="key lj">${spec.legend[1]}</span>${
      spec.noiseNote ? `<span class="key hollow">${spec.legend[2]}</span>` : ""
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
    summary.textContent = spec.table;
    scroll.replaceWith(details);
    details.append(summary, scroll);
    details.before(figure);
  }

  // Each card keeps its tables and swaps in its Japanese title, commentary and turn notes.
  function inJapanese(data, ja) {
    for (const examples of Object.values(data.chapters || {})) {
      for (const example of examples) {
        const text = ja.examples?.[example.id];
        if (!text) continue;
        example.title = text.title || example.title;
        example.text = { ...example.text, ...text.text };
        example.frames.forEach((frame, i) => {
          frame.note = text.notes?.[i] || frame.note;
        });
      }
    }
    return data;
  }

  async function main() {
    renderCommitStamp();
    setupRetractingTopbar();
    setupRunningHead();
    convertStaticTileMarkup();
    applyTileCompatibility();
    setupTimingCharts();
    setupHandToggle();
    for (const table of document.querySelectorAll("table.guide-data[data-chart]")) renderGuideChart(table);
    let data;
    try {
      const load = async (asset) => {
        const response = await fetch(asset);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      };
      const [tables, ja] = await Promise.all([load(guideAsset), isJa ? load(guideJaAsset) : null]);
      data = ja ? inJapanese(tables, ja) : tables;
    } catch (error) {
      for (const placeholder of document.querySelectorAll("[data-guide-examples]")) {
        placeholder.innerHTML = isJa
          ? `<p class="guide-error">例の表を読み込めなかった（${escapeHtml(error.message)}）。</p>`
          : `<p class="guide-error">The example tables could not load (${escapeHtml(error.message)}).</p>`;
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
