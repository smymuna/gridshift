import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactCompiler: true,
  // The API client is a workspace package shipped as TypeScript source.
  transpilePackages: ['@gridshift/api-client'],
}

export default nextConfig
