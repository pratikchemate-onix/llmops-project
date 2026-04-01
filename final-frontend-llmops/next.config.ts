import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  allowedDevOrigins: [
    "localhost",
    "127.0.0.1",
    "172.24.208.1",
  ],
  async rewrites() {
    const backendBase =
      process.env.BACKEND_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://127.0.0.1:8080";

    return [
      {
        source: "/api/backend",
        destination: `${backendBase}/`,
      },
      {
        source: "/api/backend/:path*",
        destination: `${backendBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;