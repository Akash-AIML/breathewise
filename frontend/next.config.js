/** @type {import('next').NextConfig} */

// Only browser-facing API routes are proxied. New backend routes must be added
// here deliberately instead of becoming reachable via a wildcard rewrite.
const PROXIED_API_ROUTES = [
  '/api/v1/air-quality',
  '/api/v1/assistant/chat',
  '/api/v1/locations/reverse',
  '/api/v1/locations/search',
  '/api/v1/recommendations/indoor',
  '/api/v1/recommendations/plan',
  '/api/v1/recommendations/sustainable-alternatives',
  '/api/v1/stations',
  '/api/v1/stations/comparison-presets',
  '/api/v1/stations/compare',
];

// Next injects inline bootstrap scripts, so script-src still needs
// 'unsafe-inline'. The remaining directives block framing, plugins, external
// script hosts and cross-origin form/connect targets.
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "connect-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
].join('; ');

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Content-Security-Policy', value: CONTENT_SECURITY_POLICY },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'geolocation=(self), camera=(), microphone=()' },
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
          { key: 'Cross-Origin-Resource-Policy', value: 'same-origin' },
          { key: 'X-Permitted-Cross-Domain-Policies', value: 'none' },
        ],
      },
    ];
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      ...PROXIED_API_ROUTES.map((source) => ({
        source,
        destination: `${backendUrl}${source}`,
      })),
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

module.exports = nextConfig;
