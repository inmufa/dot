import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["next.config.ts", ".next", "node_modules", "out", "next-env.d.ts", "scripts", "shots"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh, "jsx-a11y": jsxA11y },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "max-lines": ["warn", { max: 300, skipBlankLines: true, skipComments: true }],
      "max-lines-per-function": ["warn", { max: 60, skipBlankLines: true }],
      "max-depth": ["warn", 3],
      "max-params": ["warn", 5],
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-confusing-void-expression": ["error", { ignoreArrowShorthand: true, ignoreVoidOperator: true }],
      // Data-loading effects set state by design; scrollable regions must be focusable (axe scrollable-region-focusable).
      "react-hooks/set-state-in-effect": "off",
      "jsx-a11y/no-noninteractive-tabindex": "off",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
    },
  },
  {
    files: ["**/*.tsx"],
    rules: {
      "max-lines-per-function": ["warn", { max: 150, skipBlankLines: true, skipComments: true }],
      "react-refresh/only-export-components": "off",
    },
  },
  { files: ["tests/**"], rules: { "max-lines-per-function": "off" } },
);
