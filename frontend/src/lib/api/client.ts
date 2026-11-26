import { z } from "zod";

// Empty default keeps production requests on the deployment origin, where the
// request-time proxy allowlist forwards /api/v1 to the backend. A remote base
// URL is ignored in production so a public NEXT_PUBLIC_* value cannot redirect
// coordinates or household profiles to a third-party host.
const deploymentOrigin =
  typeof window === "undefined" ? "http://localhost" : window.location.origin;
const configuredBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
export const isProduction =
  process.env.NEXT_PUBLIC_APP_ENV === "production" || process.env.NODE_ENV === "production";

/** Resolve candidates against the deployment origin instead of trusting prefixes. */
export function isSameOriginBaseUrl(value: string): boolean {
  if (value === "") return true;
  try {
    return new URL(value, deploymentOrigin).origin === deploymentOrigin;
  } catch {
    return false;
  }
}

const API_BASE_URL = isProduction && !isSameOriginBaseUrl(configuredBaseUrl) ? "" : configuredBaseUrl;

export const REQUEST_TIMEOUT_MS = 15000;
export const ASSISTANT_TIMEOUT_MS = 25000;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  return new URL(`${API_BASE_URL}${path}`, deploymentOrigin).toString();
}

/**
 * Keep the abort deadline active through header receipt and body consumption.
 * The caller checks status and consumes/validates the body inside `consume`.
 */
export async function fetchWithTimeout<T>(
  url: string,
  init: RequestInit,
  consume: (response: Response) => Promise<T>,
  timeoutMs: number = REQUEST_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    return await consume(response);
  } finally {
    clearTimeout(timer);
  }
}

/** Never render raw upstream error text in the UI: it is untrusted content. */
export function safeErrorMessage(fallback: string, status: number): string {
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status >= 500) return `${fallback} The service is temporarily unavailable.`;
  return fallback;
}

/**
 * Validate every JSON response at the boundary. Object schemas are "loose" so
 * unknown backend fields are preserved rather than silently stripped.
 */
export async function parseApiResponse<S extends z.ZodType>(
  response: Response,
  schema: S,
  fallback: string
): Promise<z.output<S>> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(`${fallback} The response was malformed.`, response.status);
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiError(`${fallback} The response was invalid.`, response.status);
  }
  return parsed.data;
}
