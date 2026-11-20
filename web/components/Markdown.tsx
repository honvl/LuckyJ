"use client";
// The coach's replies: Markdown with GFM tables, plus the site's [[tile]] and [[game:...]] markup.
import { Children, isValidElement, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { STRINGS, type Lang } from "@/lib/strings";
import { TILE_GLYPHS, gameLabel, isNumericCell, replayHref, splitError, splitMarkup, tileName } from "@/lib/markup.mjs";

// assetBase: where a chapter's own figures are served; a relative image src resolves against it.
type Ctx = { lang: Lang; siteUrl: string; replays: Record<string, string>; assetBase?: string };

// remark plugin: split text nodes on the markup into spans the components below draw.
function remarkMahjong() {
  const walk = (node: any) => {
    if (!node.children) return;
    const next: any[] = [];
    for (const child of node.children) {
      if (child.type === "text" && child.value.includes("[[")) {
        for (const part of splitMarkup(child.value)) {
          if (typeof part === "string") next.push({ type: "text", value: part });
          else if ("tiles" in part)
            next.push({ type: "mjTiles", data: { hName: "span", hProperties: { className: ["mj-tiles"], dataTiles: part.tiles.join(" ") } } });
          else
            next.push({ type: "mjGame", data: { hName: "span", hProperties: { className: ["mj-game"], dataGame: JSON.stringify(part.game) } } });
        }
      } else {
        if (child.type !== "code" && child.type !== "inlineCode") walk(child);
        next.push(child);
      }
    }
    node.children = next;
  };
  return (tree: any) => walk(tree);
}

// Chromium draws the SVG tile font blank: it gets the COLRv1 font, or the plain OTF without it.
// The same check as site/app.js.
function browserTileFont(): string {
  if (!/Chrome|Chromium|Edg|Opera|OPR|OPE|MSIE/.test(navigator.userAgent)) return "";
  return globalThis.CSS?.supports?.("font-tech(color-COLRv1)") ? "colr" : "otf";
}

const noSubscribe = () => () => {};

// The server cannot know the browser, so it renders the default font and the browser switches
// after hydration; computing it during render made every tile a hydration mismatch.
function useTileFontClass(): string {
  return useSyncExternalStore(noSubscribe, browserTileFont, () => "");
}

function Tiles({ tiles, lang }: { tiles: string[]; lang: Lang }) {
  const tileFontClass = useTileFontClass();
  const label = tiles.map((t) => tileName(t, lang)).join(", ");
  return (
    <span className={`tiles inline-tile ${tileFontClass}`} role="img" aria-label={label} title={label}>
      {tiles.map((t) => (TILE_GLYPHS as Record<string, string>)[t]).join("")}
    </span>
  );
}

function GameRef({ game, ctx }: { game: any; ctx: Ctx }) {
  const date = ctx.replays[game.uuid];
  const label = gameLabel(game, ctx.lang, date);
  // Links only once the game's replay is on the site.
  if (!date) {
    return <span className="game-ref is-pending" title={STRINGS[ctx.lang].replayLater}>{label}</span>;
  }
  return (
    <a className="game-ref" href={replayHref(game, ctx.siteUrl)} target="_blank" rel="noopener">
      {label}
    </a>
  );
}

function textOf(children: ReactNode): string {
  return Children.toArray(children)
    .map((c) => (typeof c === "string" || typeof c === "number" ? String(c) : isValidElement(c) ? textOf((c.props as any).children) : ""))
    .join("");
}

// Tabular figures line digits up, but this font then makes "," and "." as wide as a digit
// ("1 , 300"), so separators get their own narrow width back.
function figures(text: string): ReactNode {
  return text.split(/([,.])/).map((part, i) => (i % 2 ? <span key={i} className="sep">{part}</span> : part));
}

function Cell({ as: Tag, children, ...rest }: { as: "td" | "th"; children?: ReactNode; [k: string]: any }) {
  const kids = Children.toArray(children);
  const text = textOf(children).trim();
  const numeric = Tag === "td" && isNumericCell(text);
  const split = kids.length === 1 && typeof kids[0] === "string" ? splitError(kids[0] as string) : null;
  const { node, style, ...props } = rest;
  return (
    <Tag {...props} className={numeric ? "num" : undefined}>
      {split ? (
        <>
          {numeric ? figures(split.value) : split.value} <span className="se">{numeric ? figures(split.error) : split.error}</span>
        </>
      ) : numeric && kids.every((k) => typeof k === "string") ? (
        figures(kids.join(""))
      ) : (
        children
      )}
    </Tag>
  );
}

function Table({ children, lang }: { children?: ReactNode; lang: Lang }) {
  const ref = useRef<HTMLTableElement>(null);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    const rows = [...(ref.current?.rows || [])].map((row) =>
      [...row.cells].map((cell) => {
        const text = (cell.textContent || "").trim();
        return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
      }).join(","),
    );
    await navigator.clipboard.writeText(rows.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <figure className="table-figure">
      <div className="table-scroll">
        <table ref={ref}>{children}</table>
      </div>
      <button type="button" className="table-copy" onClick={copy}>
        {copied ? STRINGS[lang].copied : STRINGS[lang].copyCsv}
      </button>
    </figure>
  );
}

export default function Markdown({ text, ctx }: { text: string; ctx: Ctx }) {
  const components: Components = {
    span: ({ node, children, ...props }: any) => {
      const p = node?.properties || {};
      const cls = ([] as string[]).concat(p.className || []);
      if (cls.includes("mj-tiles")) return <Tiles tiles={String(p.dataTiles).split(" ")} lang={ctx.lang} />;
      if (cls.includes("mj-game")) return <GameRef game={JSON.parse(String(p.dataGame))} ctx={ctx} />;
      return <span {...props}>{children}</span>;
    },
    table: ({ children }) => <Table lang={ctx.lang}>{children}</Table>,
    td: (props: any) => <Cell as="td" {...props} />,
    th: (props: any) => <Cell as="th" {...props} />,
    a: ({ node, href, children, ...props }: any) => (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
    ),
    img: ({ node, src, alt }: any) => {
      // Only a chapter's own figures: a bare file name, served from assetBase. Other images are dropped.
      const name = typeof src === "string" ? src.replace(/^\.\//, "") : "";
      if (!ctx.assetBase || !/^[\w.-]+\.(png|jpe?g|webp|svg|gif)$/i.test(name)) return null;
      return <img className="md-figure" src={`${ctx.assetBase}/${encodeURIComponent(name)}`} alt={alt || ""} loading="lazy" />;
    },
  };
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMahjong]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
