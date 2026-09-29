/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0F161E", // deep water-navy base, not flat black
          panel: "#161F29",
          raised: "#1C2733",
          line: "rgba(236, 231, 221, 0.08)",
          lineStrong: "rgba(236, 231, 221, 0.16)",
        },
        parchment: {
          DEFAULT: "#ECE7DD", // warm paper text — the "notebook" note
          dim: "#A9A79E",
          faint: "#75746C",
        },
        signal: {
          amber: "#E2A33D", // live / active instrument accent
          amberDim: "#8A6A32",
          teal: "#5FBEA5", // growth / reward / high credibility
          tealDim: "#3E7A6C",
          clay: "#C96E5D", // low credibility / caution, used sparingly
          clayDim: "#8B4C40",
        },
      },
      fontFamily: {
        display: ["\"Source Serif 4\"", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["\"JetBrains Mono\"", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 rgba(236,231,221,0.06) inset, 0 12px 30px -18px rgba(0,0,0,0.6)",
      },
      keyframes: {
        riseIn: {
          "0%": { opacity: 0, transform: "translateY(6px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.35 },
        },
      },
      animation: {
        riseIn: "riseIn 320ms ease-out",
        pulseDot: "pulseDot 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
