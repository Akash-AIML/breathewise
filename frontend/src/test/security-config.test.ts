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

  it("ignores a remote public API base URL in production", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_APP_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://attacker.example");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: {} }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { fetchAirQuality } = await import("@/lib/api");
    await fetchAirQuality(19.076, 72.8777);

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/api/v1/air-quality");
    expect(url).not.toContain("attacker.example");
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
