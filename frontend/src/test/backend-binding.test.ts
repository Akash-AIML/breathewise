import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET as apiProxy } from "@/app/api/v1/[...path]/route";
import { GET as healthProxy } from "@/app/health/route";
import {
  ASSISTANT_PROXY_TIMEOUT_MS,
  buildBackendUrl,
  forwardToBackend,
  isAllowedApiPath,
} from "@/lib/backend-binding";

describe("Vercel service binding proxy", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("reads the binding at call time and preserves base paths and query strings", () => {
    vi.stubEnv("BACKEND_URL", "https://internal.example/api-base/");
    expect(buildBackendUrl(["air-quality", "nearby"], "?lat=1&lon=2")).toBe(
      "https://internal.example/api-base/air-quality/nearby?lat=1&lon=2"
    );
  });

  it("encodes path segments so IDs cannot break out of the backend path", () => {
    expect(buildBackendUrl(["stations", "grid:cpcb delhi"])).toBe(
      "http://127.0.0.1:8000/stations/grid%3Acpcb%20delhi"
    );
  });

  it("allows only the browser-facing API prefixes", () => {
    expect(isAllowedApiPath(["air-quality", "nearby"])).toBe(true);
    expect(isAllowedApiPath(["assistant", "chat"])).toBe(true);
    expect(isAllowedApiPath(["admin", "debug"])).toBe(false);
    expect(isAllowedApiPath([])).toBe(false);
  });

  it("aborts the assistant proxy before the browser's 25s client timeout", () => {
    expect(ASSISTANT_PROXY_TIMEOUT_MS).toBeLessThan(25_000);
  });

  it("forwards allowlisted headers and response metadata without upstream text", async () => {
    const upstream = new Response('{"success":true}', {
      status: 429,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": "30",
        "Cache-Control": "no-store",
        "X-Internal-Secret": "do-not-forward",
      },
    });
    global.fetch = vi.fn().mockResolvedValue(upstream) as unknown as typeof fetch;

    const request = new NextRequest("http://localhost/api/v1/air-quality?lat=1", {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Forwarded-For": "attacker.example",
        Cookie: "session=secret",
      },
    });
    const response = await forwardToBackend(request, ["air-quality"], 1000);

    expect(response.status).toBe(429);
    expect(response.headers.get("Retry-After")).toBe("30");
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(response.headers.get("X-Internal-Secret")).toBeNull();
    expect(await response.text()).toBe('{"success":true}');

    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/air-quality?lat=1");
    const headers = new Headers(init.headers);
    expect(headers.get("accept")).toBe("application/json");
    expect(headers.get("x-forwarded-for")).toBeNull();
    expect(headers.get("cookie")).toBeNull();
  });

  it("returns a fixed 503 when the binding is missing", async () => {
    vi.stubEnv("BACKEND_URL", "");
    global.fetch = vi.fn() as unknown as typeof fetch;

    const request = new NextRequest("http://localhost/health");
    const response = await healthProxy(request);

    expect(response.status).toBe(503);
    expect((await response.json()).message).toBe("The service is temporarily unavailable.");
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("routes browser API paths to the internal backend through the binding", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response('{"status":"healthy"}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    ) as unknown as typeof fetch;

    const response = await apiProxy(new NextRequest("http://localhost/api/v1/air-quality"), {
      params: Promise.resolve({ path: ["air-quality"] }),
    });

    expect(response.status).toBe(200);
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/v1/air-quality"
    );
  });

  it("rejects unrecognised API prefixes before calling the backend", async () => {
    global.fetch = vi.fn() as unknown as typeof fetch;

    const response = await apiProxy(new NextRequest("http://localhost/api/v1/admin/debug"), {
      params: Promise.resolve({ path: ["admin", "debug"] }),
    });

    expect(response.status).toBe(404);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
