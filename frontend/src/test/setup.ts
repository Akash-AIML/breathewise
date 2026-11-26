import "@testing-library/jest-dom/vitest";
import "vitest-axe/extend-expect";
import * as matchers from "vitest-axe/matchers";
import { expect } from "vitest";

// Register the vitest-axe matcher (toHaveNoViolations) for all frontend tests.
expect.extend(matchers);

// vitest-axe 0.1.0 augments the legacy `Vi.Assertion` namespace. Vitest 5
// exposes its matcher types from `vitest`, so declare the matcher there.
declare module "vitest" {
  interface Matchers<
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    R extends void | Promise<void> = void | Promise<void>,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    T = unknown
  > {
    toHaveNoViolations(): void;
  }
}

// Polyfill ResizeObserver for jsdom test environment (used by Recharts ResponsiveContainer)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Polyfill scrollIntoView for jsdom (used by ChatAssistant auto-scroll)
window.HTMLElement.prototype.scrollIntoView = function () {};

