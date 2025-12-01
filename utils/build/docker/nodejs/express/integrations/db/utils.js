const sinon = require('sinon')

let dbmQueryString

function getDbmQueryString () {
  return dbmQueryString
}

function createDBMSpy () {
  const DatabasePlugin = require('dd-trace/packages/dd-trace/src/plugins/database')

  // creates a spy to get the DBM injected query string
  const dbmCommentSpy = sinon.spy(DatabasePlugin.prototype, 'injectDbmQuery')
  DatabasePlugin.prototype.injectDbmQuery = function () {
    const result = dbmCommentSpy.apply(this, arguments)
    dbmQueryString = result
    return result
  }
  return dbmCommentSpy
}

module.exports = {
  createDBMSpy,
  getDbmQueryString
}
