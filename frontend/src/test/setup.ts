import "@testing-library/jest-dom";

// Polyfill ResizeObserver for jsdom test environment (used by Recharts ResponsiveContainer)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
