import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  {
    rules: {
      // Enforce strict equality everywhere
      eqeqeq: ["error", "always", { null: "ignore" }],

      // Unused variables: prefix with _ to allow intentional ignores.
      // We use the TypeScript-aware version from the Next.js TS config,
      // but tighten it here: destructured params in interface/type
      // callback signatures that are named-but-unused are covered by
      // the { argsIgnorePattern: "^_" } option.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          vars: "all",
          args: "after-used",
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
          // Named function-type params in interfaces are purely documentary
          destructuredArrayIgnorePattern: "^_",
        },
      ],
      // Keep plain no-unused-vars off to avoid double-reporting with @typescript-eslint
      "no-unused-vars": "off",

      // Ban console.log in production source (allow warn/error)
      "no-console": ["warn", { allow: ["warn", "error"] }],

      // Disallow var
      "no-var": "error",

      // Prefer const
      "prefer-const": "error",
    },
  },
  {
    // Relax rules for test files — they legitimately use patterns that
    // production code should not.
    files: ["src/test/**/*.{ts,tsx}", "**/*.test.{ts,tsx}"],
    rules: {
      "no-console": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
    },
  },
]);

export default eslintConfig;
