import type { Metadata } from "next";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { pageLang } from "@/lib/lang";
import { SITE } from "@/lib/site-strings";
import type { Lang } from "@/lib/strings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "AI Tutor: The LuckyJ Playbook", robots: { index: true } };

// A real exchange from the site owner's own tutor thread ("Matchmaking difficulty after streaks",
// 19 Nov 2026): the question, the answer from 4,167 games, the pushback and the corrected answer.
const EXAMPLE = {
  en: {
    ask1: "Can you analyze whether players get harder after a win streak and easier after a lose streak (matchmaking)? I have such a feeling",
    checked: "Checked 4,167 Jade South games since Oct 2020, with every opponent's rank at the time",
    answer1: "Win streaks don't get you harder opponents, and loss streaks don't get you easier ones.",
    cols: ["Streak going in", "Games", "Opponents' avg rank"],
    rows: [["5+ bad games", "87", "0.99"], ["1 bad game", "1,042", "1.08"], ["1 good game", "1,042", "1.14"], ["5+ good games", "159", "1.09"]],
    after1: "No trend with streak length (p = 0.23). One real signal: the game right after a 4th, opponents average 0.13 rank steps lower. It's gone by the next game.",
    ask2: "Games with Saints are definitely harder than games with Masters? That's why people avoid Throne Room. And I feel like I'm noticing more Saints?",
    answer2a: "You're right on both counts.",
    answer2b: "Comparing opponents at the same table, Saints finish 0.14 places better than Masters (± 0.04). Each Saint at your table costs you about 7 rank points a game.",
    answer2c: "Saints per Jade table rose from about 0.42 in 2021 to 0.72 in October and November 2026. It comes from the room's player pool, not from your own climb.",
  },
  ja: {
    ask1: "連勝のあとは相手が強く、連敗のあとは弱くなる（マッチング）か分析できますか？そんな気がします",
    checked: "2020年10月以降の玉の間南風戦4,167局を、対戦時の全員の段位つきで確認",
    answer1: "連勝しても相手は強くならず、連敗しても弱くなりません。",
    cols: ["直前の流れ", "対局数", "相手の平均段位"],
    rows: [["5局以上悪い", "87", "0.99"], ["1局悪い", "1,042", "1.08"], ["1局良い", "1,042", "1.14"], ["5局以上良い", "159", "1.09"]],
    after1: "連続の長さによる傾向はありません（p = 0.23）。本当に見える信号は一つだけ：4着の直後の1局は、相手が平均0.13段階低い。その次の局には消えています。",
    ask2: "雀聖のいる卓は雀豪の卓より明らかに難しいのでは？だから王座の間を避ける人がいる。それに雀聖が増えている気がします",
    answer2a: "どちらもその通りです。",
    answer2b: "同じ卓の相手どうしで比べると、雀聖は雀豪より0.14着上で終わります（± 0.04）。卓の雀聖1人につき、1局あたり約7ポイントを失います。",
    answer2c: "玉の間の1卓あたりの雀聖は、2021年の約0.42人から2026年10〜11月の0.72人に増えました。あなたの昇段ではなく、部屋のプレイヤー層によるものです。",
  },
} satisfies Record<Lang, unknown>;

export default async function TutorPage() {
  const lang = await pageLang();
  const s = SITE[lang];
  const ex = EXAMPLE[lang];
  return (
    <div className="s-page">
      <SiteHeader lang={lang} current="tutor" path="/tutor" />
      <main>
        <section className="s-hero">
          <div className="s-hero-text">
            <p className="s-kicker">{s.tutorKicker}</p>
            <h1 className="s-h1">{s.tutorTitle}</h1>
            <p className="s-lead">{s.tutorLead}</p>
            <div className="s-actions">
              <a className="s-btn s-btn-line-ink" href="#plan">{s.seePlan}</a>
              <a className="s-strong-link" href="/honver.html">{s.readAGuide}</a>
            </div>
            <p className="s-muted s-small">{s.tutorFine}</p>
          </div>
          <figure className="s-example" aria-label={s.fromThread}>
            <figcaption className="s-side-label">{s.fromThread}</figcaption>
            <p className="s-bubble"><span className="s-sr">{s.you}: </span>{ex.ask1}</p>
            <div className="s-reply">
              <span className="s-sr">{s.tutorName}: </span>
              <span className="s-muted s-small">{ex.checked}</span>
              <p><strong>{ex.answer1}</strong></p>
              <table>
                <thead><tr>{ex.cols.map((c, i) => <th key={c} scope="col" className={i ? "num" : undefined}>{c}</th>)}</tr></thead>
                <tbody>{ex.rows.map((r) => <tr key={r[0]}>{r.map((v, i) => <td key={i} className={i ? "num" : undefined}>{v}</td>)}</tr>)}</tbody>
              </table>
              <p>{ex.after1}</p>
            </div>
            <p className="s-bubble"><span className="s-sr">{s.you}: </span>{ex.ask2}</p>
            <div className="s-reply">
              <span className="s-sr">{s.tutorName}: </span>
              <p><strong>{ex.answer2a}</strong> {ex.answer2b}</p>
              <p>{ex.answer2c}</p>
            </div>
          </figure>
        </section>

        <section className="s-band-light" aria-labelledby="get-title">
          <div className="s-wide">
            <h2 id="get-title" className="s-h2">{s.getTitle}</h2>
            <div className="s-three">
              {s.get.map(([title, text]) => (
                <div key={title}><h3 className="s-h3">{title}</h3><p>{text}</p></div>
              ))}
            </div>
          </div>
        </section>

        <section className="s-wide" aria-labelledby="steps-title">
          <h2 id="steps-title" className="s-h2">{s.stepsTitle}</h2>
          <ol className="s-steps">
            {s.steps.map(([title, text], i) => (
              <li key={title}><span className="s-step-n">{i + 1}</span><strong>{title}</strong><span>{text}</span></li>
            ))}
          </ol>
        </section>

        <section id="plan" className="s-felt" aria-labelledby="plan-title">
          <div className="s-wide s-plan">
            <div className="s-plan-text">
              <span className="s-band-kicker">{s.planKicker}</span>
              <h2 id="plan-title" className="s-plan-title">{s.planTitle}</h2>
              <p>{s.planLead}</p>
            </div>
            <div className="s-plan-card">
              <p className="s-price"><span>{s.price}</span> {s.perMonth}</p>
              <ul>{s.planItems.map((item) => <li key={item}>{item}</li>)}</ul>
              <a className="s-btn s-btn-ink" href="/login">{s.subscribeSignIn}</a>
              <span className="s-muted s-small">{s.billing}</span>
            </div>
          </div>
        </section>

        <section className="s-faq" aria-labelledby="faq-title">
          <h2 id="faq-title" className="s-h2">{s.faqTitle}</h2>
          {s.faq.map(([q, a]) => (
            <details key={q}><summary>{q}</summary><p>{a}</p></details>
          ))}
        </section>
      </main>
      <SiteFooter lang={lang} />
    </div>
  );
}
