// Mahjong Soul identities. The same nickname can exist on the China, Japan and International
// servers, so a player is pinned by account id, chosen from exact-name matches on their server.
// The server is in the account id (amae-koromo, src/data/types/zone.ts): id >> 23 is 0-6 China,
// 7-12 Japan, 13-15 International.

export const SERVERS = ["china", "japan", "international"];

/** @param {number} accountId */
export function accountServer(accountId) {
  const prefix = Number(accountId) >> 23;
  if (!accountId) return null;
  if (prefix >= 0 && prefix <= 6) return "china";
  if (prefix >= 7 && prefix <= 12) return "japan";
  if (prefix >= 13 && prefix <= 15) return "international";
  return null;
}

const RANKS = {
  en: ["", "Novice", "Adept", "Expert", "Master", "Saint", "Celestial"],
  ja: ["", "初心", "雀士", "雀傑", "雀豪", "雀聖", "魂天"],
};

/** "Saint 3" / "雀聖3" from an amae-koromo level id such as 10503 (4-player, Saint, 3 stars). */
export function rankName(levelId, lang = "en") {
  const id = Number(levelId);
  const tier = Math.floor(id / 100) % 100;
  const step = id % 100;
  const name = (RANKS[lang] || RANKS.en)[tier];
  if (!name) return "";
  return lang === "ja" ? `${name}${step}` : `${name} ${step}`;
}

/**
 * Exact-name matches on one server from amae-koromo's prefix search, newest player first.
 * @param {{id: number, nickname: string, level?: {id: number}, latest_timestamp?: number}[]} results
 * @param {string} name @param {string} server
 */
export function exactMatches(results, name, server) {
  const wanted = String(name).trim();
  return (results || [])
    .filter((p) => p && p.nickname === wanted && accountServer(p.id) === server)
    .map((p) => ({ id: p.id, nickname: p.nickname, level: p.level?.id ?? null, latest: p.latest_timestamp ?? null }))
    .sort((a, b) => (b.latest ?? 0) - (a.latest ?? 0));
}
