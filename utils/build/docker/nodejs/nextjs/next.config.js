/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disabled because standalone mode does not support using modules directly
  // from node_modules which is necessary when using `npm link dd-trace`.
  // output: 'standalone'
  outputFileTracing: false,
  experimental: {
    // Run out src/instrumentation.js hooks
    instrumentationHook: true
  }
}

module.exports = nextConfig
