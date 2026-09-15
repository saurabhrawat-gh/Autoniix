import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: {
          violet: "#7C3AED",
          "violet-light": "#9B6FF5",
          "violet-dark": "#5B21B6",
          green: "#00D89F",
          "green-dark": "#00A876",
          cyan: "#06B6D4",
          pink: "#EC4899",
        },
      },
      fontFamily: {
        sans: ["var(--font-google-sans)", "Google Sans Flex", "system-ui", "sans-serif"],
        serif: ["var(--font-google-sans)", "Google Sans Flex", "system-ui", "sans-serif"],
        display: ["var(--font-google-sans)", "Google Sans Flex", "system-ui", "sans-serif"],
        hero: ["var(--font-google-sans)", "Google Sans Flex", "system-ui", "sans-serif"],
        cursive: ["var(--font-cattalague)", "Cattalague", "cursive"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
      },
      letterSpacing: {
        tight: "-0.022em",
        tighter: "-0.03em",
      },
      backgroundImage: {
        "glow-green": "radial-gradient(ellipse at center, rgba(0,216,159,0.15) 0%, transparent 70%)",
        "glow-purple": "radial-gradient(ellipse at center, rgba(102,69,193,0.15) 0%, transparent 70%)",
        "glow-blue": "radial-gradient(ellipse at center, rgba(37,99,235,0.12) 0%, transparent 70%)",
        "hero-gradient":
          "linear-gradient(135deg, rgba(0,216,159,0.08) 0%, transparent 50%, rgba(102,69,193,0.08) 100%)",
        "btn-primary": "linear-gradient(135deg, #00D89F 0%, #00A876 100%)",
        "card-glass": "linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)",
      },
      boxShadow: {
        "glow-sm": "0 0 12px rgba(0,216,159,0.25)",
        "glow-md": "0 0 24px rgba(0,216,159,0.20)",
        "glow-lg": "0 0 48px rgba(0,216,159,0.15)",
        card: "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        "card-hover": "0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,216,159,0.2)",
        "purple-glow": "0 0 24px rgba(102,69,193,0.25)",
      },
      animation: {
        "float-slow": "float 8s ease-in-out infinite",
        "float-medium": "float 6s ease-in-out infinite 2s",
        "float-fast": "float 5s ease-in-out infinite 1s",
        "pulse-slow": "pulse 3s ease-in-out infinite",
        marquee: "marquee 30s linear infinite",
        marquee2: "marquee2 30s linear infinite",
        scan: "scan 8s linear infinite",
        blink: "blink 1s step-end infinite",
        "gradient-shift": "gradient-shift 8s ease infinite",
        "mesh-drift-1": "meshDrift1 18s ease-in-out infinite",
        "mesh-drift-2": "meshDrift2 22s ease-in-out infinite 3s",
        "mesh-drift-3": "meshDrift3 26s ease-in-out infinite 7s",
        "wave-flow": "waveFlow 6s ease-in-out infinite",
        "reveal-blur": "revealBlur 0.7s cubic-bezier(0.16,1,0.3,1) forwards",
        "node-pulse": "nodePulse 2.4s ease-in-out infinite",
        "flow-dash": "flowDash 1.8s linear infinite",
        "job-enter": "jobEnter 0.5s cubic-bezier(0.16,1,0.3,1) forwards",
        "shimmer-flow": "shimmerFlow 2.5s linear infinite",
        "border-rotate": "borderRotate 4s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px) scale(1)" },
          "50%": { transform: "translateY(-30px) scale(1.02)" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        marquee2: {
          "0%": { transform: "translateX(50%)" },
          "100%": { transform: "translateX(0%)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(200vh)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        meshDrift1: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)" },
          "33%": { transform: "translate(60px, -40px) scale(1.08)" },
          "66%": { transform: "translate(-30px, 50px) scale(0.95)" },
        },
        meshDrift2: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)" },
          "40%": { transform: "translate(-70px, 30px) scale(1.1)" },
          "70%": { transform: "translate(40px, -60px) scale(0.92)" },
        },
        meshDrift3: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)" },
          "50%": { transform: "translate(50px, 50px) scale(1.05)" },
        },
        waveFlow: {
          "0%, 100%": { transform: "translateX(-5%) scaleY(1)" },
          "50%": { transform: "translateX(5%) scaleY(1.08)" },
        },
        revealBlur: {
          "0%": { opacity: "0", filter: "blur(8px)", transform: "translateY(20px)" },
          "100%": { opacity: "1", filter: "blur(0px)", transform: "translateY(0)" },
        },
        nodePulse: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(0,216,159,0.4)" },
          "50%": { boxShadow: "0 0 0 8px rgba(0,216,159,0)" },
        },
        flowDash: {
          "0%": { strokeDashoffset: "100" },
          "100%": { strokeDashoffset: "0" },
        },
        jobEnter: {
          "0%": { opacity: "0", transform: "translateX(-16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmerFlow: {
          "0%": { backgroundPosition: "-200% center" },
          "100%": { backgroundPosition: "200% center" },
        },
        borderRotate: {
          "0%": { "--border-angle": "0deg" } as Record<string, string>,
          "100%": { "--border-angle": "360deg" } as Record<string, string>,
        },
      },
    },
  },
  plugins: [],
};

export default config;
