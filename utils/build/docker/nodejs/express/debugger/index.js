'use strict'

const Pii = require('./pii')

module.exports = {
  initRoutes (app) {
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding

    app.get('/debugger/log', (req, res) => {
      res.send('Log probe') // This needs to be line 20
    })

    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding

    app.get('/debugger/pii', (req, res) => {
      const pii = new Pii() // eslint-disable-line no-unused-vars
      res.send('Hello World') // This needs to be line 64
    })
  }
}
