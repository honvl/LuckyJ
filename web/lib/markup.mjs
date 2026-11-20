// The coach's inline markup, shared by the page and its tests.
//   [[5m]] [[5mr]] [[E]] [[2m 3m 4m]]      tiles, drawn with the site's tile font
//   [[game:<uuid> East 1-0 t9]]             a moment in one of the player's games
//   [[game:<uuid> East 1-0 t9 call]]        ... at the call decision
// Fields are separated by spaces: a | would split a Markdown table cell.

// Glyphs of the GL-MahjongTile font, the same table as site/app.js.
export const TILE_GLYPHS = {
  "1m": "q", "2m": "w", "3m": "e", "4m": "r", "5m": "t", "5mr": "8", "6m": "y", "7m": "u", "8m": "i", "9m": "o",
  "1s": "a", "2s": "s", "3s": "d", "4s": "f", "5s": "g", "5sr": "p", "6s": "h", "7s": "j", "8s": "k", "9s": "l",
  "1p": "z", "2p": "x", "3p": "c", "4p": "v", "5p": "b", "5pr": "0", "6p": "n", "7p": "m", "8p": ",", "9p": ".",
  E: "1", S: "2", W: "3", N: "4", P: "5", F: "6", C: "7",
};

const HONORS = {
  en: { E: "East wind", S: "South wind", W: "West wind", N: "North wind", P: "White dragon", F: "Green dragon", C: "Red dragon" },
  ja: { E: "東", S: "南", W: "西", N: "北", P: "白", F: "發", C: "中" },
};
const SUIT_JA = { m: "萬", p: "筒", s: "索" };
const NUM_JA = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"];

const MARKUP = /\[\[([^\]\n]{1,200})\]\]/g;

/** The tiles in a [[...]] body, or null when it is not a tile list. */
export function parseTiles(body) {
  const list = body.trim().split(/\s+/);
  return list.length && list.every((t) => t in TILE_GLYPHS) ? list : null;
}

/** A game reference, or null. */
export function parseGameRef(body) {
  const m = body.match(/^game:([0-9]{6}-[0-9a-f-]{8,40}) ((?:East|South|West|North) \d-\d+) t(\d{1,2})( call)?$/);
  if (!m) return null;
  return { uuid: m[1], round: m[2], turn: Number(m[3]), call: Boolean(m[4]) };
}

/** Splits text into plain strings, {tiles} and {game} parts; unknown [[...]] stays as text. */
export function splitMarkup(text) {
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(MARKUP)) {
    const tiles = parseTiles(m[1]);
    const game = tiles ? null : parseGameRef(m[1]);
    if (!tiles && !game) continue;
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(tiles ? { tiles } : { game });
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function tileName(tile, lang = "en") {
  const honor = HONORS[lang]?.[tile];
  if (honor) return honor;
  const red = tile.endsWith("r");
  if (lang === "ja") return `${red ? "赤" : ""}${NUM_JA[Number(tile[0])]}${SUIT_JA[tile[1]]}`;
  return red ? `red ${tile.slice(0, 2)}` : tile;
}

const ROUND_JA = { East: "東", South: "南", West: "西", North: "北" };

/**
 * Short label: "10 Nov · East 1 · turn 9" or "11/10 東1局 9巡目". `date` is the site's date for the
 * game ("2026-11-09 23:44"); without it the date in the id is used, which is often a day later.
 * @param {{ uuid: string, round: string, turn: number, call: boolean }} ref
 * @param {"en" | "ja"} [lang]
 * @param {string | null} [date]
 */
export function gameLabel(ref, lang = "en", date = null) {
  const [, mm, dd] = (date && date.match(/^\d{4}-(\d{2})-(\d{2})/)) || ref.uuid.match(/^\d{2}(\d{2})(\d{2})/) || [];
  const [wind, rest] = ref.round.split(" ");
  const [hand, repeat] = rest.split("-");
  if (lang === "ja") {
    const honba = repeat !== "0" ? ` ${repeat}本場` : "";
    return `${Number(mm)}/${Number(dd)} ${ROUND_JA[wind]}${hand}局${honba} ${ref.turn}巡目${ref.call ? "（鳴き）" : ""}`;
  }
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(mm) - 1];
  const honba = repeat !== "0" ? `-${repeat}` : "";
  return `${Number(dd)} ${month} · ${wind} ${hand}${honba} · turn ${ref.turn}${ref.call ? ", call" : ""}`;
}

/** The site's replay of that moment (site/replay.js reads g, r, t and at). */
export function replayHref(ref, siteUrl = "", book = "") {
  // A player's guide keeps its replays itself: ?b=<slug> tells the viewer where to load them.
  const params = new URLSearchParams(book ? { b: book } : {});
  params.set("g", ref.uuid);
  params.set("r", ref.round);
  params.set("t", String(ref.turn));
  if (ref.call) params.set("at", "call");
  return `${siteUrl}/replay.html?${params}`;
}

/** A table cell's text split into its value and the "± SE" after it, when it has one. */
export function splitError(text) {
  const m = text.match(/^(.*?\S)\s*(±\s*[\d.,]+\s*%?(?:\s*pts?)?)$/);
  return m ? { value: m[1], error: m[2] } : null;
}

/** Cells that read as numbers ("72.6%", "572 of 788", "-1,200", "2.9 SE") align right. */
export function isNumericCell(text) {
  return /^[-+−]?[$¥]?[\d,.]+(\s*(%|pts?|SE|rp|of\s+[\d,]+))?(\s*[=±]\s*[-+−]?[\d,.]+\s*(%|pts?|SE)?)*$/.test(text.trim());
}
