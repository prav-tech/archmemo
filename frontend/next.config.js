/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // /api/* is proxied by Next (see rewrites below), and Next's proxy gives up
    // after 30s by default. A briefing does a recall plus an LLM call, and the
    // backend allows 60s per LLM attempt (2 retries), so allow up to 3 minutes
    // rather than surfacing a slow-but-working briefing as a proxy error.
    proxyTimeout: 180_000,
  },

  // Forward API calls to the FastAPI backend. Because the browser only ever talks
  // to this origin, the session cookie the API sets is a first-party cookie.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
