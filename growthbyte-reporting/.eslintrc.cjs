module.exports = {
  root: true,
  ignorePatterns: ["**/.next/**", "**/coverage/**", "**/dist/**", "**/node_modules/**"],
  extends: ["eslint:recommended"],
  overrides: [
    {
      files: ["**/*.{ts,tsx}"],
      parser: "@typescript-eslint/parser",
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
      plugins: ["@typescript-eslint"],
      extends: ["plugin:@typescript-eslint/recommended"],
    },
    {
      files: ["**/*.test.{ts,tsx}", "**/jest.setup.ts"],
      env: { jest: true },
    },
  ],
};
