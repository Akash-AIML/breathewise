import { NextRequest, NextResponse } from "next/server";

import {
  ASSISTANT_PROXY_TIMEOUT_MS,
  forwardToBackend,
  isAllowedApiPath,
  safeProxyError,
} from "@/lib/backend-binding";

// Local type instead of Next's generated RouteContext global: CI runs tsc
// before `next build`, so generated route types may not exist yet.
interface ProxyContext {
  params: Promise<{ path: string[] }>;
}

async function proxyToBackend(
  request: NextRequest,
  context: ProxyContext
): Promise<NextResponse> {
  const { path } = await context.params;
  if (!isAllowedApiPath(path)) {
    return safeProxyError(404, "Not found.");
  }

  const isAssistant = path[0] === "assistant" && path[1] === "chat";
  return forwardToBackend(
    request,
    ["api", "v1", ...path],
    isAssistant ? ASSISTANT_PROXY_TIMEOUT_MS : 15000
  );
}

export { proxyToBackend as GET, proxyToBackend as POST };
