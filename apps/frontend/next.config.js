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
};

module.exports = nextConfig;
