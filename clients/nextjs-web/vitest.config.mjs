// Tests run the plain JavaScript logic; JSX files are compiled with React's automatic runtime.
export default {
  esbuild: { jsx: "automatic" },
  test: { include: ["src/**/*.test.js"] },
};
