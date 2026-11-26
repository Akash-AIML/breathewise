import { NextRequest, NextResponse } from "next/server";

/**
 * Runtime-only bridge to the internal FastAPI service.
 *
 * On Vercel, `BACKEND_URL` is injected by the service binding declared on the
 * frontend service. It is deliberately read inside request handlers, never at
 * module/build time and never through a NEXT_PUBLIC_* variable.
 */

const ALLOWED_API_PREFIXES = new Set([
  "air-quality",
  "assistant",
  "locations",
  "recommendations",
  "stations",
]);

const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "x-requested-with"];

const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-type",
  "retry-after",
  "x-content-type-options",
];

const UNAVAILABLE_MESSAGE = "The service is temporarily unavailable.";

// The browser aborts assistant requests at 25s. The proxy must finish before
// that so a backend response can still be delivered; the backend's 20s LLM
// budget remains the authoritative provider deadline.
export const ASSISTANT_PROXY_TIMEOUT_MS = 24_000;

export function isAllowedApiPath(segments: string[]): boolean {
  return segments.length > 0 && ALLOWED_API_PREFIXES.has(segments[0]);
}

export function getBackendBaseUrl(): string {
  const value = process.env.BACKEND_URL;
  if (!value) {
    throw new Error("BACKEND_URL is not configured for this service.");
  }
  return value;
}

export function buildBackendUrl(segments: string[], search = ""): string {
  const base = new URL(getBackendBaseUrl());
  base.pathname = `${base.pathname.replace(/\/+$/, "")}/`;
  base.search = "";
  base.hash = "";

  const target = new URL(segments.map((segment) => encodeURIComponent(segment)).join("/"), base);
  if (search) {
    target.search = search;
  }
  return target.toString();
}

export function safeProxyError(status: number, message = UNAVAILABLE_MESSAGE): NextResponse {
  return NextResponse.json(
    { success: false, message },
    { status, headers: { "Cache-Control": "no-store" } }
  );
}

function copyResponseHeaders(upstream: Response): Headers {
  const headers = new Headers();
  headers.set("Cache-Control", "no-store");
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }
  return headers;
}

export async function forwardToBackend(
  request: NextRequest,
  segments: string[],
  timeoutMs = 15000
): Promise<NextResponse> {
  let target: string;
  try {
    target = buildBackendUrl(segments, request.nextUrl.search);
  } catch {
    return safeProxyError(503);
  }

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const init: RequestInit = {
      method: request.method,
      headers,
      redirect: "error",
      signal: controller.signal,
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = await request.arrayBuffer();
    }

    // Never log or return upstream error text: it can contain provider URLs.
    const upstream = await fetch(target, init);
    return new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: copyResponseHeaders(upstream),
    });
  } catch (error) {
    const aborted = error instanceof DOMException && error.name === "AbortError";
    return safeProxyError(aborted ? 504 : 503);
  } finally {
    clearTimeout(timer);
  }
}
