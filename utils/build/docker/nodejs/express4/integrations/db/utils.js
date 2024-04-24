const sinon = require('sinon')
const DatabasePlugin = require('dd-trace/packages/dd-trace/src/plugins/database')

let dbmQueryString

function createDBMSpy () {
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
  dbmQueryString
}
