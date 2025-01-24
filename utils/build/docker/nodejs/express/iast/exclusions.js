'use strict'

const semver = require('semver')
const version = require('dd-trace/package.json').version

if (semver.match(version, '<5.33.0')) {
  const WeakHashAnalyzer = require('dd-trace/packages/dd-trace/src/appsec/iast/analyzers/weak-hash-analyzer.js')
  const original = WeakHashAnalyzer._isExcluded

  WeakHashAnalyzer._isExcluded = function wrappedIsExcluded (location) {
    if (location.path.includes('express-session/index.js')) return true
    else return original.apply(this, arguments)
  }
}
