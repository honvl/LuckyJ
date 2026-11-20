"use client";
import { signOut } from "next-auth/react";
import { useState } from "react";
import type { Profile } from "@/lib/profile";
import { STRINGS, type Lang } from "@/lib/strings";
import ManageButton from "./ManageButton";
import MajsoulPicker, { type MajsoulChoice } from "./MajsoulPicker";

type Chapter = { key: string; number: number; title: string; isPublic: boolean };

async function post(url: string, body: unknown) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return res.ok;
}

// A real switch: the track shows the state and the word beside it names it, so "Public" reads as
// what the chapter is now and not as a button that would make it public.
function Switch({ on, label, onLabel, offLabel, onToggle }: { on: boolean; label: string; onLabel: string; offLabel: string; onToggle: () => void }) {
  return (
    <button type="button" className="switch" role="switch" aria-checked={on} aria-label={label} onClick={onToggle}>
      <span className="switch-word">{on ? onLabel : offLabel}</span>
      <span className="switch-track" aria-hidden="true"><span className="switch-thumb" /></span>
    </button>
  );
}

export default function AccountPanel({ lang, email, billing, subscription, profile, guide }: {
  lang: Lang;
  email: string;
  billing: boolean;
  subscription: { comp: boolean; status: string | null; renews: string | null; canManage: boolean };
  profile: Profile | null;
  guide: { slug: string | null; isPublic: boolean; chapters: Chapter[] } | null;
}) {
  const t = STRINGS[lang];
  const [choice, setChoice] = useState<MajsoulChoice>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [publish, setPublish] = useState(profile?.publish ?? true);
  const [bookPublic, setBookPublic] = useState(guide?.isPublic ?? true);
  const [chapters, setChapters] = useState<Chapter[]>(guide?.chapters ?? []);

  const status = subscription.comp ? t.subFree
    : subscription.status === "active" || subscription.status === "trialing" ? t.subActive(subscription.renews)
    : subscription.status === "past_due" ? t.subPastDue
    : subscription.status ? t.subEnded
    : t.subNone;

  return (
    <div className="account-sections">
      <section>
        <h2>{t.subscription}</h2>
        <p className={`account-status${subscription.status === "past_due" ? " is-warning" : ""}`}>{status}</p>
        <p className="login-note">{t.signedInAs(email)}</p>
        <div className="login-actions">
          {!subscription.comp && billing && !["active", "trialing", "past_due"].includes(subscription.status || "") &&
            <a className="button" href="/start">{t.subscribe}</a>}
          {subscription.canManage && <ManageButton label={t.manage} />}
          <button type="button" className="link-button" onClick={() => signOut({ callbackUrl: "/login" })}>{t.signOut}</button>
        </div>
      </section>

      <section>
        <h2>{t.majsoulAccount}</h2>
        {profile?.majsoulAccountId && (
          <p>{t.currentAccount(profile.majsoulName || "", t[`server${(profile.majsoulServer || "").replace(/^./, (c) => c.toUpperCase())}` as "serverJapan"] || "")}</p>
        )}
        <MajsoulPicker lang={lang} initial={{ server: profile?.majsoulServer, name: profile?.majsoulName }} onChange={(c) => { setChoice(c); setSaved(null); }} />
        <div className="login-actions">
          <button type="button" className="button" disabled={!choice} onClick={async () => {
            if (!choice) return;
            const ok = await post("/api/account/profile", { majsoulServer: choice.server, majsoulName: choice.name, majsoulAccountId: choice.accountId });
            setSaved(ok ? t.savedAccount : t.error);
          }}>{t.saveAccount}</button>
        </div>
        {saved && <p className="login-note">{saved}</p>}
      </section>

      <section>
        <h2>{t.yourGuide}</h2>
        {guide ? (
          <>
            <div className="account-row">
              <span>{t.guideVisible}</span>
              <Switch on={bookPublic} label={t.guideVisible} onLabel={t.public} offLabel={t.private} onToggle={async () => {
                const next = !bookPublic;
                setBookPublic(next);
                if (!(await post("/api/account/book", { isPublic: next }))) setBookPublic(!next);
              }} />
            </div>
            {guide.slug && bookPublic && chapters.length > 0 && <p className="login-note"><a href={`/books/${guide.slug}`}>{t.readBook}</a></p>}
            {chapters.length === 0 && <p className="login-note">{t.guideNotYet}</p>}
            {!bookPublic && <p className="login-note">{t.guideHiddenNote}</p>}
          </>
        ) : <p className="login-note">{t.guideNotYet}</p>}
        {profile?.majsoulAccountId && (
          <div className="account-row">
            <span>{t.newChaptersDefault}</span>
            <Switch on={publish} label={t.newChaptersDefault} onLabel={t.public} offLabel={t.private} onToggle={async () => {
              const next = !publish;
              setPublish(next);
              if (!(await post("/api/account/profile", { publish: next }))) setPublish(!next);
            }} />
          </div>
        )}
        {chapters.length > 0 && (
          <ul className="account-chapters">
            {chapters.map((c) => (
              <li key={c.key} className="account-row">
                <span><span className="chapter-num">{t.chapter(c.number)}</span> {c.title}</span>
                <Switch on={c.isPublic} label={`${t.chapter(c.number)}: ${c.title}`} onLabel={t.public} offLabel={t.private} onToggle={async () => {
                  const next = !c.isPublic;
                  setChapters((prev) => prev.map((x) => (x.key === c.key ? { ...x, isPublic: next } : x)));
                  await post("/api/chapters", { chapter: c.key, isPublic: next });
                }} />
              </li>
            ))}
          </ul>
        )}
        <p className="login-note">{t.publicNote}</p>
      </section>

      <section className="is-quiet">
        <h2>{t.closeAccount}</h2>
        <p className="login-note">{t.closeAccountNote}</p>
        <a className="link-button" href={`mailto:luckyj@yui-life.com?subject=${encodeURIComponent(t.deleteSubject)}`}>{t.requestDeletion}</a>
      </section>
    </div>
  );
}
