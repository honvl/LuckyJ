"use client";
// Server + in-game name, then the player picks their own account from the exact-name matches on
// that server. The same nickname can exist on the China, Japan and International servers.
import { useState } from "react";
import { STRINGS, type Lang } from "@/lib/strings";

export type MajsoulChoice = { server: string; name: string; accountId: number } | null;
type Match = { id: number; nickname: string; rank: string; latest: string | null };

export default function MajsoulPicker({ lang, initial, onChange }: {
  lang: Lang;
  initial?: { server?: string | null; name?: string | null; accountId?: number | null };
  onChange: (choice: MajsoulChoice) => void;
}) {
  const t = STRINGS[lang];
  const [server, setServer] = useState(initial?.server || "");
  const [name, setName] = useState(initial?.name || "");
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [picked, setPicked] = useState<number | null>(initial?.accountId ?? null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const reset = () => {
    setMatches(null);
    setPicked(null);
    onChange(null);
  };
  const find = async () => {
    setBusy(true);
    setFailed(false);
    const q = new URLSearchParams({ server, name: name.trim(), lang });
    const res = await fetch(`/api/majsoul/lookup?${q}`).catch(() => null);
    const body = res?.ok ? await res.json() : null;
    setBusy(false);
    if (!body) return setFailed(true);
    setMatches(body.matches);
    if (body.matches.length === 1) {
      setPicked(body.matches[0].id);
      onChange({ server, name: name.trim(), accountId: body.matches[0].id });
    }
  };

  return (
    <fieldset className="picker">
      <legend>{t.majsoulAccount}</legend>
      <label className="subscribe-field">
        {t.server}
        <select value={server} onChange={(e) => { setServer(e.target.value); reset(); }} required>
          <option value="" disabled>{t.chooseServer}</option>
          <option value="international">{t.serverInternational}</option>
          <option value="japan">{t.serverJapan}</option>
          <option value="china">{t.serverChina}</option>
        </select>
      </label>
      <label className="subscribe-field">
        {t.majsoulName}
        <input value={name} onChange={(e) => { setName(e.target.value); reset(); }} maxLength={64} autoComplete="off" />
      </label>
      <button type="button" className="button button-quiet" disabled={!server || !name.trim() || busy} onClick={find}>
        {busy ? t.finding : t.findMe}
      </button>
      {failed && <p className="login-error">{t.error}</p>}
      {matches && matches.length === 0 && <p className="login-error">{t.noMatch}</p>}
      {matches && matches.length > 0 && (
        <div className="picker-matches" role="radiogroup" aria-label={matches.length > 1 ? t.pickYourself : t.foundYou}>
          <p className="login-note">{matches.length > 1 ? t.pickYourself : t.foundYou}</p>
          {matches.map((m) => (
            <label key={m.id} className={`picker-match ${picked === m.id ? "is-picked" : ""}`}>
              <input type="radio" name="majsoul-account" checked={picked === m.id}
                onChange={() => { setPicked(m.id); onChange({ server, name: name.trim(), accountId: m.id }); }} />
              <span className="picker-name">{m.nickname}</span>
              <span className="login-note">{[m.rank, m.latest && t.lastGame(m.latest)].filter(Boolean).join(" · ")}</span>
            </label>
          ))}
        </div>
      )}
      <p className="login-note">{t.coverageNote}</p>
    </fieldset>
  );
}
