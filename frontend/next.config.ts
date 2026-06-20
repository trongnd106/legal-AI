import type { NextConfig } from "next";
import path from "path";

const API_URL = process.env.API_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
  // Tăng timeout proxy lên 120s (chat request có thể mất 60-90s do GraphRAG)
  // Giá trị mặc định quá ngắn gây ECONNRESET khi backend xử lý lâu.
  experimental: {
    proxyTimeout: 120_000,
  },
};

export default nextConfig;
