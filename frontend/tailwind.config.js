/** @type {import('tailwindcss').Config} */

// Palette: Vanilla Cream #FFF7E6, Blush Petal #F7C8D3, Rosewood #B46A72,
// Sage Leaf #A8B58A, Misty Sky #A9B7C6, Midnight Lagoon #2D3A47.
// Components use the semantic names (canvas, surface, ink, muted, line) so the
// theme can change here without touching JSX.
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        canvas: "#FFF7E6",
        surface: { DEFAULT: "#FFFDF8", 2: "#FBEEDB" },
        line: { DEFAULT: "#EEDFC6", strong: "#DCC8A8" },
        ink: { DEFAULT: "#2D3A47", soft: "#46535F" },
        muted: "#5F6B77",
        faint: "#6B7480",
        brand: {
          50: "#FCF3F5",
          100: "#FAE6EB",
          200: "#F7C8D3",
          300: "#E8A9B4",
          400: "#CF8791",
          500: "#B46A72",
          600: "#9C5660",
          700: "#82444E",
          800: "#67363E",
          900: "#4B282E",
        },
        sage: {
          100: "#EFF2E7",
          200: "#DCE3CB",
          300: "#C3CDA8",
          400: "#A8B58A",
          500: "#8C9A6D",
          600: "#6E7B52",
          700: "#55603F",
        },
        sky: {
          100: "#EEF2F6",
          200: "#D5DDE6",
          300: "#A9B7C6",
          400: "#8A9BAE",
          500: "#6C7F95",
          600: "#556578",
        },
        lagoon: "#2D3A47",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(45, 58, 71, 0.06), 0 8px 24px rgba(45, 58, 71, 0.06)",
      },
    },
  },
  plugins: [],
};
