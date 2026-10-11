/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py", "./static/js/**/*.js"],
  safelist: [
    "poster-music","poster-sports","poster-festival","poster-party","poster-tech","poster-campus",
    "poster-business","poster-arts","poster-food","poster-community","poster-outdoor",
    "poster-religious","poster-conference","poster-other",
  ],
  theme: {
    extend: {
      colors: {
        navy: { 950: "#08162B", 900: "#0B1F3A", 800: "#13294B", 700: "#1D3A66", 100: "#E3E9F3" },
        flame: { 600: "#E8470E", 500: "#FF5A1F", 100: "#FFE6DB" },
        paper: { DEFAULT: "#FBF9F6", dark: "#F1EDE7" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
