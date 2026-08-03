import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ops: {
          bg: "#0a0e14",
          panel: "#12161f",
          border: "#232a38",
          amber: "#f2a900",
          teal: "#17a2b8",
          signal: "#e8622c",
        },
      },
      keyframes: {
        "flash-charge": {
          "0%": { backgroundColor: "rgba(23, 161, 184, 0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
        "flash-drain": {
          "0%": { backgroundColor: "rgba(232, 98, 44, 0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        "flash-charge": "flash-charge 500ms ease-out",
        "flash-drain": "flash-drain 500ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
