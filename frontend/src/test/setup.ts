import "@testing-library/jest-dom";
import "vitest-axe/extend-expect";
import * as matchers from "vitest-axe/matchers";
import { expect } from "vitest";

// Register the vitest-axe matcher (toHaveNoViolations) for all frontend tests.
expect.extend(matchers);

// vitest-axe 0.1.0 augments the legacy `Vi.Assertion` namespace; Vitest 2 uses
// @vitest/expect instead, so add the matching type declaration here.
declare module "@vitest/expect" {
  interface Assertion<T = any> {
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

