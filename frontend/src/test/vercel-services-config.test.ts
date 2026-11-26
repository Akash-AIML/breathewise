import { describe, expect, it } from "vitest";

const vercelConfig = require("../../../vercel.json");

describe("root Vercel services configuration", () => {
  it("declares one internal backend and one public frontend service", () => {
    expect(Object.keys(vercelConfig.services).sort()).toEqual(["backend", "frontend"]);
    expect(vercelConfig.services.backend.root).toBe("backend");
    expect(vercelConfig.services.backend.framework).toBe("fastapi");
    expect(vercelConfig.services.backend.entrypoint).toBe("app.main:app");
    expect(vercelConfig.services.frontend.root).toBe("frontend");
    expect(vercelConfig.services.frontend.framework).toBe("nextjs");
    expect(vercelConfig.services.frontend.outputDirectory).toBe(".next");
  });

  it("exposes only the frontend and injects the backend binding into it", () => {
    expect(vercelConfig.rewrites).toEqual([
      { source: "/(.*)", destination: { service: "frontend" } },
    ]);
    expect(vercelConfig.services.frontend.bindings).toEqual([
      { type: "service", service: "backend", format: "url", env: "BACKEND_URL" },
    ]);
    expect(vercelConfig.services.backend.bindings).toBeUndefined();
  });

  it("keeps build and runtime keys inside their services", () => {
    for (const key of [
      "buildCommand",
      "installCommand",
      "outputDirectory",
      "framework",
      "functions",
    ]) {
      expect(vercelConfig[key]).toBeUndefined();
    }
    expect(vercelConfig.services.frontend.buildCommand).toBe("npm run build");
    expect(vercelConfig.services.backend.installCommand).toBe(
      "pip install -r requirements.txt"
    );
  });
});
