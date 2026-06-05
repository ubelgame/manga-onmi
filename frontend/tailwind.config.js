/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
      },
      colors: {
        ink: {
          50:  "#f5f5f0",
          100: "#e8e8e0",
          200: "#c8c8bc",
          300: "#a0a090",
          400: "#707060",
          500: "#505040",
          600: "#3a3a2e",
          700: "#28281e",
          800: "#1a1a12",
          900: "#0e0e08",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "spin-slow": "spin 3s linear infinite",
      },
    },
  },
  plugins: [],
};
