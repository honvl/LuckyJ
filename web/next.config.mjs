/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  // A separate build folder lets a production preview run beside `next dev` (.claude/launch.json).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  poweredByHeader: false,
  // `next dev` copies the browser's console messages into .next/dev/logs. With Tailwind's PostCSS
  // plugin watching the project folder, each write rebuilt the styles and reloaded the page, which
  // logged again: pages reloaded several times a second and never became usable. Off, the loop stops.
  logging: { browserToTerminal: false },
  // app/global-not-found.tsx: the 404 for an address no page matches (the app has two root layouts).
  experimental: { globalNotFound: true },
  // The site's front page is the playbook (public/index.html, copied from ../site).
  // The site's address is ai.yui-life.com; the old vercel.app address forwards to it. API routes
  // are left alone so a webhook or login callback still pointed at the old address keeps working.
  async redirects() {
    return [
      {
        source: "/:path((?!api/).*)",
        has: [{ type: "host", value: "luckyj.vercel.app" }],
        destination: "https://ai.yui-life.com/:path",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return { beforeFiles: [{ source: "/", destination: "/index.html" }] };
  },
};
