import { NextRequest, NextResponse } from "next/server";

import { forwardToBackend } from "@/lib/backend-binding";

export async function GET(request: NextRequest): Promise<NextResponse> {
  return forwardToBackend(request, ["health"], 10000);
}
