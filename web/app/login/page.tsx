import { redirect } from "next/navigation";
import { authOptions, currentThread } from "@/lib/auth";
import { STRINGS, pageLang } from "@/lib/lang";
import LoginButtons from "@/components/LoginButtons";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  if (await currentThread()) redirect("/chat");
  const lang = await pageLang();
  const t = STRINGS[lang];
  // A provider's own id and name sit in `options` until next-auth initialises it.
  const providers = authOptions.providers.map((p: any) => ({ id: p.options?.id ?? p.id, name: p.options?.name ?? p.name }));
  return (
    <main className="login">
      <p className="login-kicker">Honver&rsquo;s guide</p>
      <h1>{t.signIn}</h1>
      <p className="login-lead">{t.signInLead}</p>
      <LoginButtons providers={providers} lang={lang} />
    </main>
  );
}
