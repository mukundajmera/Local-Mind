import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: ["class"],
    content: [
        "./pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                // Glassmorphism color palette
                glass: {
                    50: "rgba(255, 255, 255, 0.05)",
                    100: "rgba(255, 255, 255, 0.10)",
                    200: "rgba(255, 255, 255, 0.15)",
                    300: "rgba(255, 255, 255, 0.20)",
                    400: "rgba(255, 255, 255, 0.30)",
                },
                // Cyber accent colors
                cyber: {
                    blue: "#00d4ff",
                    purple: "#a855f7",
                    pink: "#ec4899",
                    green: "#22c55e",
                },
                // Background tones
                surface: {
                    DEFAULT: "rgba(10, 10, 20, 0.95)",
                    elevated: "rgba(20, 20, 35, 0.90)",
                    overlay: "rgba(30, 30, 50, 0.85)",
                },
            },
            backdropBlur: {
                xs: "2px",
                glass: "12px",
                heavy: "24px",
            },
            boxShadow: {
                glass: "0 8px 32px rgba(0, 0, 0, 0.3)",
                "glass-inset": "inset 0 1px 0 rgba(255, 255, 255, 0.1)",
                glow: "0 0 20px rgba(0, 212, 255, 0.3)",
                "glow-purple": "0 0 20px rgba(168, 85, 247, 0.3)",
            },
            borderColor: {
                glass: "rgba(255, 255, 255, 0.1)",
                "glass-bright": "rgba(255, 255, 255, 0.2)",
            },
            animation: {
                "pulse-slow": "pulse 3s ease-in-out infinite",
                "glow-pulse": "glow-pulse 2s ease-in-out infinite",
                "float": "float 6s ease-in-out infinite",
                "gradient-shift": "gradient-shift 8s ease infinite",
            },
            keyframes: {
                "glow-pulse": {
                    "0%, 100%": { opacity: "0.6" },
                    "50%": { opacity: "1" },
                },
                float: {
                    "0%, 100%": { transform: "translateY(0px)" },
                    "50%": { transform: "translateY(-10px)" },
                },
                "gradient-shift": {
                    "0%": { backgroundPosition: "0% 50%" },
                    "50%": { backgroundPosition: "100% 50%" },
                    "100%": { backgroundPosition: "0% 50%" },
                },
            },
            fontFamily: {
                sans: ["Inter", "system-ui", "sans-serif"],
                mono: ["JetBrains Mono", "monospace"],
            },
        },
    },
    plugins: [],
};

export default config;
