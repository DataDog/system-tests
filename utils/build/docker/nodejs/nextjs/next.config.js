/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disabled because standalone mode does not support using modules directly
  // from node_modules which is necessary when using `npm link dd-trace`.
  // output: 'standalone'
}

module.exports = nextConfig
