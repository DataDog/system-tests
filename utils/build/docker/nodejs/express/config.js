const semver = require('semver')
const expressVersion = require('express/package.json').version

const isExpress4 = semver.lt(expressVersion, '5.0.0')

module.exports = {
  graphQLEnabled: isExpress4,
  mongoSanitizeEnabled: isExpress4,
  unnamedWildcard: isExpress4
}
