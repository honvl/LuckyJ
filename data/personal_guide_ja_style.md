# The Japanese edition of Honver's Guide

`site/honver-ja.html` is `site/honver.html` in Japanese: the same ids, chapters, notices, marks and
replay links (tests/test_site_structure.py `JapaneseGuideTests`). The example cards take their words
from each spot's `ja` block (title, situation, did, luckyj, fix) and each frame's `note_ja` in
`data/personal_guide_spots.json`; `scripts/build_personal_guide.py` writes them to
`site/honver-guide-ja.json` and stops when English text has no Japanese. A new chapter therefore needs
its Japanese section, chapter-list entry and notice in honver-ja.html, and `ja` / `note_ja` on its spots.

Japanese prose goes on one line per paragraph: a line break between Japanese characters shows as a
space in Chrome.

This is the brief the edition was translated from on 29 September 2026.

The Japanese playbook (`site/ja.html`) is the style model. Follow this sheet for terms and titles so
new chapters read like the old ones.

## Voice

- である調. Plain professional-player voice: short declarative sentences, concrete numbers, direct
  instructions. Natural Japanese, not word-for-word English.
- No のである / もちろん tics, no metaphors that are not in the English, no em-dashes or long dashes
  (—, –, ――). Use 、。： or （ ）.
- The English says "you" to Honver. Drop the subject where Japanese reads naturally without it; use
  「あなた」 when the sentence contrasts you with LuckyJ ("You declare 41%" → 「あなたは41%」). Do not
  start every sentence with あなたは.
- At most one 「XではなくYである」 contrast per chapter.
- Rates: use the numbers the English gives. A ratio written in words ("three times in four") may be
  「4回に3回」, but never more than two in one paragraph and not over and over in a section; prefer a
  percentage when the English gives one.
- Write LuckyJ, Mortal, NAGA, Honver with no space before particles: 「LuckyJは」「Mortalの」.
- Japanese punctuation 、。「」（）. Half-width digits and %, with the English thousands commas
  (12,000, 3,877). Keep `&minus;` / `−` minus signs as they are.

## What must not change

- Every HTML tag and attribute stays exactly as it is: ids, classes, hrefs (including every
  `replay.html?...` link and its `data-you`), `data-*` attributes, `<mark id="fix-..." class="guide-changed">`,
  `<b>`, `<i class="safety-chip ...">`, `<code>`, `<table>` structure. Translate only the text between tags
  and the text attributes `aria-label`, `title`, `alt`, `data-contents-label`, `content` (meta).
  Inline tags may move inside a sentence to fit Japanese word order, but each must wrap the matching words.
  A `<mark class="guide-changed">` must wrap the Japanese of the sentence it wraps in English.
- `[[tile]]` markup (`[[4p]]`, `[[5m]]-[[8m]]`, `[[C]]`) stays exactly as written; do not turn it into words.
  Tile names written as words become Japanese: haku 白, hatsu 發, chun 中, East 東 (as a tile), a red five 赤5.
- Every number stays the same. English numbers in words can become digits ("three dora" → 「ドラ3枚」).
- Keep HTML comments (e.g. `<!-- caller-surface -->`) and entities such as `&#183;` as they are.
- `<code>` contents (script names, file paths) stay in English.
- Leave the tags `<span class="new-tag">New</span>`, `<span class="new-tag">Latest</span>` and
  `<span class="guide-news-tag">Corrected</span>` in English, as the Japanese playbook does.

## Titles (use these exact strings wherever a chapter's title appears: h3, chapter list, next-chapter links)

| # | id | Japanese title | Topic |
|---|----|----------------|-------|
| 01 | value | 手の方針を決める前にドラを数える | 打点 |
| 02 | open-table | 誰かが鳴いたら安手を急がない | 鳴きが入った卓 |
| 03 | calls | 鳴きには、損のない安全牌を切る | 鳴き |
| 04 | folds | 正しい牌でオリる | オリ |
| 05 | push | アガれるテンパイを押す | 押し |
| 06 | dora-points | ドラのある手は、アガリの側で点を失っている | ドラのある手 |
| 07 | dora-shape | ドラの下に手を組む | ドラのある手 |
| 08 | dora-tells | 1シャンテンでは副露者のサインを数える | ドラのある手 |
| 09 | shape-start | タンヤオと染め手はいつ始めるか | タンヤオと染め手 |
| 10 | recent-games | 9月22日の対局を振り返る | 最近の対局 |
| 11 | push-calibration | テンパイの押しを調整する | 押しの調整 |
| 12 | open-hands | 副露テンパイは保ち、鳴くなら打点のために | 副露手 |
| 13 | caller-defense | 副露者への守備は追いついた | 最近の対局 |
| 14 | three-calls | 副露者は段で数え、3副露のテンパイは保つ | 最近の対局 |
| 15 | mortal-review | 必要な対子を残し、役のない手では追わずにオリる | Mortalの検討 |
| 16 | fold-later | 安全牌は必要になるまで取っておく | 全対局のMortal検討 |
| 17 | early-safe-tiles | 安全牌の残し方は正しい。早いリーチに気をつける | 最近の対局 |
| 18 | caller-grid | どの副露者も1枚の表で読む | 副露者を読む |
| 19 | fold-line | 表の上でLuckyJがオリる位置と、ツモ切りの連続の数え方 | 副露者を読む |
| 20 | break-folds | リーチには手を崩してオリ、副露者にはまず崩さない | 副露者を読む |
| 21 | quiet-breaks | 副露者の一段目には手を崩さない | 副露者を読む |
| 22 | own-hand | オリは場ではなく、自分の手で決める | 恐れと自信 |
| 23 | pushes-pay | 安い副露テンパイは押し、出来上がった手はダマに | 最近の対局 |
| 24 | big-hands | 大きな手をダマにするとき | リーチかダマか |
| 25 | riichi-place | 着順がリーチを動かす | リーチかダマか |

- Chapter kicker "Chapter one · Value · added 22 September" → 「第1章 &#183; 打点 &#183; 9月22日追加」.
- Chapter list sub "Value · added 22 September" → 「打点 &#183; 9月22日追加」.
- "Next chapter" (link label and `aria-label`) → 「次の章」. "After the chapters" → 「本編の後」.
  "How this guide was built" → 「このガイドの作り方」.
- "Chapter 17" in prose → 「第17章」. "chapters 1 to 16" → 「第1章から第16章」.
- `<strong>Rule</strong>` → ルール, `<strong>Exception</strong>` → 例外, `<b>Evidence</b>` → 根拠.
- The guide's name "Honver's Guide" → 「Honverのガイド」. "Personal edition" → 「個人版」.
  "the playbook" / "the main LuckyJ playbook" / "the book" (LuckyJ's) → 「LuckyJ戦術書」 or 「本編の戦術書」.

## Dates and places

- "22 September" → 9月22日; "since 24 September" → 9月24日以降; "22 Sep" (news dates) → 9月22日;
  "January 2026" → 2026年1月.
- Rounds: "East 2" → 東2局; "South 2, two honba" → 南2局2本場; "East 1-0" → 東1局; "South 4-1" → 南4局1本場.
- "turn 8" → 8巡目 (the player's own turn count). "discard 3" / "the third discard" / "their 9th" → 3打目 / 9打目.
- Pond rows: "the first row" (discards 1-6) → 一段目; second row → 二段目; third row → 三段目; "rows of six" → 6枚ずつの段.
- Seats: kamicha 上家, toimen 対面, shimocha 下家, dealer 親, non-dealer 子. "the dealer's riichi" → 親リーチ.
- Game names: "game" / "hanchan" → 半荘; "hand" (one kyoku) → 局 ("830 hands" → 830局); "hand" (the tiles) → 手 / 手牌.
  Mahjong Soul 雀魂, Jade (room) 玉の間, "Jade South games" → 玉の間の南風戦（半荘戦）, Tenhou 天鳳, Tokujou 特上, Houou 鳳凰,
  Saint 3 雀聖3, rank points 段位ポイント, placement 着順, 1st/4th → 1位/4位 (トップ/ラス are fine in prose).

## Terms

| English | Japanese |
|---|---|
| riichi / declare | リーチ / リーチする（宣言する） |
| dama | ダマ |
| tenpai / 1-shanten / 2-shanten | テンパイ / 1シャンテン / 2シャンテン |
| acceptance, tiles that improve it | 受け入れ（枚数）、有効牌 |
| "8 live tiles" / "8-tile wait" (count of a wait) | 残り8枚 / 残り8枚の待ち |
| narrow wait | 狭い待ち（残り枚数の少ない待ち） |
| two-sided wait | 両面待ち |
| kanchan / tanki / shanpon | カンチャン / 単騎 / シャンポン |
| live tile (not covered by any safety read) | 生牌 (the playbook's word); live honor 生きた字牌; live terminal 無筋の端牌; live 2-8 無筋の2〜8 |
| safe tile | 安全牌 |
| genbutsu | 現物 |
| suji / nakasuji / half suji | 筋 / 中筋 / 片筋 |
| virtual nakasuji | 疑似中筋 |
| sotogawa read | 外側読み |
| anchored (a suji anchor) | 通っている（現物になっている） |
| honor with two other copies showing | 2枚見えの字牌 |
| fold | オリ / オリる |
| push | 押し / 押す |
| deal in / deal-in | 放銃する / 放銃 |
| deal-in rate / win rate | 放銃率 / 和了率 |
| win (verb) / a win | アガる / アガリ |
| caller | 副露者 |
| call (n.) / to call | 鳴き / 鳴く |
| one call / two calls / three calls | 1副露 / 2副露 / 3副露 |
| open hand / closed hand | 副露手 / 門前手 |
| open tenpai | 副露テンパイ |
| three-call hand / three-call tenpai | 3副露の手 / 3副露テンパイ |
| pon / chi / kan | ポン / チー / カン |
| tell(s) | サイン |
| tsumogiri, a tile from the wall | ツモ切り |
| a tile from hand | 手出し |
| run (of tiles from the wall) | ツモ切りの連続 |
| pond / river | 河 |
| value honor / yakuhai | 役牌 |
| guest wind | 客風 |
| dragon / seat wind / round wind | 三元牌 / 自風 / 場風 |
| yaku / yakuless / with a yaku | 役 / 役なし / 役あり |
| dora / red five / ura dora | ドラ / 赤5 / 裏ドラ |
| mangan / haneman / dealer mangan | 満貫 / 跳満 / 親満 |
| tanyao / pinfu / toitoi / chiitoitsu | タンヤオ / 平和 / 対々和 / 七対子 |
| flush / honitsu / chinitsu | 染め手 / 混一色 / 清一色 |
| terminal / middle tile (3-7) | 端牌 / 中張牌 |
| junk tiles | 不要牌 |
| standard error | 標準誤差 |
| per 100 hands | 100局あたり |
| readings (statistical observations) | 観測 |
| fit / fitted curve | 当てはめ / 当てはめ曲線 |
| LuckyJ's fold line | LuckyJのオリライン |
| the grid (chapter 18's heat table) | 表 |
| coin flip | 五分五分 |
| Mortal's first choice | Mortalの第一候補 |
| a tie (two cuts equal on efficiency) | 効率が同じ場面 |
| spend / keep a safe tile | 安全牌を使う / 残す |

## Two samples

English: "LuckyJ wins about as many hands as you do. The difference is what it does with a hand that has
dora. Sorted by the dora and red fives in the deal, your win rate stays flat while LuckyJ's climbs:"

Japanese: 「LuckyJがアガる局の数は、あなたとほぼ変わらない。差が出るのは、ドラのある手の扱いである。配牌のドラと
赤5の枚数で分けると、あなたの和了率は横ばいのままで、LuckyJの和了率は上がっていく。」

English situation: "East 2, turn 8. You are the dealer, fourth at 22,700. You draw [[4p]] into tenpai: cut
[[7s]] and you wait on [[5m]]-[[8m]] with 8 tiles live. The hand is tanyao with three [[2m]] as dora. Nobody
has declared. Kamicha has ponned [[C]] and [[F]]."

Japanese: 「東2局、8巡目。親で4位、22,700点。[[4p]]を引いてテンパイ。[[7s]]を切れば[[5m]]-[[8m]]待ちで、残り8枚。
手はタンヤオで、ドラの[[2m]]が3枚。リーチはまだない。上家が[[C]]と[[F]]をポンしている。」

## Example cards

Each spot's `title`, `situation`, `did` ("What you did"), `luckyj` ("What LuckyJ does") and `fix`
("The fix", or "The verdict" when `verdict` is fine/unlucky/close) get a Japanese twin in the spot's
`ja` block, and each frame `note` a `note_ja`. Titles are short noun phrases like the English, e.g.
「ドラ3、残り8枚の待ちでダマ」. The card's own labels (あなた, 推奨, safety chips, 局の結果) come
from site/honver.js.

## More terms settled while translating

| English | Japanese |
|---|---|
| a quiet table (nobody has called or declared) | 静かな卓 (first time: 鳴きのない静かな卓) |
| lead / leading | トップ目 |
| the last hand (all last) | オーラス |
| N-han | N翻 |
| "could win" (a caller in tenpai with a yaku) | アガれる状態 |
| rows of chapter 18's table | 1行目 / 2行目 (pond rows stay 一段目 / 二段目) |
| single caller | 1副露の副露者 |
| once-cut West | 1枚切れの西 |
| Double East / Double South | ダブ東 / ダブ南 |
| replays (the site's) | 牌譜 / 牌譜再生 |
| policy model (Mortal's) | 方策モデル |
| close call | 際どい判断 |
| riichi declared into a riichi | 追っかけリーチ |
| the lobby (who you play against) | 対戦相手の層 |
| N standard errors | 標準誤差のN倍 |
| loose tiles | 浮き牌 |
| draw payment / noten payment | 流局の精算 / ノーテン罰符 |
| "tanyao with a red five" | タンヤオ赤1 |
| costly turn (every safe tile costs a shanten) | 損な巡目 |
| extra folds (beyond Mortal's rate) | 余分なオリ |
| Mortal's rate (its weight on the safe tiles) | Mortalの割合 |
| the first / second situation (a figure's split) | 前の状況 / 後の状況 |

Chapter 18's table labels live in `scripts/build_caller_surface.py` (`WORDS["ja"]`); the prose uses the same
words (最後は手出し, 最後の1枚がツモ切り, ツモ切りが2回続く, ツモ切りが3回以上続く, ここからLuckyJはオリる, 緑の線).
