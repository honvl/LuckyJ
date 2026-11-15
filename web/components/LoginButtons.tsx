"use client";
import { signIn } from "next-auth/react";
import { useState } from "react";
import { STRINGS, type Lang } from "@/lib/strings";

export default function LoginButtons({ providers, lang }: { providers: { id: string; name: string }[]; lang: Lang }) {
  const t = STRINGS[lang];
  const [email, setEmail] = useState("");
  const [failed, setFailed] = useState(false);
  return (
    <div className="login-buttons">
      {providers
        .filter((p) => p.id !== "dev")
        .map((p) => (
          <button key={p.id} className="button" onClick={() => signIn(p.id, { callbackUrl: "/chat" })}>
            {t.signInWith(p.name)}
          </button>
        ))}
      {providers.some((p) => p.id === "dev") && (
        <form
          className="login-dev"
          onSubmit={async (e) => {
            e.preventDefault();
            const res = await signIn("dev", { email, redirect: false });
            if (res?.ok) window.location.href = "/chat";
            else setFailed(true);
          }}
        >
          <label>
            {t.devLogin}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <button className="button" type="submit">{t.signIn}</button>
          {failed && <p className="login-error">{t.notLinked}</p>}
        </form>
      )}
    </div>
  );
}
