'use strict'

const logHandler = require('./log_handler')

module.exports = {
  initRoutes (app, tracer) {
    app.get('/log', logHandler)
  }
}
