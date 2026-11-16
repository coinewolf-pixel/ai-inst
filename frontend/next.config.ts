import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: { unoptimized: true },
  output: 'export',
  distDir: 'dist',
};

export default nextConfig;
