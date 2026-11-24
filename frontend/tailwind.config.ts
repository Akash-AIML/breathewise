import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        emerald: {
          50: "#f0fdf4",
          100: "#dcfce7",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          800: "#065f46",
          900: "#064e3b",
        },
        sage: {
          50: "#f4f6f4",
          100: "#e5eae5",
          200: "#cbd5cb",
          500: "#708c70",
          800: "#324332",
        },
        aqi: {
          good: "#15803d",          // CPCB Good (0-50): Accessible dark green
          satisfactory: "#65a30d",  // CPCB Satisfactory (51-100): Accessible olive-green
          moderate: "#d97706",      // CPCB Moderate (101-200): Accessible amber
          poor: "#ea580c",          // CPCB Poor (201-300): Accessible orange
          verypoor: "#dc2626",      // CPCB Very Poor (301-400): Accessible red
          severe: "#991b1b",        // CPCB Severe (401-500): Accessible dark crimson
        },
      },
    },
  },
  plugins: [],
};
export default config;
