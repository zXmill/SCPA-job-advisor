import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/**/*.{tsx,ts,jsx,js}",
    "./app/**/*.{tsx,ts,jsx,js}",
    "./components/**/*.{tsx,ts,jsx,js}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
} satisfies Config;