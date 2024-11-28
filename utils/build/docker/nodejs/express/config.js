const semver = require('semver')

const expressVersion = require('express/package.json').version

module.exports = {
  graphQLEnabled: semver.lt(expressVersion, '5.0.0'),
  mongoSanitizeEnabled: semver.lt(expressVersion, '5.0.0')
}
