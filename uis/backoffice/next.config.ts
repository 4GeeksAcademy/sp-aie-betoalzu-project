import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backendUrl = (
      process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.BACKEND_URL ||
      ""
    ).replace(/\/$/, "");

    return backendUrl
      ? [{
          source: "/ws/chat/:sessionId",
          destination: `${backendUrl}/ws/chat/:sessionId`,
        }]
      : [];
  },
};

export default nextConfig;
