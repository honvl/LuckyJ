"use client";
import { useState } from "react";
import { STRINGS, type Lang } from "@/lib/strings";

export default function Subscribe({ lang, ended }: { lang: Lang; ended: boolean }) {
  const t = STRINGS[lang];
  const [platform, setPlatform] = useState("majsoul");
  const [gameName, setGameName] = useState("");
  const [publish, setPublish] = useState(true);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <form
      className="subscribe"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setFailed(false);
        const res = await fetch("/api/billing/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ platform, gameName, publish }),
        });
        const body = await res.json().catch(() => ({}));
        if (res.ok && body.url) window.location.href = body.url;
        else {
          setBusy(false);
          setFailed(true);
        }
      }}
    >
      {ended && <p className="login-error">{t.ended}</p>}
      <p className="login-lead">{t.subscribeLead}</p>
      <p className="subscribe-price">{t.price}</p>
      <p className="login-note">{t.priceNote}</p>
      <fieldset className="subscribe-platform">
        <legend>{t.platform}</legend>
        {(["majsoul", "tenhou"] as const).map((p) => (
          <label key={p}>
            <input type="radio" name="platform" value={p} checked={platform === p} onChange={() => setPlatform(p)} />
            {t[p]}
          </label>
        ))}
      </fieldset>
      <label className="subscribe-field">
        {t.gameName}
        <input value={gameName} onChange={(e) => setGameName(e.target.value)} maxLength={64} required />
        <span className="login-note">{t.gameNameHint}</span>
      </label>
      <label className="subscribe-check">
        <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
        {t.publishChoice}
      </label>
      <p className="login-note">
        {t.agreeBefore}{lang === "ja" ? "" : " "}<a href={t.privacyHref}>{t.privacy}</a>{t.agreeAfter}
      </p>
      <button className="button" type="submit" disabled={busy || !gameName.trim()}>
        {busy ? t.subscribing : t.subscribe}
      </button>
      {failed && <p className="login-error">{t.error}</p>}
    </form>
  );
}
