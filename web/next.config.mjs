/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  poweredByHeader: false,
  // The site's front page is the playbook (public/index.html, copied from ../site).
  async rewrites() {
    return { beforeFiles: [{ source: "/", destination: "/index.html" }] };
  },
};
