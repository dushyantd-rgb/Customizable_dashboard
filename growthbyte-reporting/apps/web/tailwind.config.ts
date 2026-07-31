import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        "growthbyte-amber": "#935600",
        "growthbyte-black": "#0B0B0B",
        "growthbyte-teal": "#009389",
        "growthbyte-white": "#FFFFFF",
      },
    },
  },
  plugins: [],
};

export default config;
