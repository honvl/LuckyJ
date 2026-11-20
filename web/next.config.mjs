/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  poweredByHeader: false,
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
