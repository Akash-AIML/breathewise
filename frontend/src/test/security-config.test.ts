import { createRequire } from "module";
import { afterEach, describe, expect, it, vi } from "vitest";

const require = createRequire(import.meta.url);
const nextConfig = require("../../next.config.js");

describe("frontend security configuration", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("sets CSP and page header parity on every route", async () => {
    const headers = await nextConfig.headers();
    const page = headers.find((entry: { source: string }) => entry.source === "/:path*");
    const values = Object.fromEntries(
      page.headers.map((header: { key: string; value: string }) => [header.key, header.value])
    );

    expect(values["Content-Security-Policy"]).toContain("default-src 'self'");
    expect(values["Content-Security-Policy"]).toContain("frame-ancestors 'none'");
    expect(values["Content-Security-Policy"]).not.toContain("unsafe-eval");
    expect(values["Permissions-Policy"]).toContain("geolocation=(self)");
    expect(values["Cross-Origin-Opener-Policy"]).toBe("same-origin");
    expect(values["Cross-Origin-Resource-Policy"]).toBe("same-origin");
  });

  it("leaves runtime service routing to the request-time proxy handlers", () => {
    expect(nextConfig.rewrites).toBeUndefined();
    expect(JSON.stringify(nextConfig)).not.toContain("onrender.com");
    expect(JSON.stringify(nextConfig)).not.toContain("BACKEND_URL");
  });

  const origin = window.location.origin;
  const baseUrlCases = [
    { label: "absolute same-origin", value: origin, expectedPrefix: origin },
    { label: "absolute remote", value: "https://attacker.example", expectedPrefix: origin },
    { label: "protocol-relative remote", value: "//attacker.example", expectedPrefix: origin },
    { label: "same-origin path prefix", value: "/proxy", expectedPrefix: `${origin}/proxy` },
    { label: "empty base", value: "", expectedPrefix: origin },
  ];

  for (const { label, value, expectedPrefix } of baseUrlCases) {
    it(`resolves a ${label} API base before sending air-quality requests`, async () => {
      vi.resetModules();
      vi.stubEnv("NEXT_PUBLIC_APP_ENV", "production");
      vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", value);
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: null, message: "No live observation" }),
      });
      global.fetch = fetchMock as unknown as typeof fetch;

      const { fetchAirQuality } = await import("@/lib/api");
      await fetchAirQuality(19.076, 72.8777);

      const url = String(fetchMock.mock.calls[0][0]);
      expect(url.startsWith(expectedPrefix)).toBe(true);
      expect(url).toContain("/api/v1/air-quality");
      expect(url).not.toContain("attacker.example");
    });
  }

  it("keeps a configured remote base outside production", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_APP_ENV", "development");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: null, message: "No live observation" }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchAirQuality } = await import("@/lib/api");
    await fetchAirQuality(19.076, 72.8777);

    expect(String(fetchMock.mock.calls[0][0])).toContain("https://api.example/api/v1/air-quality");
  });

  it("uses fixed assistant error text instead of upstream detail", async () => {
    vi.resetModules();
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ message: "upstream secret", detail: "call 900-xxx" }),
    }) as unknown as typeof fetch;

    const { sendAssistantQuery } = await import("@/components/assistant/assistant-api");
    let caught: unknown;
    try {
      await sendAssistantQuery("hello", 19.076, 72.8777);
    } catch (error) {
      caught = error;
    }

    const message = (caught as Error).message;
    expect(message).toContain("Too many assistant requests");
    expect(message).not.toContain("upstream secret");
    expect(message).not.toContain("900-xxx");
  });
});
