/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // @da/client is our own package in clients/shared: let Next.js compile it.
  transpilePackages: ["@da/client"],
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
