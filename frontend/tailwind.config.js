/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#faf7fe",
          100: "#f3eefc",
          200: "#e4d9f7",
          300: "#cbb6f0",
          400: "#b497e8",
          500: "#9b7fde",
          600: "#8266c9",
          700: "#6b52a8",
          800: "#554282",
          900: "#3d2f5e",
        },
        gold: {
          100: "#fdf6e3",
          200: "#f9e8be",
          300: "#f0d48a",
          400: "#e4bc5c",
          500: "#cfa23f",
          600: "#ad842e",
          700: "#8c6a24",
        },
      },
    },
  },
  plugins: [],
};

