"use client";
import { useState } from "react";
import { STRINGS, type Lang } from "@/lib/strings";

export default function Subscribe({ lang, ended }: { lang: Lang; ended: boolean }) {
  const t = STRINGS[lang];
  const [majsoulName, setMajsoulName] = useState("");
  const [tenhouName, setTenhouName] = useState("");
  const hasName = Boolean(majsoulName.trim() || tenhouName.trim());
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
          body: JSON.stringify({ majsoulName, tenhouName, publish }),
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
      <p className="login-note">{t.namesLead}</p>
      <label className="subscribe-field">
        {t.majsoulName}
        <input value={majsoulName} onChange={(e) => setMajsoulName(e.target.value)} maxLength={64} autoComplete="off" />
      </label>
      <label className="subscribe-field">
        {t.tenhouName}
        <input value={tenhouName} onChange={(e) => setTenhouName(e.target.value)} maxLength={64} autoComplete="off" />
      </label>
      <label className="subscribe-check">
        <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
        {t.publishChoice}
      </label>
      <p className="login-note">
        {t.agreeBefore}{lang === "ja" ? "" : " "}<a href={t.privacyHref}>{t.privacy}</a>{t.agreeAfter}
      </p>
      <button className="button" type="submit" disabled={busy || !hasName}>
        {busy ? t.subscribing : t.subscribe}
      </button>
      {failed && <p className="login-error">{t.error}</p>}
    </form>
  );
}
