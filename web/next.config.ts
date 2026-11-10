import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  reactStrictMode: true,
  serverExternalPackages: ["pg", "@prisma/client", "@prisma/adapter-pg"],
  experimental: {
    agentUpgrade: "security",
  },
};
export default nextConfig;