"use client";
import { useState } from "react";
import { STRINGS, type Lang } from "@/lib/strings";
import MajsoulPicker, { type MajsoulChoice } from "./MajsoulPicker";

export default function Subscribe({ lang, ended }: { lang: Lang; ended: boolean }) {
  const t = STRINGS[lang];
  const [choice, setChoice] = useState<MajsoulChoice>(null);
  const [publish, setPublish] = useState(true);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <form
      className="subscribe"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!choice) return;
        setBusy(true);
        setFailed(false);
        const res = await fetch("/api/billing/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ majsoulServer: choice.server, majsoulName: choice.name, majsoulAccountId: choice.accountId, publish }),
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
      <MajsoulPicker lang={lang} onChange={setChoice} />
      <label className="subscribe-check">
        <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
        {t.publishChoice}
      </label>
      <p className="login-note">
        {t.agreeBefore}{lang === "ja" ? "" : " "}<a href={t.privacyHref}>{t.privacy}</a>{t.agreeMiddle}<a href={t.termsHref}>{t.terms}</a>{t.agreeAfter}
      </p>
      <button className="button" type="submit" disabled={busy || !choice}>
        {busy ? t.subscribing : t.subscribe}
      </button>
      {failed && <p className="login-error">{t.error}</p>}
    </form>
  );
}
