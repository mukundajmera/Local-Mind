const path = require("path");

const WATCH_IGNORES = [
    "**/node_modules/**",
    "**/.git/**",
    path.resolve(__dirname, "..", "..", "data"),
    path.resolve(__dirname, "..", "..", "logs"),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",

    // Allow images from external sources
    images: {
        remotePatterns: [
            {
                protocol: "http",
                hostname: "localhost",
            },
        ],
    },

    // Experimental features for Next.js 15
    experimental: {
        // Optimize package imports
        optimizePackageImports: ["lucide-react"],
    },

    webpack: (config, { dev }) => {
        if (dev) {
            const pollInterval = Number.parseInt(process.env.WEBPACK_WATCH_POLL ?? "1000", 10);

            config.watchOptions = {
                ...(config.watchOptions ?? {}),
                poll: pollInterval,
                aggregateTimeout: 300,
                ignored: WATCH_IGNORES,
            };
        }

        return config;
    },
};

module.exports = nextConfig;
